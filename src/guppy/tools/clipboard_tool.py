"""
Clipboard tools — read and write the system clipboard.
Uses pyperclip (cross-platform, Windows-native via win32).
"""
from __future__ import annotations

import pyperclip


def clipboard_read() -> dict:
    """Return the current clipboard text content."""
    try:
        text = pyperclip.paste()
        return {
            "ok": True,
            "text": text or "",
            "length": len(text or ""),
            "empty": not bool(text and text.strip()),
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "text": ""}


def clipboard_write(text: str) -> dict:
    """Write text to the clipboard. Returns the character count written."""
    try:
        pyperclip.copy(text)
        return {"ok": True, "written": len(text)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def clipboard_append(text: str, separator: str = "\n") -> dict:
    """Append text to whatever is already on the clipboard."""
    current = pyperclip.paste() or ""
    combined = (current + separator + text) if current.strip() else text
    return clipboard_write(combined)
