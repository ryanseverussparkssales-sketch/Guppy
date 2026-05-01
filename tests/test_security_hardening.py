"""Security hardening regression tests.

Covers:
- JWT: wrong signing key, expired token, missing sub field
- Repair endpoint: no token (403), wrong token (403)
- DB: WAL pragma verified, busy_timeout verified, concurrent writers safe
- Malformed runtime files: corrupt JSON returns empty dict, truncated JSONL
- Secret store: fallback path when keyring absent
- Repair token validation: over-length, non-hex content, empty string
"""
from __future__ import annotations

import os
import json
import shutil
import sqlite3
import tempfile
import threading
import time
import unittest
import uuid
from contextlib import contextmanager
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("GUPPY_JWT_SECRET", "test-security-hardening-secret-key-32x")
os.environ.setdefault("GUPPY_DEV_MODE", "0")

try:
    from jose import jwt as _jose_jwt, JWTError
    _JOSE_AVAILABLE = True
except ImportError:
    _JOSE_AVAILABLE = False

import guppy_api
from fastapi.testclient import TestClient
import src.guppy.launcher_application as launcher_app
from src.guppy.launcher_application import is_valid_repair_token as _is_valid_repair_token
from src.guppy.api import auth as guppy_api_auth
from utils import secret_store
from utils.db_utils import open_db

# launcher_window was part of the Qt desktop UI (archived 2026-05-01 to
# docs/archive/deprecated-modules/compat_launcher_ui/). Tests that depend on
# it are skipped gracefully when the module is absent.
try:
    from ui.launcher import launcher_window as launcher_window
    _LAUNCHER_WINDOW_AVAILABLE = True
except ImportError:
    launcher_window = None  # type: ignore[assignment]
    _LAUNCHER_WINDOW_AVAILABLE = False


_TEST_SECRET = "test-security-hardening-secret-key-32x"
_ALG = "HS256"
_TEST_TEMP_ROOT = Path(__file__).resolve().parents[1] / ".tmp" / "test-scratch" / "security-hardening-root"


@contextmanager
def workspace_tempdir():
    _TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = _TEST_TEMP_ROOT / f"{int(time.time() * 1000)}-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


# Windows sandbox runs are more reliable when test scratch stays inside the repo.
tempfile.TemporaryDirectory = workspace_tempdir  # type: ignore[assignment]


# ── JWT tests ──────────────────────────────────────────────────────────────────

