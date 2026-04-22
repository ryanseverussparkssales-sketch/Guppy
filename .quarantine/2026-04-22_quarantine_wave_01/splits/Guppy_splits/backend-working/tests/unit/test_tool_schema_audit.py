from tools.audit_tool_schemas import audit_tools


def test_tool_schema_audit_passes():
    report = audit_tools()
    assert report["ok"], "Tool schema audit failed: " + " | ".join(report["errors"][:10])
