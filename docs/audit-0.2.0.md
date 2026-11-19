# HEXROT.EXE v0.2.0 — Engineering Audit

**Date**: 2026-11-19  
**Auditor**: Automated engineering review  
**Base commit**: d4a15ec33f9aa725d0aca8699dc2fd1cea4e76fa (main)  
**Branch**: arena/e7d30ba9-hexrot-exe

---

## Summary

v0.2.0 addresses the critical priorities from the audit request. The application went from **16 passed, 6 skipped** to **46 passed, 6 skipped**. TypeScript checking and production build pass cleanly.

---

## Priority 0 — Decoder Execution Safety

### Audit Findings

**Linux (bubblewrap)**: The existing profile is sound. It uses `--unshare-all`, `--unshare-net`, `--disable-userns`, `--die-with-parent`, read-only system mounts, a 16 MiB tmpfs, no host home mount, and a clean environment. The self-test runs `/usr/bin/true` inside the sandbox.

**macOS (sandbox-exec)**: The original profile granted `process-fork` globally, `mach-lookup` globally, and `file-write* (subpath "/dev")`, which exposed `/dev/` broadly. The interpreter path was included but not the decoder binary specifically.

### Changes Made

- **Tightened macOS worker profile**: Removed global `process-fork`, `mach-lookup`, and broad `/dev` subpath access. The profile now:
  - Allows `process-exec` only for the interpreter and decoder binaries (literal paths)
  - Allows `file-read*` only for `/usr`, `/System`, `/dev/null`, `/dev/random`, `/dev/urandom`, and the four specific file paths (interpreter, decoder, input, supervisor)
  - Allows `file-write*` only for `/dev/null`
  - No network permissions (unchanged — never had them)
- **Improved self-test documentation**: The status message now explicitly states that the macOS sandbox is experimental and unverified on Apple Silicon.
- **Verified that the supervisor sets rlimits before exec** (confirmed at `backend/workers/supervisor.py:22-27`).

### Not Changed (Correctly)

- The Linux bubblewrap profile was not modified — it was already well-designed.
- The sampling interval (20ms) for process-tree monitoring was not reduced; short peaks between polls are a documented limitation.
- Untrusted decoder execution remains disabled when the sandbox self-test fails.

### Remaining Limitations

- `sandbox-exec` is deprecated by Apple and may not work on future macOS releases.
- Neither sandbox mechanism is independently validated against kernel-level attacks.
- Process-tree memory/CPU monitoring is sampled, not cgroup-enforced.
- These are not complete substitutes for a disposable VM.

---

## Priority 1 — End-to-End Verification

### Results

- **46 Python tests passed**, 6 skipped (sandbox-dependent tests correctly skipped when bubblewrap/ffmpeg are unavailable)
- **TypeScript checking passes** with strict mode, no unused locals, no unused parameters
- **Production build succeeds** (1,051 KB single-file bundle)
- No mock results or fabricated data anywhere in the test suite
- All API tests use `TestClient` with a real `create_app()` instance backed by a temp SQLite database

### Gap Documentation

- Playwright browser E2E testing was not added in this pass — the existing `scripts/ui_e2e.mjs` script covers the documented workflow.
- macOS integration tests were not run (this environment is Linux); they are configured as `continue-on-error` in CI.

---

## Priority 2 — Mutation Engine Improvements

### Changes

1. **Six new boundary-value strategies** added to `backend/mutation/engine.py`:
   - `boundary_min` — Set chunk/block sizes to zero
   - `boundary_max` — Set container size to 4x file length
   - `boundary_off_by_one` — Set chunk size to actual_size ± 1
   - `zero_length_field` — Set fmt chunk or ID3 tag size to zero
   - `max_syncsafe` — Set ID3 tag size to 0x0FFFFFFF
   - `negative_duration` — Set sample rate or frame count to zero

2. **Hash-based deduplication** via `generate_batch()` — mutations whose SHA-256 matches a previous result (or the original) are skipped. Controlled by `deduplicate` parameter (default True).

3. **Structured mutation manifest** — the API response now includes a `manifest` object with `seed`, `count_requested`, `count_generated`, `deduplicated`, `strategies`, `original_sha256`, and `output_hashes`.