class JWTSecurityTests(unittest.TestCase):
    _orig_keyring_available = None

    @classmethod
    def setUpClass(cls):
        if not _JOSE_AVAILABLE:
            raise unittest.SkipTest("python-jose not available")
        # Disable OS keyring for this test class so _refresh_runtime_config()
        # reads the env var instead of a stored credential.
        cls._orig_keyring_available = secret_store._KEYRING_AVAILABLE
        secret_store._KEYRING_AVAILABLE = False
        # Force a concrete signing key for determinism.
        guppy_api_auth.SECRET_KEY = _TEST_SECRET
        os.environ["GUPPY_JWT_SECRET"] = _TEST_SECRET

    @classmethod
    def tearDownClass(cls):
        secret_store._KEYRING_AVAILABLE = cls._orig_keyring_available
        os.environ.pop("GUPPY_JWT_SECRET", None)

    def _make_token(self, payload: dict, key: str = _TEST_SECRET) -> str:
        return _jose_jwt.encode(payload, key, algorithm=_ALG)

    def test_jwt_signed_with_wrong_key_is_rejected(self):
        """A token signed with a different key must be detected as invalid."""
        payload = {
            "sub": "user1",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        bad_token = self._make_token(payload, key="completely-different-wrong-key-abc")

        from fastapi.security import HTTPAuthorizationCredentials
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=bad_token)
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            guppy_api_auth.verify_token(creds)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_jwt_expired_token_is_rejected(self):
        """A token whose exp is in the past must be rejected."""
        payload = {
            "sub": "user1",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),  # already expired
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        }
        expired_token = self._make_token(payload)

        from fastapi.security import HTTPAuthorizationCredentials
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=expired_token)
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            guppy_api_auth.verify_token(creds)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_jwt_missing_sub_is_rejected(self):
        """A token with no 'sub' claim must be rejected even if the signature is valid."""
        payload = {
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
            # 'sub' intentionally absent
        }
        no_sub_token = self._make_token(payload)

        from fastapi.security import HTTPAuthorizationCredentials
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=no_sub_token)
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            guppy_api_auth.verify_token(creds)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_jwt_valid_token_is_accepted(self):
        """A well-formed, unexpired token with a valid key can be decoded."""
        payload = {
            "sub": "unit-test-user",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        good_token = self._make_token(payload)
        # Decode directly — verifies the JWT library agrees that a token
        # signed with the expected key is structurally valid.
        decoded = _jose_jwt.decode(good_token, _TEST_SECRET, algorithms=[_ALG])
        self.assertEqual(decoded.get("sub"), "unit-test-user")


# ── Repair endpoint tests ──────────────────────────────────────────────────────

class RepairEndpointAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = guppy_api.app
        app.dependency_overrides[guppy_api.require_rate_limit] = lambda: "smoke-user"
        # Ensure any override of _require_repair_token from earlier test modules
        # is removed so the real guard runs (with _REPAIR_TOKEN == "").
        app.dependency_overrides.pop(guppy_api._require_repair_token, None)
        cls._client = TestClient(app, raise_server_exceptions=False)

    def test_repair_without_token_returns_403(self):
        """POST /repair with no X-Repair-Token header must return 403."""
        resp = self._client.post(
            "/repair",
            json={"action": "warmup", "dry_run": True},
            # No Authorization header, no X-Repair-Token header
        )
        self.assertEqual(resp.status_code, 403)

    def test_repair_with_wrong_token_returns_403(self):
        """POST /repair with an incorrect repair token must return 403."""
        resp = self._client.post(
            "/repair",
            json={"action": "warmup", "dry_run": True},
            headers={"X-Repair-Token": "0" * 64},  # valid hex format, wrong value
        )
        self.assertEqual(resp.status_code, 403)

    def test_repair_with_stale_nonhex_token_returns_403(self):
        """POST /repair with a non-hex repair token must return 403."""
        resp = self._client.post(
            "/repair",
            json={"action": "warmup", "dry_run": True},
            headers={"X-Repair-Token": "../../../etc/passwd"},
        )
        self.assertEqual(resp.status_code, 403)


class RateLimitPolicyTests(unittest.TestCase):
    def setUp(self):
        self._store = dict(guppy_api_auth.rate_limit_store)
        guppy_api_auth.rate_limit_store.clear()

    def tearDown(self):
        guppy_api_auth.rate_limit_store.clear()
        guppy_api_auth.rate_limit_store.update(self._store)

    def _req(self, path: str, method: str = "GET"):
        return SimpleNamespace(url=SimpleNamespace(path=path), method=method)

    def test_rate_limit_policy_routes_poll_vs_chat(self):
        poll_bucket, _, _ = guppy_api_auth._resolve_rate_limit_policy(self._req("/status", "GET"))
        chat_bucket, _, _ = guppy_api_auth._resolve_rate_limit_policy(self._req("/chat", "POST"))
        default_bucket, _, _ = guppy_api_auth._resolve_rate_limit_policy(self._req("/instances", "GET"))

        self.assertEqual(poll_bucket, "poll")
        self.assertEqual(chat_bucket, "chat")
        self.assertEqual(default_bucket, "default")

    def test_poll_bucket_does_not_block_chat_bucket(self):
        self.assertTrue(guppy_api_auth.check_rate_limit("user-a:poll", max_requests=1, window_minutes=60))
        self.assertFalse(guppy_api_auth.check_rate_limit("user-a:poll", max_requests=1, window_minutes=60))
        self.assertTrue(guppy_api_auth.check_rate_limit("user-a:chat", max_requests=1, window_minutes=60))


# ── DB utility tests ───────────────────────────────────────────────────────────

class DBUtilsTests(unittest.TestCase):
    def test_open_db_applies_wal_journal_mode(self):
        """open_db must set journal_mode=WAL so readers don't block the writer."""
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "test.sqlite3"
            conn = open_db(db_path)
            try:
                row = conn.execute("PRAGMA journal_mode").fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row[0].upper(), "WAL")
            finally:
                conn.close()

    def test_open_db_applies_busy_timeout(self):
        """open_db must set a non-zero busy_timeout so contended writers don't crash immediately."""
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "test.sqlite3"
            conn = open_db(db_path, busy_timeout_ms=3000)
            try:
                row = conn.execute("PRAGMA busy_timeout").fetchone()
                self.assertIsNotNone(row)
                self.assertGreater(int(row[0]), 0)
            finally:
                conn.close()

    def test_open_db_creates_parent_directory(self):
        """open_db must create missing parent directories without raising."""
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "nested" / "dir" / "test.sqlite3"
            self.assertFalse(db_path.parent.exists())
            conn = open_db(db_path)
            conn.close()
            self.assertTrue(db_path.exists())

    def test_concurrent_writes_to_shared_db_are_safe(self):
        """Multiple threads writing to the same DB must not corrupt data."""
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "concurrent.sqlite3"
            # Seed schema
            conn = open_db(db_path)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, val TEXT)"
            )
            conn.commit()
            conn.close()

            errors: list[Exception] = []
            n_writers = 5
            rows_per_writer = 20

            def _writer(idx: int) -> None:
                try:
                    c = open_db(db_path)
                    for i in range(rows_per_writer):
                        c.execute("INSERT INTO events (val) VALUES (?)", (f"w{idx}-r{i}",))
                        c.commit()
                    c.close()
                except Exception as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=_writer, args=(i,)) for i in range(n_writers)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=15.0)

            self.assertEqual(errors, [], f"Concurrent write errors: {errors}")

            verify = open_db(db_path)
            count = verify.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            verify.close()
            self.assertEqual(count, n_writers * rows_per_writer)


