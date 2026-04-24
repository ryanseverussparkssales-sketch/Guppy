"""
tool_permissions_policy.py

Purpose: Split tool permissions from policies with explicit allow/block rationale
Lane: TR54-C2

Responsibilities:
  - Permission definitions for tools (read, write, execute, etc.)
  - Policy decisions (allow/block with reasoning)
  - Policy override tracking
  - Permission audit logging

Permission Model:

ALLOW POLICY:
  {
    "tool_key": "github",
    "permissions": ["read:repos", "write:issues"],
    "policy": "allow",
    "rationale": "Needed for GitHub integration",
    "approved_by": "user@example.com",
    "approved_at": "2024-01-15T10:30:00Z",
    "expires_at": null,  # null = no expiration
    "override_reason": null,  # null = not overridden
  }

DENY POLICY:
  {
    "tool_key": "s3",
    "permissions": ["write:bucket:prod"],
    "policy": "deny",
    "rationale": "Production bucket write blocked by security policy",
    "reason_code": "security_policy_restriction",
    "affected_by": ["enterprise_policy", "data_classification_restricted"],
  }

Permission Categories:
  - read:* - Read-only access
  - write:* - Write access
  - execute:* - Execution/invocation
  - delete:* - Deletion access
  - admin:* - Administrative access

Policy Decision Reasons:
  ALLOW:
    - user_approval - User explicitly approved
    - tool_trusted - Tool is in trusted list
    - permission_granted - Permission explicitly granted
    - default_allow - Default policy is allow

  DENY:
    - user_denial - User explicitly denied
    - tool_blocked - Tool is in blocked list
    - permission_not_granted - Permission not explicitly granted
    - default_deny - Default policy is deny
    - security_policy_restriction - Org security policy blocks
    - data_classification_mismatch - Data classification incompatible
    - quota_exceeded - Resource quota exceeded
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time


class Permission(Enum):
    """Permission types."""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELETE = "delete"
    ADMIN = "admin"


class PolicyDecision(Enum):
    """Policy decision."""
    ALLOW = "allow"
    DENY = "deny"
    UNKNOWN = "unknown"


class AllowReason(Enum):
    """Reason for allow decision."""
    USER_APPROVAL = "user_approval"
    TOOL_TRUSTED = "tool_trusted"
    PERMISSION_GRANTED = "permission_granted"
    DEFAULT_ALLOW = "default_allow"
    OVERRIDE = "override"


class DenyReason(Enum):
    """Reason for deny decision."""
    USER_DENIAL = "user_denial"
    TOOL_BLOCKED = "tool_blocked"
    PERMISSION_NOT_GRANTED = "permission_not_granted"
    DEFAULT_DENY = "default_deny"
    SECURITY_POLICY = "security_policy_restriction"
    DATA_CLASSIFICATION = "data_classification_mismatch"
    QUOTA_EXCEEDED = "quota_exceeded"


@dataclass
class ToolPermission:
    """A single tool permission."""
    tool_key: str
    permission: str  # e.g., "read:files", "write:config"
    scope: str = ""  # e.g., "/path/to/resource" for scoped permissions


@dataclass
class PolicyDecisionRecord:
    """Records a policy decision for a tool permission."""
    tool_key: str
    permissions: list[str] = field(default_factory=list)
    decision: PolicyDecision = PolicyDecision.UNKNOWN
    rationale: str = ""
    reason: Optional[str] = None  # Allow/DenyReason enum value as string
    approved_by: Optional[str] = None
    approved_at: Optional[float] = None
    expires_at: Optional[float] = None  # None = no expiration
    override_reason: Optional[str] = None  # If overridden, why
    affected_by: list[str] = field(default_factory=list)  # List of policies affecting this

    def is_allow(self) -> bool:
        """Check if decision is allow."""
        return self.decision == PolicyDecision.ALLOW

    def is_deny(self) -> bool:
        """Check if decision is deny."""
        return self.decision == PolicyDecision.DENY

    def is_expired(self) -> bool:
        """Check if decision has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def is_overridden(self) -> bool:
        """Check if decision was overridden."""
        return self.override_reason is not None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "tool_key": self.tool_key,
            "permissions": self.permissions,
            "decision": self.decision.value,
            "rationale": self.rationale,
            "reason": self.reason,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "expires_at": self.expires_at,
            "override_reason": self.override_reason,
            "affected_by": self.affected_by,
        }


