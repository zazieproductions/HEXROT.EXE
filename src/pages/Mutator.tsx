import { ArrowDownToLine, FileSearch, FlaskConical, GitCompareArrows, Search } from 'lucide-react';
import { useEffect, useState } from 'react';
import { PageHeader, PanelTitle } from '../components/Chrome';
import { api, decodeBase64, formatBytes, hexOffset } from '../services/api';
import type { CompareBytes, FileRecord } from '../types';
import type { Workspace } from '../hooks/useWorkspace';

const choices:[string,string][]=[['default','Default cycle: five strategies'],['header_boundary','Header boundary value'],['chunk_length','Chunk length inconsistency'],['truncation','File truncation'],['duplicate_metadata','Duplicate RIFF INFO field'],['metadata_value','Empty / oversized RIFF INFO value'],['invalid_encoding','Invalid ID3 text encoding marker'],['signature','Container signature inconsistency'],['trailing','Seeded trailing bytes'],['chunk_order','Chunk order change'],['seeded_bytes','Seeded byte mutation']];

function ByteComparison({workspace,file}:{workspace:Workspace;file:FileRecord}) {
  const initial=Math.floor((file.mutation?.edits[0]?.offset || 0)/16)*16;
  const [offset,setOffset]=useState(initial); const [data,setData]=useState<CompareBytes|null>(null); const [error,setError]=useState('');
  useEffect(()=>{setOffset(Math.floor((file.mutation?.edits[0]?.offset || 0)/16)*16);},[file.id,file.mutation]);
  useEffect(()=>{let live=true;api.compareBytes(file.session_id,file.id,offset,96).then(x=>{if(live){setData(x);setError('');}}).catch(e=>{if(live)setError(e.message);});return()=>{live=false;};},[file.id,file.session_id,offset]);
  const line=(encoded:string)=>{const bytes=decodeBase64(encoded);return <div className="diff-bytes">{Array.from({length:Math.ceil(bytes.length/16)},(_,row)=><div key={row}><span>{hexOffset(offset+row*16)}</span><code>{Array.from(bytes.slice(row*16,row*16+16),(b,i)=><i className={data?.changed_offsets.includes(offset+row*16+i)?'changed':''} key={i}>{b.toString(16).toUpperCase().padStart(2,'0')} </i>)}</code></div>)}</div>;};
  return <section className="panel compare-panel"><PanelTitle number="03" title="BYTE COMPARISON" sub="OFFSET-ALIGNED" action={<span className="panel-count">{file.name}</span>}/>
    <div className="compare-navigation"><span>Starting offset: <strong>{hexOffset(offset)}</strong></span><div><button className="btn btn-mini" disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-96))}>PREVIOUS</button><button className="btn btn-mini" disabled={offset+96>=Math.max(data?.original_size || 0,data?.mutated_size || 0)} onClick={()=>setOffset(offset+96)}>NEXT</button></div></div>
    {error?<div className="quiet-message">{error}</div>:data&&<div className="diff-grid"><div><h3>ORIGINAL</h3>{line(data.original)}</div><div><h3>MUTATED</h3>{line(data.mutated)}</div></div>}
    <div className="panel-note">Offset-aligned comparison: an insertion or deletion shifts later bytes. Highlighted bytes differ at the same offset.</div>
    <div className="edit-list">{file.mutation?.edits.map((edit,i)=><div key={i}><span>{hexOffset(edit.offset)}</span><strong>{edit.description}</strong><span>{edit.old_length} B <b>&gt;</b> {edit.new_length} B</span></div>)}</div>
    <div className="panel-note">Edits are recorded in execution order. Large before/after values are represented by length, preview, and SHA-256 in evidence exports.</div>
    <span className="sr-only">Comparison loaded from the {workspace.mode} workspace.</span>
  </section>;
}

