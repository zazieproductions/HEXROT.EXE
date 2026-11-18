import { ArrowDownToLine, ArrowRight, Check, CheckCircle2, ChevronRight, Copy, FileAudio, FileSearch, Fingerprint, FolderOpen, Info, Upload, AlertTriangle } from 'lucide-react';
import { useEffect, useState } from 'react';
import { formatBytes, hexOffset } from '../services/api';
import type { Chunk, Page } from '../types';
import type { Workspace } from '../hooks/useWorkspace';
import { HexViewer } from '../components/HexViewer';
import { PageHeader, PanelTitle } from '../components/Chrome';

const duration=(value:number|null) => value==null?'Not determined':`${Number(value.toFixed(3))} sec`;
const rate=(value:number|null) => value==null?'Not determined':`${value.toLocaleString()} Hz`;

export function Autopsy({workspace,onImport,onPage}:{workspace:Workspace;onImport:()=>void;onPage:(page:Page)=>void}) {
  const file=workspace.selected;
  const [selectedChunk,setSelectedChunk]=useState<Chunk|null>(null);
  const [offset,setOffset]=useState(0);
  const [copied,setCopied]=useState(false);
  useEffect(()=>{setSelectedChunk(file?.analysis.chunks[0] || null);setOffset(0);},[file?.id]);
  if (!file) return <main className="content"><PageHeader index="01" title="FILE AUTOPSY" description="Inspect the anatomy of an audio file."/><div className="loading-state">{workspace.connecting?'Loading the local fixture...':'Import an audio file to begin.'}</div></main>;
  const a=file.analysis;
  const chooseChunk=(chunk:Chunk)=>{setSelectedChunk(chunk);setOffset(Math.floor(chunk.offset/16)*16);};
  const copy=async()=>{try {await navigator.clipboard.writeText(a.sha256);setCopied(true);window.setTimeout(()=>setCopied(false),1600);} catch {workspace.setError('Could not copy the hash to the clipboard.');}};
  const facts=[['Container',a.facts.container],['Encoding',a.facts.codec || 'Not determined'],['Sample rate',rate(a.facts.sample_rate)],['Channels',a.facts.channels==null?'Not determined':`${a.facts.channels} ${a.facts.channels===1?'(mono)':a.facts.channels===2?'(stereo)':''}`],['Bit depth',a.facts.bit_depth==null?'Not determined':`${a.facts.bit_depth}-bit`],['Duration',duration(a.facts.duration)]];
  return <main className="content autopsy-page">
    <PageHeader index="01" title="FILE AUTOPSY" description="Dissect the file. Understand the structure. Find the unexpected." action={<><button className="btn btn-secondary" onClick={workspace.loadDemo} disabled={workspace.busy}><FolderOpen size={15}/> LOAD SAMPLE</button><button className="btn btn-primary" onClick={onImport} disabled={workspace.busy}><Upload size={15}/> IMPORT FILE</button></>}/>
    <div className="content-rule"><span>ANALYSIS WORKSPACE</span><span className="rule-line"/><span>{workspace.mode==='backend'?'PERSISTENT SESSION':'IN-BROWSER SESSION'}</span></div>
    <section className="target-panel panel">
      <div className="target-top"><div><span className="panel-index">01</span><h2>TARGET FILE</h2><span className="panel-sub">CURRENT EVIDENCE</span></div><div className="target-top-right">{(workspace.detail?.files.length || 0)>1 && <label className="file-switcher">INPUT <select aria-label="Select session file" value={file.id} onChange={e=>workspace.setSelectedId(e.target.value)}>{workspace.detail?.files.map(item=><option value={item.id} key={item.id}>{item.name}</option>)}</select></label>}<div className="target-status"><span className="status-dot green"/> FILE INSPECTED <span className="tiny-slash">//</span> {file.kind==='original'?'ORIGINAL':'MUTATION'}</div></div></div>
      <div className="target-body">
        <div className="file-primary"><div className="file-emblem"><FileAudio size={27} strokeWidth={1.35}/><span>FILE</span></div><div className="file-name-group"><div className="file-name">{file.name}</div><div className="file-meta"><span>{a.format} AUDIO</span><i/> <span>{formatBytes(a.size)}</span><i/> <span>{a.size.toLocaleString()} BYTES</span></div></div></div>
        <div className="target-hash"><div className="hash-label"><Fingerprint size={13}/> SHA-256 <span> / COMPUTED</span></div><div className="hash-value" title={a.sha256}>{a.sha256}</div></div>
        <button className="icon-btn copy-hash" onClick={copy} aria-label="Copy SHA-256 hash" title="Copy SHA-256">{copied?<Check size={16}/>:<Copy size={15}/>}</button>
      </div>
      <div className="target-foot"><div><span>MAGIC BYTES</span><strong>{a.magic}</strong></div><div><span>DETECTED FORMAT</span><strong>{a.facts.container}</strong></div><div><span>EXTENSION CHECK</span><strong className={a.extension_mismatch?'warning-text':'good-text'}>{a.format==='Unknown'?'NOT DETERMINED':a.extension_mismatch?'MISMATCH':'MATCH'}</strong></div><button onClick={()=>onPage('metadata')}>VIEW METADATA <ArrowRight size={13}/></button></div>
    </section>
    <div className="autopsy-grid">
      <div className="autopsy-main-column">
        <section className="panel structure-panel">
          <PanelTitle number="02" title="FILE STRUCTURE" sub="CONTAINER MAP" action={<span className="panel-count">{String(a.chunks.length).padStart(2,'0')} REGIONS</span>}/>
          <div className="structure-intro"><div><span className="structure-glyph"><FileSearch size={16}/></span><div><strong>PARSED STRUCTURE</strong><small>Select a region to highlight its bytes below.</small></div></div><span className="structure-format">{a.format} <ChevronRight size={12}/> BINARY</span></div>
          <div className="structure-table">
            <div className="structure-head"><span>CHUNK / REGION</span><span>OFFSET</span><span>DECLARED</span><span>ACTUAL</span><span>STATUS</span><span/></div>
            {a.chunks.map((chunk,i)=><button key={chunk.id} className={`structure-row ${selectedChunk?.id===chunk.id?'selected':''}`} onClick={()=>chooseChunk(chunk)} aria-pressed={selectedChunk?.id===chunk.id}>
              <span className="chunk-name"><span className="tree-mark">{i===a.chunks.length-1?'\\':'+'}</span><b>{chunk.name.trim() || '(blank)'}</b><small>{chunk.kind==='container'?'CONTAINER':chunk.kind==='trailing'?'UNREFERENCED':chunk.kind.toUpperCase()}</small></span><span>{hexOffset(chunk.offset)}</span><span>{chunk.declared_size.toLocaleString()} B</span><span>{chunk.actual_size.toLocaleString()} B</span><span className={chunk.status==='ok'?'row-ok':'row-warning'}><i className={`status-dot ${chunk.status==='ok'?'green':'amber'}`}/>{chunk.status==='ok'?'OK':'WARN'}</span><ChevronRight size={13}/>
            </button>)}
          </div>
          <div className="structure-footer"><span><span className="status-dot red"/> SELECTED REGION HIGHLIGHTED IN HEX VIEW</span><span>OFFSETS ARE FILE-RELATIVE</span></div>
        </section>
        <HexViewer workspace={workspace} file={file} chunk={selectedChunk} offset={offset} onOffset={setOffset}/>
      </div>
      <div className="autopsy-side-column">
        <section className="panel profile-panel">
          <PanelTitle number="04" title="FILE PROFILE" sub="EXTRACTED FACTS"/>
          <div className="profile-list">{facts.map(([label,value])=><div className="profile-row" key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
          <div className="profile-foot"><span><CheckCircle2 size={14}/> {a.format==='Unknown'?'SIGNATURE UNRECOGNIZED':'SIGNATURE IDENTIFIED'}</span><span>{a.format}</span></div>
        </section>
        <section className="panel findings-panel">
          <PanelTitle number="05" title="STRUCTURAL FINDINGS" action={<span className={`finding-count ${a.warnings.length?'has-warnings':''}`}>{String(a.warnings.length).padStart(2,'0')}</span>}/>
          {a.warnings.length ? <div className="finding-list">{a.warnings.slice(0,4).map((warning,i)=><div className="finding-item" key={i}><AlertTriangle size={15}/><div><strong>{warning.severity.toUpperCase()}</strong><p>{warning.message}</p></div></div>)}</div> : <div className="clean-finding"><div className="finding-icon"><Check size={16}/></div><div><strong>NO PARSER WARNINGS</strong><p>No structural warnings were raised by this parser.</p></div></div>}
          <div className="finding-note"><Info size={13}/><span>Observations are not a security verdict.</span></div>
        </section>
        <section className="panel metadata-preview">
          <PanelTitle number="06" title="METADATA" action={<button className="text-link" onClick={()=>onPage('metadata')}>VIEW ALL <ArrowRight size={13}/></button>}/>
          {a.metadata.length ? <div className="metadata-list">{a.metadata.slice(0,3).map((item,i)=><div className="metadata-line" key={i}><span>{item.key}</span><strong title={item.value}>{item.value || '(empty)'}</strong></div>)}</div> : <div className="no-metadata">No text metadata extracted.</div>}
          <div className="metadata-foot"><span>{a.metadata.length} FIELD{a.metadata.length===1?'':'S'} EXTRACTED</span><span>{a.artwork.length} ARTWORK</span></div>
        </section>
        <div className="side-caption"><ArrowDownToLine size={13}/><span>Evidence stays in {workspace.mode==='backend'?'your local workspace':'this browser session'}.</span></div>
      </div>
    </div>
  </main>;
}