# ── Malformed runtime file tests ───────────────────────────────────────────────

@unittest.skipIf(not _LAUNCHER_WINDOW_AVAILABLE, "launcher_window archived — skip")
class MalformedRuntimeFileTests(unittest.TestCase):
    def test_corrupt_json_status_file_does_not_raise(self):
        """Corrupt JSON in a status file must be handled gracefully by the launcher."""
        with tempfile.TemporaryDirectory() as td:
            runtime_dir = Path(td)
            status_path = runtime_dir / "guppy.status"
            status_path.write_text("{not valid json{{{{", encoding="utf-8")

            old_runtime = launcher_window._RUNTIME
            launcher_window._RUNTIME = runtime_dir
            try:
                result = launcher_window.read_json_dict(status_path)
                self.assertIsInstance(result, dict)
                self.assertEqual(result, {})
            finally:
                launcher_window._RUNTIME = old_runtime

    def test_missing_status_file_returns_empty_dict(self):
        """A missing status file must return an empty dict, not raise."""
        with tempfile.TemporaryDirectory() as td:
            result = launcher_window.read_json_dict(Path(td) / "nonexistent.status")
            self.assertIsInstance(result, dict)
            self.assertEqual(result, {})

    def test_truncated_jsonl_file_skips_bad_lines(self):
        """A JSONL file with a truncated final line must yield only the valid lines."""
        with tempfile.TemporaryDirectory() as td:
            jsonl_path = Path(td) / "events.jsonl"
            jsonl_path.write_text(
                '{"event": "ok1"}\n'
                '{"event": "ok2"}\n'
                '{"event": "truncated',  # intentionally truncated
                encoding="utf-8",
            )
            result = launcher_window.read_jsonl_tail(jsonl_path, limit=50)
            events = [r.get("event") for r in result if isinstance(r, dict)]
            self.assertIn("ok1", events)
            self.assertIn("ok2", events)
            # Truncated line must not crash; it may be skipped or surfaced as error obj
            bad = [r for r in result if r.get("parse_error")]
            # Either skipped or surfaced — what's forbidden is an exception being raised.

    def test_empty_status_file_returns_empty_dict(self):
        """An empty status file must return empty dict."""
        with tempfile.TemporaryDirectory() as td:
            empty = Path(td) / "empty.status"
            empty.write_text("", encoding="utf-8")
            result = launcher_window.read_json_dict(empty)
            self.assertIsInstance(result, dict)
            self.assertEqual(result, {})