export function Mutator({workspace,onInspect}:{workspace:Workspace;onInspect:(id:string)=>void}) {
  const [seed,setSeed]=useState(42); const [count,setCount]=useState(5); const [strategy,setStrategy]=useState('default'); const [region,setRegion]=useState('any'); const [limit,setLimit]=useState(32); const [metadataSize,setMetadataSize]=useState(8192); const [query,setQuery]=useState(''); const [compared,setCompared]=useState<FileRecord|null>(null);
  const original=workspace.detail?.files.find(f=>f.kind==='original');
  const files=(workspace.detail?.files || []).filter(f=>f.kind==='mutation' && `${f.name} ${f.mutation?.strategy}`.toLowerCase().includes(query.toLowerCase()));
  const create=()=>workspace.mutate({seed,count,max_file_size:Math.floor(limit*1024*1024),metadata_size:metadataSize,region,strategies:strategy==='default'?['header_boundary','chunk_length','truncation','signature','trailing']:[strategy]});
  return <main className="content"><PageHeader index="03" title="MUTATION ENGINE" description="Generate reproducible malformed test cases from the original file."/>
    <div className="content-rule"><span>AUTHORIZED LOCAL TESTING</span><span className="rule-line"/><span>ORIGINAL IS NEVER MODIFIED</span></div>
    <div className="two-column-layout"><div className="column-stack">
      <section className="panel"><PanelTitle number="01" title="MUTATION CONFIGURATION" sub="DETERMINISTIC"/>
        <div className="form-grid"><label>ORIGINAL INPUT<div className="input-readonly">{original?.name || 'No original file'}</div></label><label>STRATEGY<select value={strategy} onChange={e=>setStrategy(e.target.value)}>{choices.map(([value,label])=><option value={value} key={value}>{label}</option>)}</select></label>
          <label>SEED<input type="number" min="0" max="4294967295" value={seed} onChange={e=>setSeed(Number(e.target.value))}/></label><label>VARIANT COUNT<input type="number" min="1" max="50" value={count} onChange={e=>setCount(Number(e.target.value))}/></label>
          <label>MAX FILE SIZE (MB)<input type="number" min="1" max="32" value={limit} onChange={e=>setLimit(Number(e.target.value))}/></label><label>BYTE MUTATION REGION<select value={region} onChange={e=>setRegion(e.target.value)} disabled={strategy!=='seeded_bytes'}><option value="any">Any structural region</option>{original?.analysis.chunks.map(c=><option value={c.id} key={c.id}>{c.name} / {hexOffset(c.offset)}</option>)}</select></label><label>METADATA VALUE LIMIT (BYTES)<input type="number" min="0" max="65536" value={metadataSize} disabled={strategy!=='metadata_value'} onChange={e=>setMetadataSize(Number(e.target.value))}/></label>
        </div>
        <div className="form-footer"><span>{workspace.health?'Outputs are written to the dedicated local workspace.':'Start the local backend to write mutation files.'}</span><button className="btn btn-primary" disabled={!workspace.health||workspace.mode!=='backend'||workspace.busy||!original} onClick={create}><FlaskConical size={15}/> GENERATE VARIANTS</button></div>
      </section>
      <section className="panel"><PanelTitle number="02" title="GENERATED TEST CASES" sub={`${files.length} VISIBLE`} action={<label className="search-box"><Search size={13}/><input aria-label="Search generated test cases" placeholder="Search cases" value={query} onChange={e=>setQuery(e.target.value)}/></label>}/>
        {files.length?<div className="case-list">{files.map(file=><div className={`case-row ${compared?.id===file.id?'selected':''}`} key={file.id}><div><strong>{file.name}</strong><span>{file.mutation?.strategy.replace(/_/g,' ').toUpperCase()} / SEED {file.mutation?.seed} / {formatBytes(file.analysis.size)}</span></div><button className="icon-btn" title="Inspect file" aria-label={`Inspect ${file.name}`} onClick={()=>onInspect(file.id)}><FileSearch size={16}/></button><button className="icon-btn" title="Compare bytes" aria-label={`Compare ${file.name}`} onClick={()=>setCompared(file)}><GitCompareArrows size={16}/></button><a className="icon-btn" href={api.downloadUrl(file.session_id,file.id)} download title="Download case" aria-label={`Download ${file.name}`}><ArrowDownToLine size={16}/></a></div>)}</div>:<div className="quiet-message">{query?'No test cases match this search.':'No variants have been generated in this session.'}</div>}
      </section>
      {compared && <ByteComparison workspace={workspace} file={compared}/>}
    </div><div className="column-stack"><section className="panel"><PanelTitle title="ENGINE NOTES" sub="SAFE BY DESIGN"/><div className="notes-list"><div><span>01</span><p>Every variant starts from the unchanged original input.</p></div><div><span>02</span><p>The seed, selected strategy, exact edit offsets, and byte hashes are recorded.</p></div><div><span>03</span><p>Format-specific strategies require the corresponding structure. Unsupported combinations return an error.</p></div><div><span>04</span><p>No payload injection or automatic exploitation is performed.</p></div></div></section>
      <div className="research-note"><span>REPRODUCIBILITY</span><p>Use the same original file, seed, strategy, region, and count to reproduce the generated bytes.</p></div></div></div>
  </main>;
}
