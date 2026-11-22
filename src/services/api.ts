import type { Comparison, CompareBytes, Detail, FileRecord, Health, Job, Session, Triage } from '../types';

const configuredBase = import.meta.env.VITE_HEXROT_API;
const isLocalHost = typeof window !== 'undefined' && ['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname);
// On the published preview (or any non-local origin) there is no loopback API to
// probe: fetching http://127.0.0.1 from an HTTPS page is blocked as mixed content.
// Leave BASE empty there so request() fails fast and the app runs browser-only
// instead of stalling on a doomed connection attempt.
const BASE = configuredBase ?? (isLocalHost ? 'http://127.0.0.1:8000/api' : '');

async function request<T>(path:string, options:RequestInit = {}, timeoutMs:number|null = 8000):Promise<T> {
  if (!BASE) throw new Error('Local backend is not configured for this origin. Run the app locally to use persistent sessions and decoder jobs.');
  const signal = options.signal ?? (timeoutMs===null?undefined:AbortSignal.timeout(timeoutMs));
  const response = await fetch(`${BASE}${path}`, { ...options, signal });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try { const body = await response.json(); message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail); } catch { /* use HTTP status */ }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}
const post = (body:unknown):RequestInit => ({method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
export const api = {
  health: () => request<Health>('/health',{signal:AbortSignal.timeout(1800)}),
  sessions: () => request<Session[]>('/sessions'),
  detail: (sid:string) => request<Detail>(`/sessions/${sid}`),
  demo: () => request<{session:Session;file:FileRecord}>('/sessions/demo',{method:'POST'}),
  upload: (file:File) => { const form = new FormData(); form.append('file',file); return request<{session:Session;file:FileRecord}>('/sessions/upload',{method:'POST',body:form},null); },
  mutate: (sid:string, body:unknown) => request<{files:FileRecord[]}>(`/sessions/${sid}/mutations`,post(body)),
  startJob: (sid:string, body:unknown) => request<Job>(`/sessions/${sid}/jobs`,post(body)),
  job: (id:string) => request<Job>(`/jobs/${id}`),
  cancel: (id:string) => request<{status:string}>(`/jobs/${id}/cancel`,{method:'POST'}),
  compare: (sid:string) => request<Comparison[]>(`/sessions/${sid}/differential`),
  compareBytes: (sid:string, fid:string, offset:number, length:number) => request<CompareBytes>(`/sessions/${sid}/files/${fid}/compare?offset=${offset}&length=${length}`),
  bytes: (sid:string,fid:string,offset:number,length:number) => request<{offset:number;data:string;size:number}>(`/sessions/${sid}/files/${fid}/bytes?offset=${offset}&length=${length}`),
  triage: (sid:string,rid:string) => request<Triage>(`/sessions/${sid}/runs/${rid}/triage`,{method:'POST',signal:AbortSignal.timeout(120000)}),
  downloadUrl: (sid:string,fid:string) => `${BASE}/sessions/${sid}/files/${fid}/download`,
  mediaUrl: (sid:string,fid:string) => `${BASE}/sessions/${sid}/files/${fid}/media`,
  reportUrl: (sid:string,format:string) => `${BASE}/sessions/${sid}/report?format=${format}`,
};
export function decodeBase64(value:string):Uint8Array { return Uint8Array.from(atob(value), c => c.charCodeAt(0)); }
export function hexOffset(value:number):string { return `0x${value.toString(16).toUpperCase().padStart(8,'0')}`; }
export function formatBytes(size:number | null | undefined):string {
  if (size == null) return 'N/A';
  if (size < 1024) return `${size} B`;
  if (size < 1024*1024) return `${(size/1024).toFixed(2)} KB`;
  return `${(size/(1024*1024)).toFixed(2)} MB`;
}
