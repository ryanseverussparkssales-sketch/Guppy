from __future__ import annotations

import re

PIPELINE_STAGES = [
    "new_lead",
    "contacted",
    "qualified",
    "proposal",
    "negotiation",
    "won",
    "lost",
]


def normalize_text(value: str) -> str:
    """Create a stable search projection from markdown-heavy content."""
    text = (value or "").replace("\r\n", "\n")
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"[`*_>#\[\]()]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_stage(stage: str) -> str:
    candidate = normalize_text(stage).replace(" ", "_")
    return candidate if candidate in PIPELINE_STAGES else "new_lead"


_MEMORY_KEY_RE = re.compile(r"[^a-z0-9]+")
_USER_PREFERENCE_PATTERNS = [
    re.compile(r"\bi prefer\s+([^.!?\n]+)", re.IGNORECASE),
    re.compile(r"\bplease keep\s+([^.!?\n]+)", re.IGNORECASE),
    re.compile(r"\bi want\s+([^.!?\n]+)", re.IGNORECASE),
]
_IDENTITY_PATTERNS = [
    re.compile(r"\bmy name is\s+([^.!?\n]+)", re.IGNORECASE),
    re.compile(r"\bcall me\s+([^.!?\n]+)", re.IGNORECASE),
]
_DECISION_PATTERNS = [
    re.compile(r"\bwe decided(?: that)?\s+([^.!?\n]+)", re.IGNORECASE),
    re.compile(r"\bthe direction is to\s+([^.!?\n]+)", re.IGNORECASE),
]
_SCOPE_PATTERNS = [
    (
        re.compile(
            r"\b(?P<subject>[A-Za-z0-9][A-Za-z0-9 /+,_-]{2,80}?)\s+should\s+stay\s+out\s+of\s+(?P<container>[A-Za-z0-9][A-Za-z0-9 /+,_-]{1,80})",
            re.IGNORECASE,
        ),
        "scope",
        "should stay out of",
    ),
    (
        re.compile(
            r"\b(?P<subject>[A-Za-z0-9][A-Za-z0-9 /+,_-]{2,80}?)\s+should\s+remain\s+separate\s+from\s+(?P<container>[A-Za-z0-9][A-Za-z0-9 /+,_-]{1,80})",
            re.IGNORECASE,
        ),
        "scope",
        "should remain separate from",
    ),
    (
        re.compile(
            r"\b(?P<subject>[A-Za-z0-9][A-Za-z0-9 /+,_-]{2,80}?)\s+belongs\s+in\s+(?P<container>[A-Za-z0-9][A-Za-z0-9 /+,_-]{1,80})",
            re.IGNORECASE,
        ),
        "placement",
        "belongs in",
    ),
]


def slug_memory_fragment(value: str, limit: int = 48) -> str:
    slug = _MEMORY_KEY_RE.sub("_", (value or "").strip().lower()).strip("_")
    if not slug:
        slug = "note"
    return slug[:limit].strip("_") or "note"


def clean_memory_fragment(value: str) -> str:
    text = " ".join(str(value or "").strip().split())
    return text.strip(" ,.;:")


def looks_like_product_memory(value: str) -> bool:
    lowered = (value or "").lower()
    return any(
        token in lowered
        for token in (
            "home",
            "launcher",
            "workspace",
            "app mgmt",
            "app management",
            "route",
            "voice",
            "runtime",
            "automation",
            "local llm",
            "page",
            "panel",
            "logs",
            "recovery",
        )
    )


def memory_candidate(key: str, value: str, category: str, source: str) -> dict[str, str]:
    return {
        "key": key,
        "value": value,
        "category": category,
        "source": source,
    }


def extract_preference_candidates(text: str, *, speaker: str) -> list[dict[str, str]]:
    cleaned = clean_memory_fragment(text)
    if not cleaned or speaker != "user":
        return []

    results: list[dict[str, str]] = []
    for pattern in _USER_PREFERENCE_PATTERNS:
        for match in pattern.finditer(cleaned):
            fragment = clean_memory_fragment(match.group(1))
            if not fragment:
                continue
            key = (
                "preferences.concise_answers"
                if "concise" in fragment.lower() and "answer" in fragment.lower()
                else f"preferences.{slug_memory_fragment(fragment)}"
            )
            value = f"Ryan prefers {fragment}."
            category = "work" if looks_like_product_memory(fragment) else "preferences"
            results.append(memory_candidate(key, value, category, f"{speaker}_preference"))
    return results


def extract_identity_candidates(text: str, *, speaker: str) -> list[dict[str, str]]:
    if speaker != "user":
        return []

    cleaned = clean_memory_fragment(text)
    if not cleaned:
        return []

    results: list[dict[str, str]] = []
    for pattern in _IDENTITY_PATTERNS:
        for match in pattern.finditer(cleaned):
            fragment = clean_memory_fragment(match.group(1))
            if not fragment:
                continue
            results.append(
                memory_candidate(
                    "personal.preferred_name",
                    f"Ryan prefers to be addressed as {fragment}.",
                    "personal",
                    "user_identity",
                )
            )
    return results


def extract_decision_candidates(text: str, *, speaker: str) -> list[dict[str, str]]:
    if speaker != "user":
        return []

    cleaned = clean_memory_fragment(text)
    if not cleaned:
        return []

    results: list[dict[str, str]] = []
    for pattern in _DECISION_PATTERNS:
        for match in pattern.finditer(cleaned):
            fragment = clean_memory_fragment(match.group(1))
            if not fragment:
                continue
            results.append(
                memory_candidate(
                    f"work.decision_{slug_memory_fragment(fragment)}",
                    f"We decided {fragment}.",
                    "work",
                    f"{speaker}_decision",
                )
            )
    return results


def extract_scope_candidates(text: str, *, speaker: str) -> list[dict[str, str]]:
    if speaker != "user":
        return []

    cleaned = clean_memory_fragment(text)
    if not cleaned:
        return []

    results: list[dict[str, str]] = []
    for pattern, suffix, relation in _SCOPE_PATTERNS:
        for match in pattern.finditer(cleaned):
            subject = clean_memory_fragment(match.group("subject"))
            container = clean_memory_fragment(match.group("container"))
            if not subject or not container:
                continue
            prefix = (
                "product"
                if looks_like_product_memory(subject) or looks_like_product_memory(container)
                else "work"
            )
            key = f"{prefix}.{slug_memory_fragment(subject)}_{suffix}"
            value = (
                f"{subject} belongs in {container}."
                if relation == "belongs in"
                else f"{subject} {relation} {container}."
            )
            results.append(memory_candidate(key, value, "work", f"{speaker}_{suffix}"))
    return results


def dedupe_memory_candidates(candidates: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for candidate in candidates:
        key = str(candidate.get("key", "")).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped
