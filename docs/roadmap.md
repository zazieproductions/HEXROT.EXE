# HEXROT.EXE — engineering roadmap

**Current release:** v0.2.0 — a local-first, Mac-oriented prototype using SQLite and Python/FastAPI. The core workflow is parser → mutation → sandboxed decoder → differential → evidence. The roadmap prioritizes honest verification of that workflow over adding surface area.

## Implemented in 0.2.0

1. **Deterministic boundary-value mutation:** `boundary_min`, `boundary_max`, `boundary_off_by_one`, `zero_length_field`, `max_syncsafe`, and `negative_duration`, plus the original strategy set.
2. **Batch deduplication and replay manifests:** SHA-256 dedup plus `reproduction_inputs` on every variant.
3. **Bounded crash triage:** two reruns, an original baseline, and single-edit-drop analysis (max 20 edits) with a lossy-preview guard.
4. **Tighter macOS Seatbelt profile:** no global `process-fork`, writes only to `/dev/null`, explicit interpreter/decoder/input/supervisor allowlist.
5. **Parser resilience:** malformed headers, zero-length fields, oversized declarations, duplicate chunks, bad encodings, and garbage inputs.
6. **Seven-job CI matrix:** Linux sandbox, macOS, no-sandbox refusal, frontend, mutation reproducibility, malformed parsers, and API contracts.

## Next

| Priority | Work | Why it matters |
|---|---|---|
| P0 | Validate the macOS `sandbox-exec` profile on current Apple Silicon and record the run | The profile is unverified and `sandbox-exec` is deprecated |
| P0 | Run the full bubblewrap + FFmpeg integration suite on a disposable Linux runner and retain current logs | Six tests are environment-skipped in the recorded checkout |
| P1 | Add Playwright browser E2E to CI with explicit Chromium/dependency checks | `scripts/ui_e2e.mjs` is currently a manual check |
| P1 | Replace single-edit-drop triage with a budgeted `ddmin` over edit subsets | Current triage identifies candidates, not minimal reproducers |
| P2 | MP3 frame-level validation and FLAC audio-frame verification | Parsing is currently structure- and metadata-level |
| P2 | cgroup/container resource enforcement | Sampled RSS/CPU can miss short peaks |
| P2 | Additional separately sandboxed decoders (SoX, reference FLAC, mpg123) | FFmpeg and ffprobe are not independent implementations |
| P3 | Structured HTML report layout (still escaped, no active content) | Current HTML is an escaped Markdown snapshot |

## Explicit non-goals

- Cloud upload, remote analysis, telemetry, or a hosted service.
- Exploit payload generation, automatic exploitation, or weaponization.
- Claiming a vulnerability, CVE, or exploitability from a rejection, discrepancy, or crash.
- Multi-user authentication or binding the API to a non-loopback interface.
- Migrating the local SQLite workflow to PostgreSQL before the core sandboxed workflow is validated on the target hardware.

## Change discipline

Every roadmap item must preserve these invariants:

1. The original file is never modified.
2. Observations and interpretations remain separate.
3. Decoder execution stays gated by an OS sandbox self-test.
4. A missing dependency never becomes simulated evidence.
5. Reports keep redaction, confidence, and limitation sections.

No item on this roadmap is represented as implemented in v0.2.0 unless it appears under **Implemented in 0.2.0**.
