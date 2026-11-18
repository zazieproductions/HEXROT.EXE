"""Metadata extraction and explicitly labeled, non-security heuristics."""
from __future__ import annotations
import hashlib
import re
from collections import Counter
from pathlib import Path
from typing import Any

MAX_TEXT = 4096


def text_value(raw: bytes) -> tuple[str, bool]:
    raw = raw.rstrip(b'\0')
    try:
        return raw.decode('utf-8'), False
    except UnicodeDecodeError:
        return raw.decode('utf-8', errors='replace'), True


def add_metadata(result: dict[str, Any], key: str, raw: bytes, source: str, offset: int | None) -> None:
    value, malformed = text_value(raw)
    result['metadata'].append({'key': key, 'value': value[:MAX_TEXT], 'source': source,
                               'offset': offset, 'byte_length': len(raw), 'truncated': len(value) > MAX_TEXT})
    if malformed:
        result['heuristics'].append({'kind': 'Malformed text encoding', 'detail': f'{source} {key} is not valid UTF-8.', 'offset': offset})
    inspect_text(result, key, value, len(raw), offset)


def inspect_text(result: dict[str, Any], key: str, value: str, size: int, offset: int | None) -> None:
    if size > MAX_TEXT:
        result['heuristics'].append({'kind': 'Large metadata field', 'detail': f'{key} contains {size} bytes.', 'offset': offset})
    if '\ufffd' in value or any(ord(c) < 32 and c not in '\t\r\n' for c in value):
        result['heuristics'].append({'kind': 'Unusual text characters', 'detail': f'{key} contains replacement or control characters.', 'offset': offset})
    if re.search(r'(?i)\b(?:https?|ftp)://', value):
        result['heuristics'].append({'kind': 'URL in metadata', 'detail': f'{key} contains a URL; it was not opened.', 'offset': offset})
    if re.search(r'(?:[A-Za-z]:\\|/[^\s/]+/|\.\.[/\\])', value):
        result['heuristics'].append({'kind': 'Path-like text', 'detail': f'{key} contains a path-like string; it was not accessed.', 'offset': offset})


def extract_mutagen(path: Path, result: dict[str, Any]) -> None:
    """Mutagen is supplementary; raw parser output stays authoritative for offsets."""
    try:
        import mutagen
        audio = mutagen.File(path)
        if audio is None:
            return
        info = getattr(audio, 'info', None)
        if info:
            for target, source in [('sample_rate', 'sample_rate'), ('channels', 'channels'), ('bit_depth', 'bits_per_sample'), ('duration', 'length')]:
                val = getattr(info, source, None)
                if result['facts'].get(target) is None and isinstance(val, (int, float)):
                    result['facts'][target] = round(val, 6) if isinstance(val, float) else val
        tags = getattr(audio, 'tags', None)
        if tags:
            for key, item in list(tags.items())[:500]:
                # ID3 picture frames may contain megabytes; only expose their fingerprint.
                if hasattr(item, 'data') and isinstance(item.data, bytes):
                    data = item.data
                    result['artwork'].append({'source': 'Mutagen / ' + str(key), 'mime': str(getattr(item, 'mime', 'unknown')),
                                              'byte_length': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
                    continue
                values = getattr(item, 'text', item)
                if not isinstance(values, (list, tuple)):
                    values = [values]
                for value in values[:50]:
                    if isinstance(value, bytes):
                        continue
                    text = str(value)
                    # RIFF INFO and AIFF text are already extracted with byte offsets.
                    result['metadata'].append({'key': str(key), 'value': text[:MAX_TEXT], 'source': 'Mutagen', 'offset': None,
                                               'byte_length': len(text.encode('utf-8', 'replace')), 'truncated': len(text) > MAX_TEXT})
                    inspect_text(result, str(key), text, len(text.encode('utf-8', 'replace')), None)
        for picture in getattr(audio, 'pictures', [])[:50]:
            data = getattr(picture, 'data', b'')
            result['artwork'].append({'source': 'FLAC picture', 'mime': str(getattr(picture, 'mime', 'unknown')),
                                      'byte_length': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    except Exception as exc:
        result['warnings'].append({'severity': 'warning', 'message': f'Mutagen could not fully parse metadata: {type(exc).__name__}: {str(exc)[:180]}', 'offset': None})


def duplicate_heuristics(result: dict[str, Any]) -> None:
    counts = Counter((m['source'], m['key'].upper()) for m in result['metadata'])
    for (source, key), count in counts.items():
        if count > 1:
            result['heuristics'].append({'kind': 'Duplicate metadata', 'detail': f'{source} {key} occurs {count} times.', 'offset': None})
