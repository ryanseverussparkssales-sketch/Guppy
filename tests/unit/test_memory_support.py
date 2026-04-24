from __future__ import annotations

from src.guppy.memory import memory_support


def test_extract_scope_candidates_marks_product_scope_when_ui_terms_present() -> None:
    candidates = memory_support.extract_scope_candidates(
        "The Local LLM page should stay out of Home.",
        speaker="user",
    )

    assert candidates
    assert candidates[0]["key"] == "product.the_local_llm_page_scope"
    assert "should stay out of Home" in candidates[0]["value"]


def test_dedupe_memory_candidates_keeps_first_unique_key_only() -> None:
    deduped = memory_support.dedupe_memory_candidates(
        [
            {"key": "preferences.concise", "value": "first", "category": "preferences", "source": "a"},
            {"key": "preferences.concise", "value": "second", "category": "preferences", "source": "b"},
            {"key": "work.scope", "value": "third", "category": "work", "source": "c"},
        ]
    )

    assert [item["value"] for item in deduped] == ["first", "third"]
