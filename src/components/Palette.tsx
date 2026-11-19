import { useEffect, useMemo, useRef, useState } from 'react';
import { Activity, Archive, Braces, FileSearch, FileText, FlaskConical, GitCompareArrows, Radio, Upload } from 'lucide-react';
import { navigation, BrandMark } from './Chrome';
import { logSys } from './Console';
import type { Page } from '../types';
import type { Workspace } from '../hooks/useWorkspace';

interface Command { id:string; group:string; label:string; hint?:string; code?:string; run:()=>void; icon:typeof FileSearch }

export function CommandPalette({open,onClose,workspace,onPage,onImport}:{open:boolean;onClose:()=>void;workspace:Workspace;onPage:(p:Page)=>void;onImport:()=>void}) {
  const [query,setQuery]=useState(''); const [active,setActive]=useState(0);
  const input=useRef<HTMLInputElement>(null);

  const commands:Command[] = useMemo(()=>[
    ...navigation.map(({id,label,icon})=>({ id,group:'navigate',label:`goto ${label.toLowerCase().replace(/\s+/g,'.')}`,hint:label,code:`mod ${String(navigation.findIndex(n=>n.id===id)+1).padStart(2,'0')}`,icon,run:()=>onPage(id) })),
    { id:'import',group:'action',label:'import file into workspace',hint:'open file dialog',code:'import',icon:Upload,run:onImport },
    { id:'sample',group:'action',label:'load reference sample',hint:'fixture / reference.wav',code:'sample',icon:FileSearch,run:()=>void workspace.loadDemo() },
    { id:'reconnect',group:'action',label:'reconnect local engine',hint:workspace.health?'already online':'probe 127.0.0.1:8000',code:'link --up',icon:Activity,run:()=>void workspace.connect(true) },
    { id:'probe',group:'action',label:'probe engine health',hint:'GET /api/health',code:'probe',icon:Activity,run:()=>{logSys(workspace.health?`engine online · isolation ${workspace.health.isolation.available?'ready':'unavailable'}`:'engine unreachable · browser mode');} },
    { id:'mutate',group:'action',label:'generate mutation variants',hint:'mutator defaults · seed 42',code:'mutate --n 5',icon:FlaskConical,run:()=>{onPage('mutator');void workspace.mutate({seed:42,count:5,max_file_size:32*1024*1024,metadata_size:8192,region:'any',strategies:['header_boundary','chunk_length','truncation','signature','trailing']});} },
    { id:'mutate-seeded',group:'action',label:'generate seeded byte mutations',hint:'mutator · seeded_bytes',code:'mutate --seed',icon:FlaskConical,run:()=>{onPage('mutator');void workspace.mutate({seed:1337,count:5,max_file_size:32*1024*1024,metadata_size:8192,region:'any',strategies:['seeded_bytes']});} },
    { id:'decode',group:'action',label:'run decoder tests',hint:workspace.health?.decoders.filter(d=>d.available).map(d=>d.id).join(' ') || 'requires local engine',code:'decode --all',icon:Radio,run:()=>{onPage('decoder');void workspace.runJob({decoders:workspace.health?workspace.health.decoders.filter(d=>d.available).map(d=>d.id):[],timeout_seconds:5,memory_mb:512,repeats:1});} },
    { id:'differential',group:'action',label:'compare decoder observations',hint:'differential matrix',code:'diff --matrix',icon:GitCompareArrows,run:()=>onPage('differential') },
    { id:'crash',group:'action',label:'open crash vault',hint:'abnormal terminations',code:'crash --list',icon:Archive,run:()=>onPage('crash') },
    { id:'export-json',group:'export',label:'export json evidence bundle',hint:'hexrot-evidence.json',code:'export --json',icon:Braces,run:()=>onPage('evidence') },
    { id:'export-md',group:'export',label:'export markdown report',hint:'readable research report',code:'export --md',icon:FileText,run:()=>onPage('evidence') },
  ],[workspace,onPage,onImport]);

  const results = useMemo(()=>{
    const q=query.trim().toLowerCase();
    if(!q) return commands;
    return commands.filter(c=>`${c.label} ${c.hint||''} ${c.code||''} ${c.group}`.toLowerCase().includes(q));
  },[commands,query]);
  const grouped = useMemo(()=>results.map((command,index)=>({ command, index })).filter(({command},i,all)=>i===0||all[i-1].command.group!==command.group),[results]);

  useEffect(()=>{ if(open){ setQuery(''); setActive(0); window.setTimeout(()=>input.current?.focus(),20); } },[open]);
  useEffect(()=>{ setActive(0); },[query]);

  if(!open) return null;
  const choose=(command:Command)=>{ logSys(`exec ${command.code || command.id}`); command.run(); onClose(); };
  const onKey=(event:React.KeyboardEvent)=>{
    if(event.key==='Escape'){ onClose(); return; }
    if(event.key==='ArrowDown'){ event.preventDefault(); setActive(i=>Math.min(i+1,results.length-1)); }
    if(event.key==='ArrowUp'){ event.preventDefault(); setActive(i=>Math.max(i-1,0)); }
    if(event.key==='Enter' && results[active]){ event.preventDefault(); choose(results[active]); }
  };

  return <div className="palette-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)onClose();}}>
    <div className="palette" role="dialog" aria-modal="true" aria-label="Command palette" onKeyDown={onKey}>
      <div className="palette-head">
        <span>›</span>
        <input ref={input} value={query} onChange={e=>setQuery(e.target.value)} placeholder="type a command  ·  goto autopsy  ·  mutate  ·  export" aria-label="Command input" spellCheck={false}/>
        <span className="palette-hint">ESC</span>
      </div>
      <div className="palette-list">
        {results.length ? grouped.map(({command,index:i})=>{
          const Icon=command.icon; const startsGroup=i===0||results[i-1].group!==command.group;
          return <div key={command.id}>
            {startsGroup && <div className="palette-group">{command.group.toUpperCase()}</div>}
            <button className={`palette-item ${i===active?'active':''}`} onMouseEnter={()=>setActive(i)} onClick={()=>choose(command)}>
              <Icon size={13}/><span>{command.label}</span>
              {command.code && <span className="cmd">{command.code}</span>}
              {command.hint && <kbd>{command.hint}</kbd>}
            </button>
          </div>;
        }) : <div className="palette-empty">// no command matches “{query}”</div>}
      </div>
      <div className="palette-foot"><span><b>↑↓</b> navigate <b>·</b> <b>↵</b> execute <b>·</b> <b>esc</b> abort</span><span>authorized research only</span></div>
    </div>
  </div>;
}

export function BootSequence({lines,done,onSkip}:{lines:string[];done:boolean;onSkip:()=>void}) {
  const active=lines.length-1;
  return <div className="boot" onClick={onSkip}>
    <div className="boot-inner">
      <div className="boot-mark"><BrandMark/><div><div className="boot-title">HEXROT<span>.EXE</span></div><div className="boot-tag">LOCAL-FIRST AUDIO FORENSICS TERMINAL · v0.2.0</div></div></div>
      <div className="boot-head"><div className="boot-rule">BOOT SEQUENCE</div><div className="boot-tag">isolation: probe</div></div>
      <div className="boot-lines">
        {lines.map((line,index)=>{
          const [name,status]=line.split('::');
          const pending = index===active && !done;
          return <div className={`boot-line ${index===active&&!done?'current':''}`} key={index}><em>»</em><span>{name}</span><i/><b className={status==='ready'?'':'wait'}>{pending?'····':status}</b></div>;
        })}
      </div>
      <div className="boot-bar"><span>LOAD</span><div className="boot-bar-track"><span style={{width:`${Math.round(lines.length/6*100)}%`}}/></div><span>{String(lines.length).padStart(2,'0')}/06</span></div>
      <div className="boot-hint"><span>press any key to skip</span><span className="boot-state">{done?'AGENT READY':'MOUNTING WORKSPACE'}<b>_</b></span></div>
    </div>
  </div>;
}

