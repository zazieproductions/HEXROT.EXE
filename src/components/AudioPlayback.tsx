import { useEffect, useMemo, useRef, useState } from 'react';
import { Activity, Pause, Play, RotateCcw, RotateCw, Volume2, VolumeX } from 'lucide-react';
import { api, formatBytes, hexOffset } from '../services/api';
import type { Analysis, Chunk, FileRecord } from '../types';
import type { Workspace } from '../hooks/useWorkspace';
import { PanelTitle } from './Chrome';

export interface AudioSeekRequest { token:number; offset:number }
export interface PlaybackPosition { time:number; duration:number; byteOffset:number; chunkId:string|null }
export interface AudioRegion { chunk:Chunk|null; start:number; end:number }

export function findAudioRegion(analysis:Analysis):AudioRegion {
  const chunk = analysis.chunks.find(item=>item.audio_offset!==undefined)
    || analysis.chunks.find(item=>item.kind==='audio')
    || analysis.chunks.find(item=>/^(data|ssnd)$/i.test(item.name.trim()));
  if (!chunk) return {chunk:null,start:0,end:Math.max(0,analysis.size)};
  const name=chunk.name.trim().toLowerCase();
  const start=chunk.audio_offset ?? (name==='data'?chunk.offset+8:name==='ssnd'?chunk.offset+16:chunk.offset);
  return {chunk,start:Math.max(chunk.offset,Math.min(start,chunk.end)),end:Math.max(start,chunk.end)};
}

function byteAtTime(analysis:Analysis, region:AudioRegion, time:number, duration:number):number {
  if (!region.chunk || region.end<=region.start) return 0;
  const facts=analysis.facts;
  const pcm=(analysis.format==='WAV' && ['PCM','IEEE float','Extensible'].includes(facts.codec || '') && facts.block_align && facts.sample_rate)
    || ((analysis.format==='AIFF' || analysis.format==='AIFC') && facts.codec==='PCM' && facts.channels && facts.bit_depth && facts.sample_rate);
  let offset:number;
  if (pcm && analysis.format==='WAV') offset=region.start+time*facts.sample_rate!*facts.block_align!;
  else if (pcm && (analysis.format==='AIFF'||analysis.format==='AIFC')) offset=region.start+time*facts.sample_rate!*facts.channels!*Math.ceil(facts.bit_depth!/8);
  else offset=region.start+(duration>0?time/duration:0)*(region.end-region.start);
  return Math.max(region.start,Math.min(region.end-1,Math.floor(offset)));
}

function timeAtByte(analysis:Analysis, region:AudioRegion, offset:number, mediaDuration:number):number|null {
  if (!region.chunk || offset<region.chunk.offset || offset>=region.end) return null;
  const duration=analysis.facts.duration || mediaDuration;
  if (!Number.isFinite(duration) || duration<=0) return null;
  const facts=analysis.facts;
  const pcm=(analysis.format==='WAV' && ['PCM','IEEE float','Extensible'].includes(facts.codec || '') && facts.block_align && facts.sample_rate)
    || ((analysis.format==='AIFF'||analysis.format==='AIFC') && facts.codec==='PCM' && facts.channels && facts.bit_depth && facts.sample_rate);
  let time:number;
  if (pcm && analysis.format==='WAV') time=(offset-region.start)/(facts.sample_rate!*facts.block_align!);
  else if (pcm && (analysis.format==='AIFF'||analysis.format==='AIFC')) time=(offset-region.start)/(facts.sample_rate!*facts.channels!*Math.ceil(facts.bit_depth!/8));
  else time=(offset-region.start)/(region.end-region.start)*duration;
  return Math.max(0,Math.min(duration,time));
}

function formatTime(seconds:number):string {
  if (!Number.isFinite(seconds) || seconds<0) return '00:00';
  const whole=Math.floor(seconds); const minutes=Math.floor(whole/60); const remainder=whole%60;
  return `${String(minutes).padStart(2,'0')}:${String(remainder).padStart(2,'0')}`;
}

