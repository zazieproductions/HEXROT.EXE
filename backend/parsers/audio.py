"""Bounded binary parsers for RIFF/WAVE, AIFF/AIFC, FLAC and ID3/MP3."""
from __future__ import annotations
import hashlib
import math
import struct
from pathlib import Path
from typing import Any
from backend.metadata.inspection import add_metadata, duplicate_heuristics, extract_mutagen


def warning(result: dict, message: str, offset: int | None = None, severity: str = 'warning') -> None:
    result['warnings'].append({'severity': severity, 'message': message, 'offset': offset})


def label(raw: bytes) -> str:
    return ''.join(chr(c) if 32 <= c <= 126 else '.' for c in raw)


def add_chunk(result: dict, name: str, start: int, end: int, declared: int, actual: int, kind: str = 'chunk', status: str = 'ok', detail: str = '') -> dict:
    item = {'id': f'{start:08x}-{len(result["chunks"])}', 'name': name, 'offset': start, 'end': end,
            'declared_size': declared, 'actual_size': actual, 'kind': kind, 'status': status, 'detail': detail}
    result['chunks'].append(item)
    return item


def extended80(raw: bytes) -> float | None:
    if len(raw) != 10:
        return None
    exponent = int.from_bytes(raw[:2], 'big')
    mantissa = int.from_bytes(raw[2:], 'big')
    if not exponent and not mantissa:
        return 0.0
    if exponent & 0x7fff == 0x7fff:
        return None
    try:
        value = math.ldexp(mantissa / (1 << 63), (exponent & 0x7fff) - 16383)
        value = -value if exponent & 0x8000 else value
        return value if math.isfinite(value) and 0 < value < 10000000 else None
    except OverflowError:
        return None


def parse_info(data: bytes, body: int, end: int, result: dict) -> None:
    if body + 4 > end or data[body:body+4] != b'INFO':
        return
    pos = body + 4
    while pos + 8 <= end:
        key = label(data[pos:pos+4])
        size = int.from_bytes(data[pos+4:pos+8], 'little')
        stop = min(pos + 8 + size, end)
        add_metadata(result, key, data[pos+8:stop], 'RIFF INFO', pos + 8)
        if pos + 8 + size > end:
            warning(result, f'INFO field {key} declares {size} bytes but only {max(0, end-pos-8)} remain.', pos)
            break
        pos += 8 + size + (size & 1)
    if pos < end and end - pos < 8:
        warning(result, f'{end-pos} unparsed byte(s) at end of INFO list.', pos)


