# Security and Resilience

Last verified: 2026-04-20

> **Updated: April 19, 2026 — Threat model and launch-gate sections added for PL-C6.**

## 1) Secret Storage Model

### OS-backed first

- Implementation: `utils/secret_store.py`
- Backend: `keyring` (Credential Manager / Keychain / SecretService)

### Fallback model

When keyring is unavailable, the code falls back to existing env/file paths to
preserve compatibility in constrained environments.

## 2) JWT Security

- JWT creation and verification in `src/guppy/api/auth.py`
- Placeholder secret detection enforced
- Strict-mode behavior rejects invalid/expired tokens
- Secret retrieval supports OS store (`jwt_secret`) with env fallback
- Direct loopback callers still require a valid bearer token; localhost only bypasses rate limiting, not authentication
- Request-rate enforcement now uses a SQLite-backed event store so limits stay bounded and shared across local processes on the same machine

## 3) Repair Endpoint Security

- Endpoint: `POST /repair`
- Requires valid `X-Repair-Token`
- Token is process-scoped and regenerated on API startup
- Cleanup removes token from OS store and file fallback on API shutdown
- Related endpoint: `GET /repair-token/refresh`
- `GET /repair-token/refresh` now requires both localhost origin and a valid bearer token before returning the active repair token

## 4) UI Concurrency Safety

Launcher assistant requests are correlated with monotonic sequence ids.
Responses from older requests are dropped before UI render.

Security impact:

- Prevents stale output from a prior command being rendered as the latest user response
- Reduces chance of operator error in multi-request bursts

## 5) Auth and Repair Diagnostics

### Launcher auth handshake probe

- Endpoint: `GET /auth/self-check`
- Purpose: validate launcher bearer token against API auth path before interactive chat/recovery usage
- Launcher logs `auth_self_check` events with token source metadata and result

### JWT reject reason codes

`guppy_api_auth.verify_token` now emits reason-coded responses:

- `auth_missing_bearer`
- `auth_invalid_payload`
- `auth_token_expired`
- `auth_token_invalid`
- `auth_jwt_not_configured`

### Repair token reject reason codes

`guppy_api._require_repair_token` emits reason-coded responses and warning telemetry events:

- `repair_token_uninitialized`
- `repair_token_missing`
- `repair_token_mismatch`

## 6) Instance Capability Enforcement

- Instance tool permissions are resolved from `config/tool_permissions.json`
- Backend enforcement now runs in `guppy_core/tool_runner.py`, not just launcher UI filters
- Active chat and instance-query inference forward instance name/type into tool execution

## 7) Instance Log Retention and Redaction

- Per-instance logs redact token-shaped secrets before persistence
- Raw per-instance JSONL logs are retention-pruned to a 14-day window on append/read
- 30-day summary metadata is maintained alongside raw logs for operator inspection

## 8) Database Lock and Durability Policy

All product SQLite paths should use `utils/db_utils.py`.

Policy enforces:

- WAL for reader/writer concurrency
- Busy timeout to reduce lock-race failures
- Synchronous mode consistency
- Foreign-key checks on

## 9) Regression Coverage

`tests/unit/test_security_hardening.py` includes coverage for:

1. Invalid JWT signatures and expired tokens
2. Missing JWT payload fields
3. Invalid/missing repair token rejection
4. Malformed runtime file handling
5. DB contention and concurrent write resilience
6. Secret-store fallback behavior
7. Launcher local bearer token accepted by API self-check
8. Repair token acceptance via keyring and file fallback reader paths
9. Repair token rotation rejects old token and accepts new token

Additional targeted coverage:

1. `tests/unit/test_instance_controls.py` validates backend capability gating and log retention behavior.
2. `tests/smoke/test_runtime_smoke.py` validates API forwarding of active instance context.

Current status: the default pytest gate excludes the interactive PTT hardware smoke and should be evaluated against the non-interactive unit plus integration suite.

---

## 10) Launch Security Gate (PL-C6, April 19 2026)

The explicit launch security gate runs as a step in `tools/dev_workflow.py release-check`
via `tools/run_security_gate.py`. It executes five checks and writes the result to
`runtime/security_gate_report.json`. `release-check` fails if the gate is not launch-ready.

### Gate checks

