from __future__ import annotations

from pathlib import Path

from src.guppy.runtime_application.json_io import read_json_dict, read_jsonl_tail


def test_read_json_dict_returns_empty_on_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("not json", encoding="utf-8")
    assert read_json_dict(path) == {}


def test_read_jsonl_tail_marks_parse_errors(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text('{"ok": 1}\nnot-json\n{"ok": 2}\n', encoding="utf-8")
    rows = read_jsonl_tail(path, limit=10)
    assert rows[0] == {"ok": 1}
    assert rows[1].get("parse_error") is True
    assert rows[2] == {"ok": 2}