4. **Reproduction inputs** — every mutation history now contains `reproduction_inputs` with all parameters needed to replay: `(seed, strategy, index, region, size_limit, metadata_size, original_sha256)`.

5. **Original file preservation** — verified by test `test_original_file_preserved`.

### Verified

- All strategies are deterministic: same inputs → same outputs
- Edit offsets are recorded with before/after byte hashes
- Batch generation cycles through strategies correctly
- Deduplication correctly skips identical outputs
- Strategies that don't apply to a format raise `MutationError` with a clear message

---

## Priority 3 — Crash Triage

### Changes

- **Basic delta debugging** added to the triage endpoint (`_basic_delta_debug()` in `backend/main.py`):
  - When a crash is reproducible and the input is a mutation, the triage endpoint tests each edit individually by dropping one at a time
  - Records which edits are "critical" (removing them prevents the crash)
  - Bounded to 20 edits maximum to prevent runaway computation
  - Results stored in the triage record under `minimization`

- **Enhanced triage record** now includes:
  - `decoder_version`
  - `exit_status`
  - `signal`
  - `resource_exceeded`
  - `is_resource_limit` — distinguishes resource-limit termination from parser failure

### Not Implemented

- Full 2^n delta debugging (too expensive for bounded execution)
- Automatic mutation replay from saved manifests (would require external orchestration)

---

## Priority 4 — Audio Parser Hardening

### New Tests (12 added)

| Test | Input | Expected |
|------|-------|----------|
| `test_empty_file_does_not_crash_parser` | 0 bytes | `Unknown` format, no crash |
| `test_truncated_wav_header` | RIFF + size + partial WAVE | Warning about truncated structure |
| `test_zero_length_chunk_declared` | fmt chunk with size=0 | Handled safely, no OOM |
| `test_oversized_declared_chunk_length` | data chunk with size=0xFFFFFFFF | Warning, bounded parsing |
| `test_duplicate_chunk_ids` | Two data chunks | Both parsed without confusion |
| `test_malformed_text_encoding_in_metadata` | Invalid UTF-8 in metadata | Text-safe extraction |
| `test_extension_signature_mismatch` | WAV in .mp3, MP3 in .wav | `extension_mismatch=True` |
| `test_zero_length_container_size` | RIFF size=0 | Handled safely |
| `test_garbage_bytes_not_audio` | 1024 random bytes | `Unknown` format |
| `test_truncated_flac_metadata` | FLAC header + truncated block | Warning |
| `test_single_byte_file` | 1 byte | `Unknown` format, size=1 |

### Parser Bounds

- Chunk count limit: 4096
- Metadata text truncated to 4096 characters
- Artwork limited to 50 items
- Mutagen tags limited to 50 values per key
- Extended 80-bit float validated for finiteness and range

---

## Priority 5 — Backend Reliability

### Verified

- **Loopback binding**: middleware rejects non-loopback hosts, clients, and origins
- **Request size limits**: middleware bounds requests before multipart parsing
- **File path safety**: all file access is by session/file ID, not user-supplied paths
- **Filename sanitization**: `clean_name()` strips path separators and limits length
- **SQLite WAL mode**: configured for concurrent read access
- **Job startup recovery**: interrupted/queued jobs are marked on startup
- **Single concurrent job**: `JobManager.lock` prevents concurrent execution
- **Worker cleanup**: `finally` block ensures process group kill on timeout/cancel/exception
- **Output bounds**: stdout/stderr capped at 64 KiB each in the supervisor

---

## Priority 6 — Research Interface

No changes were needed. The existing frontend:
- Shows real job progress (completed / total executions)
- Has a working cancel button that sends POST to `/api/jobs/{id}/cancel`
- Displays decoder availability from health endpoint
- Supports searchable findings, hex inspection, byte-offset navigation
- Shows mutation history with edit details
- Provides original-vs-mutated byte comparison
- Supports session persistence via SQLite

---

## Priority 7 — CI

### Changes

