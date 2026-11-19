import { Activity, Archive, ArrowUpRight, AudioLines, Braces, ChevronDown, CircleHelp, Command, FileSearch, FileText, FlaskConical, GitCompareArrows, HardDrive, LockKeyhole, PanelLeftClose, Radio, ShieldCheck, Terminal } from 'lucide-react';
import type { Page } from '../types';
import type { Workspace } from '../hooks/useWorkspace';

export const navigation:{id:Page; label:string; icon:typeof FileSearch}[] = [
  {id:'autopsy',label:'Autopsy',icon:FileSearch}, {id:'metadata',label:'Metadata',icon:Braces},
  {id:'mutator',label:'Mutator',icon:FlaskConical}, {id:'decoder',label:'Decoder Lab',icon:Radio},
  {id:'differential',label:'Differential',icon:GitCompareArrows}, {id:'crash',label:'Crash Vault',icon:Archive},
  {id:'evidence',label:'Evidence',icon:FileText},
];

export function BrandMark() {
  return <svg className="brand-mark" viewBox="0 0 36 36" aria-hidden="true">
    <path d="M9.2 2.6h17.6L34.4 18 26.8 33.4H9.2L1.6 18 9.2 2.6Z" fill="none" stroke="currentColor" strokeWidth="1.6"/>
    <path d="M10.5 11.5 15 18l-4.5 6.5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="square"/>
    <path d="M18.6 24.6h7" stroke="currentColor" strokeWidth="2.2" strokeLinecap="square"/>
    <path d="M18.6 11.5h7" stroke="currentColor" strokeWidth="1.4" strokeLinecap="square" opacity=".55"/>
    <path d="M18.6 15.4h4.4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="square" opacity=".35"/>
  </svg>;
}

export function TopBar({workspace,page,onPalette}:{workspace:Workspace;page:Page;onPalette:()=>void}) {
  const label=navigation.find(n=>n.id===page)?.label || 'Autopsy';
  const index=navigation.findIndex(n=>n.id===page)+1;
  return <header className="topbar">
    <div className="brand"><BrandMark/><div><strong>HEXROT<span>.EXE</span></strong><small>AUDIO FORENSICS TTY</small></div></div>
    <div className="top-crumb"><span>ROOT://WORKSPACE</span><span className="crumb-slash">/</span><b>{label.toUpperCase()}</b><span className="crumb-slash">/</span><span>MODULE {String(Math.max(index,1)).padStart(2,'0')}</span><span className="crumb-caret">_</span></div>
    <div className="top-actions">
      <div className="top-engine"><span className={`status-dot ${workspace.health?'green':'amber'}`}/><span>{workspace.connecting?'PROBING LINK':workspace.health?'ENGINE ONLINE':workspace.mode==='backend'?'ENGINE OFFLINE':'BROWSER MODE'}</span></div>
      <span className="top-separator"/>
      <div className="top-local"><LockKeyhole size={12}/><span>LOOPBACK ONLY</span></div>
      <span className="top-separator"/>
      <span className="header-version">v0.2.0</span>
      <button className="top-cmd" onClick={onPalette} aria-label="Open command palette" title="Command palette (Ctrl+K)"><Command size={11}/>CTRL+K</button>
    </div>
  </header>;
}

export function Sidebar({workspace,page,onPage,onImport}:{workspace:Workspace;page:Page;onPage:(p:Page)=>void;onImport:()=>void}) {
  return <aside className="sidebar">
    <div className="sidebar-scroll">
      <div className="side-heading"><span>RESEARCH MODULES</span><span>{String(navigation.findIndex(n=>n.id===page)+1).padStart(2,'0')}/07</span></div>
      <nav className="side-nav" aria-label="Research modules">
        {navigation.map(({id,label,icon:Icon},i)=><button key={id} className={`nav-item ${page===id?'active':''}`} onClick={()=>onPage(id)} aria-current={page===id?'page':undefined}>
          <Icon size={15} strokeWidth={1.5}/><span>{label}</span><span className="nav-index">{String(i+1).padStart(2,'0')}</span>
        </button>)}
      </nav>
      <div className="side-divider"/>
      <div className="side-heading workspace-heading"><span>WORKSPACE</span><PanelLeftClose size={12}/></div>
      {workspace.mode==='backend' && workspace.sessions.length>0 ? <div className="session-picker"><HardDrive size={14}/><select aria-label="Open saved research session" value={workspace.detail?.session.id || ''} onChange={e=>workspace.openSession(e.target.value)}>{workspace.sessions.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select><ChevronDown size={11}/></div> : <div className="session-picker"><HardDrive size={14}/><span className="session-name">in-browser / preview</span></div>}
      <button className="side-import" onClick={onImport}><span>+</span> new session // import</button>
    </div>
    <div className="sidebar-bottom">
      <div className="side-status-title"><span>ENVIRONMENT</span><Activity size={12}/></div>
      <div className="side-status-row"><span>local backend</span><span className={workspace.health?'state-good':'state-muted'}><i className={`status-dot ${workspace.health?'green':'amber'}`}/>{workspace.health?'online':'offline'}</span></div>
      <div className="side-status-row"><span>worker isolation</span><span className={workspace.health?.isolation.available?'state-good':'state-muted'}><i className={`status-dot ${workspace.health?.isolation.available?'green':'grey'}`}/>{workspace.health ? workspace.health.isolation.available?'ready':'unavailable':'no link'}</span></div>
      <div className="side-status-row"><span>egress policy</span><span className="state-muted"><i className="status-dot grey"/>blocked</span></div>
      {!workspace.health && <button className="reconnect" onClick={()=>workspace.connect(true)}>reconnect engine <ArrowUpRight size={11}/></button>}
      <div className="side-brand"><div className="side-brand-icon"><AudioLines size={15}/></div><div><strong>CHURCH OF MALWARE</strong><small>AUTHORIZED RESEARCH ONLY</small></div><ShieldCheck size={13}/></div>
    </div>
  </aside>;
}

export function PageHeader({index,title,description,action}:{index:string;title:string;description:string;action?:React.ReactNode}) {
  return <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-square"/>RESEARCH MODULE<span className="muted-slash">/</span>{index}</div><h1>{title}</h1><p>{description}</p></div>{action && <div className="heading-actions">{action}</div>}</div>;
}

export function PanelTitle({number,title,sub,action}:{number?:string;title:string;sub?:string;action?:React.ReactNode}) {
  return <div className="panel-title"><div className="panel-title-main">{number && <span className="panel-index">{number}</span>}<h2>{title}</h2>{sub && <span className="panel-sub">{sub}</span>}</div>{action}</div>;
}

export function EmptyState({title,description}:{title:string;description:string}) {
  return <div className="empty-state"><CircleHelp size={18}/><strong>{title}</strong><span>{description}</span></div>;
}

export function ConsoleChip({open,onToggle,count}:{open:boolean;onToggle:()=>void;count:number}) {
  return <button className={`status-console ${open?'live':''}`} onClick={onToggle} aria-pressed={open} title="Toggle system console (`)">
    <Terminal size={10}/> console {String(count).padStart(3,'0')}
  </button>;
}
