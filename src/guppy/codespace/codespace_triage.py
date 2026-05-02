"""Codespace self-triage module.

Runs `python tools/dev_workflow.py dev-check --guard-scope delta` on demand
or when source files change (debounced watchdog thread). Results are stored
in a SQLite DB for the API and UI to query.

Public API
----------
run_triage()          — run a dev-check immediately, blocking; returns TriageRun dict
trigger_triage_async()— schedule a run in the background thread pool; returns run_id
get_runs(limit)       — list recent runs from DB
start_watchdog()      — start background thread that watches src/guppy/ for changes
stop_watchdog()       — signal background thread to stop
"""
from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────

_REPO_ROOT   = Path(__file__).parent.parent.parent.parent
_WATCH_PATHS = [_REPO_ROOT / "src" / "guppy", _REPO_ROOT / "tools"]
_DB_PATH     = _REPO_ROOT / "runtime" / "triage.db"

# ── DB ────────────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS triage_runs (
            id           TEXT PRIMARY KEY,
            triggered_at TEXT NOT NULL,
            trigger      TEXT NOT NULL DEFAULT 'manual',
            status       TEXT NOT NULL DEFAULT 'running',
            output       TEXT NOT NULL DEFAULT '',
            failures     TEXT NOT NULL DEFAULT '[]',
            duration_s   REAL
        )
    """)
    conn.commit()
    return conn

# ── Parsing ───────────────────────────────────────────────────────────────────

_FAIL_RE = re.compile(r"(FAIL|ERROR|failed|error).*$", re.IGNORECASE)
_CHECK_RE = re.compile(r"^==> (.+)$", re.MULTILINE)

def _parse_output(output: str) -> list[str]:
    """Extract failure lines from dev-check output."""
    failures: list[str] = []
    for line in output.splitlines():
        low = line.lower()
        if ("fail" in low or "error" in low) and not low.startswith("#"):
            failures.append(line.strip())
    return failures[:50]  # cap at 50

# ── Core runner ───────────────────────────────────────────────────────────────

_run_lock = threading.Lock()  # prevent concurrent triage runs

def run_triage(trigger: str = "manual") -> dict[str, Any]:
    """Run dev-check synchronously. Returns a TriageRun dict."""
    run_id  = str(uuid.uuid4())
    started = datetime.now(timezone.utc).isoformat()
    logger.info("[triage] run %s started (trigger=%s)", run_id[:8], trigger)

    # Insert a running record immediately
    with _conn() as conn:
        conn.execute(
            "INSERT INTO triage_runs (id, triggered_at, trigger, status, output, failures, duration_s) "
            "VALUES (?, ?, ?, 'running', '', '[]', NULL)",
            (run_id, started, trigger),
        )
        conn.commit()

    t0 = time.monotonic()
    try:
        with _run_lock:
            proc = subprocess.run(
                [
                    sys.executable, "tools/dev_workflow.py",
                    "dev-check", "--guard-scope", "delta",
                ],
                cwd=str(_REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=300,  # 5-minute hard cap
            )
        output   = (proc.stdout or "") + (proc.stderr or "")
        failures = _parse_output(output)
        status   = "passed" if proc.returncode == 0 else "failed"
    except subprocess.TimeoutExpired:
        output   = "dev-check timed out after 300 s"
        failures = [output]
        status   = "failed"
    except Exception as exc:
        output   = f"run error: {exc}"
        failures = [output]
        status   = "failed"

    duration = round(time.monotonic() - t0, 2)
    logger.info("[triage] run %s %s in %.1f s", run_id[:8], status, duration)

    with _conn() as conn:
        conn.execute(
            "UPDATE triage_runs SET status=?, output=?, failures=?, duration_s=? WHERE id=?",
            (status, output[:50_000], json.dumps(failures), duration, run_id),
        )
        conn.commit()

    # Teach semantic memory: store each unique failure pattern so future agents
    # can recall what errors have been seen and how they were categorised.
    if failures:
        try:
            from src.guppy.memory.semantic import remember_semantic
            # Deduplicate: strip line numbers / file paths to get the error type
            _seen: set[str] = set()
            for line in failures[:10]:
                # Normalise: drop leading path components and collapse whitespace
                _key_raw = re.sub(r"([\\/][\w.\-]+){2,}", "<path>", line)
                _key_raw = re.sub(r"\s+", " ", _key_raw).strip()
                _bucket  = _key_raw[:120]
                if _bucket in _seen:
                    continue
                _seen.add(_bucket)
                _mem_key = f"triage_error:{_bucket[:80]}"
                _mem_val = (
                    f"Triage failure ({status}) in run {run_id[:8]} "
                    f"[trigger={trigger}]:\n{line.strip()}"
                )
                remember_semantic(_mem_key, _mem_val, "triage_pattern")
        except Exception as _mex:
            logger.debug("[triage] semantic pattern store skipped: %s", _mex)

    return {
        "id":           run_id,
        "triggered_at": started,
        "trigger":      trigger,
        "status":       status,
        "output":       output[:50_000],
        "failures":     failures,
        "duration_s":   duration,
    }


def trigger_triage_async(trigger: str = "manual") -> str:
    """Kick off a triage run in a daemon thread. Returns run_id immediately."""
    run_id  = str(uuid.uuid4())
    started = datetime.now(timezone.utc).isoformat()

    with _conn() as conn:
        conn.execute(
            "INSERT INTO triage_runs (id, triggered_at, trigger, status) VALUES (?, ?, ?, 'queued')",
            (run_id, started, trigger),
        )
        conn.commit()

    def _worker():
        # Replace the queued record with a real run
        with _conn() as conn:
            conn.execute("DELETE FROM triage_runs WHERE id=?", (run_id,))
            conn.commit()
        result = run_triage(trigger)
        # Update with the actual run_id from run_triage (same id since we pass trigger)
        # run_triage generates its own id — patch ours back in
        with _conn() as conn:
            # The record was already written by run_triage with its own id
            # We need to update that newest record to use our promised run_id
            newest = conn.execute(
                "SELECT id FROM triage_runs ORDER BY triggered_at DESC LIMIT 1"
            ).fetchone()
            if newest and newest["id"] != run_id:
                conn.execute(
                    "UPDATE triage_runs SET id=? WHERE id=?",
                    (run_id, newest["id"]),
                )
                conn.commit()

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return run_id


def get_runs(limit: int = 20) -> list[dict[str, Any]]:
    """Return recent triage runs, newest first."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, triggered_at, trigger, status, failures, duration_s "
            "FROM triage_runs ORDER BY triggered_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    result = []
    for r in rows:
        result.append({
            "id":           r["id"],
            "triggered_at": r["triggered_at"],
            "trigger":      r["trigger"],
            "status":       r["status"],
            "failures":     json.loads(r["failures"] or "[]"),
            "duration_s":   r["duration_s"],
        })
    return result


