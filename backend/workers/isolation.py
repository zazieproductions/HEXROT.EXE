"""OS sandbox gates. A successful subprocess alone is never called isolation."""
from __future__ import annotations
import os
import platform
import subprocess
import sys
from functools import lru_cache
from pathlib import Path


def linux_base() -> list[str]:
    bwrap = next((str(Path(p).resolve()) for p in ('/usr/bin/bwrap','/usr/local/bin/bwrap') if Path(p).is_file() and os.access(p,os.X_OK)),None)
    if not bwrap: raise RuntimeError('bubblewrap is not installed')
    args = [bwrap,'--unshare-all','--unshare-user','--unshare-net','--disable-userns','--die-with-parent','--new-session']
    for path in ['/usr','/lib','/lib64','/bin']:
        if Path(path).exists(): args += ['--ro-bind',path,path]
    args += ['--dir','/etc']
    if Path('/etc/ld.so.cache').exists(): args += ['--ro-bind','/etc/ld.so.cache','/etc/ld.so.cache']
    # Debian's shared-library links can resolve through this read-only directory.
    if Path('/etc/alternatives').exists(): args += ['--ro-bind','/etc/alternatives','/etc/alternatives']
    args += ['--proc','/proc','--dev','/dev','--size','16777216','--tmpfs','/tmp','--dir','/input','--chdir','/tmp','--clearenv','--setenv','PATH','/usr/bin:/bin','--setenv','HOME','/tmp']
    return args


@lru_cache(maxsize=1)
def isolation_status() -> dict:
    system = platform.system()
    try:
        if system == 'Linux':
            proc = subprocess.run(linux_base()+['/usr/bin/true'], capture_output=True, timeout=5)
            if proc.returncode != 0:
                return {'available':False,'mechanism':'bubblewrap','reason':'Sandbox self-test failed: '+proc.stderr.decode(errors='replace')[:250]}
            return {'available':True,'mechanism':'bubblewrap (network namespace)','reason':'Sandbox self-test passed; workers have no host home mount or network namespace access.'}
        if system == 'Darwin':
            tool = '/usr/bin/sandbox-exec'
            if not Path(tool).is_file(): return {'available':False,'mechanism':'macOS sandbox-exec','reason':'sandbox-exec is unavailable on this macOS installation.'}
            profile = '(version 1)(deny default)(allow process-exec (literal "/usr/bin/true"))(allow file-read* (subpath "/usr") (subpath "/System"))(allow sysctl-read)(allow mach-lookup)'
            proc = subprocess.run([tool,'-p',profile,'/usr/bin/true'],capture_output=True,timeout=5)
            if proc.returncode != 0: return {'available':False,'mechanism':'macOS sandbox-exec','reason':'Sandbox self-test failed: '+proc.stderr.decode(errors='replace')[:250]}
            return {'available':True,'mechanism':'macOS sandbox-exec','reason':'Sandbox self-test passed; network and non-allowlisted file access are denied.'}
        return {'available':False,'mechanism':'none','reason':'Only Linux bubblewrap and macOS sandbox-exec are supported.'}
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
        return {'available':False,'mechanism':'OS sandbox','reason':f'Sandbox self-test failed: {exc}'}


def isolated_command(input_file: Path, decoder_command: list[str], memory_mb: int = 512, timeout: float = 5.0) -> tuple[list[str], list[str]]:
    status = isolation_status()
    if not status['available']: raise RuntimeError(status['reason'])
    if not (128 <= memory_mb <= 2048 and 0.25 <= timeout <= 30):
        raise ValueError('Decoder worker limits are outside permitted bounds')
    supervisor = Path(__file__).with_name('supervisor.py').resolve()
    # Set rlimits in the supervisor, not via subprocess.Popen(preexec_fn):
    # preexec_fn can deadlock when the API uses worker threads.
    worker_args = ['--hexrot-memory-mb', str(memory_mb), '--hexrot-timeout', str(timeout), '--', *decoder_command]
    if platform.system() == 'Linux':
        cmd = linux_base() + ['--dir','/worker','--ro-bind',str(supervisor),'/worker/supervisor.py',
                              '--ro-bind',str(input_file),'/input/audio','--','/usr/bin/python3','-I','-S','/worker/supervisor.py',*worker_args]
        safe = ['<INPUT>' if x == str(input_file) else '<SUPERVISOR>' if x == str(supervisor) else x for x in cmd]
        return cmd,safe
    def quote(value: str) -> str: return '"' + value.replace('\\','\\\\').replace('"','\\"') + '"'
    interpreter = str(Path(sys.executable).resolve())
    executable = decoder_command[0]
    profile = ('(version 1)(deny default)(allow process-fork)'
               '(allow process-exec (literal ' + quote(interpreter) + ') (literal ' + quote(executable) + '))'
               '(allow sysctl-read)(allow mach-lookup)(allow file-read* (subpath "/usr") (subpath "/System") (subpath "/dev") '
               '(subpath "/opt/homebrew") (subpath "/opt/local") (literal ' + quote(interpreter) + ') (literal ' + quote(str(input_file)) + ') (literal ' + quote(str(supervisor)) + '))'
               '(allow file-write* (subpath "/dev"))')
    actual = ['/usr/bin/sandbox-exec','-p',profile,interpreter,'-I','-S',str(supervisor),*worker_args]
    safe = [x.replace(str(input_file),'<INPUT>').replace(str(supervisor),'<SUPERVISOR>') for x in actual]
    return actual,safe
