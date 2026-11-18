import { useEffect, useState } from 'react';
import { Search } from 'lucide-react';
import { EmptyState, PageHeader, PanelTitle } from '../components/Chrome';
import type { Workspace } from '../hooks/useWorkspace';
import type { Comparison } from '../types';

export function Differential({workspace}:{workspace:Workspace}) {
  const [query,setQuery]=useState(''); const [selected,setSelected]=useState<Comparison|null>(null);
  const cases=workspace.comparisons.filter(c=>`${c.filename} ${c.findings.map(f=>f.classification+' '+f.detail).join(' ')}`.toLowerCase().includes(query.toLowerCase()));
  useEffect(()=>{if(selected){const fresh=workspace.comparisons.find(c=>c.file_id===selected.file_id);if(fresh)setSelected(fresh);}},[workspace.comparisons]);
  const decoders=Array.from(new Set(workspace.comparisons.flatMap(c=>c.runs.map(r=>r.decoder))));
  return <main className="content"><PageHeader index="05" title="DIFFERENTIAL ANALYSIS" description="Compare what independent decoders actually observed."/>
    <div className="content-rule"><span>OBSERVED RESULTS ONLY</span><span className="rule-line"/><span>NO EXPLOITABILITY CLAIMS</span></div>
    <section className="panel"><PanelTitle number="01" title="COMPARISON MATRIX" sub={`${cases.length} CASES`} action={<label className="search-box"><Search size={13}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search findings" aria-label="Search differential findings"/></label>}/>
      {cases.length?<div className="matrix-scroll"><table className="matrix"><thead><tr><th>TEST CASE</th>{decoders.map(d=><th key={d}>{d.toUpperCase()}</th>)}<th>OBSERVATION</th></tr></thead><tbody>{cases.map(c=><tr key={c.file_id} onClick={()=>setSelected(c)} tabIndex={0} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();setSelected(c);}}} className={selected?.file_id===c.file_id?'selected':''}><td><strong>{c.filename}</strong></td>{decoders.map(d=>{const rows=c.runs.filter(r=>r.decoder===d);return <td key={d}>{rows.length?rows.map(r=>r.result.canceled?'CANCELED':r.result.timed_out?'TIMEOUT':r.result.resource_exceeded?'RESOURCE LIMIT':r.result.infrastructure_error?'SANDBOX ERROR':r.result.abnormal?'SIGNAL':r.result.accepted===null?'UNKNOWN':r.result.accepted?'ACCEPT':'REJECT').join(' / '):'NOT RUN'}</td>;})}<td>{c.findings.length?c.findings.map(f=>f.classification).join(' / '):'No discrepancy observed'}</td></tr>)}</tbody></table></div>:<EmptyState title="No comparisons available" description="Run at least one isolated decoder job to populate this matrix."/>}
    </section>
    {selected&&<section className="panel spaced-panel"><PanelTitle number="02" title="CASE EVIDENCE" sub={selected.filename}/><div className="case-evidence">{selected.findings.length?selected.findings.map((f,i)=><div className="evidence-finding" key={i}><strong>{f.classification.toUpperCase()}</strong><p>{f.detail}</p></div>):<div className="quiet-message">No discrepancy was identified from these observations.</div>}
      {selected.runs.map(r=><details className="run-detail" key={r.id}><summary><span className={`status-dot ${r.result.accepted?'green':'amber'}`}/><strong>{r.decoder}</strong><span>EXIT {r.result.exit_code ?? 'N/A'}</span><span>{r.result.duration_seconds} S</span><span>{r.result.accepted===null?'UNKNOWN':r.result.accepted?'ACCEPTED':'REJECTED'}</span></summary><div className="run-evidence"><div><b>INVOCATION</b><code>{JSON.stringify(r.result.invocation)}</code></div><div><b>INTERPRETATION</b><span>Channels: {r.result.channels ?? 'N/A'} / duration: {r.result.duration ?? 'N/A'} / decoded hash: {r.result.output_sha256 || 'N/A'}</span></div><pre>{r.result.stderr || r.result.stdout || '(no output)'}</pre></div></details>)}
    </div></section>}
    <div className="research-note wide-note"><span>CONFIDENCE</span><p>A discrepancy is an observed difference in behavior. A crash is not proof of memory corruption, code execution, or exploitability.</p></div>
  </main>;
}
