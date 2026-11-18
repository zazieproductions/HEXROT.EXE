"""Evidence bundles use JSON as the canonical source for all export formats."""
from __future__ import annotations
import html
import json
import platform
from backend.analysis.differential import compare
from backend.decoders.adapters import inventory
from backend.storage.database import Database, now
from backend.workers.isolation import isolation_status


def bundle(db: Database, session_id: str) -> dict:
    session = db.get_session(session_id)
    if not session: raise KeyError('Session not found')
    files = db.list_files(session_id)
    runs = db.list_runs(session_id)
    triage = db.list_triage(session_id)
    result = {'schema':'hexrot-evidence-v1','exported_at':now(),'session':session,
              'environment':{'platform':platform.system(),'architecture':platform.machine(),'python':platform.python_version(),
                             'isolation':isolation_status(),'decoders':inventory()},
              'files':files,'jobs':db.list_jobs(session_id),'runs':runs,'differential':compare(files,runs,triage),'triage':triage,
              'confidence':{'process_observations':'Directly captured exit status and bounded process output; resource measurements are sampled.',
                            'security_interpretation':'Unconfirmed; observed rejection, discrepancy, or crash does not establish exploitability.'},
              'limitations':['A rejection or crash alone does not establish a vulnerability or exploitability.',
                             'Memory and CPU measurements are sampled; short-lived peaks can be missed.',
                             'Sandbox invocation paths are redacted; reproduce with the same isolation and limits.',
                             'Byte comparisons are offset-aligned; insertions shift later bytes.']}
    # Sanitizes any workspace paths that third-party parser error strings might contain.
    return json.loads(json.dumps(result,ensure_ascii=False).replace(str(db.root),'<WORKSPACE>'))


def render(report: dict, fmt: str) -> tuple[str,str]:
    if fmt == 'json': return json.dumps(report,indent=2,ensure_ascii=False), 'application/json'
    lines = ['# HEXROT.EXE Evidence Report','',f"Exported: {report['exported_at']}",f"Session: {report['session']['name']} ({report['session']['id']})",'',
             '## Environment', f"- Platform: {report['environment']['platform']} / {report['environment']['architecture']}",
             f"- Python: {report['environment']['python']}", f"- Isolation: {report['environment']['isolation']['mechanism']} ({report['environment']['isolation']['reason']})",
             *[f"- {tool['label']}: {tool['version'] or 'not available'}" for tool in report['environment']['decoders']], '', '## File Identification']
    for file in report['files']:
        a = file['analysis']
        lines += ['',f"### {file['name']}",f"- Kind: {file['kind']}",f"- SHA-256: `{a['sha256']}`",f"- Size: {a['size']} bytes",f"- Detected: {a['format']}",
                  f"- Structural warnings: {len(a['warnings'])}"]
        for w in a['warnings']: lines.append(f"  - {w['message']}")
        for metadata in a['metadata']:
            lines.append(f"- Metadata ({metadata['source']}) {metadata['key']}: {metadata['value']}")
        if file['mutation']: lines += ['', 'Mutation history:', '```json',json.dumps(file['mutation'],indent=2),'```']
    lines += ['','## Decoder Observations']
    for run in report['runs']:
        r = run['result']
        lines += ['',f"### {run['decoder']} / file {run['file_id']}",f"- Version: {r['version']}",f"- Invocation: `{json.dumps(r['invocation'])}`",
                  f"- Exit: {r['exit_code']}; accepted: {r['accepted']}; timeout: {r['timed_out']}; canceled: {r['canceled']}",
                  f"- Duration: {r['duration_seconds']} s; peak RSS: {r['peak_memory_bytes']} bytes; CPU: {r['cpu_seconds']} s",
                  f"- Decoded output SHA-256: {r['output_sha256']}", '```text',(r['stderr'] or r['stdout'])[:4096],'```']
    lines += ['', '## Differential Findings']
    for case in report['differential']:
        for finding in case['findings']: lines.append(f"- {case['filename']}: {finding['classification']}: {finding['detail']}")
    lines += ['', '## Crash Triage']
    for item in report['triage']:
        lines += [f"- Run {item['run_id']}: reproducible = {item['result']['reproducible']}", '```json', json.dumps(item['result'],indent=2), '```']
    lines += ['', '## Confidence', *[f'- {key}: {value}' for key,value in report['confidence'].items()],
              '', '## Reproduction And Limits', 'Use the recorded decoder invocation with the recorded input inside the configured sandbox and limits.',
              'The exported JSON contains the full configurations, observations, mutation edits, triage, and environment.',
              *[f'- {x}' for x in report['limitations']]]
    markdown = '\n'.join(lines)+'\n'
    if fmt == 'md': return markdown, 'text/markdown'
    if fmt == 'html':
        return '<!doctype html><html lang="en"><meta charset="utf-8"><title>HEXROT Evidence</title><style>body{max-width:1000px;margin:3rem auto;padding:0 1rem;background:#111;color:#ddd;font:14px/1.6 monospace}pre{white-space:pre-wrap}</style><pre>'+html.escape(markdown)+'</pre></html>', 'text/html'
    raise ValueError('Unknown report format')
