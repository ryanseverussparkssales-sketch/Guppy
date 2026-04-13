"""utils/secret_store.py — OS-backed secret storage with environment fallback.

On Windows uses Windows Credential Manager via keyring.
On macOS uses Keychain.  On Linux uses SecretService / libsecret.
Falls back gracefully to the caller-supplied value when keyring is absent.

Usage
-----
    from utils import secret_store

    # Retrieve — keyring wins over fallback when a value is stored there.
    jwt_key = secret_store.get_secret("jwt_secret",
                                      fallback=os.getenv("GUPPY_JWT_SECRET"))

    # Persist — no-op when keyring unavailable, returns False.
    secret_store.set_secret("repair_token", token)

    # Erase — no-op when keyring unavailable, returns False.
    secret_store.delete_secret("repair_token")
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_SERVICE_NAME = "guppy"

try:
    import keyring as _keyring  # type: ignore[import-untyped]
    _KEYRING_AVAILABLE = True
except ImportError:
    _keyring = None  # type: ignore[assignment]
    _KEYRING_AVAILABLE = False


def get_secret(key: str, *, fallback: Optional[str] = None) -> Optional[str]:
    """Return the secret for *key*, checking OS credential store first.

    If keyring is unavailable or has no entry for *key*, *fallback* is
    returned unchanged (which may be ``None`` or an env-var value).
    """
    if _KEYRING_AVAILABLE:
        try:
            val = _keyring.get_password(_SERVICE_NAME, key)
            if val is not None:
                return val
        except Exception as exc:
            logger.debug("keyring.get_password(%r) failed, using fallback: %s", key, exc)
    return fallback


def set_secret(key: str, value: str) -> bool:
    """Persist *value* for *key* in the OS credential store.

    Returns ``True`` if the value was stored, ``False`` if keyring is
    unavailable or the operation failed (the secret was NOT persisted to the
    OS store, but the caller's in-memory copy is still authoritative).
    """
    if not _KEYRING_AVAILABLE:
        logger.debug("keyring unavailable; secret %r not persisted to OS store", key)
        return False
    try:
        _keyring.set_password(_SERVICE_NAME, key, value)
        return True
    except Exception as exc:
        logger.warning("keyring.set_password(%r) failed: %s", key, exc)
        return False


def delete_secret(key: str) -> bool:
    """Remove any stored value for *key* from the OS credential store.

    Returns ``True`` if the deletion succeeded (or the entry did not exist),
    ``False`` if keyring is unavailable or raised an unexpected error.
    """
    if not _KEYRING_AVAILABLE:
        return False
    try:
        _keyring.delete_password(_SERVICE_NAME, key)
        return True
    except Exception as exc:
        # keyring.errors.PasswordDeleteError is raised when the entry does not
        # exist; that is not an error from our perspective.
        logger.debug("keyring.delete_password(%r): %s", key, exc)
        return True
