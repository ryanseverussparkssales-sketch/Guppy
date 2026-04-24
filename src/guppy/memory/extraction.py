from __future__ import annotations

import re


def normalize_text(value: str) -> str:
    """Create a stable search projection from markdown-heavy content."""
    text = (value or "").replace("\r\n", "\n")
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"[`*_>#\[\]()]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


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
    text = clean_memory_fragment(value).lower()
    if len(text) < 8:
        return False
    generic_prefixes = (
        "be helpful",
        "be concise",
        "be proactive",
        "reply in",
        "talk in",
        "explain like",
        "remember to",
        "the user said",
        "assistant should",
        "we should",
        "need to",
    )
    if text.startswith(generic_prefixes):
        return False
    return True


def memory_candidate(key: str, value: str, category: str, source: str) -> dict[str, str]:
    return {
        "key": key,
        "value": value,
        "category": category,
        "source": source,
    }


def extract_preference_candidates(text: str, *, speaker: str) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    if speaker != "user":
        return candidates
    for pattern in _USER_PREFERENCE_PATTERNS:
        for match in pattern.finditer(text or ""):
            value = clean_memory_fragment(match.group(1))
            if not looks_like_product_memory(value):
                continue
            key = f"pref_{slug_memory_fragment(value)}"
            candidates.append(memory_candidate(key, value, "preference", "chat_preference"))
    return candidates


def extract_identity_candidates(text: str, *, speaker: str) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    if speaker != "user":
        return candidates
    for pattern in _IDENTITY_PATTERNS:
        for match in pattern.finditer(text or ""):
            value = clean_memory_fragment(match.group(1))
            if len(value) < 2 or len(value) > 80:
                continue
            key = f"identity_{slug_memory_fragment(value)}"
            candidates.append(memory_candidate(key, value, "identity", "chat_identity"))
    return candidates


def extract_decision_candidates(text: str, *, speaker: str) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    if speaker not in {"user", "assistant"}:
        return candidates
    for pattern in _DECISION_PATTERNS:
        for match in pattern.finditer(text or ""):
            value = clean_memory_fragment(match.group(1))
            if len(value) < 8:
                continue
            key = f"decision_{slug_memory_fragment(value)}"
            candidates.append(memory_candidate(key, value, "decision", "chat_decision"))
    return candidates


def extract_scope_candidates(text: str, *, speaker: str) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    if speaker not in {"user", "assistant"}:
        return candidates
    for pattern, category, relation in _SCOPE_PATTERNS:
        for match in pattern.finditer(text or ""):
            subject = clean_memory_fragment(match.group("subject"))
            container = clean_memory_fragment(match.group("container"))
            if len(subject) < 3 or len(container) < 2:
                continue
            value = f"{subject} {relation} {container}"
            key = f"{category}_{slug_memory_fragment(subject)}_{slug_memory_fragment(container)}"
            candidates.append(memory_candidate(key, value, category, f"chat_{category}"))
    return candidates


def dedupe_memory_candidates(candidates: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, str]] = []
    for candidate in candidates:
        signature = (
            str(candidate.get("key", "")).strip().lower(),
            str(candidate.get("value", "")).strip().lower(),
            str(candidate.get("category", "")).strip().lower(),
        )
        if signature in seen:
            continue
        seen.add(signature)
        result.append(candidate)
    return result

