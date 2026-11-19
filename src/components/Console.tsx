import { useEffect, useRef, useState } from 'react';
import { Terminal, X } from 'lucide-react';

export type LogLevel = 'sys' | 'ok' | 'warn' | 'err';
export interface LogLine { id:number; at:string; tag:string; level:LogLevel; msg:string }

const MAX_LINES = 240;
let sequence = 0;
const listeners = new Set<(lines:LogLine[]) => void>();
let lines:LogLine[] = [];

const stamp = () => new Date().toLocaleTimeString('en-GB', { hour12:false });

export function log(level:LogLevel, tag:string, msg:string) {
  lines = [...lines, { id:++sequence, at:stamp(), tag:tag.toUpperCase(), level, msg }].slice(-MAX_LINES);
  listeners.forEach(fn=>fn(lines));
}
export const logSys = (msg:string) => log('sys','sys',msg);
export const logOk = (msg:string) => log('ok','ok',msg);
export const logWarn = (msg:string) => log('warn','wrn',msg);
export const logErr = (msg:string) => log('err','err',msg);

export function useConsoleLog() {
  const [snapshot,setSnapshot] = useState<LogLine[]>(lines);
  useEffect(()=>{ listeners.add(setSnapshot); return ()=>{ listeners.delete(setSnapshot); }; },[]);
  return snapshot;
}

export function ConsoleDrawer({open,onClose}:{open:boolean;onClose:()=>void}) {
  const entries = useConsoleLog();
  const scroller = useRef<HTMLDivElement>(null);
  useEffect(()=>{ if(open && scroller.current) scroller.current.scrollTop = scroller.current.scrollHeight; },[entries,open]);
  if (!open) return null;
  return <section className="console-drawer" aria-label="System console">
    <div className="console-head">
      <div><Terminal size={11}/><b>SYSTEM CONSOLE</b><span>// stdout · loopback · {entries.length} lines</span></div>
      <button onClick={onClose} aria-label="Close console"><X size={12}/></button>
    </div>
    <div className="console-body" ref={scroller} role="log" aria-live="polite">
      {entries.length ? entries.map(line=><div className={`console-line ${line.level}`} key={line.id}>
        <time>{line.at}</time><span className={`tag ${line.level}`}>[{line.tag}]</span><span className="msg">{line.msg}</span>
      </div>) : <div className="console-line"><span className="msg">console idle — awaiting events</span></div>}
      <div className="console-prompt">root@hexrot:~$</div>
    </div>
  </section>;
}