| Check | Category | What it verifies |
|-------|----------|-----------------|
| `secret_storage` | SECRET_STORAGE | OS keyring is available and not a degraded (null/plain) backend |
| `network_boundary` | NETWORK_BOUNDARY | `server_runtime.py` binds to 127.0.0.1, not 0.0.0.0 |
| `connector_scope` | CONNECTOR_SCOPE | `connector_manager.py` gates all access via auth_state checks; no raw unauthenticated HTTP |
| `build_posture` | BUILD_POSTURE | No plaintext secret files (*.env, *.key, *.pem, secrets.*) in `runtime/` |
| `dependency_hygiene` | DEPENDENCY | `requirements.txt` or `pyproject.toml` has at least one version-constrained dependency (`==`, `>=`, `~=`, `<=`, `!=`) |

Implementation: `src/guppy/launcher_application/security_gate.py`
Test coverage: `tests/unit/test_security_gate.py`

### Secret storage posture

All runtime secret writes MUST use `utils/secret_store.py`, which writes to the OS keyring first
(Windows Credential Manager, macOS Keychain, Linux SecretService). The env-var fallback is
allowed only when `GUPPY_DEV_MODE=1` is set.

No plaintext secrets should appear in:
- `config/` files (except documentation of field names, not values)
- `runtime/` files (gate check enforces this)
- Any file tracked by git (`.gitignore` enforces common patterns; audit enforced by `secret_storage` check)

### Network boundary posture

The Guppy API server (`src/guppy/api/server_runtime.py`) MUST bind to `127.0.0.1` by default.
Binding to `0.0.0.0` requires an explicit config override (`GUPPY_ALLOW_EXTERNAL_BIND=1`) and is
not supported in the default launcher configuration.

External tunnel access (e.g. Cloudflare) goes through the tunnel binary, not through a
`0.0.0.0` server bind.

### Connector least-privilege posture

Each connector action in `config/connector_bindings.json` must declare its required permission
scope. Connector binding validation (`src/guppy/workspace_governance/connector_binding_validation.py`)
rejects bindings that:
- Reference unknown connectors or providers
- Combine conflicting allow/block actions
- Request unsupported action IDs
- Use empty endpoint filters without explicit justification

### Dependency hygiene posture

`requirements.txt` must list runtime dependencies with explicit version constraints
(`==`, `>=`, `~=`, `<=`, or `!=`).
`requirements-dev.txt` and `requirements-optional.txt` may use range pins for developer flexibility.
The gate check confirms at least one constrained dependency line exists in
`requirements.txt` or `pyproject.toml`.

`python tools/dev_workflow.py release-check` now runs `tools/run_dependency_audit.py`,
which executes `pip-audit -r requirements.txt` and writes JSON evidence to
`.tmp/dev-workflow/reports/pip-audit-report.json`. External release candidates
should treat a failing dependency audit as a blocker.

---

## 11) Threat Model Summary

### Assets and trust levels

| Asset | Trust level | Primary protection |
|-------|------------|-------------------|
| JWT signing secret | OS keyring (high) | `utils/secret_store.py`, never written to disk in production |
| Repair token | In-process + OS keyring | Process-scoped, regenerated on startup, cleaned on shutdown |
| API-key credentials (providers) | OS keyring (high) | Entered via Settings UI, stored via `utils/secret_store.py` |
| Workspace files (user data) | Filesystem (user-owned) | Approved-root model in `src/guppy/workspace_governance/` |
| Connector OAuth tokens | OS keyring | Stored via keyring, never logged in full |
| Launcher auth bearer token | In-process | Scoped to launcher session, validated via `/auth/self-check` |

### Attack surface

| Surface | Exposure | Mitigation |
|---------|---------|-----------|
| HTTP API (port 47821) | localhost only | `HOST = "127.0.0.1"` enforced by network boundary gate check |
| Connector outbound calls | Remote via provider SDKs | Auth gated by auth_state checks; connector binding validation |
| Tool execution (read_file, run_python, etc.) | Local filesystem/runtime | Instance capability enforcement via `config/tool_permissions.json` |
| Packaged build (EXE) | Distribution surface | PyInstaller + validate_build_checks.py; secrets not bundled |
| Voice audio capture | Local mic | PTT model; no persistent audio recording; hardware tested in test_ptt.py |

### Known accepted risks

1. **Localhost-only API**: The API does not have TLS. This is accepted because it binds to 127.0.0.1 only.
	Guppy is a personal desktop assistant, not a multi-user server.
2. **Env-var fallback for secrets**: Allowed when `GUPPY_DEV_MODE=1` to preserve CI/dev ergonomics.
	The launch gate checks that keyring is available in production.
3. **Connector rate limits**: Rate limits on connector actions are enforced per-instance, not per-user.
	Adequate for personal use; external deployment would need per-user rate limiting.