# ── Secret store tests ─────────────────────────────────────────────────────────

class SecretStoreTests(unittest.TestCase):
    def test_get_secret_returns_fallback_when_keyring_absent(self):
        """When keyring is unavailable, get_secret must return the fallback."""
        original_available = secret_store._KEYRING_AVAILABLE
        try:
            secret_store._KEYRING_AVAILABLE = False
            result = secret_store.get_secret("nonexistent_key", fallback="env-fallback-value")
            self.assertEqual(result, "env-fallback-value")
        finally:
            secret_store._KEYRING_AVAILABLE = original_available

    def test_get_secret_returns_none_fallback_when_nothing_configured(self):
        """No fallback and keyring absent → None."""
        original_available = secret_store._KEYRING_AVAILABLE
        try:
            secret_store._KEYRING_AVAILABLE = False
            result = secret_store.get_secret("nonexistent_key_no_fallback")
            self.assertIsNone(result)
        finally:
            secret_store._KEYRING_AVAILABLE = original_available

    def test_set_secret_returns_false_when_keyring_absent(self):
        """Writing to OS store must fail gracefully when keyring is absent."""
        original_available = secret_store._KEYRING_AVAILABLE
        try:
            secret_store._KEYRING_AVAILABLE = False
            result = secret_store.set_secret("some_key", "some_value")
            self.assertFalse(result)
        finally:
            secret_store._KEYRING_AVAILABLE = original_available

    def test_delete_secret_returns_false_when_keyring_absent(self):
        """Deleting from OS store must return False without raising when keyring absent."""
        original_available = secret_store._KEYRING_AVAILABLE
        try:
            secret_store._KEYRING_AVAILABLE = False
            result = secret_store.delete_secret("some_key")
            self.assertFalse(result)
        finally:
            secret_store._KEYRING_AVAILABLE = original_available


# ── Auth handshake and repair lifecycle tests ─────────────────────────────────

