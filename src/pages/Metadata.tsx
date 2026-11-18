import { AlertTriangle, Image, Search } from 'lucide-react';
import { useEffect, useState } from 'react';
import { PageHeader, PanelTitle, EmptyState } from '../components/Chrome';
import { HexViewer } from '../components/HexViewer';
import { formatBytes, hexOffset } from '../services/api';
import type { Chunk, MetadataField } from '../types';
import type { Workspace } from '../hooks/useWorkspace';

export function Metadata({workspace}:{workspace:Workspace}) {
  const file=workspace.selected; const [query,setQuery]=useState(''); const [field,setField]=useState<MetadataField|null>(null); const [offset,setOffset]=useState(0);
  useEffect(()=>{setField(null);setOffset(0);},[file?.id]);
  if (!file) return <main className="content"><PageHeader index="02" title="METADATA FORENSICS" description="Examine embedded fields without executing their content."/><EmptyState title="No file selected" description="Import a file to inspect its metadata."/></main>;
  const a=file.analysis; const fields=a.metadata.filter(x=>`${x.key} ${x.value} ${x.source}`.toLowerCase().includes(query.toLowerCase()));
  const select=(item:MetadataField)=>{setField(item);if(item.offset!==null)setOffset(Math.floor(item.offset/16)*16);};
  const chunk:Chunk|null=field?.offset!=null?{id:'metadata',name:field.key,offset:field.offset,end:field.offset+field.byte_length,declared_size:field.byte_length,actual_size:field.byte_length,kind:'metadata',status:'ok',detail:''}:null;
  return <main className="content">
    <PageHeader index="02" title="METADATA FORENSICS" description="Inspect embedded tags, artwork, and text-level anomalies."/>
    <div className="content-rule"><span>EXTRACTED FROM {file.name.toUpperCase()}</span><span className="rule-line"/><span>FACTS + HEURISTICS</span></div>
    <div className="two-column-layout"><div className="column-stack">
      <section className="panel"><PanelTitle number="01" title="EXTRACTED FIELDS" sub={`${a.metadata.length} FIELD${a.metadata.length===1?'':'S'}`} action={<label className="search-box"><Search size={13}/><input placeholder="Search metadata" value={query} onChange={e=>setQuery(e.target.value)} aria-label="Search metadata"/></label>}/>
        <div className="data-table metadata-table"><div className="data-head"><span>FIELD</span><span>VALUE</span><span>SOURCE</span><span>OFFSET</span></div>
          {fields.map((item,i)=><button className={`data-row metadata-row ${field===item?'selected':''}`} key={`${item.source}-${item.key}-${i}`} onClick={()=>select(item)}><strong>{item.key}</strong><span title={item.value}>{item.value || '(empty)'}</span><span>{item.source}</span><span>{item.offset===null?'N/A':hexOffset(item.offset)}</span></button>)}
          {!fields.length && <div className="table-empty">{query?'No fields match this search.':'No text fields were extracted.'}</div>}
        </div>
        <div className="panel-note">Select a field with a known offset to inspect its original bytes.</div>
      </section>
      <HexViewer workspace={workspace} file={file} chunk={chunk} offset={offset} onOffset={setOffset}/>
    </div><div className="column-stack">
      <section className="panel"><PanelTitle number="02" title="HEURISTIC REVIEW" sub="INTERPRETATIONS" action={<span className="panel-count">{a.heuristics.length} SIGNALS</span>}/>
        {a.heuristics.length?<div className="finding-list">{a.heuristics.map((h,i)=><div className="finding-item" key={i}><AlertTriangle size={15}/><div><strong>{h.kind.toUpperCase()}</strong><p>{h.detail}</p></div></div>)}</div>:<div className="quiet-message">No metadata heuristics were triggered.</div>}
        <div className="finding-note">Heuristics are not verified security findings.</div>
      </section>
      <section className="panel"><PanelTitle number="03" title="EMBEDDED ARTWORK" sub="NOT EXECUTED"/><div className="artwork-list">{a.artwork.length?a.artwork.map((image,i)=><div className="artwork-item" key={i}><Image size={18}/><div><strong>{image.mime}</strong><span>{image.source} / {formatBytes(image.byte_length)}</span><code>{image.sha256}</code></div></div>):<div className="quiet-message">No embedded artwork was extracted.</div>}</div></section>
      <div className="research-note"><span>METHOD NOTE</span><p>Text values and byte offsets are extracted from the file. URL, path, encoding, and size checks are heuristic observations; links are never opened.</p></div>
    </div></div>
  </main>;
}
