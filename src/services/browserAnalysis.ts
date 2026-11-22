import type { Analysis, Chunk, MetadataField, Warning } from '../types';

// A small offline fallback. The backend remains the authoritative full-format parser.
export async function inspectInBrowser(file:File):Promise<{analysis:Analysis;bytes:Uint8Array}> {
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer); const view = new DataView(buffer);
  const ascii = (start:number,end:number) => Array.from(bytes.slice(start,end), b => b >= 32 && b <= 126 ? String.fromCharCode(b) : '.').join('');
  const u32 = (at:number,little:boolean) => view.getUint32(at,little);
  const word = (at:number,little:boolean) => view.getUint16(at,little);
  const signature = ascii(0,4), subtype = ascii(8,12);
  let format = 'Unknown';
  if (signature === 'RIFF' && subtype === 'WAVE') format = 'WAV';
  else if (signature === 'FORM' && ['AIFF','AIFC'].includes(subtype)) format = subtype;
  else if (signature === 'fLaC') format = 'FLAC';
  else if (ascii(0,3) === 'ID3' || (bytes.length >= 2 && bytes[0] === 255 && (bytes[1] & 224) === 224)) format = 'MP3';
  const hash = await crypto.subtle.digest('SHA-256',buffer);
  const sha256 = Array.from(new Uint8Array(hash),b => b.toString(16).padStart(2,'0')).join('');
  const chunks:Chunk[] = []; const metadata:MetadataField[] = []; const warnings:Warning[] = [];
  const facts:Analysis['facts'] = {container:({WAV:'RIFF / WAVE',AIFF:'FORM / AIFF',AIFC:'FORM / AIFC',FLAC:'FLAC',MP3:'MPEG audio'} as Record<string,string>)[format] || 'Unknown',codec:null,sample_rate:null,channels:null,bit_depth:null,duration:null};
  const add = (name:string,offset:number,end:number,declared:number,actual:number,kind='chunk',status='ok',detail='') => chunks.push({id:`${offset.toString(16).padStart(8,'0')}-${chunks.length}`,name,offset,end,declared_size:declared,actual_size:actual,kind,status,detail});
  let trailing = 0;
  if (['WAV','AIFF','AIFC'].includes(format) && bytes.length >= 12) {
    const little = format === 'WAV'; const declared = u32(4,little); const declaredEnd = declared+8; const limit = Math.min(bytes.length,declaredEnd);
    add(little?'RIFF':'FORM',0,12,declared,bytes.length-8,'container',declaredEnd===bytes.length?'ok':'warning','Container header');
    if (declaredEnd > bytes.length) warnings.push({severity:'warning',message:`Container declares ${declaredEnd} bytes, but file contains ${bytes.length}.`,offset:4});
    if (declaredEnd < bytes.length) { trailing=bytes.length-declaredEnd; warnings.push({severity:'warning',message:`${trailing} trailing byte(s) follow the declared container.`,offset:declaredEnd}); }
    let pos=12; let byteRate=0; let dataBytes:number | null=null;
    while (pos+8 <= limit && chunks.length < 4096) {
      const name=ascii(pos,pos+4), size=u32(pos+4,little), body=pos+8, actual=Math.max(0,Math.min(size,limit-body));
      const end=Math.min(limit,body+size+(size&1)); const truncated=actual<size;
      add(name,pos,end,size,actual,'chunk',truncated?'warning':'ok',truncated?'Truncated chunk':'');
      if (truncated) warnings.push({severity:'warning',message:`${name} chunk declares ${size} bytes but only ${actual} are available.`,offset:pos+4});
      if (little && name==='fmt ' && actual>=16) {
        const code=word(body,true); facts.codec=code===1?'PCM':code===3?'IEEE float':`WAVE codec 0x${code.toString(16).toUpperCase()}`;
        facts.channels=word(body+2,true); facts.sample_rate=u32(body+4,true); byteRate=u32(body+8,true); facts.block_align=word(body+12,true); facts.bit_depth=word(body+14,true);
      } else if (little && name==='data') { dataBytes=actual; chunks[chunks.length-1].audio_offset=body; }
      else if (little && name==='LIST' && ascii(body,body+4)==='INFO') {
        let p=body+4; const stop=body+actual;
        while (p+8<=stop) {
          const key=ascii(p,p+4), n=u32(p+4,true), e=Math.min(stop,p+8+n);
          const raw=bytes.slice(p+8,e); const value=new TextDecoder('utf-8').decode(raw).replace(/\0+$/,'');
          metadata.push({key,value:value.slice(0,4096),source:'RIFF INFO',offset:p+8,byte_length:raw.length,truncated:value.length>4096});
          if (p+8+n>stop) break; p+=8+n+(n&1);
        }
      } else if (!little && name==='COMM' && actual>=18) {
        facts.channels=word(body,false); const frames=u32(body+2,false); facts.bit_depth=word(body+6,false);
        const exponent=word(body+8,false)&0x7fff; const hi=u32(body+10,false), lo=u32(body+14,false);
        const rate=(hi*2**32+lo)/2**63*2**(exponent-16383);
        if (Number.isFinite(rate) && rate>0 && rate<10000000) { facts.sample_rate=Math.round(rate); facts.duration=frames/rate; }
        facts.codec=format==='AIFF'?'PCM':actual>=22?ascii(body+18,body+22):'AIFC';
      } else if (!little && name==='SSND' && actual>=8) {
        const soundOffset=u32(body,false); chunks[chunks.length-1].audio_offset=Math.min(body+8+soundOffset,body+actual);
      } else if (!little && ['NAME','AUTH','ANNO','(c) '].includes(name)) {
        metadata.push({key:name,value:new TextDecoder().decode(bytes.slice(body,body+actual)).replace(/\0+$/,''),source:'AIFF',offset:body,byte_length:actual,truncated:false});
      }
      if (truncated) break; const next=body+size+(size&1); if (next>limit) break; pos=next;
    }
    if (dataBytes!==null && byteRate) facts.duration=dataBytes/byteRate;
    if (trailing) add('TRAILING',declaredEnd,bytes.length,trailing,trailing,'trailing','warning','Outside declared container');
  } else {
    add(format==='FLAC'?'fLaC':format==='MP3'?'MPEG / ID3':'UNRECOGNIZED',0,bytes.length,bytes.length,bytes.length,format==='Unknown'?'unknown':'audio',format==='Unknown'?'warning':'ok');
    warnings.push({severity:'warning',message:format==='Unknown'?'Unrecognized or unsupported file signature.':'Full structure and metadata for this format require the local backend.',offset:0});
  }
  const extension=(file.name.match(/\.[^.]+$/)?.[0] || '').toLowerCase();
  const expected:Record<string,string[]>={WAV:['.wav','.wave'],AIFF:['.aif','.aiff'],AIFC:['.aifc','.aif','.aiff'],FLAC:['.flac'],MP3:['.mp3']};
  const mismatch=format!=='Unknown' && !expected[format].includes(extension);
  if (mismatch) warnings.unshift({severity:'warning',message:`Extension ${extension || '(none)'} does not match detected ${format} format.`,offset:0});
  const heuristics:Analysis['heuristics']=[];
  for (const key of new Set(metadata.map(x=>x.key))) {
    const count=metadata.filter(x=>x.key===key).length;
    if (count>1) heuristics.push({kind:'Duplicate metadata',detail:`RIFF INFO ${key} occurs ${count} times.`,offset:null});
  }
  return {bytes,analysis:{filename:file.name,size:bytes.length,sha256,magic:Array.from(bytes.slice(0,12),b=>b.toString(16).padStart(2,'0').toUpperCase()).join(' '),format,extension,extension_mismatch:mismatch,facts,chunks,metadata,artwork:[],warnings,heuristics,trailing_bytes:trailing}};
}