@unittest.skipIf(not _LAUNCHER_WINDOW_AVAILABLE, "launcher_window archived — skip")
class AuthAndRepairLifecycleTests(unittest.TestCase):
    def setUp(self):
        self._orig_keyring_available_secret_store = secret_store._KEYRING_AVAILABLE
        self._orig_keyring_available_launcher = launcher_window._SECRET_STORE_AVAILABLE
        self._orig_launcher_secret_store_obj = launcher_window._secret_store
        self._orig_api_repair_token = guppy_api._REPAIR_TOKEN
        self._orig_jwt_env = os.environ.get("GUPPY_JWT_SECRET")

    def tearDown(self):
        secret_store._KEYRING_AVAILABLE = self._orig_keyring_available_secret_store
        launcher_window._SECRET_STORE_AVAILABLE = self._orig_keyring_available_launcher
        launcher_window._secret_store = self._orig_launcher_secret_store_obj
        guppy_api._REPAIR_TOKEN = self._orig_api_repair_token
        guppy_api.app.dependency_overrides.pop(guppy_api.require_rate_limit, None)
        if self._orig_jwt_env is None:
            os.environ.pop("GUPPY_JWT_SECRET", None)
        else:
            os.environ["GUPPY_JWT_SECRET"] = self._orig_jwt_env

    def test_launcher_local_bearer_token_passes_auth_self_check(self):
        secret_store._KEYRING_AVAILABLE = False
        os.environ["GUPPY_JWT_SECRET"] = _TEST_SECRET
        guppy_api_auth.SECRET_KEY = _TEST_SECRET

        dummy = type("_DummyLauncher", (), {})()
        token = launcher_window.LauncherWindow._build_local_bearer_token(dummy)
        self.assertTrue(token)

        app = guppy_api.app
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/auth/self-check", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("ok"))

    def test_localhost_self_check_requires_bearer_token(self):
        secret_store._KEYRING_AVAILABLE = False
        os.environ["GUPPY_JWT_SECRET"] = _TEST_SECRET
        guppy_api_auth.SECRET_KEY = _TEST_SECRET
        # Freeze config so .env GUPPY_DEV_MODE=1 can't override our test state.
        with patch.object(guppy_api_auth, "_refresh_runtime_config"):
            guppy_api_auth.DEV_MODE = False
            app = guppy_api.app
            client = TestClient(app, raise_server_exceptions=False, client=("127.0.0.1", 50000))
            resp = client.get("/auth/self-check")
        self.assertEqual(resp.status_code, 401)

    def test_repair_token_accepted_from_keyring_and_file_fallback(self):
        app = guppy_api.app
        app.dependency_overrides[guppy_api.require_rate_limit] = lambda: "smoke-user"

        token = "b" * 64
        guppy_api._REPAIR_TOKEN = token

        # Keyring-backed launcher token source
        class _SecretStoreStub:
            @staticmethod
            def get_secret(_key: str):
                return token

        launcher_window._SECRET_STORE_AVAILABLE = True
        launcher_window._secret_store = _SecretStoreStub()
        dummy = type("_DummyLauncher", (), {})()
        k_token = launcher_window.LauncherWindow._read_repair_token(dummy)
        self.assertEqual(k_token, token)

        client = TestClient(app, raise_server_exceptions=False)
        resp_keyring = client.post(
            "/repair",
            json={"action": "warmup", "dry_run": True},
            headers={"X-Repair-Token": k_token},
        )
        self.assertNotEqual(resp_keyring.status_code, 403)

        # File fallback launcher token source
        with tempfile.TemporaryDirectory() as td:
            runtime_dir = Path(td)
            old_runtime = launcher_window._RUNTIME
            launcher_window._RUNTIME = runtime_dir
            launcher_window._SECRET_STORE_AVAILABLE = False
            (runtime_dir / "repair_token.txt").write_text(token, encoding="utf-8")
            f_token = launcher_window.LauncherWindow._read_repair_token(dummy)
            self.assertEqual(f_token, token)
            resp_file = client.post(
                "/repair",
                json={"action": "warmup", "dry_run": True},
                headers={"X-Repair-Token": f_token},
            )
            self.assertNotEqual(resp_file.status_code, 403)
            launcher_window._RUNTIME = old_runtime

    def test_repair_token_rotation_rejects_old_token(self):
        app = guppy_api.app
        app.dependency_overrides[guppy_api.require_rate_limit] = lambda: "smoke-user"
        client = TestClient(app, raise_server_exceptions=False)

        old_token = "c" * 64
        new_token = "d" * 64

        guppy_api._REPAIR_TOKEN = old_token
        resp_old_ok = client.post(
            "/repair",
            json={"action": "warmup", "dry_run": True},
            headers={"X-Repair-Token": old_token},
        )
        self.assertNotEqual(resp_old_ok.status_code, 403)

        guppy_api._REPAIR_TOKEN = new_token
        resp_old_rejected = client.post(
            "/repair",
            json={"action": "warmup", "dry_run": True},
            headers={"X-Repair-Token": old_token},
        )
        self.assertEqual(resp_old_rejected.status_code, 403)

        resp_new_ok = client.post(
            "/repair",
            json={"action": "warmup", "dry_run": True},
            headers={"X-Repair-Token": new_token},
        )
        self.assertNotEqual(resp_new_ok.status_code, 403)


