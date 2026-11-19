"""Seeded, bounded byte edits. Offsets are recorded in execution order.

Every mutation is reproducible from (original_bytes, analysis, strategy, seed, index,
limit, region, metadata_size). No mutation is applied to the original — a copy is edited.
"""
from __future__ import annotations
import hashlib
import random
import struct
import time
from typing import Any
from backend.config import MAX_FILE_SIZE, MAX_METADATA_VALUE

STRATEGIES = ['header_boundary','chunk_length','truncation','duplicate_metadata','metadata_value',
              'invalid_encoding','signature','trailing','chunk_order','seeded_bytes',
              'boundary_min','boundary_max','boundary_off_by_one','zero_length_field',
              'max_syncsafe','negative_duration']
DEFAULT_STRATEGIES = ['header_boundary','chunk_length','truncation','signature','trailing']

# Additional boundary-value strategies introduced in v0.2.0
BOUNDARY_STRATEGIES = {'boundary_min','boundary_max','boundary_off_by_one','zero_length_field',
                       'max_syncsafe','negative_duration'}


class MutationError(ValueError): pass


class Editor:
    def __init__(self, data: bytes, limit: int):
        self.data = bytearray(data)
        self.edits: list[dict[str, Any]] = []
        self.limit = min(limit, MAX_FILE_SIZE)

    def replace(self, offset: int, length: int, new: bytes, description: str) -> None:
        if offset < 0 or length < 0 or offset + length > len(self.data): raise MutationError('Edit out of bounds')
        if len(self.data) - length + len(new) > self.limit: raise MutationError('Mutation exceeds configured file-size limit')
        old = bytes(self.data[offset:offset+length])
        self.data[offset:offset+length] = new
        self.edits.append({'offset':offset, 'old_length':len(old), 'new_length':len(new),
            'before_hex':old[:128].hex(), 'after_hex':new[:128].hex(),
            'before_sha256':hashlib.sha256(old).hexdigest(), 'after_sha256':hashlib.sha256(new).hexdigest(),
            'preview_truncated':len(old)>128 or len(new)>128, 'description':description})


