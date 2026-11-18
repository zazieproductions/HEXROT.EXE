"""Fixed decoder adapters. No user-controlled executable or shell syntax."""
from __future__ import annotations
import re
import subprocess
import os
from pathlib import Path

ADAPTERS = {
    'ffmpeg': {'executable':'ffmpeg', 'version_args':['-version'], 'label':'FFmpeg'},
    'ffprobe': {'executable':'ffprobe', 'version_args':['-version'], 'label':'ffprobe'},
    'sndfile-info': {'executable':'sndfile-info', 'version_args':['--version'], 'label':'libsndfile / sndfile-info'},
}


def executable_for(name: str) -> str | None:
    """Resolve only fixed tool names in fixed system/package-manager directories."""
    if name not in {item['executable'] for item in ADAPTERS.values()}:
        return None
    for directory in ('/usr/bin', '/usr/local/bin', '/opt/homebrew/bin', '/opt/local/bin'):
        candidate = Path(directory) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            resolved = candidate.resolve()
            if any(str(resolved).startswith(root + '/') for root in ('/usr', '/opt/homebrew', '/opt/local')):
                return str(resolved)
    return None


def inventory() -> list[dict]:
    result = []
    for key, adapter in ADAPTERS.items():
        path = executable_for(adapter['executable'])
        version = None
        if path:
            try:
                if key == 'sndfile-info':
                    import ctypes
                    import ctypes.util
                    library = ctypes.CDLL(ctypes.util.find_library('sndfile'))
                    library.sf_version_string.restype = ctypes.c_char_p
                    version = library.sf_version_string().decode('utf-8', 'replace')
                else:
                    proc = subprocess.run([path, *adapter['version_args']], capture_output=True, text=True, timeout=2, env={'PATH':'/usr/bin:/bin:/opt/homebrew/bin'})
                    version = (proc.stdout or proc.stderr).splitlines()[0][:200]
            except (OSError, subprocess.TimeoutExpired, TypeError, AttributeError): version = 'Version unavailable'
        result.append({'id':key,'label':adapter['label'],'available':bool(path),'version':version})
    return result


def command(decoder: str, input_path: str) -> list[str]:
    if decoder not in ADAPTERS: raise ValueError('Decoder is not allowlisted')
    executable = executable_for(ADAPTERS[decoder]['executable'])
    if not executable: raise ValueError(f'{decoder} is not installed')
    if decoder == 'ffmpeg':
        return [executable,'-v','error','-nostdin','-threads','1','-i',input_path,'-map','0:a:0','-f','hash','-hash','sha256','-']
    if decoder == 'ffprobe':
        return [executable,'-v','error','-show_entries','format=duration:stream=codec_name,sample_rate,channels,bits_per_sample,duration','-of','json',input_path]
    return [executable,input_path]


def interpret(decoder: str, stdout: str) -> dict:
    result: dict = {'duration':None,'channels':None,'sample_rate':None,'output_sha256':None}
    if decoder == 'ffmpeg':
        match = re.search(r'SHA256=([0-9a-fA-F]{64})', stdout)
        if match: result['output_sha256'] = match.group(1).lower()
    elif decoder == 'ffprobe':
        import json
        try:
            data = json.loads(stdout)
            stream = next((s for s in data.get('streams',[]) if 'channels' in s), {})
            result['channels'] = stream.get('channels')
            if stream.get('sample_rate'): result['sample_rate'] = int(stream['sample_rate'])
            duration = stream.get('duration') or data.get('format',{}).get('duration')
            if duration not in (None, 'N/A'): result['duration'] = float(duration)
        except (ValueError, TypeError, AttributeError): pass
    elif decoder == 'sndfile-info':
        for key, pattern in [('channels', r'Channels\s*:\s*(\d+)'), ('sample_rate', r'Sample Rate\s*:\s*(\d+)')]:
            match = re.search(pattern, stdout, re.I)
            if match: result[key] = int(match.group(1))
        match = re.search(r'Duration\s*:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', stdout)
        if match: result['duration'] = int(match.group(1))*3600 + int(match.group(2))*60 + float(match.group(3))
    return result


def accepted(decoder: str, exit_code: int, stdout: str, stderr: str) -> bool | None:
    """sndfile-info can exit zero even when it cannot open the input."""
    if exit_code != 0:
        return False
    if decoder == 'sndfile-info':
        output = stdout + '\n' + stderr
        if re.search(r'(?im)^Error\s*:\s*Not able to open input file', output) or 'Format not recognised.' in output:
            return False
        if re.search(r'(?im)^\s*Sample Rate\s*:\s*\d+', output) and re.search(r'(?im)^\s*Channels\s*:\s*\d+', output):
            return True
        return None
    return True