class ToolPermissionPolicy:
    """Manages tool permissions and policy decisions."""

    def __init__(self) -> None:
        """Initialize policy manager."""
        self.policies: dict[str, PolicyDecisionRecord] = {}
        self.policy_overrides: dict[str, PolicyDecisionRecord] = {}
        self.audit_log: list[dict] = []

    def set_policy(
        self,
        tool_key: str,
        permissions: list[str],
        decision: PolicyDecision,
        rationale: str,
        reason: Optional[str] = None,
        approved_by: Optional[str] = None,
        expires_at: Optional[float] = None,
    ) -> PolicyDecisionRecord:
        """
        Set a policy decision for a tool.

        Args:
            tool_key: Tool identifier
            permissions: List of permissions (e.g., ["read:files", "write:config"])
            decision: Allow or deny
            rationale: Human-readable explanation
            reason: Machine-readable reason (AllowReason/DenyReason enum value)
            approved_by: User who approved
            expires_at: Unix timestamp when policy expires (None = no expiration)

        Returns:
            PolicyDecisionRecord
        """
        record = PolicyDecisionRecord(
            tool_key=tool_key,
            permissions=permissions,
            decision=decision,
            rationale=rationale,
            reason=reason,
            approved_by=approved_by,
            approved_at=time.time(),
            expires_at=expires_at,
        )
        self.policies[tool_key] = record
        self._audit_log("policy_set", record.to_dict())
        return record

    def override_policy(
        self,
        tool_key: str,
        override_reason: str,
        new_decision: Optional[PolicyDecision] = None,
    ) -> PolicyDecisionRecord:
        """
        Override an existing policy.

        Args:
            tool_key: Tool identifier
            override_reason: Reason for override
            new_decision: Optional new decision (if changing)

        Returns:
            Updated PolicyDecisionRecord
        """
        if tool_key not in self.policies:
            raise ValueError(f"No policy found for tool: {tool_key}")

        record = self.policies[tool_key]
        record.override_reason = override_reason

        if new_decision:
            record.decision = new_decision

        self.policy_overrides[tool_key] = record
        self._audit_log("policy_override", {"tool_key": tool_key, "reason": override_reason})
        return record

    def get_policy(self, tool_key: str) -> Optional[PolicyDecisionRecord]:
        """Get policy for a tool."""
        return self.policies.get(tool_key)

    def check_permission(
        self, tool_key: str, permission: str
    ) -> tuple[PolicyDecision, str]:
        """
        Check if a permission is allowed.

        Args:
            tool_key: Tool identifier
            permission: Permission to check (e.g., "read:files")

        Returns:
            Tuple of (decision, rationale)
        """
        if tool_key not in self.policies:
            # No policy = unknown
            return PolicyDecision.UNKNOWN, f"No policy defined for tool: {tool_key}"

        record = self.policies[tool_key]

        if record.is_expired():
            return PolicyDecision.UNKNOWN, f"Policy expired for tool: {tool_key}"

        if permission not in record.permissions:
            return PolicyDecision.DENY, f"Permission not in policy: {permission}"

        return record.decision, record.rationale

    def list_policies(self) -> list[PolicyDecisionRecord]:
        """Get all policies."""
        return list(self.policies.values())

    def list_allow_policies(self) -> list[PolicyDecisionRecord]:
        """Get all allow policies."""
        return [p for p in self.policies.values() if p.is_allow()]

    def list_deny_policies(self) -> list[PolicyDecisionRecord]:
        """Get all deny policies."""
        return [p for p in self.policies.values() if p.is_deny()]

    def list_overridden_policies(self) -> list[PolicyDecisionRecord]:
        """Get all overridden policies."""
        return [p for p in self.policies.values() if p.is_overridden()]

    def _audit_log(self, action: str, data: dict) -> None:
        """Log audit event."""
        self.audit_log.append({
            "timestamp": time.time(),
            "action": action,
            "data": data,
        })

    def get_audit_log(self, limit: int = 100) -> list[dict]:
        """Get recent audit log entries."""
        return self.audit_log[-limit:]
