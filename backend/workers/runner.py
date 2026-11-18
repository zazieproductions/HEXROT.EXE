"""Cancelable sandboxed processes with bounded output and resource sampling."""
from __future__ import annotations
import json
import os
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path
import psutil
from backend.decoders.adapters import accepted, command, interpret, inventory
from backend.workers.isolation import isolated_command


def execute(path: Path, decoder: str, timeout: float, memory_mb: int, cancel: threading.Event | None = None, on_start=None) -> dict:
    from platform import system
    target = '/input/audio' if system() == 'Linux' else str(path)
    logical = command(decoder,target)
    actual, safe = isolated_command(path,logical,memory_mb,timeout)
    versions = {x['id']:x['version'] for x in inventory()}
    start = time.monotonic(); peak = 0; cpu = 0.0; timed_out = False; canceled = False; resource_exceeded = None
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        proc = subprocess.Popen(actual, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                start_new_session=True)
        if on_start: on_start(proc.pid)
        try:
            while proc.poll() is None:
                try:
                    parent = psutil.Process(proc.pid)
                    children = [parent,*parent.children(recursive=True)]
                    current_rss = sum(p.memory_info().rss for p in children if p.is_running())
                    current_cpu = sum(sum(p.cpu_times()[:2]) for p in children if p.is_running())
                    peak = max(peak,current_rss)
                    cpu = max(cpu,current_cpu)
                    if len(children) > 32: resource_exceeded = 'sampled process-tree count limit'
                    if current_rss > memory_mb * 1024 * 1024: resource_exceeded = 'sampled process-tree memory limit'
                    if current_cpu > timeout: resource_exceeded = 'sampled process-tree CPU limit'
                except (psutil.Error, ProcessLookupError): pass
                if cancel and cancel.is_set(): canceled = True
                if time.monotonic()-start >= timeout: timed_out = True
                if canceled or timed_out or resource_exceeded:
                    try: os.killpg(proc.pid,signal.SIGKILL)
                    except ProcessLookupError: pass
                    break
                time.sleep(.02)
            proc.wait(timeout=3)
        finally:
            if proc.poll() is None:
                try: os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError: pass
                proc.wait()
            if on_start: on_start(None)
        if cancel and cancel.is_set(): canceled = True
        stdout.seek(0); envelope = stdout.read(1024*1024)
        stderr.seek(0); sandbox_error = stderr.read(65536).decode('utf-8','replace')
    elapsed = round(time.monotonic()-start,4)
    infrastructure_error = None
    child = None
    if not canceled and not timed_out and not resource_exceeded:
        try:
            child = json.loads(envelope)
            if not isinstance(child.get('returncode'),int): raise ValueError('missing child status')
        except (ValueError,TypeError,AttributeError):
            infrastructure_error = f'Sandbox supervisor failed (exit {proc.returncode}): {sandbox_error[:500]}'
    code = child['returncode'] if child else None
    limit_signals = {getattr(signal, 'SIGXCPU', -999), getattr(signal, 'SIGXFSZ', -998)}
    if code is not None and code < 0 and -code in limit_signals:
        resource_exceeded = 'process CPU or file-size limit signal'
    output = child['stdout'] if child else ''
    errors = child['stderr'] if child else sandbox_error
    fields = interpret(decoder,output)
    logical_safe = [('<INPUT>' if x == str(path) else x) for x in logical]
    return {'decoder':decoder, 'version':versions.get(decoder), 'invocation':logical_safe, 'sandbox_invocation':safe,
            'exit_code':code, 'sandbox_exit_code':proc.returncode, 'infrastructure_error':infrastructure_error,
            'accepted':accepted(decoder,code,output,errors) if child else None, 'resource_exceeded':resource_exceeded,
            'abnormal':bool(code is not None and code < 0 and not resource_exceeded), 'signal':-code if code is not None and code < 0 else None,
            'stdout':output,'stderr':errors,'stdout_truncated':child['stdout_truncated'] if child else False,
            'stderr_truncated':child['stderr_truncated'] if child else False,
            'duration_seconds':elapsed,'timed_out':timed_out,'canceled':canceled,'peak_memory_bytes':peak or None,
            'cpu_seconds':round(cpu,3),'limits':{'timeout_seconds':timeout,'memory_mb':memory_mb,'output_bytes':65536,'process_tree_count':32,'per_uid_process_rlimit':512}, **fields}