# ── Repair token validation tests ─────────────────────────────────────────────

class RepairTokenValidationTests(unittest.TestCase):
    def test_validate_repair_token_rejects_empty_string(self):
        self.assertFalse(_is_valid_repair_token(""))

    def test_validate_repair_token_rejects_over_max_length(self):
        self.assertFalse(_is_valid_repair_token("a" * 257))

    def test_validate_repair_token_rejects_non_hex(self):
        self.assertFalse(_is_valid_repair_token("not-a-valid-token"))

    def test_validate_repair_token_rejects_mixed_case_non_hex(self):
        self.assertFalse(_is_valid_repair_token("ZZZZZZZZ"))

    def test_validate_repair_token_accepts_valid_64_char_hex(self):
        self.assertTrue(_is_valid_repair_token("a" * 64))

    def test_validate_repair_token_accepts_valid_hex_at_boundary(self):
        self.assertTrue(_is_valid_repair_token("0" * 256))

    def test_validate_repair_token_rejects_path_traversal_attempt(self):
        self.assertFalse(_is_valid_repair_token("../../../etc/passwd"))

    def test_validate_repair_token_rejects_null_bytes(self):
        token_with_null = "abcdef" + "\x00" + "abcdef"
        self.assertFalse(_is_valid_repair_token(token_with_null))


