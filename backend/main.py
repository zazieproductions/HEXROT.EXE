"""Loopback-only local API for the HEXROT workstation."""
from __future__ import annotations
import base64
import os
import re
import shlex
import tempfile
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from backend.analysis.differential import compare
from backend.config import MAX_FILE_SIZE, MAX_METADATA_VALUE, MAX_MUTATIONS
from backend.decoders.adapters import inventory
from backend.mutation.engine import DEFAULT_STRATEGIES, STRATEGIES, MutationError, generate, generate_batch
from backend.reports.export import bundle, render
from backend.storage.database import Database
from backend.workers.isolation import isolation_status
from backend.workers.jobs import JobManager
from backend.workers.runner import execute

ROOT = Path(__file__).resolve().parents[1]
LOCAL_ORIGIN = r'^https?://(localhost|127\.0\.0\.1|\\[::1\\])(:\\d+)?$'


class RequestSizeLimit:
    """Bound the request before multipart parsing can spool an oversized upload."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('method') != 'POST':
            return await self.app(scope, receive, send)
        limit = MAX_FILE_SIZE + 1024 * 1024 if scope.get('path') == '/api/sessions/upload' else 1024 * 1024
        headers = dict(scope.get('headers', []))
        try:
            declared = int(headers.get(b'content-length', b'0'))
        except ValueError:
            declared = limit + 1
        if declared > limit:
            return await JSONResponse({'detail':'Request exceeds the configured size limit.'}, status_code=413)(scope, receive, send)
        messages = []
        size = 0
        while True:
            message = await receive()
            messages.append(message)
            if message['type'] != 'http.request':
                break
            size += len(message.get('body', b''))
            if size > limit:
                return await JSONResponse({'detail':'Request exceeds the configured size limit.'}, status_code=413)(scope, receive, send)
            if not message.get('more_body', False):
                break
        async def replay():
            return messages.pop(0) if messages else await receive()
        return await self.app(scope, replay, send)


class MutationRequest(BaseModel):
    count: int = Field(default=5,ge=1,le=MAX_MUTATIONS)
    seed: int = Field(default=42,ge=0,le=2**32-1)
    strategies: list[str] = Field(default_factory=lambda: DEFAULT_STRATEGIES.copy(),min_length=1,max_length=16)
    max_file_size: int = Field(default=MAX_FILE_SIZE,ge=1,le=MAX_FILE_SIZE)
    metadata_size: int = Field(default=8192,ge=0,le=MAX_METADATA_VALUE)
    region: str = Field(default='any',max_length=100)
    deduplicate: bool = Field(default=True, description='Skip mutations whose output hash matches a previous result')


class JobRequest(BaseModel):
    file_ids: list[str] = Field(default_factory=list,max_length=51)
    decoders: list[str] = Field(default_factory=lambda:['ffmpeg','ffprobe'],min_length=1,max_length=3)
    timeout_seconds: float = Field(default=5,ge=0.25,le=30)
    memory_mb: int = Field(default=512,ge=128,le=2048)
    repeats: int = Field(default=1,ge=1,le=5)


def _basic_delta_debug(mutated_file: dict, original_file: dict, decoder: str,
                       limits: dict, expected_signal: int | None) -> dict | None:
    """Bounded single-edit-drop triage for a reproducible signal termination.

    Replays the original mutation edits from their stored previews, dropping one
    edit per candidate. This is intentionally narrow: it is not full ddmin, it
    tests only single-edit contributions, and it refuses lossy replay when an
    edit preview was truncated at 128 bytes. A candidate "still crashes" only
    when it is abnormal with the same signal observed in the triaged run.
    """
    mutation = mutated_file.get('mutation') or {}
    edits = mutation.get('edits') or []
    if not edits or expected_signal is None:
        return None
    if len(edits) > 20:
        return {'method': 'single_edit_drop', 'skipped': True, 'edit_count': len(edits),
                'note': 'Too many edits for bounded analysis (limit 20).'}
    if any(edit.get('preview_truncated') for edit in edits):
        return {'method': 'single_edit_drop', 'skipped': True, 'edit_count': len(edits),
                'note': 'Replay refused: an edit preview was truncated at 128 bytes, so rebuilding would be lossy.'}
    original_data = Path(original_file['path']).read_bytes()
    timeout = limits['timeout_seconds']
    memory_mb = limits['memory_mb']
    results = []
    for drop_idx in range(len(edits)):
        candidate = bytearray(original_data)
        valid = True
        for idx, edit in enumerate(edits):
            if idx == drop_idx:
                continue
            try:
                offset = int(edit['offset'])
                old_len = int(edit['old_length'])
                new_bytes = bytes.fromhex(str(edit['after_hex']))
            except (KeyError, TypeError, ValueError):
                valid = False
                break
            if offset < 0 or old_len < 0 or offset + old_len > len(candidate):
                valid = False
                break
            candidate[offset:offset + old_len] = new_bytes
        if not valid:
            results.append({'dropped_edit_index': drop_idx,
                            'dropped_edit_description': edits[drop_idx].get('description', ''),
                            'still_crashes': None, 'exit_code': None, 'signal': None,
                            'note': 'Replay offset was out of bounds for this candidate.'})
            continue
        with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as tmp:
            tmp.write(bytes(candidate))
            tmp_path = Path(tmp.name)
        try:
            result = execute(tmp_path, decoder, timeout, memory_mb)
            results.append({
                'dropped_edit_index': drop_idx,
                'dropped_edit_description': edits[drop_idx].get('description', ''),
                'still_crashes': bool(result.get('abnormal') and result.get('signal') == expected_signal),
                'exit_code': result.get('exit_code'),
                'signal': result.get('signal'),
            })
        finally:
            tmp_path.unlink(missing_ok=True)
    critical = [r for r in results if r['still_crashes'] is False]
    return {
        'method': 'single_edit_drop',
        'edit_count': len(edits),
        'edits_tested': len([r for r in results if r['still_crashes'] is not None]),
        'expected_signal': expected_signal,
        'critical_edits': critical,
        'results': results,
        'note': ('Dropped one edit at a time. An edit is a contributing candidate when removing it '
                 'stops the same signal; this is not proof of exploitability.'),
    }


def create_app(db_root: Path | None = None) -> FastAPI:
    app = FastAPI(title='HEXROT.EXE local API',version='0.2.0')
    db = Database(db_root); jobs = JobManager(db)
    app.state.db = db; app.state.jobs = jobs
    app.add_middleware(CORSMiddleware,allow_origin_regex=LOCAL_ORIGIN,allow_credentials=False,allow_methods=['GET','POST'],allow_headers=['Content-Type'])
    app.add_middleware(RequestSizeLimit)

    @app.middleware('http')
    async def loopback_only(request: Request, call_next):
        host = request.headers.get('host','').split(':')[0].strip('[]').lower()
        if host not in {'127.0.0.1','localhost','testserver',''} and not request.headers.get('host','').startswith('[::1]'):
            return JSONResponse({'detail':'Loopback host required.'},status_code=403)
        if request.client and request.client.host not in {'127.0.0.1','::1','testclient'}:
            return JSONResponse({'detail':'Loopback client required.'},status_code=403)
        origin = request.headers.get('origin')
        if origin and not re.fullmatch(LOCAL_ORIGIN,origin):
            return JSONResponse({'detail':'Non-local browser origin denied.'},status_code=403)
        return await call_next(request)

    def require_session(sid: str) -> dict:
        session = db.get_session(sid)
        if not session: raise HTTPException(404,'Session not found')
        return session

    def require_file(sid: str, fid: str, internal: bool = False) -> dict:
        file = db.get_file(sid,fid,internal)
        if not file: raise HTTPException(404,'File not found')
        return file

    @app.get('/api/health')
    def health():
        return {'status':'online','version':'0.2.0','isolation':isolation_status(),'decoders':inventory(),
                'limits':{'max_file_size':MAX_FILE_SIZE,'max_mutations':MAX_MUTATIONS,'strategies':sorted(STRATEGIES)}}

    @app.get('/api/sessions')
    def sessions(): return db.list_sessions()

    @app.post('/api/sessions/demo')
    def demo():
        path = ROOT/'tests'/'fixtures'/'reference.wav'
        if not path.exists(): raise HTTPException(503,'Fixture missing. Run scripts/generate_fixtures.py.')
        session = db.create_session(path.name)
        file = db.add_file(session['id'],path.name,path.read_bytes(),'original')
        return {'session':session,'file':file}

    @app.post('/api/sessions/upload')
    async def upload(file: UploadFile = File(...)):
        data = bytearray()
        while True:
            chunk = await file.read(1024*1024)
            if not chunk: break
            data.extend(chunk)
            if len(data)>MAX_FILE_SIZE: raise HTTPException(413,f'File exceeds {MAX_FILE_SIZE} bytes')
        if not data: raise HTTPException(400,'Empty files are not accepted')
        session = db.create_session(file.filename or 'upload.bin')
        item = db.add_file(session['id'],file.filename or 'upload.bin',bytes(data),'original')
        return {'session':session,'file':item}

    @app.get('/api/sessions/{sid}')
    def session_detail(sid: str):
        return {'session':require_session(sid),'files':db.list_files(sid),'jobs':db.list_jobs(sid),
                'runs':db.list_runs(sid),'triage':db.list_triage(sid)}

    @app.get('/api/sessions/{sid}/files/{fid}/bytes')
    def bytes_at(sid: str, fid: str, offset: int = Query(0,ge=0), length: int = Query(256,ge=1,le=4096)):
        file = require_file(sid,fid,True)
        with open(file['path'],'rb') as f:
            f.seek(offset); data = f.read(length)
        return {'offset':offset,'length':len(data),'data':base64.b64encode(data).decode('ascii'),'size':file['analysis']['size']}

    @app.get('/api/sessions/{sid}/files/{fid}/compare')
    def bytes_compare(sid: str, fid: str, offset: int = Query(0,ge=0), length: int = Query(256,ge=1,le=4096)):
        file = require_file(sid,fid,True)
        original = next((f for f in db.list_files(sid,True) if f['kind']=='original'),None)
        if not original: raise HTTPException(404,'Original not found')
        with open(original['path'],'rb') as f: f.seek(offset); before=f.read(length)
        with open(file['path'],'rb') as f: f.seek(offset); after=f.read(length)
        return {'offset':offset,'original':base64.b64encode(before).decode(),'mutated':base64.b64encode(after).decode(),
                'original_size':original['analysis']['size'],'mutated_size':file['analysis']['size'],
                'changed_offsets':[offset+i for i in range(max(len(before),len(after))) if before[i:i+1]!=after[i:i+1]],
                'alignment':'offset-aligned'}

    @app.get('/api/sessions/{sid}/files/{fid}/download')
    def download(sid: str, fid: str):
        file = require_file(sid,fid,True)
        return FileResponse(file['path'],media_type='application/octet-stream',filename=file['name'])

    @app.post('/api/sessions/{sid}/mutations')
    def mutations(sid: str, request: MutationRequest):
        require_session(sid)
        unknown = [s for s in request.strategies if s not in STRATEGIES]
        if unknown: raise HTTPException(422,f'Unknown strategies: {unknown}')
        original = next((f for f in db.list_files(sid,True) if f['kind']=='original'),None)
        if not original: raise HTTPException(404,'Original not found')
        data = Path(original['path']).read_bytes()
        if len(data)>request.max_file_size: raise HTTPException(422,'Original exceeds configured size limit')
        outputs = generate_batch(data, original['analysis'], request.count, request.seed,
                                  request.strategies, request.max_file_size, request.region,
                                  request.metadata_size, deduplicate=request.deduplicate)
        stem = Path(original['name']).stem; ext = Path(original['name']).suffix or '.bin'
        files = []
        for i,(out,history) in enumerate(outputs):
            files.append(db.add_file(sid, f'{stem}__s{request.seed}_m{i+1:02d}{ext}', out, 'mutation', history))
        manifest = {
            'session_id': sid, 'seed': request.seed, 'count_requested': request.count,
            'count_generated': len(files), 'deduplicated': request.deduplicate,
            'strategies': request.strategies, 'max_file_size': request.max_file_size,
            'metadata_size': request.metadata_size, 'region': request.region,
            'original_sha256': history['original_sha256'] if history else None,
            'output_hashes': [f['analysis']['sha256'] for f in files],
        }
        return {'files': files, 'manifest': manifest}

    @app.post('/api/sessions/{sid}/jobs')
    def start_job(sid: str, request: JobRequest):
        require_session(sid)
        isolation = isolation_status()
        if not isolation['available']: raise HTTPException(503,f"Decoder execution disabled: {isolation['reason']}")
        available = {x['id'] for x in inventory() if x['available']}
        if any(x not in available for x in request.decoders): raise HTTPException(422,'A selected decoder is unavailable or not allowlisted')
        ids = list(dict.fromkeys(request.file_ids))
        files = [require_file(sid,fid,True) for fid in ids] if ids else db.list_files(sid,True)
        if not files: raise HTTPException(422,'No files selected')
        if len(files)*len(request.decoders)*request.repeats > 300: raise HTTPException(422,'Job exceeds 300 process executions')
        try:
            return jobs.start(sid,files,list(dict.fromkeys(request.decoders)),request.timeout_seconds,request.memory_mb,request.repeats)
        except RuntimeError as exc:
            raise HTTPException(409,str(exc)) from exc

    @app.get('/api/jobs/{job_id}')
    def get_job(job_id: str):
        job = db.get_job(job_id)
        if not job: raise HTTPException(404,'Job not found')
        return {**job,'worker_pid':jobs.current_pid(job_id)}

    @app.post('/api/jobs/{job_id}/cancel')
    def cancel_job(job_id: str):
        if not db.get_job(job_id): raise HTTPException(404,'Job not found')
        if not jobs.cancel(job_id): raise HTTPException(409,'Job is not running')
        return {'status':'cancel_requested'}

    @app.get('/api/sessions/{sid}/differential')
    def differential(sid: str):
        require_session(sid)
        return compare(db.list_files(sid),db.list_runs(sid),db.list_triage(sid))

    @app.post('/api/sessions/{sid}/runs/{run_id}/triage')
    def triage(sid: str,run_id: str):
        require_session(sid)
        run = next((r for r in db.list_runs(sid) if r['id']==run_id),None)
        if not run: raise HTTPException(404,'Run not found')
        if not run['result']['abnormal']: raise HTTPException(422,'Triage requires an observed abnormal signal termination')
        if jobs.has_active(): raise HTTPException(409,'Wait for the active decoder job to finish before triage')
        file = require_file(sid,run['file_id'],True)
        original = next((f for f in db.list_files(sid,True) if f['kind']=='original'),None)
        if not original: raise HTTPException(404,'Original not found')
        limits = run['result']['limits']
        # Reproduce: rerun the suspected crash twice
        repeated = [execute(Path(file['path']),run['decoder'],limits['timeout_seconds'],limits['memory_mb']) for _ in range(2)]
        baseline = execute(Path(original['path']),run['decoder'],limits['timeout_seconds'],limits['memory_mb'])
        reproducible = all(r['abnormal'] and r['signal']==run['result']['signal'] for r in repeated)
        reproduction = [('<INPUT>' if arg in ('/input/audio', file['path']) else arg) for arg in run['result']['invocation']]
        # Basic delta debugging: if the file is a mutation, try to identify which edit matters
        minimization = None
        if reproducible and file.get('mutation') and file['mutation'].get('edits'):
            minimization = _basic_delta_debug(file, original, run['decoder'], limits, run['result'].get('signal'))
        return db.add_triage(sid,run_id,{
            'reproducible':reproducible,
            'original_run':run['result'],
            'repeats':repeated,
            'baseline':baseline,
            'mutation':file['mutation'],
            'reproduction':reproduction,
            'reproduction_command':shlex.join(reproduction),
            'minimization': minimization,
            'note':'A crash is an observation, not proof of memory corruption or code execution.',
            'decoder_version': run['result'].get('version'),
            'exit_status': run['result'].get('exit_code'),
            'signal': run['result'].get('signal'),
            'resource_exceeded': run['result'].get('resource_exceeded'),
            'is_resource_limit': bool(run['result'].get('resource_exceeded')),
        })

    @app.get('/api/sessions/{sid}/report')
    def report(sid: str, format: Literal['json','md','html']='json'):
        require_session(sid)
        content, media = render(bundle(db,sid),format)
        return Response(content,media_type=media,headers={'Content-Disposition':f'attachment; filename="hexrot-evidence.{format}"'})

    return app


app = create_app()
