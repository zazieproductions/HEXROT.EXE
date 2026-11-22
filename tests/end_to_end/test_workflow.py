import asyncio
import base64
import hashlib
import os
import time
import httpx
from pathlib import Path
import psutil
import pytest
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.workers.isolation import isolation_status
from backend.decoders.adapters import inventory

FIX = Path(__file__).parents[1]/'fixtures'/'reference.wav'


def wait_job(client, job_id, timeout=30):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        job=client.get(f'/api/jobs/{job_id}').json()
        if job['status'] not in ('queued','running'): return job
        time.sleep(.03)
    raise AssertionError('Job did not finish')


def test_full_persistent_research_workflow(tmp_path):
    app=create_app(tmp_path); client=TestClient(app)
    original=FIX.read_bytes()
    response=client.post('/api/sessions/upload',files={'file':('reference.wav',original,'audio/wav')})
    assert response.status_code==200
    data=response.json(); sid=data['session']['id']; fid=data['file']['id']; a=data['file']['analysis']
    assert a['sha256']==hashlib.sha256(original).hexdigest()
    assert [c['name'] for c in a['chunks']]==['RIFF','fmt ','LIST','data'] and len(a['metadata'])==3
    response=client.post(f'/api/sessions/{sid}/mutations',json={'count':5,'seed':42})
    assert response.status_code==200
    mutation_response = response.json()
    variants=mutation_response['files']; assert len(variants)==5
    # Verify manifest is included
    assert 'manifest' in mutation_response
    manifest = mutation_response['manifest']
    assert manifest['count_generated'] == 5
    assert manifest['seed'] == 42
    assert manifest['original_sha256'] == a['sha256']
    for variant in variants:
        internal=app.state.db.get_file(sid,variant['id'],True)
        assert Path(internal['path']).exists() and Path(internal['path']).read_bytes()!=original
        assert variant['mutation']['edits']
        # v0.2.0: mutation history includes reproduction inputs
        assert 'reproduction_inputs' in variant['mutation']
    compare=client.get(f"/api/sessions/{sid}/files/{variants[0]['id']}/compare?offset=0&length=64").json()
    assert compare['changed_offsets'] and base64.b64decode(compare['original'])==original[:64]
    available=[x['id'] for x in inventory() if x['available'] and x['id'] in ('ffmpeg','sndfile-info')]
    if isolation_status()['available'] and available:
        job=client.post(f'/api/sessions/{sid}/jobs',json={'decoders':available,'timeout_seconds':5}).json()
        finished=wait_job(client,job['id']); assert finished['status']=='completed' and finished['completed']==6*len(available)
        detail=client.get(f'/api/sessions/{sid}').json(); assert len(detail['runs'])==finished['completed']
        assert all(r['result']['infrastructure_error'] is None for r in detail['runs'])
        assert len(client.get(f'/api/sessions/{sid}/differential').json())==6
    report=client.get(f'/api/sessions/{sid}/report?format=json').json()
    assert report['files'][0]['analysis']['sha256']==a['sha256'] and str(tmp_path) not in str(report)
    assert 'Environment' in client.get(f'/api/sessions/{sid}/report?format=md').text
    assert '&lt;' not in client.get(f'/api/sessions/{sid}/report?format=html').text[:15]
    reopened=TestClient(create_app(tmp_path)).get(f'/api/sessions/{sid}').json()
    assert len(reopened['files'])==6 and reopened['files'][0]['id']==fid
    if isolation_status()['available'] and available: assert len(reopened['runs'])==6*len(available)


def test_cancel_stops_actual_decoder_worker(tmp_path):
    if not isolation_status()['available'] or not any(x['id']=='ffmpeg' and x['available'] for x in inventory()): pytest.skip('ffmpeg or isolation unavailable')
    client=TestClient(create_app(tmp_path))
    sid=client.post('/api/sessions/demo').json()['session']['id']
    client.post(f'/api/sessions/{sid}/mutations',json={'count':15,'seed':9})
    job=client.post(f'/api/sessions/{sid}/jobs',json={'decoders':['ffmpeg'],'repeats':5}).json()
    worker=None; deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        snapshot=client.get(f"/api/jobs/{job['id']}").json()
        if snapshot.get('worker_pid'):
            worker=snapshot['worker_pid'];break
        time.sleep(.005)
    assert worker is not None, 'No actual decoder worker was observed'
    assert client.post(f"/api/jobs/{job['id']}/cancel").status_code==200
    result=wait_job(client,job['id']); assert result['status']=='canceled' and result['completed']<result['total']
    deadline=time.monotonic()+3
    while psutil.pid_exists(worker) and time.monotonic()<deadline: time.sleep(.02)
    assert not psutil.pid_exists(worker), f'Worker {worker} still exists after cancellation'
    runs=client.get(f'/api/sessions/{sid}').json()['runs']
    assert any(r['result']['canceled'] for r in runs)


