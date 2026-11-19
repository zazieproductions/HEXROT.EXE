import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../services/api';
import { inspectInBrowser } from '../services/browserAnalysis';
import type { Comparison, Detail, FileRecord, Health, Job, Session } from '../types';

const emptyDetail = (file:FileRecord):Detail => ({session:{id:'browser',name:file.name,created_at:file.created_at},files:[file],jobs:[],runs:[],triage:[]});

export function useWorkspace() {
  const [detail,setDetail]=useState<Detail|null>(null);
  const [selectedId,setSelectedId]=useState('');
  const [localBytes,setLocalBytes]=useState<Uint8Array|null>(null);
  const [health,setHealth]=useState<Health|null>(null);
  const [mode,setMode]=useState<'browser'|'backend'>('browser');
  const [sessions,setSessions]=useState<Session[]>([]);
  const [comparisons,setComparisons]=useState<Comparison[]>([]);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const [connecting,setConnecting]=useState(true);
  const initialized=useRef(false);

  const localFile = useCallback(async (file:File) => {
    const {analysis,bytes}=await inspectInBrowser(file);
    const item:FileRecord={id:'browser-file',session_id:'browser',name:file.name,kind:'original',created_at:new Date().toISOString(),analysis,mutation:null};
    setDetail(emptyDetail(item)); setSelectedId(item.id); setLocalBytes(bytes); setMode('browser'); setComparisons([]);
  },[]);
  const localDemo = useCallback(async () => {
    const response=await fetch(import.meta.env.BASE_URL + 'fixtures/reference.wav');
    if (!response.ok) throw new Error('The generated demo fixture could not be loaded.');
    await localFile(new File([await response.blob()],'reference.wav',{type:'audio/wav'}));
  },[localFile]);
  const reload = useCallback(async (sid:string, selected?:string) => {
    const [next,all,cases]=await Promise.all([api.detail(sid),api.sessions(),api.compare(sid)]);
    setDetail(next); setSessions(all); setComparisons(cases); setMode('backend'); setLocalBytes(null);
    try { localStorage.setItem('hexrot:last-session',sid); } catch { /* storage may be disabled */ }
    setSelectedId(previous => selected || (next.files.some(f=>f.id===previous)?previous:next.files[0]?.id || ''));
  },[]);
  const connect = useCallback(async (notify=true) => {
    setConnecting(true);
    try {
      const currentHealth=await api.health(); setHealth(currentHealth);
      const all=await api.sessions(); setSessions(all);
      let remembered:string | null=null;
      try { remembered=localStorage.getItem('hexrot:last-session'); } catch { /* storage may be disabled */ }
      if (all.length) await reload(all.find(session=>session.id===remembered)?.id || all[0].id);
      else { const created=await api.demo(); await reload(created.session.id,created.file.id); }
      setError('');
    } catch (e) {
      setHealth(null);
      if (notify) setError(`Backend unavailable: ${e instanceof Error?e.message:'connection failed'}. Start the local API to use persistent sessions and decoder jobs.`);
    } finally { setConnecting(false); }
  },[reload]);
  useEffect(() => {
    if (initialized.current) return; initialized.current=true;
    void (async()=>{
      try { await localDemo(); } catch (e) { setError(e instanceof Error?e.message:'Could not load the fixture.'); }
      await connect(false);
    })();
  },[connect,localDemo]);

  useEffect(()=>{
    if (mode!=='backend') return;
    const timer=window.setInterval(async()=>{
      try {
        const current=await api.health();
        setHealth(previous=>JSON.stringify(previous)===JSON.stringify(current)?previous:current);
      } catch { setHealth(null); }
    },15000);
    return ()=>window.clearInterval(timer);
  },[mode]);

  const activeJob=detail?.jobs.find(j=>j.status==='running'||j.status==='queued');
  useEffect(()=>{
    if (!activeJob || mode!=='backend' || !detail) return;
    let stopped=false;
    const timer=window.setInterval(async()=>{
      try {
        const [job,next]=await Promise.all([api.job(activeJob.id),api.detail(detail.session.id)]);
        if (stopped) return;
        setDetail({...next,jobs:next.jobs.map(j=>j.id===job.id?job:j)});
        if (!['queued','running'].includes(job.status)) {
          setComparisons(await api.compare(detail.session.id));
        }
      } catch (e) { if (!stopped) setError(e instanceof Error?e.message:'Job status could not be loaded.'); }
    },700);
    return ()=>{stopped=true;window.clearInterval(timer);};
  },[activeJob?.id,activeJob?.status,detail?.session.id,mode]);

  const perform = useCallback(async (operation:()=>Promise<void>)=>{
    setBusy(true); setError('');
    try { await operation(); } catch (e) { setError(e instanceof Error?e.message:'Operation failed.'); }
    finally { setBusy(false); }
  },[]);
  const importFile = (file:File) => perform(async()=>{
    if (health) { const created=await api.upload(file); await reload(created.session.id,created.file.id); }
    else await localFile(file);
  });
  const loadDemo = () => perform(async()=>{
    if (health) { const created=await api.demo(); await reload(created.session.id,created.file.id); }
    else await localDemo();
  });
  const openSession = (sid:string) => perform(()=>reload(sid));
  const mutate = (body:unknown) => perform(async()=>{
    if (!detail || mode!=='backend') throw new Error('Start the local backend to create persistent mutation files.');
    await api.mutate(detail.session.id,body); await reload(detail.session.id);
  });
  const runJob = (body:unknown) => perform(async()=>{
    if (!detail || mode!=='backend') throw new Error('Start the local backend and configure isolation to run decoders.');
    await api.startJob(detail.session.id,body); await reload(detail.session.id);
  });
  const cancelJob = (job:Job) => perform(async()=>{
    await api.cancel(job.id); if(detail) await reload(detail.session.id);
  });
  const triage = (id:string) => perform(async()=>{
    if (!detail || mode!=='backend') return;
    await api.triage(detail.session.id,id); await reload(detail.session.id);
  });
  const selected=detail?.files.find(f=>f.id===selectedId) || detail?.files[0] || null;
  return {detail,selected,selectedId,setSelectedId,localBytes,health,mode,sessions,comparisons,error,setError,busy,connecting,
          activeJob,importFile,loadDemo,openSession,mutate,runJob,cancelJob,triage,connect};
}
export type Workspace = ReturnType<typeof useWorkspace>;
