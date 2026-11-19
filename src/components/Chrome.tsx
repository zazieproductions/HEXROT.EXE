import { Activity, Archive, ArrowUpRight, AudioLines, Braces, ChevronDown, CircleHelp, FileSearch, FileText, FlaskConical, GitCompareArrows, HardDrive, LockKeyhole, PanelLeftClose, Radio, ShieldCheck } from 'lucide-react';
import type { Page } from '../types';
import type { Workspace } from '../hooks/useWorkspace';

export const navigation:{id:Page; label:string; icon:typeof FileSearch}[] = [
  {id:'autopsy',label:'Autopsy',icon:FileSearch}, {id:'metadata',label:'Metadata',icon:Braces},
  {id:'mutator',label:'Mutator',icon:FlaskConical}, {id:'decoder',label:'Decoder Lab',icon:Radio},
  {id:'differential',label:'Differential',icon:GitCompareArrows}, {id:'crash',label:'Crash Vault',icon:Archive},
  {id:'evidence',label:'Evidence',icon:FileText},
];

export function BrandMark() {
  return <svg className="brand-mark" viewBox="0 0 36 36" aria-hidden="true"><path d="M9 3h18l7 15-7 15H9L2 18 9 3Z" fill="none" stroke="currentColor" strokeWidth="2"/><path d="M10 23V13h3l3.3 5L20 13h3v10h-3v-5l-3.7 5L13 18v5h-3Z" fill="currentColor"/><path d="M26 12v12" stroke="currentColor" strokeWidth="2"/></svg>;
}

export function TopBar({workspace,page}:{workspace:Workspace;page:Page}) {
  const label=navigation.find(n=>n.id===page)?.label || 'Autopsy';
  return <header className="topbar">
    <div className="brand"><BrandMark/><div><strong>HEXROT<span>.EXE</span></strong><small>AUDIO RESEARCH WORKSTATION</small></div></div>
    <div className="top-crumb"><span>WORKSPACE</span><span className="crumb-slash">/</span><b>{label.toUpperCase()}</b></div>
    <div className="top-actions"><div className="top-engine"><span className={`status-dot ${workspace.health?'green':'amber'}`}/><span>{workspace.connecting?'CONNECTING':workspace.health?'ENGINE ONLINE':workspace.mode==='backend'?'ENGINE OFFLINE':'BROWSER MODE'}</span></div><span className="top-separator"/><div className="top-local"><LockKeyhole size={13}/><span>LOCAL WORKSPACE</span></div><span className="top-separator"/><span className="header-version">v0.2.0</span></div>
  </header>;
}

export function Sidebar({workspace,page,onPage,onImport}:{workspace:Workspace;page:Page;onPage:(p:Page)=>void;onImport:()=>void}) {
  return <aside className="sidebar">
    <div className="sidebar-scroll">
      <div className="side-heading"><span>RESEARCH MODULES</span><span>01 / 07</span></div>
      <nav className="side-nav" aria-label="Research modules">
        {navigation.map(({id,label,icon:Icon},i)=><button key={id} className={`nav-item ${page===id?'active':''}`} onClick={()=>onPage(id)} aria-current={page===id?'page':undefined}>
          <Icon size={16} strokeWidth={1.6}/><span>{label}</span><span className="nav-index">{String(i+1).padStart(2,'0')}</span>
        </button>)}
      </nav>
      <div className="side-divider"/>
      <div className="side-heading workspace-heading"><span>WORKSPACE</span><PanelLeftClose size={13}/></div>
      {workspace.mode==='backend' && workspace.sessions.length>0 ? <div className="session-picker"><HardDrive size={15}/><select aria-label="Open saved research session" value={workspace.detail?.session.id || ''} onChange={e=>workspace.openSession(e.target.value)}>{workspace.sessions.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select><ChevronDown size={12}/></div> : <div className="session-picker"><HardDrive size={15}/><span className="session-name">In-browser preview</span></div>}
      <button className="side-import" onClick={onImport}><span>+</span> New research session</button>
    </div>
    <div className="sidebar-bottom">
      <div className="side-status-title"><span>ENVIRONMENT</span><Activity size={13}/></div>
      <div className="side-status-row"><span>Local backend</span><span className={workspace.health?'state-good':'state-muted'}><i className={`status-dot ${workspace.health?'green':'amber'}`}/>{workspace.health?'Online':'Offline'}</span></div>
      <div className="side-status-row"><span>Worker isolation</span><span className={workspace.health?.isolation.available?'state-good':'state-muted'}><i className={`status-dot ${workspace.health?.isolation.available?'green':'grey'}`}/>{workspace.health ? workspace.health.isolation.available?'Ready':'Unavailable':'Not connected'}</span></div>
      {!workspace.health && <button className="reconnect" onClick={()=>workspace.connect(true)}>Reconnect backend <ArrowUpRight size={12}/></button>}
      <div className="side-brand"><div className="side-brand-icon"><AudioLines size={16}/></div><div><strong>CHURCH OF MALWARE</strong><small>AUTHORIZED RESEARCH ONLY</small></div><ShieldCheck size={14}/></div>
    </div>
  </aside>;
}

export function PageHeader({index,title,description,action}:{index:string;title:string;description:string;action?:React.ReactNode}) {
  return <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-square"/> RESEARCH MODULE <span className="muted-slash">/</span> {index}</div><h1>{title}</h1><p>{description}</p></div>{action && <div className="heading-actions">{action}</div>}</div>;
}

export function PanelTitle({number,title,sub,action}:{number?:string;title:string;sub?:string;action?:React.ReactNode}) {
  return <div className="panel-title"><div className="panel-title-main">{number && <span className="panel-index">{number}</span>}<h2>{title}</h2>{sub && <span className="panel-sub">{sub}</span>}</div>{action}</div>;
}

export function EmptyState({title,description}:{title:string;description:string}) {
  return <div className="empty-state"><CircleHelp size={19}/><strong>{title}</strong><span>{description}</span></div>;
}