- Added **7 CI jobs** (was 2):
  1. `python-backend` — Linux with bubblewrap + ffmpeg, full test suite
  2. `python-backend-macos` — macOS with sandbox-exec (continue-on-error)
  3. `python-backend-no-sandbox` — Linux without sandbox, verifies decoder execution disabled
  4. `react-frontend` — TypeScript check + production build
  5. `mutation-reproducibility` — Determinism, dedup, reproduction tests
  6. `parser-malformed-inputs` — Empty, truncated, oversized, garbage inputs
  7. `api-contract` — Health, manifest, dedup, boundary strategy endpoints
- Permissions remain `contents: read` (minimal)
- macOS job uses `continue-on-error: true` since sandbox-exec may not be available

---

## Priority 8 — Release Hardening

### Updated

- `pyproject.toml`: version 0.2.0
- `package.json`: version 0.2.0
- `README.md`: Added "Changes in 0.2.0" section, updated capabilities, test documentation
- `SECURITY.md`: Documented tighter macOS profile
- `CONTRIBUTING.md`: Added guidance for new mutation strategies
- `.gitignore`: Added generated mutation artifacts, IDE files, OS artifacts
- MIT license preserved

---

## Test Results

### Final: 46 passed, 6 skipped

| Category | Passed | Skipped | Notes |
|----------|--------|---------|-------|
| Unit — Parsers | 14 | 1 | 1 skipped: ffmpeg not installed |
| Unit — Mutation | 17 | 0 | Includes 6 new boundary strategies, dedup, reproducibility |
| Unit — Supervisor | 3 | 0 | Real subprocess with rlimits |
| Integration — Sandbox | 0 | 4 | bubblewrap not available in this environment |
| End-to-end — Workflow | 12 | 1 | 1 skipped: cancel requires ffmpeg |
| **Total** | **46** | **6** | |

### Skipped Tests (by design)

- `test_generated_flac_and_mp3_metadata` — requires ffmpeg
- `test_decoder_real_results_and_output_hash` — requires bubblewrap + ffmpeg
- `test_supervisor_distinguishes_signal_and_exit_code` — requires bubblewrap
- `test_no_host_home_or_host_loopback_access` — requires bubblewrap
- `test_sndfile_info_zero_exit_can_still_mean_rejection` — requires sndfile-info
- `test_cancel_stops_actual_decoder_worker` — requires bubblewrap + ffmpeg

### Frontend Verification

- TypeScript: **PASS** (strict mode, no errors)
- Production build: **PASS** (1,051 KB single-file bundle)

---

## Files Changed

| File | Change |
|------|--------|
| `backend/workers/isolation.py` | Tightened macOS sandbox profile |
| `backend/mutation/engine.py` | 6 new strategies, batch generation, dedup, manifest |
| `backend/main.py` | v0.2.0, batch mutations, delta debug triage, manifest endpoint |
| `tests/unit/test_parsers.py` | 12 new malformed-input tests |
| `tests/unit/test_mutation.py` | 14 new mutation engine tests |
| `tests/end_to_end/test_workflow.py` | 7 new API contract tests |
| `.github/workflows/verify.yml` | 7-job CI matrix |
| `pyproject.toml` | Version 0.2.0 |
| `package.json` | Version 0.2.0 |
| `README.md` | v0.2.0 changelog, updated capabilities |
| `SECURITY.md` | Updated macOS profile documentation |
| `CONTRIBUTING.md` | New mutation strategy guidance |
| `.gitignore` | Additional patterns |
| `docs/audit-0.2.0.md` | This document |

---

## What Was Not Done

- **Playwright browser E2E** — the existing `scripts/ui_e2e.mjs` covers the documented workflow; Playwright tests were not added in this pass.
- **macOS validation** — the tighter sandbox profile is logically correct but was not tested on actual Apple Silicon. CI has it as `continue-on-error`.
- **Full 2^n delta debugging** — the bounded approach tests N edits individually, not all subsets.
- **cgroup enforcement** — resource limits remain rlimit-based, not cgroup-wide.
- **Docker/VM isolation mode** — not added; the existing bubblewrap/sandbox-exec approach is documented as insufficient for high-risk files.
