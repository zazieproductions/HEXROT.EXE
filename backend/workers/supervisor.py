"""Run inside the OS sandbox so waitpid preserves signal-vs-exit information."""
import json
import math
import resource
import os
import selectors
import subprocess
import sys

LIMIT = 65536


def parse_worker_arguments(argv: list[str]) -> tuple[int, float, list[str]]:
    """Parse only our fixed runner flags; decoder options remain untouched."""
    if len(argv) < 6 or argv[0] != '--hexrot-memory-mb' or argv[2] != '--hexrot-timeout' or argv[4] != '--':
        raise ValueError('Invalid HEXROT worker arguments')
    memory_mb, timeout = int(argv[1]), float(argv[3])
    if not (128 <= memory_mb <= 2048 and math.isfinite(timeout) and 0.25 <= timeout <= 30):
        raise ValueError('Decoder worker limits are outside permitted bounds')
    return memory_mb, timeout, argv[5:]


def apply_limits(memory_mb: int, timeout: float) -> None:
    """Apply inheritable OS limits within the already-sandboxed supervisor."""
    cpu = max(1, math.ceil(timeout) + 1)
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))
    resource.setrlimit(resource.RLIMIT_AS, (memory_mb * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if hasattr(resource, 'RLIMIT_NPROC'):
        resource.setrlimit(resource.RLIMIT_NPROC, (512, 512))


def main():
    memory_mb, timeout, command = parse_worker_arguments(sys.argv[1:])
    apply_limits(memory_mb, timeout)
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
    selector = selectors.DefaultSelector()
    buffers = {'stdout':bytearray(), 'stderr':bytearray()}
    truncated = {'stdout':False, 'stderr':False}
    for name, stream in [('stdout',process.stdout),('stderr',process.stderr)]:
        selector.register(stream,selectors.EVENT_READ,name)
    while selector.get_map():
        for key, _ in selector.select(timeout=0.1):
            data = os.read(key.fileobj.fileno(),8192)
            if not data:
                selector.unregister(key.fileobj); key.fileobj.close(); continue
            name = key.data
            remaining = LIMIT-len(buffers[name])
            buffers[name].extend(data[:max(0,remaining)])
            if len(data)>remaining: truncated[name] = True
    code = process.wait()
    print(json.dumps({'returncode':code, 'stdout':buffers['stdout'].decode('utf-8','replace'),
                      'stderr':buffers['stderr'].decode('utf-8','replace'), 'stdout_truncated':truncated['stdout'],
                      'stderr_truncated':truncated['stderr']}),flush=True)

if __name__ == '__main__':
    main()
