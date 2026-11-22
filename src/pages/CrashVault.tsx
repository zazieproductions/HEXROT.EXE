import { Archive, RefreshCw } from 'lucide-react';
import { EmptyState, PageHeader, PanelTitle } from '../components/Chrome';
import type { Workspace } from '../hooks/useWorkspace';

export function CrashVault({workspace}:{workspace:Workspace}) {
  const crashes=(workspace.detail?.runs || []).filter(run=>run.result.abnormal);
  const latestTriage=(runId:string)=>[...(workspace.detail?.triage || [])].reverse().find(item=>item.run_id===runId);
  return <main className="content"><PageHeader index="06" title="CRASH VAULT" description="Investigate unexpected process termination with preserved evidence."/>
    <div className="content-rule"><span>TRIAGE WORKFLOW</span><span className="rule-line"/><span>CRASH DOES NOT MEAN EXPLOITABLE</span></div>
    <section className="panel"><PanelTitle number="01" title="ABNORMAL TERMINATIONS" sub={`${crashes.length} OBSERVED`} action={<Archive size={15}/>}/>
      {crashes.length?crashes.map(run=>{
        const file=workspace.detail?.files.find(f=>f.id===run.file_id);
        const triage=latestTriage(run.id);
        const minimization=triage?.result.minimization;
        return <div className="crash-entry" key={run.id}><div>
          <strong>{file?.name || run.file_id}</strong>
          <span>{run.decoder} / SIGNAL {run.result.signal} / EXIT {run.result.exit_code}</span>
          <p>{triage?triage.result.reproducible?'Same signal reproduced in both reruns.':'Same signal was not reproduced in both reruns.':'Not yet rerun for reproducibility.'}</p>
          {triage&&<code>{typeof triage.result.reproduction_command==='string'?triage.result.reproduction_command:JSON.stringify(triage.result.reproduction)}</code>}
          {minimization&&<>
            <span>{minimization.skipped?'TRIAGE MINIMIZATION · SKIPPED':`TRIAGE MINIMIZATION · ${minimization.edits_tested ?? 0}/${minimization.edit_count} EDITS TESTED`}</span>
            <p>{minimization.note}</p>
            {!minimization.skipped&&(minimization.critical_edits?.length
              ? minimization.critical_edits.map(edit=><code key={edit.dropped_edit_index}>CANDIDATE EDIT #{edit.dropped_edit_index} · {edit.dropped_edit_description} · REMOVAL STOPPED SIGNAL {minimization.expected_signal}</code>)
              : <p>No single dropped edit stopped the same signal; the crash may require multiple edits.</p>)}
          </>}
        </div><button className="btn btn-secondary" disabled={workspace.busy || !workspace.health} title={!workspace.health?'Requires the local engine':undefined} onClick={()=>workspace.triage(run.id)}><RefreshCw size={14}/> {triage?'RERUN TRIAGE':'TRIAGE CRASH'}</button></div>;
      }):<EmptyState title="No abnormal terminations recorded" description="Only real signal-terminated decoder processes appear here. Rejections and timeouts are not crashes."/>}
    </section>
    <div className="research-note wide-note"><span>TRIAGE METHOD</span><p>Reruns the same input twice, compares it against the original input, and records the executable version, limits, logs, and reproduction arguments. For mutated files it also performs bounded single-edit drop replay (up to 20 edits, only when previews are complete) to flag edits whose removal stops the same signal. It does not claim exploitability or run full delta debugging.</p></div>
  </main>;
}