def parse_riff_aiff(data: bytes, result: dict, fmt: str) -> None:
    endian = 'little' if fmt == 'WAV' else 'big'
    if len(data) < 12:
        warning(result, 'Container header is truncated.', 0, 'error')
        return
    declared = int.from_bytes(data[4:8], endian)
    expected_end = 8 + declared
    limit = min(len(data), expected_end)
    add_chunk(result, 'RIFF' if fmt == 'WAV' else 'FORM', 0, 12, declared, max(0, len(data)-8), 'container', 'warning' if expected_end != len(data) else 'ok', 'Container header')
    if expected_end > len(data):
        warning(result, f'Container declares {expected_end} bytes, but file contains {len(data)}.', 4)
    if expected_end < len(data):
        result['trailing_bytes'] = len(data) - expected_end
        warning(result, f'{len(data)-expected_end} trailing byte(s) follow the declared container.', expected_end)
        add_chunk(result, 'TRAILING', expected_end, len(data), len(data)-expected_end, len(data)-expected_end, 'trailing', 'warning', 'Outside declared container')
    pos = 12
    data_bytes = None
    byte_rate = None
    while pos + 8 <= limit and len(result['chunks']) < 4096:
        raw_id = data[pos:pos+4]
        name = label(raw_id)
        size = int.from_bytes(data[pos+4:pos+8], endian)
        body = pos + 8
        actual = max(0, min(size, limit - body))
        body_end = body + actual
        padded_end = min(limit, body + size + (size & 1))
        truncated = size > limit - body
        add_chunk(result, name, pos, padded_end, size, actual, 'chunk', 'warning' if truncated else 'ok', 'Truncated chunk' if truncated else '')
        if truncated:
            warning(result, f'{name} chunk declares {size} bytes but only {actual} are available.', pos + 4)
        if fmt == 'WAV' and raw_id == b'fmt ' and actual >= 16:
            codec, channels, rate, byte_rate, align, bits = struct.unpack_from('<HHIIHH', data, body)
            result['facts'].update({'codec': {1:'PCM', 3:'IEEE float', 0xfffe:'Extensible'}.get(codec, f'WAVE codec 0x{codec:04X}'),
                                    'channels': channels, 'sample_rate': rate, 'bit_depth': bits, 'block_align': align})
        elif fmt == 'WAV' and raw_id == b'data':
            data_bytes = actual
        elif fmt == 'WAV' and raw_id == b'LIST':
            parse_info(data, body, body_end, result)
        elif fmt != 'WAV' and raw_id == b'COMM' and actual >= 18:
            channels, frames, bits = struct.unpack_from('>hIh', data, body)
            rate = extended80(data[body+8:body+18])
            codec = 'PCM' if fmt == 'AIFF' else (label(data[body+18:body+22]) if actual >= 22 else 'AIFC')
            result['facts'].update({'codec': codec, 'channels': channels, 'sample_rate': round(rate) if rate else None, 'bit_depth': bits,
                                    'duration': round(frames / rate, 6) if rate else None})
        elif fmt != 'WAV' and raw_id in (b'NAME', b'AUTH', b'ANNO', b'(c) '):
            add_metadata(result, name, data[body:body_end], 'AIFF', body)
        if truncated:
            break
        next_pos = body + size + (size & 1)
        if next_pos > limit:
            warning(result, f'{name} chunk is missing its alignment padding.', body + size)
            break
        pos = next_pos
    if pos < limit and limit - pos < 8:
        warning(result, f'{limit-pos} unparsed byte(s) inside the container.', pos)
    if data_bytes is not None and byte_rate:
        result['facts']['duration'] = round(data_bytes / byte_rate, 6)
    if len(result['chunks']) >= 4096:
        warning(result, 'Chunk count limit reached; remaining structure was not parsed.', pos)
    result['chunks'].sort(key=lambda c: c['offset'])


def parse_flac(data: bytes, result: dict) -> None:
    add_chunk(result, 'fLaC', 0, min(4, len(data)), 4, min(4, len(data)), 'container', detail='FLAC signature')
    pos, last = 4, False
    names = {0:'STREAMINFO', 1:'PADDING', 2:'APPLICATION', 3:'SEEKTABLE', 4:'VORBIS_COMMENT', 5:'CUESHEET', 6:'PICTURE'}
    while not last and pos + 4 <= len(data) and len(result['chunks']) < 4096:
        head = data[pos]
        last = bool(head & 0x80)
        typ = head & 0x7f
        size = int.from_bytes(data[pos+1:pos+4], 'big')
        actual = min(size, len(data)-pos-4)
        name = names.get(typ, f'BLOCK_{typ}')
        add_chunk(result, name, pos, pos+4+actual, size, actual, 'metadata', 'warning' if actual < size else 'ok')
        if actual < size:
            warning(result, f'{name} block declares {size} bytes but only {actual} are available.', pos)
            break
        if typ == 0 and actual >= 34:
            packed = int.from_bytes(data[pos+14:pos+22], 'big')
            rate = (packed >> 44) & 0xfffff
            channels = ((packed >> 41) & 7) + 1
            bits = ((packed >> 36) & 31) + 1
            samples = packed & ((1 << 36)-1)
            result['facts'].update({'codec':'FLAC', 'sample_rate':rate, 'channels':channels, 'bit_depth':bits,
                                    'duration':round(samples/rate, 6) if rate else None})
        pos += 4 + size
    if not last:
        warning(result, 'FLAC metadata blocks do not terminate cleanly.', pos)
    elif pos < len(data):
        add_chunk(result, 'AUDIO FRAMES', pos, len(data), len(data)-pos, len(data)-pos, 'audio')


def syncsafe(raw: bytes) -> int:
    val = 0
    for byte in raw:
        val = (val << 7) | (byte & 0x7f)
    return val