def test_local_origin_and_path_safety(tmp_path):
    client=TestClient(create_app(tmp_path))
    assert client.get('/api/health',headers={'host':'evil.example'}).status_code==403
    assert client.post('/api/sessions/demo',headers={'origin':'https://evil.example'}).status_code==403
    local=client.get('/api/health',headers={'origin':'http://localhost:5173'})
    assert local.status_code==200 and local.headers['access-control-allow-origin']=='http://localhost:5173'
    response=client.post('/api/sessions/upload',files={'file':('../../outside.wav',FIX.read_bytes(),'audio/wav')})
    assert response.status_code==200 and response.json()['file']['name']=='outside.wav'
    assert not (tmp_path.parent/'outside.wav').exists()


def test_decoder_execution_disabled_without_isolation(tmp_path, monkeypatch):
    import backend.main as main
    client=TestClient(create_app(tmp_path))
    sid=client.post('/api/sessions/demo').json()['session']['id']
    monkeypatch.setattr(main,'isolation_status',lambda:{'available':False,'mechanism':'none','reason':'self-test failed'})
    response=client.post(f'/api/sessions/{sid}/jobs',json={'decoders':['ffmpeg']})
    assert response.status_code==503 and 'disabled' in response.json()['detail'].lower()
    assert client.get(f'/api/sessions/{sid}').json()['runs']==[]


def test_request_limit_rejects_oversized_content_length(tmp_path):
    client=TestClient(create_app(tmp_path))
    response=client.post('/api/sessions/demo',content=b'x',headers={'content-length':str(2*1024*1024)})
    assert response.status_code==413


