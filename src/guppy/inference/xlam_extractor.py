"""xLAM-2-8B structured extraction helper.

xLAM-2-8B-fc-r (Salesforce, #1 BFCL ≤8B) is purpose-built for JSON tool-call
extraction. Use it any time you need to pull structured data from unstructured
text rather than asking Hermes to do it mid-conversation.

Primary use cases:
  - extract_contact()  — scraper.do raw HTML → {name, company, email, phone, notes}
  - xlam_extract()     — generic: natural language → list of tool_call dicts

Falls back gracefully if xLAM is offline (returns None / empty list).
"""
from __future__ import annotations

import asyncio
import json
import logging

import httpx

_log = logging.getLogger(__name__)

_XLAM_URL = "http://127.0.0.1:8089/v1/chat/completions"
_XLAM_TIMEOUT = 30.0

# xLAM system prompt (Salesforce canonical format)
_XLAM_SYSTEM = (
    "You are an expert in composing functions. You are given a question and a set of "
    "possible functions. Based on the question, you will need to make one or more function "
    "calls to achieve the purpose.\n"
    "If none of the functions can be used, point it out and refuse to answer.\n"
    "If the given question lacks the parameters required by the function, also point it out."
)

# Tool schema for contact extraction
_CONTACT_TOOL = {
    "type": "function",
    "function": {
        "name": "save_contact",
        "description": "Save a business contact extracted from the provided text.",
        "parameters": {
            "type": "object",
            "properties": {
                "name":    {"type": "string", "description": "Full name of the person"},
                "company": {"type": "string", "description": "Company or organization name"},
                "email":   {"type": "string", "description": "Email address"},
                "phone":   {"type": "string", "description": "Phone number"},
                "title":   {"type": "string", "description": "Job title or role"},
                "notes":   {"type": "string", "description": "Any other relevant info (location, specialty, etc.)"},
            },
            "required": ["name"],
        },
    },
}


async def xlam_extract(user_text: str, tools: list[dict]) -> list[dict]:
    """
    Send user_text to xLAM and return a list of extracted tool_call argument dicts.

    Returns [] on any error (xLAM offline, parse failure, etc.) — callers should
    fall back to their own normalization.
    """
    payload = {
        "model":    "Llama-xLAM-2-8B-fc-r-Q4_K_M.gguf",
        "messages": [
            {"role": "system", "content": _XLAM_SYSTEM},
            {"role": "user",   "content": user_text},
        ],
        "tools":       tools,
        "tool_choice": "auto",
        "temperature": 0.0,
        "max_tokens":  512,
    }
    try:
        async with httpx.AsyncClient(timeout=_XLAM_TIMEOUT) as client:
            resp = await client.post(_XLAM_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            return []
        msg = choices[0].get("message", {})
        tool_calls = msg.get("tool_calls", [])
        results = []
        for tc in tool_calls:
            raw_args = tc.get("function", {}).get("arguments", "{}")
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                results.append({"name": tc["function"]["name"], "arguments": args})
            except Exception:
                pass
        return results
    except Exception as exc:
        _log.debug("xLAM extraction failed (non-fatal): %s", exc)
        return []


async def extract_contacts(raw_text: str) -> list[dict]:
    """
    Use xLAM to extract one or more contacts from raw scraped text.

    Returns a list of contact dicts with keys: name, company, email, phone, title, notes.
    Returns [] if xLAM is offline — caller should fall back to regex normalization.
    """
    if not raw_text.strip():
        return []

    prompt = (
        "Extract all business contacts from the following text. "
        "Call save_contact() once for each person found.\n\n"
        f"TEXT:\n{raw_text[:4000]}"
    )
    calls = await xlam_extract(prompt, [_CONTACT_TOOL])
    contacts = []
    for call in calls:
        if call.get("name") == "save_contact":
            args = call.get("arguments", {})
            contacts.append({
                "name":    str(args.get("name",    "")).strip(),
                "company": str(args.get("company", "")).strip(),
                "email":   str(args.get("email",   "")).strip(),
                "phone":   str(args.get("phone",   "")).strip(),
                "notes":   " | ".join(filter(None, [
                    args.get("title", "").strip(),
                    args.get("notes", "").strip(),
                ])),
            })
    return contacts


def extract_contacts_sync(raw_text: str) -> list[dict]:
    """Sync wrapper for use in non-async contexts."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already in an event loop — caller must use the async version
            return []
        return loop.run_until_complete(extract_contacts(raw_text))
    except Exception:
        return []
