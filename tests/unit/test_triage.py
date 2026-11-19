"""Regression tests for the bounded single-edit-drop triage helper.

The helper used to compare candidates against a ``signal`` key that mutation
records never contained, so every tested edit was reported as critical. These
tests pin the observed-run signal semantics and the lossy-replay guard.
"""
from pathlib import Path

import backend.main as main


def edit(offset: int, old: str, new: str, description: str, truncated: bool = False):
    return {
        "offset": offset,
        "old_length": len(bytes.fromhex(old)),
        "new_length": len(bytes.fromhex(new)),
        "before_hex": old,
        "after_hex": new,
        "description": description,
        "preview_truncated": truncated,
    }


def record(path: Path, edits: list[dict]) -> dict:
    return {"path": str(path), "mutation": {"edits": edits, "strategy": "seeded_bytes"}}


def test_same_observed_signal_is_required(monkeypatch, tmp_path):
    target = tmp_path / "mut.bin"
    target.write_bytes(b"XBCD")
    source = tmp_path / "original.bin"
    source.write_bytes(b"ABCD")

    def always_crash(path, decoder, timeout, memory_mb, *args, **kwargs):
        return {"abnormal": True, "signal": 11, "exit_code": -11}

    monkeypatch.setattr(main, "execute", always_crash)
    result = main._basic_delta_debug(
        record(target, [edit(0, "41", "58", "A to X"), edit(2, "43", "5a", "C to Z")]),
        {"path": str(source)}, "ffmpeg", {"timeout_seconds": 1, "memory_mb": 512}, 11,
    )
    assert result["expected_signal"] == 11
    assert result["edits_tested"] == 2
    assert result["critical_edits"] == []

    # A different observed signal must not count as the same crash.
    result_other = main._basic_delta_debug(
        record(target, [edit(0, "41", "58", "A to X")]),
        {"path": str(source)}, "ffmpeg", {"timeout_seconds": 1, "memory_mb": 512}, 6,
    )
    assert [r["still_crashes"] for r in result_other["results"]] == [False]
    assert len(result_other["critical_edits"]) == 1


def test_dropping_a_contributing_edit_changes_the_outcome(monkeypatch, tmp_path):
    target = tmp_path / "mut.bin"
    target.write_bytes(b"XBCD")
    source = tmp_path / "original.bin"
    source.write_bytes(b"ABCD")

    def crash_only_with_x(path, decoder, timeout, memory_mb, *args, **kwargs):
        crash = Path(path).read_bytes().startswith(b"X")
        return {"abnormal": crash, "signal": 11 if crash else None,
                "exit_code": -11 if crash else 0}

    monkeypatch.setattr(main, "execute", crash_only_with_x)
    result = main._basic_delta_debug(
        record(target, [edit(0, "41", "58", "A to X"), edit(2, "43", "5a", "C to Z")]),
        {"path": str(source)}, "ffmpeg", {"timeout_seconds": 1, "memory_mb": 512}, 11,
    )
    critical = [row["dropped_edit_index"] for row in result["critical_edits"]]
    assert critical == [0]
    assert result["results"][1]["still_crashes"] is True


def test_truncated_previews_refuse_lossy_replay(monkeypatch, tmp_path):
    target = tmp_path / "mut.bin"
    target.write_bytes(b"XBCD")
    source = tmp_path / "original.bin"
    source.write_bytes(b"ABCD")
    calls = []
    monkeypatch.setattr(main, "execute", lambda *a, **k: calls.append(a) or {})

    result = main._basic_delta_debug(
        record(target, [edit(0, "41", "58", "A to X", truncated=True)]),
        {"path": str(source)}, "ffmpeg", {"timeout_seconds": 1, "memory_mb": 512}, 11,
    )
    assert result["skipped"] is True
    assert "truncated" in result["note"].lower()
    assert calls == []


def test_too_many_edits_are_skipped(monkeypatch, tmp_path):
    target = tmp_path / "mut.bin"
    target.write_bytes(b"ABCD")
    source = tmp_path / "original.bin"
    source.write_bytes(b"ABCD")
    monkeypatch.setattr(main, "execute", lambda *a, **k: {})
    edits = [edit(0, "41", "58", f"edit {i}") for i in range(21)]
    result = main._basic_delta_debug(
        record(target, edits), {"path": str(source)}, "ffmpeg",
        {"timeout_seconds": 1, "memory_mb": 512}, 11,
    )
    assert result["skipped"] is True
    assert result["edit_count"] == 21
