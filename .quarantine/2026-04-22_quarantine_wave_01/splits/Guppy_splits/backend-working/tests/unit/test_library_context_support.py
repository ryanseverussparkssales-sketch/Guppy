from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from src.guppy.launcher_application.library_context_support import (
    build_library_chat_submission,
    resolve_saved_context_payload,
)


def test_build_library_chat_submission_with_saved_reply_note_sets_notice() -> None:
    submission = build_library_chat_submission(
        "Continue this work",
        history=[{"role": "user", "content": "Earlier prompt"}],
        active_items=[
            {
                "title": "Release review",
                "kind": "note",
                "detail": "Saved response body",
                "origin": "assistant_reply",
                "source_label": "Saved reply note",
            }
        ],
    )

    assert submission.status_text == "Processing with 1 context item(s)..."
    assert "saved reply note as the current source" in submission.context_notice
    assert submission.history[-1]["role"] == "system"


def test_resolve_saved_context_payload_prefers_library_item_id_for_duplicate_titles() -> None:
    with patch(
        "src.guppy.launcher_application.library_context_support.list_workspace_library_items",
        return_value=[
            {
                "id": 12,
                "title": "Review packet",
                "summary": "Wrong note body.",
                "metadata": {"source": "assistant_reply"},
                "item_path": "",
            },
            {
                "id": 42,
                "title": "Review packet",
                "summary": "Correct note body for the selected card.",
                "metadata": {"source": "assistant_reply"},
                "item_path": "",
            },
        ],
    ):
        detail, source_label, origin = resolve_saved_context_payload(
            "guppy-primary",
            title="Review packet",
            item_path="library-item://42",
            item_kind="note",
        )

    assert "Correct note body" in detail
    assert source_label == "Saved reply note"
    assert origin == "assistant_reply"


def test_resolve_saved_context_payload_uses_approved_root_detail_for_file_context() -> None:
    repo_root = Path.cwd()
    item_path = str(repo_root / "docs" / "PROJECT_BRIEF.md")
    with patch(
        "src.guppy.launcher_application.library_context_support.list_approved_roots",
        return_value=[{"label": "Current Guppy repo", "root_path": str(repo_root)}],
    ):
        detail, source_label, origin = resolve_saved_context_payload(
            "guppy-primary",
            title="PROJECT_BRIEF",
            item_path=item_path,
            item_kind="study",
        )

    assert "docs/PROJECT_BRIEF.md" in detail
    assert source_label == "Current Guppy repo"
    assert origin == "library_source"