export function AudioPlayback({workspace,file,onPosition,seekRequest}:{workspace:Workspace;file:FileRecord;onPosition:(position:PlaybackPosition)=>void;seekRequest:AudioSeekRequest|null}) {
  const audioRef=useRef<HTMLAudioElement>(null);
  const canvasRef=useRef<HTMLCanvasElement>(null);
  const contextRef=useRef<AudioContext|null>(null);
  const analyserRef=useRef<AnalyserNode|null>(null);
  const sourceRef=useRef<MediaElementAudioSourceNode|null>(null);
  const samplesRef=useRef<Uint8Array<ArrayBuffer>|null>(null);
  const peaksRef=useRef<Float32Array>(new Float32Array(1));
  const onPositionRef=useRef(onPosition);
  const [playing,setPlaying]=useState(false);
  const [ready,setReady]=useState(false);
  const [duration,setDuration]=useState(file.analysis.facts.duration || 0);
  const [time,setTime]=useState(0);
  const [muted,setMuted]=useState(false);
  const [error,setError]=useState('');
  const region=useMemo(()=>findAudioRegion(file.analysis),[file.analysis]);
  const sourceLabel=region.chunk?.name.trim() || file.analysis.format;

  useEffect(()=>{ onPositionRef.current=onPosition; },[onPosition]);

  useEffect(()=>{
    const audio=audioRef.current;
    if (!audio) return;
    let objectUrl:string|undefined;
    audio.pause();
    setPlaying(false); setReady(false); setTime(0); setDuration(file.analysis.facts.duration || 0); setError('');
    if (workspace.mode==='backend') {
      audio.crossOrigin='anonymous';
      audio.src=api.mediaUrl(file.session_id,file.id);
    } else if (workspace.browserFile) {
      objectUrl=URL.createObjectURL(workspace.browserFile);
      audio.removeAttribute('crossorigin');
      audio.src=objectUrl;
    } else {
      setError('The browser audio source is no longer available. Re-import the file to play it.');
      return;
    }
    audio.preload='metadata';
    audio.load();
    return ()=>{
      audio.pause(); audio.removeAttribute('src'); audio.load();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  },[file.id,file.session_id,file.analysis.facts.duration,workspace.mode,workspace.browserFile]);

  useEffect(()=>{
    const audio=audioRef.current;
    if (!audio || !seekRequest || !ready) return;
    const mediaDuration=Number.isFinite(audio.duration)&&audio.duration>0?audio.duration:duration;
    const target=timeAtByte(file.analysis,region,seekRequest.offset,mediaDuration);
    if (target===null) return;
    if (Number.isFinite(audio.duration) && audio.duration>0) audio.currentTime=Math.min(target,audio.duration);
  },[duration,file.analysis,region,seekRequest,ready]);

  useEffect(()=>{
    peaksRef.current.fill(0);
  },[file.id]);

  useEffect(()=>{
    let frame=0;
    let lastPublish=0;
    const draw=()=>{
      const canvas=canvasRef.current;
      const audio=audioRef.current;
      if (canvas) {
        const ratio=window.devicePixelRatio || 1;
        const width=Math.max(1,Math.round(canvas.clientWidth*ratio));
        const height=Math.max(1,Math.round(canvas.clientHeight*ratio));
        if (canvas.width!==width || canvas.height!==height) {
          canvas.width=width; canvas.height=height;
          peaksRef.current=new Float32Array(width);
        }
        const context=canvas.getContext('2d');
        if (context) {
          const current=audio?.currentTime || 0;
          const total=(audio && Number.isFinite(audio.duration) && audio.duration>0)?audio.duration:duration;
          const progress=total>0?Math.max(0,Math.min(1,current/total)):0;
          const analyser=analyserRef.current;
          if (audio && !audio.paused && !audio.ended && analyser) {
            if (!samplesRef.current || samplesRef.current.length!==analyser.fftSize) samplesRef.current=new Uint8Array(analyser.fftSize);
            analyser.getByteTimeDomainData(samplesRef.current);
            let peak=0;
            for (const sample of samplesRef.current) peak=Math.max(peak,Math.abs(sample-128)/128);
            const index=Math.min(width-1,Math.floor(progress*width));
            peaksRef.current[index]=Math.max(peaksRef.current[index] || 0,Math.min(1,peak*1.7));
          }
          context.fillStyle='#04100c'; context.fillRect(0,0,width,height);
          context.strokeStyle='rgba(102,160,128,.12)'; context.lineWidth=1;
          for (let x=0;x<=width;x+=Math.max(1,Math.floor(width/8))) {
            context.beginPath(); context.moveTo(x,0); context.lineTo(x,height); context.stroke();
          }
          const middle=height/2;
          context.strokeStyle='rgba(102,160,128,.22)'; context.beginPath(); context.moveTo(0,middle); context.lineTo(width,middle); context.stroke();
          for (let x=0;x<width;x++) {
            const peak=peaksRef.current[x] || 0;
            if (!peak) continue;
            const amp=Math.max(1,peak*height*.43);
            context.strokeStyle=x<=progress*width?'rgba(47,229,143,.92)':'rgba(47,229,143,.36)';
            context.beginPath(); context.moveTo(x,middle-amp); context.lineTo(x,middle+amp); context.stroke();
          }
          const cursor=Math.min(width-1,Math.floor(progress*width));
          context.fillStyle='#ffd486'; context.fillRect(cursor,0,2,height);
          context.fillStyle='rgba(255,212,134,.14)'; context.fillRect(0,0,cursor,height);
        }
      }
      if (audio) {
        const current=audio.currentTime || 0;
        const total=(Number.isFinite(audio.duration) && audio.duration>0)?audio.duration:duration;
        const byteOffset=byteAtTime(file.analysis,region,current,total);
        if (performance.now()-lastPublish>=80) {
          lastPublish=performance.now();
          setTime(previous=>Math.abs(previous-current)<.015?previous:current);
          if (total>0) setDuration(previous=>Math.abs(previous-total)<.02?previous:total);
          onPositionRef.current({time:current,duration:total,byteOffset,chunkId:region.chunk?.id || null});
        }
      }
      frame=window.requestAnimationFrame(draw);
    };
    frame=window.requestAnimationFrame(draw);
    return ()=>window.cancelAnimationFrame(frame);
  },[duration,file.analysis,region]);

  useEffect(()=>()=>{
    if (contextRef.current) void contextRef.current.close().catch(()=>undefined);
    contextRef.current=null; analyserRef.current=null; sourceRef.current=null;
  },[]);

  const play=async()=>{
    const audio=audioRef.current;
    if (!audio) return;
    if (!audio.paused) { audio.pause(); return; }
    setError('');
    try {
      if (!contextRef.current && typeof window.AudioContext!=='undefined') {
        const context=new window.AudioContext();
        try {
          const source=context.createMediaElementSource(audio);
          const analyser=context.createAnalyser(); analyser.fftSize=1024; analyser.smoothingTimeConstant=.12;
          source.connect(analyser); analyser.connect(context.destination);
          contextRef.current=context; sourceRef.current=source; analyserRef.current=analyser;
        } catch {
          await context.close();
        }
      }
      if (contextRef.current?.state==='suspended') await contextRef.current.resume();
      if (audio.ended) audio.currentTime=0;
      await audio.play();
    } catch (e) {
      setError(e instanceof Error?e.message:'Playback could not start.');
    }
  };
  const seek=(next:number)=>{
    const audio=audioRef.current;
    if (!audio || !Number.isFinite(next)) return;
    const total=(Number.isFinite(audio.duration)&&audio.duration>0)?audio.duration:duration;
    audio.currentTime=Math.max(0,Math.min(total,next));
  };
  const skip=(delta:number)=>seek((audioRef.current?.currentTime || 0)+delta);
  const total=(Number.isFinite(duration)&&duration>0)?duration:(file.analysis.facts.duration || 0);
  const currentByte=byteAtTime(file.analysis,region,time,total);

  return <section className="panel audio-panel">
    <PanelTitle number="02" title="REAL-TIME PLAYBACK" sub="AUDIO CLOCK ↔ FILE DATA" action={<span className="audio-status"><i className={`status-dot ${playing?'green':ready?'amber':'red'}`}/>{playing?'PLAYING':error?'UNAVAILABLE':ready?'READY':'LOADING'}</span>}/>
    <audio ref={audioRef} className="audio-element" preload="metadata" aria-hidden="true" tabIndex={-1} onLoadedMetadata={event=>{const value=event.currentTarget.duration;if(Number.isFinite(value)&&value>0){setDuration(value);setReady(true);}}} onCanPlay={()=>setReady(true)} onPlay={()=>setPlaying(true)} onPause={()=>setPlaying(false)} onEnded={()=>setPlaying(false)} onError={event=>{const code=event.currentTarget.error?.code;setError(code===4?'This browser cannot decode the selected audio format.':'Audio data could not be loaded.');setReady(false);}} />
    <div className="audio-signal"><canvas ref={canvasRef} aria-label="Live waveform envelope synchronized to playback"/><div className="audio-signal-caption"><span><Activity size={12}/> LIVE SIGNAL ENVELOPE</span><span>PLAYHEAD FOLLOWS AUDIO CLOCK</span></div></div>
    <div className="audio-controls">
      <button className="audio-control-btn audio-play-btn" onClick={()=>void play()} disabled={!ready} aria-label={playing?'Pause audio':'Play audio'} title={playing?'Pause':'Play'}>{playing?<Pause size={17} fill="currentColor"/>:<Play size={17} fill="currentColor"/>}</button>
      <button className="audio-control-btn" onClick={()=>skip(-5)} disabled={!ready} aria-label="Back five seconds" title="Back 5 seconds"><RotateCcw size={15}/></button>
      <div className="audio-clock"><strong>{formatTime(time)}</strong><span>/</span><span>{formatTime(total)}</span></div>
      <input className="audio-seek" type="range" min="0" max={Math.max(total,.01)} step="0.01" value={Math.min(time,total || .01)} onChange={event=>seek(Number(event.currentTarget.value))} disabled={!ready||total<=0} aria-label="Seek audio"/>
      <button className="audio-control-btn" onClick={()=>skip(5)} disabled={!ready} aria-label="Forward five seconds" title="Forward 5 seconds"><RotateCw size={15}/></button>
      <button className="audio-control-btn" onClick={()=>{const audio=audioRef.current;if(audio){audio.muted=!audio.muted;setMuted(audio.muted);}}} aria-label={muted?'Unmute audio':'Mute audio'} title={muted?'Unmute':'Mute'}>{muted?<VolumeX size={15}/>:<Volume2 size={15}/>}</button>
    </div>
    <div className="audio-sync-row"><span><i className={`status-dot ${playing?'green':'red'}`}/><b>DATA SYNC</b></span><span>{sourceLabel} <b>·</b> {formatBytes(file.analysis.size)}</span><code>{hexOffset(currentByte)}</code><span>{file.analysis.facts.sample_rate?`${file.analysis.facts.sample_rate.toLocaleString()} Hz`:file.analysis.format}</span></div>
    {error&&<div className="audio-error" role="status">{error}</div>}
    <div className="audio-footnote">Playback seeks the media stream; the hex cursor follows its sample/frame offset. Click an audio byte to seek back into the recording.</div>
  </section>;
}