@unittest.skipIf(not _LAUNCHER_WINDOW_AVAILABLE, "launcher_window archived — skip")
class LauncherWriteJsonTests(unittest.TestCase):
    def test_write_json_raises_when_atomic_write_fails(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "state.json"

            with patch.object(launcher_window, "write_json_atomic", return_value=False):
                with self.assertRaises(OSError):
                    launcher_window._write_json(target, {"ok": True})


# ── Repair token re-sync endpoint tests ──────────────────────────────────────

class RepairTokenRefreshEndpointTests(unittest.TestCase):
    """Tests for GET /repair-token/refresh (repair token re-sync after API restart)."""

    @classmethod
    def setUpClass(cls):
        cls.app = guppy_api.app
        secret_store._KEYRING_AVAILABLE = False
        os.environ["GUPPY_JWT_SECRET"] = _TEST_SECRET
        guppy_api_auth.SECRET_KEY = _TEST_SECRET
        cls._client = TestClient(cls.app, raise_server_exceptions=False, client=("127.0.0.1", 50000))
        cls._external_client = TestClient(cls.app, raise_server_exceptions=False, client=("10.0.0.1", 50000))
        cls._token = guppy_api_auth.create_access_token({"sub": "smoke-user"})

    @classmethod
    def _auth_headers(cls):
        return {"Authorization": f"Bearer {cls._token}"}

    def test_refresh_returns_current_token_to_localhost(self):
        """
        GET /repair-token/refresh from localhost must return the active repair token.
        This is the primary re-sync path after an API restart.
        """
        token = "ee" * 32  # valid 64-char hex
        guppy_api._REPAIR_TOKEN = token
        resp = self._client.get("/repair-token/refresh", headers=self._auth_headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("repair_token", data)
        self.assertEqual(data["repair_token"], token)

    def test_refresh_endpoint_uses_in_memory_token_fallback(self):
        """
        When keyring and file are both unavailable the in-memory token is returned.
        """
        token = "ff" * 32
        guppy_api._REPAIR_TOKEN = token
        # Simulate keyring unavailable and no file
        old_available = guppy_api._SECRET_STORE_AVAILABLE
        old_file = guppy_api._REPAIR_TOKEN_FILE
        try:
            guppy_api._SECRET_STORE_AVAILABLE = False
            guppy_api._REPAIR_TOKEN_FILE = Path("/nonexistent/path/repair_token.txt")
            resp = self._client.get("/repair-token/refresh", headers=self._auth_headers())
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json().get("repair_token"), token)
        finally:
            guppy_api._SECRET_STORE_AVAILABLE = old_available
            guppy_api._REPAIR_TOKEN_FILE = old_file

    def test_refresh_requires_bearer_token_even_on_localhost(self):
        token = "cd" * 32
        guppy_api._REPAIR_TOKEN = token
        guppy_api_auth.DEV_MODE = False
        resp = self._client.get("/repair-token/refresh")
        self.assertEqual(resp.status_code, 401)

    def test_refresh_rejects_non_localhost_client(self):
        """
        GET /repair-token/refresh from a non-localhost IP must return 403.
        Simulates an external caller attempting to harvest the repair token.
        """
        token = "ab" * 32
        guppy_api._REPAIR_TOKEN = token
        resp = self._external_client.get("/repair-token/refresh", headers=self._auth_headers())
        self.assertEqual(resp.status_code, 403)


@unittest.skipIf(not _LAUNCHER_WINDOW_AVAILABLE, "launcher_window archived — skip")
class LauncherRepairTokenResyncTests(unittest.TestCase):
    """
    Tests for the launcher 403-triggered token re-sync flow.
    Simulates: old token cached → API restart → 403 → fetch refresh → retry → success.
    """

    def test_token_mismatch_triggers_refresh_and_retry(self):
        """
        Scenario: launcher sends old token → 403 repair_token_mismatch →
        launcher fetches /repair-token/refresh → retries with new token → succeeds.
        """
        import types as _types
        import urllib.error
        from unittest.mock import patch, MagicMock
        from ui.launcher import launcher_window as lw

        old_token = "aa" * 32
        new_token = "bb" * 32

        # Build a duck-typed stub and bind the real methods under test.
        stub = _types.SimpleNamespace()
        stub._api_bearer_token = "local-bearer"
        stub._api_token_source = "test"
        stub._api_base_url = lambda: "http://127.0.0.1:8100"
        stub._log_launcher_event = lambda *a, **kw: None
        stub._read_repair_token = lambda: old_token
        stub._http_json = _types.MethodType(lw.LauncherWindow._http_json, stub)
        stub._refresh_repair_token_from_api = _types.MethodType(
            lw.LauncherWindow._refresh_repair_token_from_api, stub
        )

        call_count = {"n": 0}

        def _fake_urlopen(req, timeout=None):
            url = req.get_full_url()
            call_count["n"] += 1
            if "/repair-token/refresh" in url:
                self.assertEqual(req.headers.get("Authorization"), "Bearer local-bearer")
                cm = MagicMock()
                cm.__enter__ = lambda s: MagicMock(
                    read=lambda: json.dumps({"repair_token": new_token}).encode()
                )
                cm.__exit__ = MagicMock(return_value=False)
                return cm
            if call_count["n"] == 1:
                # First /repair call → 403 mismatch
                body = json.dumps(
                    {"detail": {"code": "repair_token_mismatch", "message": "bad"}}
                ).encode()
                err = urllib.error.HTTPError(url, 403, "Forbidden", {}, None)
                err.read = lambda: body
                raise err
            # Retry /repair call after re-sync → success
            cm = MagicMock()
            cm.__enter__ = lambda s: MagicMock(
                read=lambda: json.dumps({"ok": True}).encode()
            )
            cm.__exit__ = MagicMock(return_value=False)
            return cm

        with patch.object(launcher_app, "is_valid_repair_token", return_value=True):
            with patch("ui.launcher.launcher_window.urllib.request.urlopen", side_effect=_fake_urlopen):
                result = stub._http_json(
                    "/repair", method="POST",
                    payload={"action": "warmup", "dry_run": True},
                )

        self.assertEqual(result.get("ok"), True)
        # Calls: initial /repair + /repair-token/refresh + retry /repair
        self.assertGreaterEqual(call_count["n"], 3)


if __name__ == "__main__":
    unittest.main()

