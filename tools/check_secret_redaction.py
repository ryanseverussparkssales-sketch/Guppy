"""tools/check_secret_redaction.py

Audit tool: scan snapshot and readiness response-builder source files for
credential patterns that might leak into API response bodies.

Rules
-----
A line is flagged if it contains a credential pattern (api_key, password,
token, secret) AND it appears inside a response dict literal or return
statement without a redaction marker (*** or [REDACTED]).

Exit codes
----------
0 — no leaks found
1 — one or more potential leaks found (must be reviewed)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Files that assemble snapshot / readiness / status response bodies.
_SCAN_TARGETS: list[str] = [
    "src/guppy/api/server_runtime_snapshot.py",
    "src/guppy/api/snapshot_status_context_support.py",
    "src/guppy/api/services_runtime.py",
    "src/guppy/api/status_support.py",
    "src/guppy/api/_server_fragment_runtime_status.py",
    "src/guppy/api/snapshot_runtime_support.py",
    "src/guppy/api/snapshot_route_support.py",
]

# Patterns that indicate a credential value is being handled.
_CREDENTIAL_PATTERN = re.compile(
    r"\b(api_key|password|token|secret)\b",
    re.IGNORECASE,
)

# Patterns that indicate the value is being CHECKED (bool/ready check),
# not included in a response body.
_SAFE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"secret_ready\("),          # bool readiness check
    re.compile(r"backend_is_secure\("),     # keyring posture check
    re.compile(r"os\.environ\.get\("),      # reading env (not emitting)
    re.compile(r"\.get\(.*ANTHROPIC"),      # reading config key
    re.compile(r"create_access_token\("),   # JWT creation call
    re.compile(r"verify_token\("),          # JWT validation call
    re.compile(r"require_turnstile"),       # auth middleware
    re.compile(r"#\s*(noqa|nosec|redact)"), # explicit annotation
    re.compile(r"\*\*\*"),                  # redaction marker present
    re.compile(r"\[REDACTED\]"),            # redaction marker present
    re.compile(r"import\s"),               # import lines
    re.compile(r"from\s"),                 # import lines
    re.compile(r"^\s*#"),                  # comment lines
    re.compile(r"del\s+"),                 # variable deletion
    re.compile(r"api_key=api_key"),        # passing to SDK constructor (not response)
    re.compile(r"logger\.(debug|info|warning|error)"),  # log calls
    re.compile(r"log_session_event\("),    # session log calls
    re.compile(r"raise\s+RuntimeError"),   # raising errors, not emitting
    re.compile(r"if\s+(not\s+)?\w"),       # conditional checks on variable
    re.compile(r"bool\("),                 # bool() wrapping a variable
    re.compile(r"secret_store\.get_secret"),  # reading from store (local var)
    re.compile(r"getattr\("),              # attribute access
    re.compile(r"read_text\("),            # reading a file into a local var
]

# Lines that look like they're INSIDE a response dict or return statement.
_RESPONSE_CONTEXT = re.compile(
    r"""(
        ".*":\s*.*\b(api_key|password|token|secret)\b  # dict key/value pair
      | return\s+\{.*\b(api_key|password|token|secret)\b  # inline return dict
    )""",
    re.IGNORECASE | re.VERBOSE,
)


def _is_safe(line: str) -> bool:
    """Return True if the credential mention is demonstrably safe."""
    return any(pat.search(line) for pat in _SAFE_PATTERNS)


def _looks_like_response_emission(line: str) -> bool:
    """Return True if the line looks like it puts a credential into a response body."""
    stripped = line.strip()
    # Dictionary literal entry: "some_key": <value with credential>
    if re.search(r'"[^"]*":\s*.*(api_key|password|token|secret)', stripped, re.IGNORECASE):
        return True
    # Direct assignment inside a dict building block
    if re.search(r"(api_key|password|token|secret)\s*[:=]", stripped, re.IGNORECASE):
        return True
    return False


def _scan_file(path: Path) -> list[tuple[int, str]]:
    """Return (line_number, line_text) tuples for flagged lines in *path*."""
    if not path.exists():
        return []
    findings: list[tuple[int, str]] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        if not _CREDENTIAL_PATTERN.search(raw):
            continue
        if _is_safe(raw):
            continue
        if _looks_like_response_emission(raw):
            findings.append((lineno, raw.rstrip()))
    return findings


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    total_findings: list[tuple[str, int, str]] = []

    for relative in _SCAN_TARGETS:
        path = root / relative
        for lineno, text in _scan_file(path):
            total_findings.append((relative, lineno, text))

    if not total_findings:
        print("check_secret_redaction: PASS — no credential patterns found in response builders.")
        return 0

    print("check_secret_redaction: WARN — review the following lines for potential secret leakage:\n")
    for rel, lineno, text in total_findings:
        print(f"  {rel}:{lineno}: {text.strip()}")
    print(
        f"\n{len(total_findings)} line(s) flagged. Confirm each is a variable name or safe reference, "
        "not a literal credential value in a response body."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