def generate(original: bytes, analysis: dict, strategy: str, seed: int, index: int, limit: int = MAX_FILE_SIZE, region: str = 'any', metadata_size: int = 8192) -> tuple[bytes, dict]:
    if strategy not in STRATEGIES: raise MutationError(f'Unknown strategy: {strategy}')
    if not original: raise MutationError('Cannot mutate an empty file')
    if len(original) > limit or not 0 <= metadata_size <= MAX_METADATA_VALUE: raise MutationError('Invalid mutation size limit')
    rng = random.Random(f'{seed}:{index}:{strategy}')
    ed = Editor(original, limit)
    fmt = analysis['format']
    chunks = [c for c in analysis['chunks'] if c['kind'] in ('chunk','metadata') and c['end'] > c['offset']]
    endian = 'big' if fmt in ('AIFF','AIFC','FLAC') else 'little'
    if strategy == 'header_boundary':
        if fmt in ('WAV','AIFF','AIFC') and len(original)>=8:
            ed.replace(4,4,rng.choice([0, 1, 0xffffffff]).to_bytes(4,endian), 'Set container size to a boundary value')
        elif fmt == 'FLAC' and len(original)>=8:
            ed.replace(5,3,b'\xff\xff\xff','Set metadata block length to maximum')
        elif fmt == 'MP3' and original.startswith(b'ID3') and len(original)>=10:
            ed.replace(6,4,b'\x7f\x7f\x7f\x7f','Set ID3 tag size to maximum syncsafe value')
        else: raise MutationError('No supported header size field in this file')
    elif strategy == 'chunk_length':
        choices = [c for c in chunks if c['kind'] == 'chunk']
        if fmt in ('WAV','AIFF','AIFC') and choices:
            c = rng.choice(choices); ed.replace(c['offset']+4,4,(0xffffffff).to_bytes(4,endian),f'Inflate {c["name"]} declared chunk size')
        elif fmt == 'FLAC' and chunks:
            c = rng.choice(chunks); ed.replace(c['offset']+1,3,b'\xff\xff\xff','Inflate FLAC metadata block size')
        else: raise MutationError('No supported chunk size field in this file')
    elif strategy == 'truncation':
        cut = max(1, len(original) - max(1, rng.randrange(1, max(2, len(original)//3))))
        ed.replace(cut,len(original)-cut,b'', 'Truncate the file at this offset')
    elif strategy == 'signature':
        count = min(4,len(original)); ed.replace(0,count,b'XROT'[:count], 'Replace container signature')
    elif strategy == 'trailing':
        extra = bytes(rng.randrange(256) for _ in range(24))
        ed.replace(len(original),0,extra,'Append seeded non-audio bytes')
    elif strategy == 'seeded_bytes':
        candidates = [c for c in analysis['chunks'] if c['end'] > c['offset']]
        if region != 'any': candidates = [c for c in candidates if c['id'] == region or c['name'] == region]
        if not candidates: raise MutationError('Selected structural region is unavailable')
        c = rng.choice(candidates); offset = rng.randrange(c['offset'], min(c['end'],len(original)))
        ed.replace(offset,1,bytes([original[offset] ^ (1 << rng.randrange(8))]), f'Flip a seeded bit in {c["name"]}')
    elif strategy == 'chunk_order':
        choices = sorted([c for c in chunks if c['kind'] == 'chunk'], key=lambda c:c['offset'])
        if len(choices)<2: raise MutationError('At least two container chunks are required')
        a,b = choices[:2]
        if a['end'] != b['offset']: raise MutationError('First chunks are not adjacent')
        ed.replace(a['offset'], b['end']-a['offset'], original[b['offset']:b['end']] + original[a['offset']:a['end']], 'Swap first two adjacent chunks')
    elif strategy in ('duplicate_metadata','metadata_value'):
        info = next((c for c in chunks if c['name']=='LIST' and original[c['offset']+8:c['offset']+12] == b'INFO'), None)
        if fmt != 'WAV' or not info: raise MutationError('A RIFF INFO list is required for this metadata strategy')
        sub = info['offset']+12
        if sub+8>info['end']: raise MutationError('INFO list has no complete field')
        old_size = int.from_bytes(original[sub+4:sub+8],'little')
        old_end = sub+8+old_size+(old_size&1)
        if old_end>info['end']: raise MutationError('First INFO field is truncated')
        if strategy == 'duplicate_metadata':
            payload = original[sub:old_end]
            delta = len(payload)
            ed.replace(4,4,(int.from_bytes(original[4:8],'little')+delta).to_bytes(4,'little'),'Update RIFF size for duplicate field')
            ed.replace(info['offset']+4,4,(info['declared_size']+delta).to_bytes(4,'little'),'Update INFO list size')
            ed.replace(old_end,0,payload,'Duplicate first INFO field')
        else:
            size = rng.choice([0, min(metadata_size,MAX_METADATA_VALUE)])
            value = b'A'*size
            payload = value + (b'\0' if size & 1 else b'')
            delta = len(payload) - (old_end-(sub+8))
            ed.replace(4,4,(int.from_bytes(original[4:8],'little')+delta).to_bytes(4,'little'),'Update RIFF size for metadata value')
            ed.replace(info['offset']+4,4,(info['declared_size']+delta).to_bytes(4,'little'),'Update INFO list size')
            ed.replace(sub+4,4,size.to_bytes(4,'little'),'Set metadata value length')
            ed.replace(sub+8,old_end-(sub+8),payload,'Replace metadata value with empty or bounded oversized value')
    elif strategy == 'invalid_encoding':
        frame = next((c for c in chunks if c['name'].startswith('T') and c['kind']=='metadata' and c['actual_size']>0),None)
        if fmt != 'MP3' or not frame: raise MutationError('An ID3v2 text frame is required')
        ed.replace(frame['offset']+10,1,b'\xff','Set invalid ID3 text encoding marker')
    elif strategy == 'boundary_min':
        # Set a container/chunk size field to zero to test zero-length handling
        if fmt in ('WAV','AIFF','AIFC') and len(original) >= 8:
            choices = [c for c in chunks if c['kind'] == 'chunk' and c['actual_size'] > 0]
            if choices:
                c = rng.choice(choices)
                ed.replace(c['offset']+4, 4, b'\x00\x00\x00\x00', f'Set {c["name"]} chunk size to zero')
            else:
                raise MutationError('No chunk with non-zero size available for boundary_min')
        elif fmt == 'FLAC' and len(original) >= 8:
            if chunks:
                c = rng.choice([c for c in chunks if c['actual_size'] > 0])
                ed.replace(c['offset']+1, 3, b'\x00\x00\x00', f'Set {c["name"]} block size to zero')
            else:
                raise MutationError('No metadata block available for boundary_min')
        else:
            raise MutationError('Format not supported for boundary_min')
    elif strategy == 'boundary_max':
        # Set a container size to a value larger than the file
        if fmt in ('WAV','AIFF','AIFC') and len(original) >= 8:
            inflated = len(original) * 4
            ed.replace(4, 4, min(inflated, 0xffffffff).to_bytes(4, endian), 'Set container size to 4x file length')
        else:
            raise MutationError('Format not supported for boundary_max')
    elif strategy == 'boundary_off_by_one':
        # Set a chunk size to actual_size + 1 or actual_size - 1 to test off-by-one
        if fmt in ('WAV','AIFF','AIFC'):
            choices = [c for c in chunks if c['kind'] == 'chunk' and c['actual_size'] >= 2]
            if choices:
                c = rng.choice(choices)
                delta = rng.choice([-1, 1])
                new_size = max(0, c['actual_size'] + delta)
                ed.replace(c['offset']+4, 4, new_size.to_bytes(4, endian),
                           f'Set {c["name"]} chunk size to actual_size {delta:+d} (off-by-one)')
            else:
                raise MutationError('No suitable chunk for off-by-one boundary')
        else:
            raise MutationError('Format not supported for boundary_off_by_one')
    elif strategy == 'zero_length_field':
        # Set a declared field length to 0 while leaving surrounding data intact
        if fmt == 'WAV' and len(original) >= 12:
            # Set the fmt chunk body size to 0
            fmt_chunk = next((c for c in chunks if c['name'] == 'fmt '), None)
            if fmt_chunk and fmt_chunk['actual_size'] > 0:
                ed.replace(fmt_chunk['offset']+4, 4, b'\x00\x00\x00\x00', 'Set fmt chunk size to zero')
            else:
                raise MutationError('No fmt chunk for zero_length_field')
        elif fmt == 'MP3' and original.startswith(b'ID3') and len(original) >= 10:
            ed.replace(6, 4, b'\x00\x00\x00\x00', 'Set ID3 tag size to zero')
        else:
            raise MutationError('Format not supported for zero_length_field')
    elif strategy == 'max_syncsafe':
        # Set ID3 tag size to the maximum valid syncsafe value
        if fmt == 'MP3' and original.startswith(b'ID3') and len(original) >= 10:
            ed.replace(6, 4, b'\x7f\x7f\x7f\x7f', 'Set ID3 tag size to maximum syncsafe (0x0FFFFFFF)')
        else:
            raise MutationError('An ID3v2 header is required for max_syncsafe')
    elif strategy == 'negative_duration':
        # Manipulate the sample rate or frame count to produce an impossible duration
        if fmt == 'WAV' and len(original) >= 44:
            # Set sample rate to 0 in fmt chunk
            fmt_chunk = next((c for c in chunks if c['name'] == 'fmt '), None)
            if fmt_chunk and fmt_chunk['actual_size'] >= 16:
                # Sample rate is at offset +8..+12 in fmt body (offset +16 from chunk start)
                ed.replace(fmt_chunk['offset']+8+8, 4, b'\x00\x00\x00\x00', 'Set sample rate to zero (infinite/undefined duration)')
            else:
                raise MutationError('fmt chunk too small for negative_duration')
        elif fmt in ('AIFF','AIFC'):
            comm_chunk = next((c for c in chunks if c['name'] == 'COMM'), None)
            if comm_chunk and comm_chunk['actual_size'] >= 18:
                # Set numSampleFrames to 0
                ed.replace(comm_chunk['offset']+8+4, 4, b'\x00\x00\x00\x00', 'Set AIFF numSampleFrames to zero')
            else:
                raise MutationError('COMM chunk too small for negative_duration')
        else:
            raise MutationError('Format not supported for negative_duration')
    result = bytes(ed.data)
    if result == original: raise MutationError('The requested strategy made no byte changes to this input')
    history = {
        'strategy': strategy, 'seed': seed, 'index': index, 'region': region,
        'size_limit': limit, 'metadata_size': metadata_size,
        'edits': ed.edits,
        'original_sha256': hashlib.sha256(original).hexdigest(),
        'original_size': len(original),
        'sha256': hashlib.sha256(result).hexdigest(),
        'result_size': len(result),
        'format': fmt,
        'reproducible': True,
        'reproduction_inputs': {
            'seed': seed, 'strategy': strategy, 'index': index,
            'region': region, 'size_limit': limit, 'metadata_size': metadata_size,
            'original_sha256': hashlib.sha256(original).hexdigest(),
        },
    }
    return result, history


def generate_batch(original: bytes, analysis: dict, count: int, seed: int,
                   strategies: list[str], limit: int = MAX_FILE_SIZE,
                   region: str = 'any', metadata_size: int = 8192,
                   deduplicate: bool = True) -> list[tuple[bytes, dict]]:
    """Generate up to `count` mutations, cycling through strategies.

    When deduplicate=True, mutations that produce an output hash identical to a
    previous result (or identical to the original) are skipped and not counted.
    The function always attempts exactly `count` generation calls, but may return
    fewer results if deduplication eliminates duplicates.
    """
    seen_hashes: set[str] = {hashlib.sha256(original).hexdigest()}
    outputs: list[tuple[bytes, dict]] = []
    for i in range(count):
        strategy = strategies[i % len(strategies)]
        try:
            data, history = generate(original, analysis, strategy, seed, i, limit, region, metadata_size)
        except MutationError:
            continue
        output_hash = history['sha256']
        if deduplicate and output_hash in seen_hashes:
            continue
        seen_hashes.add(output_hash)
        outputs.append((data, history))
    return outputs
