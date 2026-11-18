# Local verification — v0.1.1

Environment: this container, Linux x86_64, Python 3.13.5, Node 22.16.0.

- `python scripts/generate_fixtures.py`: passed, generated deterministic WAV and AIFF fixtures.
- `python -m pytest -q`: **17 passed, 5 skipped**. Five tests require a working OS decoder sandbox and were skipped because the available environment lacks bubblewrap.
- Supervisor regression tests: executed harmless real child processes and confirmed exit-code reporting, invalid-limit rejection, and inherited `RLIMIT_AS`, `RLIMIT_CORE`, and `RLIMIT_NOFILE`.
- Frontend install: `npm ci --ignore-scripts --no-audit --no-fund --fetch-retries=0 --fetch-timeout=10000` failed because the sandbox could not reach the npm registry (`EAI_AGAIN`). Consequently, TypeScript compilation and frontend production build have not been independently verified here.
- Apple Silicon/macOS: not tested here. The macOS `sandbox-exec` profile is experimental, and an isolated Linux VM is recommended for untrusted files.

The historical original-build results in `docs/pytest-output.txt` and `docs/ui-e2e-output.json` are preserved for provenance; they are not evidence that the revised build passed those integration checks.
