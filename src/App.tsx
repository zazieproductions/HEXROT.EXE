import { useRef, useState } from 'react';
import { X } from 'lucide-react';
import { Sidebar, TopBar } from './components/Chrome';
import { useWorkspace } from './hooks/useWorkspace';
import { Autopsy } from './pages/Autopsy';
import { Metadata } from './pages/Metadata';
import { Mutator } from './pages/Mutator';
import { DecoderLab } from './pages/DecoderLab';
import { Differential } from './pages/Differential';
import { CrashVault } from './pages/CrashVault';
import { Evidence } from './pages/Evidence';
import type { Page } from './types';

export default function App() {
  const workspace=useWorkspace(); const [page,setPage]=useState<Page>('autopsy'); const input=useRef<HTMLInputElement>(null);
  const openFile=()=>input.current?.click();
  return <div className="app-shell">
    <TopBar workspace={workspace} page={page}/>
    <Sidebar workspace={workspace} page={page} onPage={setPage} onImport={openFile}/>
    <input ref={input} className="sr-only" type="file" accept=".wav,.wave,.aiff,.aif,.aifc,.flac,.mp3,audio/*" onChange={e=>{const file=e.currentTarget.files?.[0];if(file){void workspace.importFile(file);setPage('autopsy');}e.currentTarget.value='';}}/>
    {workspace.error&&<div className="error-banner" role="alert"><span>{workspace.error}</span><button onClick={()=>workspace.setError('')} aria-label="Dismiss error"><X size={15}/></button></div>}
    <div className="main-area">
      {page==='autopsy'&&<Autopsy workspace={workspace} onImport={openFile} onPage={setPage}/>}
      {page==='metadata'&&<Metadata workspace={workspace}/>}
      {page==='mutator'&&<Mutator workspace={workspace} onInspect={id=>{workspace.setSelectedId(id);setPage('autopsy');}}/>}
      {page==='decoder'&&<DecoderLab workspace={workspace}/>}
      {page==='differential'&&<Differential workspace={workspace}/>}
      {page==='crash'&&<CrashVault workspace={workspace}/>}
      {page==='evidence'&&<Evidence workspace={workspace}/>}
    </div>
    <footer className="status-bar"><div><span className={`status-dot ${workspace.health?'green':'amber'}`}/><strong>{workspace.health?'LOCAL ENGINE CONNECTED':workspace.mode==='backend'?'LOCAL ENGINE OFFLINE':'BROWSER-ONLY PREVIEW'}</strong><span className="status-divider"/><span>{workspace.mode==='backend'?'SESSION PERSISTED':'START BACKEND FOR FULL WORKFLOW'}</span></div><div><span>HEXROT.EXE <b>/</b> CORRUPT THE FORMAT. EXPOSE THE FAULT.</span><span className="status-divider"/><span>AUTHORIZED RESEARCH ONLY</span></div></footer>
  </div>;
}
