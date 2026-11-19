import { useEffect, useRef, useState } from 'react';
import { X } from 'lucide-react';
import { ConsoleChip, Sidebar, TopBar } from './components/Chrome';
import { BootSequence, CommandPalette } from './components/Palette';
import { ConsoleDrawer, logErr, logOk, logSys, logWarn, useConsoleLog } from './components/Console';
import { useWorkspace } from './hooks/useWorkspace';
import { Autopsy } from './pages/Autopsy';
import { Metadata } from './pages/Metadata';
import { Mutator } from './pages/Mutator';
import { DecoderLab } from './pages/DecoderLab';
import { Differential } from './pages/Differential';
import { CrashVault } from './pages/CrashVault';
import { Evidence } from './pages/Evidence';
import type { Page } from './types';

const BOOT_STEPS = ['KERNEL MOUNT::ready','WORKSPACE FS::ready','PARSER MATRIX::ready','ISOLATION LAYER::probe','POLICY GATE::ready','AGENT CONSOLE::ready'];

export default function App() {
  const workspace=useWorkspace(); const [page,setPage]=useState<Page>('autopsy'); const input=useRef<HTMLInputElement>(null);
  const [palette,setPalette]=useState(false); const [consoleOpen,setConsoleOpen]=useState(false);
  const [boot,setBoot]=useState(BOOT_STEPS.slice(0,2)); const [booting,setBooting]=useState(true);
  const [clock,setClock]=useState(()=>new Date());
  const entries=useConsoleLog();
  const openFile=()=>input.current?.click();

  /* boot sequence */
  useEffect(()=>{
    if(!booting) return;
    if(boot.length>=BOOT_STEPS.length){ const t=window.setTimeout(()=>setBooting(false),320); return ()=>window.clearTimeout(t); }
    const t=window.setTimeout(()=>setBoot(BOOT_STEPS.slice(0,boot.length+1)),170);
    return ()=>window.clearTimeout(t);
  },[boot,booting]);

  /* any key or tap skips the boot sequence */
  useEffect(()=>{
    if(!booting) return;
    const skip=()=>setBooting(false);
    window.addEventListener('keydown',skip,{once:true});
    window.addEventListener('pointerdown',skip,{once:true});
    return ()=>{ window.removeEventListener('keydown',skip); window.removeEventListener('pointerdown',skip); };
  },[booting]);

  /* clock */
  useEffect(()=>{ const t=window.setInterval(()=>setClock(new Date()),1000); return ()=>window.clearInterval(t); },[]);

  /* global shortcuts */
  useEffect(()=>{
    const onKey=(event:KeyboardEvent)=>{
      const target=event.target as HTMLElement | null;
      const typing=target && (target.tagName==='INPUT'||target.tagName==='SELECT'||target.tagName==='TEXTAREA');
      if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k'){ event.preventDefault(); setPalette(v=>!v); return; }
      if(typing) return;
      if(event.key==='`'){ event.preventDefault(); setConsoleOpen(v=>!v); return; }
      if(event.key==='?'&&!event.metaKey&&!event.ctrlKey){ event.preventDefault(); setPalette(true); }
    };
    window.addEventListener('keydown',onKey);
    return ()=>window.removeEventListener('keydown',onKey);
  },[]);

  /* mirror real workspace state into the console */
  const seen=useRef<string>('');
  useEffect(()=>{
    const signature=JSON.stringify({health:!!workspace.health,mode:workspace.mode,isolation:workspace.health?.isolation.available,error:workspace.error,file:workspace.selected?.id,runs:workspace.detail?.runs.length,jobs:workspace.detail?.jobs.length,mutations:workspace.detail?.files.filter(f=>f.kind==='mutation').length,busy:workspace.busy});
    if(signature===seen.current) return; const first=!seen.current; seen.current=signature;
    if(first){ logSys('console attached · local-first session'); }
    if(workspace.health) logOk(`engine online · isolation ${workspace.health.isolation.available?'ready':'unavailable'} · ${workspace.health.decoders.filter(d=>d.available).length} decoder(s)`);
    else if(!workspace.connecting) logWarn('engine offline · running browser-only preview');
    if(workspace.selected && (!first || workspace.mode==='browser')) logSys(`loaded ${workspace.selected.name} · ${workspace.selected.analysis.format} · ${workspace.selected.analysis.size} bytes`);
    if(workspace.error) logErr(workspace.error);
  },[workspace.health,workspace.mode,workspace.error,workspace.selected,workspace.detail,workspace.busy,workspace.connecting]);

  const clockText=clock.toLocaleTimeString('en-GB',{hour12:false});

  return <div className="app-shell">
    <div className="crt-beam" aria-hidden="true"/>
    <TopBar workspace={workspace} page={page} onPalette={()=>setPalette(true)}/>
    <Sidebar workspace={workspace} page={page} onPage={setPage} onImport={openFile}/>
    <input ref={input} className="sr-only" type="file" accept=".wav,.wave,.aiff,.aif,.aifc,.flac,.mp3,audio/*" onChange={e=>{const file=e.currentTarget.files?.[0];if(file){void workspace.importFile(file);setPage('autopsy');}e.currentTarget.value='';}}/>
    {workspace.error&&<div className="error-banner" role="alert"><span>{workspace.error}</span><button onClick={()=>workspace.setError('')} aria-label="Dismiss error"><X size={13}/></button></div>}
    <div className="main-area">
      {page==='autopsy'&&<Autopsy workspace={workspace} onImport={openFile} onPage={setPage}/>}
      {page==='metadata'&&<Metadata workspace={workspace}/>}
      {page==='mutator'&&<Mutator workspace={workspace} onInspect={id=>{workspace.setSelectedId(id);setPage('autopsy');}}/>}
      {page==='decoder'&&<DecoderLab workspace={workspace}/>}
      {page==='differential'&&<Differential workspace={workspace}/>}
      {page==='crash'&&<CrashVault workspace={workspace}/>}
      {page==='evidence'&&<Evidence workspace={workspace}/>}
    </div>
    <ConsoleDrawer open={consoleOpen} onClose={()=>setConsoleOpen(false)}/>
    <footer className="status-bar">
      <div>
        <span className={`status-dot ${workspace.health?'green':'amber'}`}/>
        <strong>{workspace.health?'LINK::ESTABLISHED':workspace.mode==='backend'?'LINK::LOST':'LINK::LOCAL-BROWSER'}</strong>
        <span className="status-divider"/>
        <span>{workspace.mode==='backend'?'TTY /dev/hexrot0':'PREVIEW · NO PERSISTENCE'}</span>
        <span className="status-divider"/>
        <span className="status-clock">{clockText}</span>
      </div>
      <div>
        <ConsoleChip open={consoleOpen} onToggle={()=>setConsoleOpen(v=>!v)} count={entries.length}/>
        <span className="status-divider"/>
        <span>HEXROT.EXE <b>/</b> CORRUPT THE FORMAT · EXPOSE THE FAULT</span>
        <span className="status-divider"/>
        <span>AUTHORIZED RESEARCH ONLY</span>
      </div>
    </footer>
    <CommandPalette open={palette} onClose={()=>setPalette(false)} workspace={workspace} onPage={setPage} onImport={openFile}/>
    {booting&&<BootSequence lines={boot} done={boot.length>=BOOT_STEPS.length} onSkip={()=>setBooting(false)}/>}
  </div>;
}
