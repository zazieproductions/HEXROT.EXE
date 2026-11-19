# Security Policy

## Intended Use

Use HEXROT.EXE only with files and decoders you are authorized to examine. A parser discrepancy, malformed-file rejection, resource limit, or crash is an observation, not proof of exploitable memory corruption or code execution. Do not add exploit payloads or automatic exploitation.

## Threat Model

Uploaded files and their metadata are untrusted. Filenames are sanitized, stored paths are generated UUIDs, API file access is by session/file ID, and data is rendered as text rather than HTML. The backend rejects non-loopback clients, unexpected Host headers, and non-local browser origins. The service has no authentication and is not designed to resist a hostile process already running as the same local user. Do not bind it to a public address, expose it via a tunnel, or rely on browser-origin checks as a substitute for OS access control.

Python binary parsing and Mutagen metadata extraction happen in the backend, outside the decoder sandbox. Malicious media may trigger denial of service or flaws in dependencies. The upload limit is 32 MiB; individual metadata output and structure loops are bounded where implemented. Use a disposable VM or a dedicated research machine for high-risk files.

Decoder processes are disabled unless the OS sandbox's basic self-test succeeds. On Linux, bubblewrap creates isolated namespaces including a network namespace, exposes only read-only system directories and the selected input, and uses a 16 MiB tmpfs. On macOS, a deny-by-default `sandbox-exec` profile (v0.2.0) permits only the interpreter, decoder, input, and supervisor for reads; no `process-fork`, no `mach-lookup`, no `file-write*` except `/dev/null`, no network access. macOS support is not independently verified on current Apple Silicon and `sandbox-exec` is deprecated by Apple. Both mechanisms share the host kernel, may have policy or kernel flaws, and are not complete containment.

Per-process rlimits constrain address space, CPU, file size, open descriptors, and core dumps; the process-count rlimit is 512 per real UID because Linux also counts other desktop threads for that user. A wall-clock timeout and sampled process-tree RSS, CPU, and 32-process monitor add controls. Aggregate sampling is approximate and is not equivalent to a cgroup memory or CPU quota. Captured stdout/stderr are capped at 64 KiB each. Only one decoder job may run at a time.

Reports redact the local workspace path, but file metadata and decoder logs are evidence and can contain sensitive information from the input. Review exports before sharing. System executable paths and tool versions may appear in invocations.

## Reporting

Please report suspected security issues privately through the hosting repository's security advisory mechanism or directly to the maintainers. Include affected versions, minimal harmless reproducer, observed impact, and isolation details. Do not publish a working exploit or unrelated private data. Coordinate disclosure with affected decoder maintainers; confirm findings independently before assigning a CVE or claiming exploitability.
