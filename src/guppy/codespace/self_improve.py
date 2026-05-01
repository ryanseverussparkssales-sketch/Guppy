"""Self-improvement pipeline.

When a triage run fails, the pipeline can:
1. Request an AI-generated fix proposal via the local inference stack
2. Apply the proposed changes to a feature branch
3. Run the dev-check in Docker (or subprocess) on the branch
4. Return the diff and test result for user review

Public API
----------
propose_fix(run_id, failure_text)  — blocking; returns FixProposal dict
apply_fix(proposal_id)             — applies patch to a new git branch
reject_fix(proposal_id)            — marks rejected; no branch changes
get_proposals(limit)               — list recent proposals
get_proposal(proposal_id)          — single proposal detail
"""
from __future__ import annotations

import logging
import sqlite3
import subprocess
import sys
import textwrap
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).parent.parent.parent.parent
_DB_PATH   = _REPO_ROOT / "runtime" / "triage.db"

# ── DB ────────────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fix_proposals (
            id           TEXT PRIMARY KEY,
            run_id       TEXT NOT NULL,
            created_at   TEXT NOT NULL,
            status       TEXT NOT NULL DEFAULT 'proposed',
            summary      TEXT NOT NULL DEFAULT '',
            diff         TEXT NOT NULL DEFAULT '',
            branch_name  TEXT,
            test_status  TEXT,
            test_output  TEXT
        )
    """)
    conn.commit()
    return conn


# ── Inference helper (local llama.cpp runtime) ───────────────────────────────

def _ask_inference(prompt: str, model: str = "hermes-3-8b-lorablated") -> str:
    """Call the local llama.cpp/OpenAI-compatible runtime."""
    try:
        from src.guppy.inference.local_client import local_chat

        result = local_chat(
            model,
            [{"role": "user", "content": prompt}],
            timeout=120,
            num_predict=800,
            max_retries=1,
        )
        if isinstance(result, dict):
            return str(result.get("response") or "").strip()
    except Exception as exc:
        logger.warning("[self_improve] inference call failed: %s", exc)
    return ""


# ── Proposal generation ───────────────────────────────────────────────────────

_FIX_PROMPT_TEMPLATE = textwrap.dedent("""
You are a Python developer working on the Guppy AI assistant codebase.
A dev-check (automated quality check) just failed. Analyze the failures below
and produce a concise fix in unified diff format.

FAILURES:
{failures}

RULES:
- Only touch files that are clearly responsible for the failures.
- Output ONLY a unified diff (--- a/... +++ b/...). No prose explanation before or after.
- If you cannot determine a safe fix, output: NO_FIX
""").strip()


def propose_fix(run_id: str, failure_text: str) -> dict[str, Any]:
    """Generate an AI fix proposal for a failed triage run."""
    pid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Try hermes4 (workspace.worker.primary – 14B code specialist) then hermes3 (8B fast fallback)
    prompt = _FIX_PROMPT_TEMPLATE.format(failures=failure_text[:3000])
    response = _ask_inference(prompt, model="hermes-4-14b") or _ask_inference(prompt, model="hermes-3-8b-lorablated")

    if not response or "NO_FIX" in response:
        diff    = ""
        summary = "No safe fix could be determined automatically."
        status  = "no_fix"
    else:
        # Extract diff block if wrapped in code fences
        diff = _extract_diff(response)
        summary = _summarize_diff(diff) if diff else "Proposed fix (no valid diff extracted)"
        status = "proposed"

    with _conn() as conn:
        conn.execute(
            "INSERT INTO fix_proposals (id, run_id, created_at, status, summary, diff) VALUES (?,?,?,?,?,?)",
            (pid, run_id, now, status, summary, diff),
        )
        conn.commit()

    logger.info("[self_improve] proposal %s: status=%s diff_lines=%d", pid[:8], status, diff.count("\n"))
    return {
        "id":         pid,
        "run_id":     run_id,
        "created_at": now,
        "status":     status,
        "summary":    summary,
        "diff":       diff,
    }


def _extract_diff(text: str) -> str:
    """Pull unified diff from model output, stripping code fences if present."""
    lines = text.splitlines()
    in_fence = False
    diff_lines: list[str] = []
    for line in lines:
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or line.startswith(("---", "+++", "@@", " ", "+", "-")):
            diff_lines.append(line)
    result = "\n".join(diff_lines).strip()
    # Must have at least one hunk
    return result if "@@" in result else ""


def _summarize_diff(diff: str) -> str:
    files = [l[6:] for l in diff.splitlines() if l.startswith("+++ b/")]
    if not files:
        return "Proposed code change"
    return f"Fix in: {', '.join(files[:3])}"


# ── Apply / reject ────────────────────────────────────────────────────────────

def apply_fix(proposal_id: str) -> dict[str, Any]:
    """Apply the fix diff to a new git branch and run a quick sanity check."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM fix_proposals WHERE id=?", (proposal_id,)
        ).fetchone()
    if not row:
        raise ValueError(f"Proposal {proposal_id} not found")
    if not row["diff"]:
        raise ValueError("No diff to apply")

    branch = f"guppy-fix-{proposal_id[:8]}"

    # Create branch
    _git("checkout", "-b", branch)

    # Write diff to temp file and apply
    diff_path = _REPO_ROOT / "runtime" / f"{proposal_id}.patch"
    diff_path.write_text(row["diff"], encoding="utf-8")
    apply_result = subprocess.run(
        ["git", "apply", "--check", str(diff_path)],
        cwd=str(_REPO_ROOT), capture_output=True, text=True,
    )

    if apply_result.returncode != 0:
        _git("checkout", "-")  # switch back to original branch
        _git("branch", "-D", branch)
        diff_path.unlink(missing_ok=True)
        with _conn() as conn:
            conn.execute("UPDATE fix_proposals SET status='apply_failed' WHERE id=?", (proposal_id,))
            conn.commit()
        return {"ok": False, "error": apply_result.stderr.strip(), "branch": branch}

    # Actually apply
    subprocess.run(
        ["git", "apply", str(diff_path)], cwd=str(_REPO_ROOT), capture_output=True
    )
    diff_path.unlink(missing_ok=True)

    # Run dev-check
    test_result = subprocess.run(
        [sys.executable, "tools/dev_workflow.py", "dev-check", "--guard-scope", "delta"],
        cwd=str(_REPO_ROOT), capture_output=True, text=True, timeout=180,
    )
    test_ok     = test_result.returncode == 0
    test_output = (test_result.stdout + test_result.stderr)[:5000]
    test_status = "passed" if test_ok else "failed"

    with _conn() as conn:
        conn.execute(
            "UPDATE fix_proposals SET status='applied', branch_name=?, test_status=?, test_output=? WHERE id=?",
            (branch, test_status, test_output, proposal_id),
        )
        conn.commit()

    return {
        "ok":          True,
        "branch":      branch,
        "test_status": test_status,
        "test_output": test_output,
    }


def reject_fix(proposal_id: str) -> None:
    with _conn() as conn:
        conn.execute("UPDATE fix_proposals SET status='rejected' WHERE id=?", (proposal_id,))
        conn.commit()


def get_proposals(limit: int = 20) -> list[dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, run_id, created_at, status, summary, branch_name, test_status "
            "FROM fix_proposals ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_proposal(proposal_id: str) -> dict[str, Any] | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM fix_proposals WHERE id=?", (proposal_id,)
        ).fetchone()
    return dict(row) if row else None


# ── Git helper ────────────────────────────────────────────────────────────────

def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=str(_REPO_ROOT), capture_output=True, text=True
    )
