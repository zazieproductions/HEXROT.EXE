"""Observed differences only; a decoder rejection is not a vulnerability."""
from collections import defaultdict


def compare(files: list[dict], runs: list[dict], triage: list[dict]) -> list[dict]:
    by_file = defaultdict(list)
    for run in runs: by_file[run['file_id']].append(run)
    triaged = {t['run_id']:t['result'] for t in triage}
    output = []
    for file in files:
        rows = by_file[file['id']]
        if not rows: continue
        completed = [r for r in rows if not r['result']['canceled'] and not r['result'].get('infrastructure_error')]
        accepted = [r for r in completed if r['result']['accepted'] is True]
        rejected = [r for r in completed if r['result']['accepted'] is False and not r['result']['timed_out'] and not r['result']['abnormal'] and not r['result'].get('resource_exceeded')]
        findings = []
        if accepted and rejected:
            findings.append({'classification':'Parser discrepancy','detail':'At least one decoder accepted this input while another rejected it.'})
        elif rejected and not accepted:
            findings.append({'classification':'Expected rejection','detail':f'{len(rejected)} decoder run(s) rejected this input and none accepted it; rejection alone is not a vulnerability.'})
        for key,title,tolerance in [('channels','channel counts',0),('duration','durations',0.001)]:
            vals = [r['result'][key] for r in accepted if r['result'].get(key) is not None]
            if len(vals)>1 and max(vals)-min(vals)>tolerance:
                findings.append({'classification':'Parser discrepancy','detail':f'Decoders reported different {title}: {sorted(set(vals))}.'})
        hashes = {r['result']['output_sha256'] for r in accepted if r['result'].get('output_sha256')}
        if len(hashes)>1: findings.append({'classification':'Parser discrepancy','detail':'Observed decoded-output hashes differ.'})
        if any(r['result']['timed_out'] or r['result'].get('resource_exceeded') or (r['result'].get('peak_memory_bytes') or 0)>r['result']['limits']['memory_mb']*1024*1024*.8 for r in completed):
            findings.append({'classification':'Resource anomaly','detail':'A run timed out or exceeded 80% of its configured memory limit.'})
        for r in completed:
            if r['result']['abnormal']:
                confirmed = triaged.get(r['id'],{}).get('reproducible',False)
                findings.append({'classification':'Reproducible crash' if confirmed else 'Unconfirmed security concern',
                                 'detail':f"{r['decoder']} terminated by signal {r['result']['signal']}; this is not evidence of exploitability."})
        per_decoder = defaultdict(list)
        for r in completed: per_decoder[(r['job_id'],r['decoder'])].append(r['result'])
        for (_, decoder), results in per_decoder.items():
            signatures = {(r['accepted'],r['exit_code'],r['duration'],r['channels'],r['output_sha256']) for r in results}
            if len(results)>1 and len(signatures)>1:
                findings.append({'classification':'Parser discrepancy','detail':f'{decoder} produced different outcomes across repeated runs.'})
        output.append({'file_id':file['id'],'filename':file['name'],'findings':findings,'runs':rows})
    return output