def get_run_output(run_id: str) -> str | None:
    """Return full output text for a run."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT output FROM triage_runs WHERE id=?", (run_id,)
        ).fetchone()
    return row["output"] if row else None

# ── Watchdog ──────────────────────────────────────────────────────────────────

_watchdog_thread: threading.Thread | None = None
_watchdog_stop   = threading.Event()
_DEBOUNCE_S      = 60  # seconds to wait after last change before triggering

def _mtimes() -> dict[str, float]:
    """Collect modification times of all .py files under watched paths."""
    result = {}
    for root_path in _WATCH_PATHS:
        if not root_path.exists():
            continue
        for p in root_path.rglob("*.py"):
            try:
                result[str(p)] = p.stat().st_mtime
            except OSError:
                pass
    return result


def _watchdog_loop() -> None:
    logger.info("[triage] watchdog started (debounce=%ds)", _DEBOUNCE_S)
    last_mtimes = _mtimes()
    last_change: float | None = None

    while not _watchdog_stop.is_set():
        time.sleep(5)  # poll every 5 s
        if _watchdog_stop.is_set():
            break

        current = _mtimes()
        changed = current != last_mtimes
        last_mtimes = current

        if changed:
            last_change = time.monotonic()

        if last_change and (time.monotonic() - last_change) >= _DEBOUNCE_S:
            last_change = None
            logger.info("[triage] file changes detected — auto-triggering triage")
            try:
                trigger_triage_async(trigger="watchdog")
            except Exception as exc:
                logger.warning("[triage] watchdog trigger failed: %s", exc)

    logger.info("[triage] watchdog stopped")


def start_watchdog() -> None:
    """Start the background file-change watchdog (idempotent)."""
    global _watchdog_thread
    if _watchdog_thread and _watchdog_thread.is_alive():
        return
    _watchdog_stop.clear()
    _watchdog_thread = threading.Thread(target=_watchdog_loop, name="triage-watchdog", daemon=True)
    _watchdog_thread.start()


def stop_watchdog() -> None:
    """Signal the watchdog thread to stop."""
    _watchdog_stop.set()