def parse_mp3(data: bytes, result: dict) -> None:
    pos = 0
    result['facts']['codec'] = 'MPEG audio'
    if data.startswith(b'ID3') and len(data) >= 10:
        version = data[3]
        size = syncsafe(data[6:10])
        end = min(len(data), 10 + size)
        add_chunk(result, f'ID3v2.{version}', 0, end, size, max(0,end-10), 'metadata', 'warning' if 10+size > len(data) else 'ok')
        if any(b & 0x80 for b in data[6:10]):
            warning(result, 'ID3 size contains non-syncsafe bytes.', 6)
        if 10+size > len(data):
            warning(result, 'ID3v2 tag extends past end of file.', 6)
        frame = 10
        if version in (3,4) and not data[5] & 0x40:
            while frame + 10 <= end:
                fid = data[frame:frame+4]
                if fid == b'\0\0\0\0':
                    break
                fs = syncsafe(data[frame+4:frame+8]) if version == 4 else int.from_bytes(data[frame+4:frame+8], 'big')
                stop = min(end, frame+10+fs)
                add_chunk(result, label(fid), frame, stop, fs, max(0,stop-frame-10), 'metadata', 'warning' if frame+10+fs>end else 'ok')
                if fid.startswith(b'T') and fs and frame+10 < end and data[frame+10] not in (0,1,2,3):
                    result['heuristics'].append({'kind':'Invalid ID3 text encoding marker', 'detail':f'{label(fid)} uses marker 0x{data[frame+10]:02X}.', 'offset':frame+10})
                if frame+10+fs > end:
                    warning(result, f'ID3 frame {label(fid)} exceeds tag bounds.', frame)
                    break
                frame += 10+fs
        pos = end
    if data[-128:-125] == b'TAG':
        tag = len(data)-128
        add_chunk(result, 'ID3v1', tag, len(data), 128, 128, 'metadata')
        for key, start, length in [('TITLE',3,30), ('ARTIST',33,30), ('ALBUM',63,30), ('YEAR',93,4), ('COMMENT',97,30)]:
            add_metadata(result, key, data[tag+start:tag+start+length].rstrip(b'\0 '), 'ID3v1', tag+start)
        audio_end = tag
    else:
        audio_end = len(data)
    if audio_end > pos:
        add_chunk(result, 'MPEG FRAMES', pos, audio_end, audio_end-pos, audio_end-pos, 'audio')
    result['chunks'].sort(key=lambda c:c['offset'])


def analyze(path: Path, filename: str) -> dict[str, Any]:
    data = path.read_bytes()
    ext = Path(filename).suffix.lower()
    if data.startswith(b'RIFF') and data[8:12] == b'WAVE': fmt = 'WAV'
    elif data.startswith(b'FORM') and data[8:12] in (b'AIFF', b'AIFC'): fmt = data[8:12].decode('ascii')
    elif data.startswith(b'fLaC'): fmt = 'FLAC'
    elif data.startswith(b'ID3') or (len(data) >= 2 and data[0] == 0xff and data[1] & 0xe0 == 0xe0): fmt = 'MP3'
    else: fmt = 'Unknown'
    expected = {'WAV': {'.wav','.wave'}, 'AIFF':{'.aiff','.aif'}, 'AIFC':{'.aifc','.aiff','.aif'}, 'FLAC':{'.flac'}, 'MP3':{'.mp3'}}
    result: dict[str, Any] = {'filename': filename, 'size':len(data), 'sha256':hashlib.sha256(data).hexdigest(),
        'magic':data[:12].hex(' ').upper(), 'format':fmt, 'extension':ext, 'extension_mismatch': fmt != 'Unknown' and ext not in expected[fmt],
        'facts':{'container':{'WAV':'RIFF / WAVE','AIFF':'FORM / AIFF','AIFC':'FORM / AIFC','FLAC':'FLAC','MP3':'MPEG audio'}.get(fmt, 'Unknown'),
                 'codec':None, 'sample_rate':None, 'channels':None, 'bit_depth':None, 'duration':None},
        'chunks':[], 'metadata':[], 'artwork':[], 'warnings':[], 'heuristics':[], 'trailing_bytes':0}
    if result['extension_mismatch']:
        warning(result, f'Extension {ext or "(none)"} does not match detected {fmt} format.', 0)
    if fmt in ('WAV','AIFF','AIFC'): parse_riff_aiff(data, result, fmt)
    elif fmt == 'FLAC': parse_flac(data, result)
    elif fmt == 'MP3': parse_mp3(data, result)
    else:
        warning(result, 'Unrecognized or unsupported file signature.', 0, 'error')
        add_chunk(result, 'UNRECOGNIZED', 0, len(data), len(data), len(data), 'unknown', 'warning')
    extract_mutagen(path, result)
    duplicate_heuristics(result)
    return result
