"""
guppy_core — Shared backend for Guppy
======================================
Package entry point. All public symbols are re-exported here so that
existing `from guppy_core import X` calls continue to work unchanged.

Submodules (import directly for leaner imports):
  guppy_core.debug_flags   — runtime constants, circuit-breaker config
  guppy_core.beta_policy   — beta-restricted-mode allowlist
  guppy_core.network_utils — is_online(), check_llamacpp()
  guppy_core.tool_metrics  — circuit-breaker helpers, get_tool_health_snapshot()
  guppy_core.tool_registry — TOOLS list, _validate_tool_input()
  guppy_core.system_prompt — SYSTEM prompt, get_startup_system()
  guppy_core.tool_runner   — run_tool(), _exec_tool(), _morning_brief()

Adding a new tool? Edit TOOLS in guppy_core/tool_registry.py and
_exec_tool in guppy_core/tool_runner.py.
"""

# ── Extracted submodules ───────────────────────────────────────────────────────────────────────────────────────
from guppy_core.debug_flags import (  # noqa: F401
    SAFE_MODE, TOOL_LOG,
    TOOL_EXEC_TIMEOUT_SECONDS, TOOL_CIRCUIT_FAIL_THRESHOLD,
    TOOL_CIRCUIT_COOLDOWN_SECONDS, TOOL_MAX_OUTPUT_CHARS,
    _TOOL_EXECUTOR, _TOOL_GUARD_LOCK, _TOOL_GUARDS, _TOOL_METRICS,
)
from guppy_core.beta_policy import (  # noqa: F401
    BETA_RESTRICTED_MODE, BETA_TOOL_ALLOWLIST, get_beta_policy_snapshot,
)
from guppy_core.network_utils import is_online, check_llamacpp  # noqa: F401
from guppy_core.tool_metrics import (  # noqa: F401
    _tool_metric, _record_tool_call, _tool_guard,
    _is_tool_blocked, _mark_tool_success, _mark_tool_failure,
    get_tool_health_snapshot,
)
from guppy_core.tool_registry import TOOLS, _validate_tool_input  # noqa: F401
from guppy_core.system_prompt import (  # noqa: F401
    SYSTEM, REPORTS_DIR,
    _needs_memory_context, get_startup_system,
)
from guppy_core.tool_runner import run_tool  # noqa: F401

# ── Module-level optional-import state re-exported for legacy callers ─────────────────
# merlin_core.py does: from guppy_core import _mem, _MEM
# Keep these as module attributes on guppy_core so that import works.
from guppy_core.tool_runner import (  # noqa: F401
    _mem, _MEM,
    _smem, _SMEM,
    DAEMON,
    PYA,
)
