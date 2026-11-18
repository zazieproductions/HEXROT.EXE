# Contributing

Contributions should prioritize reproducible observations, defensive file handling, and honest reporting. Never replace a missing dependency or failed process with simulated evidence. Avoid weaponized payloads and automatic exploitation.

1. Create a local virtual environment and install `python -m pip install -e '.[test]'`.
2. Generate fixtures with `python scripts/generate_fixtures.py`.
3. Run `python -m pytest -q`, `npx tsc --noEmit`, and `npm run build`.
4. Test UI changes against a loopback backend with `node scripts/ui_e2e.mjs` and document platform-specific gaps.
5. For a new decoder, follow `docs/adapters.md`; use a fixed allowlist and preserve sandbox isolation, timeouts, and bounded logs.
6. Include regression tests for actual input bytes and observable outcomes. Document any unsupported formats, sandbox assumptions, and privacy impact.

Do not include private samples, local workspace databases, personal paths, fabricated findings, or screenshots that imply unverified behavior.
