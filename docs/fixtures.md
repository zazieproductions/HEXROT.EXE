# Generated Fixtures

Run `python scripts/generate_fixtures.py`. The generator writes deterministic 8 kHz, mono, 16-bit PCM and harmless text; it uses no proprietary samples. The reference is also copied into `public/fixtures` for the browser-only preview. The reference WAV checked into this build is 4,144 bytes with SHA-256 `7a854dbf8865aa2f82e9f39cde4e0af812b053ce1bee077442cbf346c7ed6f1a`.

| Fixture | Expected observation |
| --- | --- |
| `reference.wav` | RIFF/WAVE, `fmt `, `LIST/INFO`, and `data`; 8 kHz mono PCM, 0.25 s, three INFO fields; no structural warning from this parser. |
| `reference.aiff` | FORM/AIFF with `COMM`, `NAME`, and `SSND`; 8 kHz mono PCM, 0.25 s. |
| `inconsistent_length.wav` | The data chunk declares 512 more bytes than are available. |
| `truncated.wav` | The container and data chunk extend past the shortened file. |
| `extension_mismatch.mp3` | RIFF/WAVE magic with an `.mp3` extension. |
| `duplicate_info.wav` | Two `INAM` INFO fields; duplicate metadata heuristic. |
| `trailing_bytes.wav` | 21 bytes following the declared RIFF container. |

These expectations are asserted by `tests/unit/test_parsers.py`. FLAC and MP3 metadata tests are generated from the PCM fixture with FFmpeg when it is installed. Neither the fixtures nor the tests imply a decoder vulnerability.
