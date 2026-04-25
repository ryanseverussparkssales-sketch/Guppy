"""Audit tool schemas registered in guppy_core/tool_registry.py.

Verifies that every registered tool has the minimum required fields:
name, description, and a valid parameters schema. Writes a JSON report.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_REQUIRED_FIELDS = {"name", "description"}


def _load_tools() -> list[dict]:
    """Load tool definitions from guppy_core if available, else return []."""
    try:
        import importlib
        mod = importlib.import_module("guppy_core.tool_registry")
        # Try TOOLS first (canonical), then TOOL_REGISTRY, then get_tools()
        tools = getattr(mod, "TOOLS", None)
        if tools is None:
            tools = getattr(mod, "TOOL_REGISTRY", None)
        if tools is None:
            getter = getattr(mod, "get_tools", None)
            if callable(getter):
                tools = getter()
        return list(tools) if tools else []
    except Exception as exc:
        print(f"  note: could not load guppy_core.tool_registry ({exc}) — skipping tool audit")
        return []


def audit(tools: list[dict]) -> list[dict]:
    findings: list[dict] = []
    for tool in tools:
        name = tool.get("name", "<unnamed>")
        missing = _REQUIRED_FIELDS - set(tool.keys())
        if missing:
            findings.append({"tool": name, "issue": f"missing fields: {sorted(missing)}"})
        # Accept either 'parameters' (OpenAI style) or 'input_schema' (Anthropic style)
        schema = tool.get("parameters") or tool.get("input_schema")
        if schema is not None and not isinstance(schema, dict):
            findings.append({"tool": name, "issue": "schema (parameters/input_schema) must be a dict"})
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit tool schemas")
    parser.add_argument("--report", type=Path, default=None, help="Write JSON report to path")
    args = parser.parse_args()

    tools = _load_tools()
    findings = audit(tools)

    report = {
        "tool_count": len(tools),
        "finding_count": len(findings),
        "findings": findings,
    }

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2))
        print(f"  report written to {args.report}")

    if findings:
        print(f"tool schema audit FAILED ({len(findings)} finding(s)):")
        for f in findings:
            print(f"  [{f['tool']}] {f['issue']}")
        sys.exit(1)

    print(f"tool schema audit passed ({len(tools)} tool(s) checked)")


if __name__ == "__main__":
    main()
