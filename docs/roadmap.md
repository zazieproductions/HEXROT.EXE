# HEXROT.EXE — engineering roadmap

The current v0.1.1 release focuses on a Mac-oriented, local-first prototype using SQLite and Python/FastAPI. The second submitted prototype offered additional research features worth evaluating **only after** confirming the core sandboxed workflow on the intended target hardware.

## Potential future improvements from the alternative prototype

1. **Bounded crash-case minimization:** deterministic edit replay plus a test-budget-limited ddmin implementation, with evidence recorded at each minimization step.
2. **Additional decoders:** separately sandboxed SoX, FLAC reference decoder, and mpg123 adapters, with accurate acceptance/rejection interpretation.
3. **Deeper parsing:** FLAC metadata detail and MP3 frame-level inspection with explicit, documented validation limits.
4. **Stronger isolation verification:** validate that the exact worker profile blocks network access and unauthorized filesystem reads, not just that a dummy process exits successfully.
5. **Continuous UI verification:** real browser-to-backend tests on a disposable Linux runner with explicit dependency checks.

Avoid migrating to PostgreSQL solely to add these features; the local SQLite backend is simpler for the primary Apple Silicon workflow. No feature in this roadmap is represented as implemented in v0.1.1.