def test_upload_streams_file_larger_than_previous_32_mib_limit(tmp_path):
    app=create_app(tmp_path)
    size=32*1024*1024+1
    boundary='HEXROT-STREAM-TEST'
    prefix=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="large.bin"\r\n'
            'Content-Type: application/octet-stream\r\n\r\n').encode()
    suffix=f'\r\n--{boundary}--\r\n'.encode()
    block=bytes(1024*1024)

    async def body():
        yield prefix
        for _ in range(size//len(block)):
            yield block
        remainder=size%len(block)
        if remainder:
            yield bytes(remainder)
        yield suffix

    async def upload():
        transport=httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport,base_url='http://testserver') as client:
            return await client.post('/api/sessions/upload',content=body(),
                                     headers={'content-type':f'multipart/form-data; boundary={boundary}'})

    response=asyncio.run(upload())
    assert response.status_code==200, response.text
    analysis=response.json()['file']['analysis']
    expected=hashlib.sha256()
    for _ in range(size//len(block)):
        expected.update(block)
    expected.update(bytes(size%len(block)))
    assert analysis['size']==size and analysis['sha256']==expected.hexdigest()


def test_media_route_supports_byte_ranges(tmp_path):
    client=TestClient(create_app(tmp_path))
    created=client.post('/api/sessions/demo').json()
    sid=created['session']['id']; fid=created['file']['id']; original=FIX.read_bytes()
    response=client.get(f'/api/sessions/{sid}/files/{fid}/media',headers={'range':'bytes=8-23','origin':'http://localhost:5173'})
    assert response.status_code==206
    assert response.headers['content-range']==f'bytes 8-23/{len(original)}'
    assert response.headers['accept-ranges']=='bytes'
    assert response.headers['access-control-allow-origin']=='http://localhost:5173'
    assert response.headers['content-type'].startswith('audio/')
    assert response.content==original[8:24]
    assert client.get(f'/api/sessions/{sid}/files/{fid}/media',headers={'range':'bytes=999999-'}).status_code==416


def test_html_report_escapes_file_metadata(tmp_path):
    client=TestClient(create_app(tmp_path))
    data=FIX.read_bytes().replace(b'HEXROT reference',b'<script>alert(1)')
    sid=client.post('/api/sessions/upload',files={'file':('text.wav',data,'audio/wav')}).json()['session']['id']
    report=client.get(f'/api/sessions/{sid}/report?format=html').text
    assert '&lt;script&gt;alert(1)' in report and '<script>alert(1)' not in report


# --- v0.2.0 API contract tests ---

def test_health_returns_version_and_strategies(tmp_path):
    client = TestClient(create_app(tmp_path))
    health = client.get('/api/health').json()
    assert health['version'] == '0.2.0'
    assert health['limits']['max_file_size'] is None
    assert 'strategies' in health['limits']
    assert 'boundary_min' in health['limits']['strategies']
    assert 'header_boundary' in health['limits']['strategies']


def test_mutation_endpoint_returns_manifest(tmp_path):
    client = TestClient(create_app(tmp_path))
    sid = client.post('/api/sessions/demo').json()['session']['id']
    response = client.post(f'/api/sessions/{sid}/mutations', json={
        'count': 3, 'seed': 7, 'strategies': ['header_boundary', 'truncation'],
        'deduplicate': True
    })
    assert response.status_code == 200
    body = response.json()
    assert 'files' in body and 'manifest' in body
    manifest = body['manifest']
    assert manifest['seed'] == 7
    assert manifest['count_requested'] == 3
    assert manifest['deduplicated'] is True
    assert manifest['original_sha256']


def test_mutation_deduplication_skips_duplicates(tmp_path):
    """When deduplicate=True, identical outputs should be skipped."""
    client = TestClient(create_app(tmp_path))
    sid = client.post('/api/sessions/demo').json()['session']['id']
    # 'signature' always produces the same output (replaces first 4 bytes with 'XROT')
    response = client.post(f'/api/sessions/{sid}/mutations', json={
        'count': 5, 'seed': 1, 'strategies': ['signature'], 'deduplicate': True
    })
    assert response.status_code == 200
    body = response.json()
    # All 5 attempts produce the same hash; only 1 survives dedup
    assert len(body['files']) == 1
    assert body['manifest']['count_generated'] == 1


def test_mutation_no_deduplication_returns_all(tmp_path):
    """When deduplicate=False, all mutations are returned even if identical."""
    client = TestClient(create_app(tmp_path))
    sid = client.post('/api/sessions/demo').json()['session']['id']
    response = client.post(f'/api/sessions/{sid}/mutations', json={
        'count': 3, 'seed': 1, 'strategies': ['signature'], 'deduplicate': False
    })
    assert response.status_code == 200
    body = response.json()
    assert len(body['files']) == 3


def test_mutation_history_has_reproduction_data(tmp_path):
    """Each mutation's history must contain reproduction_inputs for replay."""
    client = TestClient(create_app(tmp_path))
    sid = client.post('/api/sessions/demo').json()['session']['id']
    response = client.post(f'/api/sessions/{sid}/mutations', json={
        'count': 1, 'seed': 42, 'strategies': ['header_boundary']
    })
    body = response.json()
    file = body['files'][0]
    mutation = file['mutation']
    assert 'reproduction_inputs' in mutation
    ri = mutation['reproduction_inputs']
    assert ri['seed'] == 42
    assert ri['strategy'] == 'header_boundary'
    assert ri['original_sha256'] == mutation['original_sha256']


def test_unknown_strategy_returns_422(tmp_path):
    client = TestClient(create_app(tmp_path))
    sid = client.post('/api/sessions/demo').json()['session']['id']
    response = client.post(f'/api/sessions/{sid}/mutations', json={
        'count': 1, 'strategies': ['nonexistent_strategy']
    })
    assert response.status_code == 422


def test_boundary_strategies_via_api(tmp_path):
    """New boundary strategies should work through the API."""
    client = TestClient(create_app(tmp_path))
    sid = client.post('/api/sessions/demo').json()['session']['id']
    for strategy in ['boundary_min', 'boundary_max', 'boundary_off_by_one', 'zero_length_field', 'negative_duration']:
        response = client.post(f'/api/sessions/{sid}/mutations', json={
            'count': 1, 'seed': 1, 'strategies': [strategy]
        })
        assert response.status_code == 200, f'{strategy} failed: {response.text}'
        body = response.json()
        assert len(body['files']) == 1
        assert body['files'][0]['mutation']['strategy'] == strategy
