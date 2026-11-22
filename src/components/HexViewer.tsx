import { useEffect, useState } from 'react';
import { ArrowLeft, ArrowRight, CornerDownLeft, Crosshair } from 'lucide-react';
import { api, decodeBase64, hexOffset } from '../services/api';
import type { Chunk, FileRecord } from '../types';
import type { Workspace } from '../hooks/useWorkspace';
import { PanelTitle } from './Chrome';

const PAGE=160;
const printable=(b:number)=>b>=32&&b<=126?String.fromCharCode(b):'.';

export function HexViewer({workspace,file,chunk,offset,onOffset,playheadOffset=null}:{workspace:Workspace;file:FileRecord;chunk:Chunk | null;offset:number;onOffset:(n:number)=>void;playheadOffset?:number|null}) {
  const [bytes,setBytes]=useState<Uint8Array>(new Uint8Array());
  const [jump,setJump]=useState('00000000'); const [loadError,setLoadError]=useState('');
  useEffect(()=>{setJump(offset.toString(16).toUpperCase().padStart(8,'0'));},[offset]);
  useEffect(()=>{
    let live=true; setLoadError('');
    if (workspace.mode==='browser' && workspace.localBytes) { setBytes(workspace.localBytes.slice(offset,offset+PAGE)); return; }
    if (workspace.mode==='backend') api.bytes(file.session_id,file.id,offset,PAGE).then(r=>{if(live)setBytes(decodeBase64(r.data));}).catch(e=>{if(live)setLoadError(e.message);});
    return ()=>{live=false;};
  },[file.id,file.session_id,offset,workspace.localBytes,workspace.mode]);
  const lines=Array.from({length:Math.ceil(bytes.length/16)},(_,i)=>bytes.slice(i*16,i*16+16));
  const go=()=>{const parsed=Number.parseInt(jump.replace(/^0x/i,''),16); if(Number.isFinite(parsed)&&parsed>=0) onOffset(Math.floor(Math.min(parsed,Math.max(0,file.analysis.size-1))/16)*16);};
  const inChunk=(absolute:number)=>!!chunk && absolute>=chunk.offset && absolute<chunk.end;
  const highlightEnd=chunk ? Math.min(chunk.end, offset+bytes.length) : 0;
  return <section className="panel hex-panel">
    <PanelTitle number="04" title="HEX VIEWER" sub="BYTE-LEVEL INSPECTION" action={<div className="panel-actions"><span className="live-indicator"><span className={`status-dot ${playheadOffset!==null?'green':'red'}`}/>{playheadOffset!==null?'PLAYHEAD':'CURSOR'} {hexOffset(playheadOffset??offset)}</span></div>}/>
    <div className="hex-toolbar"><div><Crosshair size={13}/><span>{chunk?`SELECTED: ${chunk.name.trim()}`:'SELECT A STRUCTURE REGION'}</span></div><div className="offset-control"><label htmlFor="hex-offset">OFFSET</label><span>0x</span><input id="hex-offset" value={jump} onChange={e=>setJump(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')go();}} aria-label="Jump to hexadecimal offset"/><button onClick={go} aria-label="Go to offset"><CornerDownLeft size={12}/></button></div></div>
    <div className="hex-scroll">
      <div className="hex-head"><span>OFFSET</span><span className="hex-cols">{Array.from({length:16},(_,i)=><span key={i}>{i.toString(16).toUpperCase().padStart(2,'0')}</span>)}</span><span>ASCII</span></div>
      {loadError ? <div className="hex-error">{loadError}</div> : lines.length ? lines.map((line,row)=><div className="hex-line" key={offset+row*16}>
        <span className="hex-offset">{(offset+row*16).toString(16).toUpperCase().padStart(8,'0')}</span>
        <span className="hex-cols">{Array.from({length:16},(_,col)=>{const byte=line[col];const absolute=offset+row*16+col;const highlighted=byte!==undefined && inChunk(absolute); return <span key={col} className={`${highlighted?'hex-selected':''} ${absolute===playheadOffset?'hex-playhead':''} ${byte===0?'zero-byte':''}`}>{byte===undefined?'--':byte.toString(16).toUpperCase().padStart(2,'0')}</span>;})}</span>
        <span className="hex-ascii">{Array.from(line,(b,col)=>{const absolute=offset+row*16+col;const on=inChunk(absolute);return <span key={col} className={`${on?'ascii-hi':b===0?'ascii-dim':''} ${absolute===playheadOffset?'ascii-playhead':''}`}>{printable(b)}</span>;})}</span>
      </div>) : <div className="hex-error">No bytes at this offset.</div>}
    </div>
    <div className="hex-footer"><span>OFFSET-ALIGNED VIEW <b>/</b> {bytes.length} BYTES LOADED {chunk&&<><b>/</b> {Math.max(0,highlightEnd-chunk.offset)} IN REGION</>}</span><div><button onClick={()=>onOffset(Math.max(0,offset-PAGE))} disabled={offset===0} aria-label="Previous bytes"><ArrowLeft size={12}/></button><span>{hexOffset(offset)}</span><button onClick={()=>onOffset(Math.min(Math.floor(Math.max(0,file.analysis.size-1)/16)*16,offset+PAGE))} disabled={offset+PAGE>=file.analysis.size} aria-label="Next bytes"><ArrowRight size={12}/></button></div></div>
  </section>;
}
