from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ALLOWED_TYPES = {
    "string",
    "number",
    "integer",
    "boolean",
    "array",
    "object",
    "null",
}


def _load_tools() -> list[dict[str, Any]]:
    from guppy_core import TOOLS  # Imported lazily to keep module load cheap.

    if not isinstance(TOOLS, list):
        raise TypeError("guppy_core.TOOLS is not a list")
    return TOOLS


def audit_tools() -> dict[str, Any]:
    tools = _load_tools()
    errors: list[str] = []
    warnings: list[str] = []
    seen_names: set[str] = set()

    for idx, tool in enumerate(tools):
        prefix = f"tool[{idx}]"
        if not isinstance(tool, dict):
            errors.append(f"{prefix} is not a dict")
            continue

        name = tool.get("name")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"{prefix} has invalid or missing 'name'")
            continue
        name = name.strip()

        if name in seen_names:
            errors.append(f"{name}: duplicate tool name")
            continue
        seen_names.add(name)

        schema = tool.get("input_schema")
        if not isinstance(schema, dict):
            errors.append(f"{name}: missing or invalid input_schema")
            continue

        schema_type = schema.get("type")
        if schema_type != "object":
            errors.append(f"{name}: input_schema.type must be 'object', got {schema_type!r}")

        properties = schema.get("properties")
        if not isinstance(properties, dict):
            errors.append(f"{name}: input_schema.properties must be a dict")
            continue

        required = schema.get("required", [])
        if required is None:
            required = []
        if not isinstance(required, list):
            errors.append(f"{name}: input_schema.required must be a list")
            required = []

        prop_names = set(properties.keys())
        for req in required:
            if not isinstance(req, str):
                errors.append(f"{name}: required contains non-string value {req!r}")
                continue
            if req not in prop_names:
                errors.append(f"{name}: required field {req!r} not present in properties")

        for prop_name, prop_schema in properties.items():
            if not isinstance(prop_schema, dict):
                errors.append(f"{name}: property {prop_name!r} schema must be an object")
                continue

            prop_type = prop_schema.get("type")
            if prop_type is None:
                warnings.append(f"{name}: property {prop_name!r} missing explicit type")
                continue

            if isinstance(prop_type, list):
                invalid = [t for t in prop_type if t not in ALLOWED_TYPES]
                if invalid:
                    errors.append(
                        f"{name}: property {prop_name!r} has unsupported type entries {invalid!r}"
                    )
            elif isinstance(prop_type, str):
                if prop_type not in ALLOWED_TYPES:
                    errors.append(
                        f"{name}: property {prop_name!r} has unsupported type {prop_type!r}"
                    )
            else:
                errors.append(
                    f"{name}: property {prop_name!r} has invalid type descriptor {prop_type!r}"
                )

    summary = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tool_count": len(tools),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "ok": len(errors) == 0,
    }
    return summary


def write_report(report: dict[str, Any], report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Guppy tool input schemas")
    parser.add_argument(
        "--report",
        default="runtime/tool_schema_audit.json",
        help="Path to write JSON audit report",
    )
    args = parser.parse_args()

    report = audit_tools()
    path = Path(args.report)
    write_report(report, path)

    print(f"Tool schema audit: {report['tool_count']} tools")
    print(f"Errors: {report['error_count']} | Warnings: {report['warning_count']}")
    print(f"Report: {path}")
    if report["errors"]:
        for err in report["errors"][:25]:
            print(f"- ERROR: {err}")
    if report["warnings"]:
        for warn in report["warnings"][:10]:
            print(f"- WARN: {warn}")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
