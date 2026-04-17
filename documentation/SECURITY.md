# Security and Resilience

Last verified: 2026-04-16

## 1) Secret Storage Model

### OS-backed first

- Implementation: `utils/secret_store.py`
- Backend: `keyring` (Credential Manager / Keychain / SecretService)

### Fallback model

When keyring is unavailable, the code falls back to existing env/file paths to
preserve compatibility in constrained environments.

## 2) JWT Security

- JWT creation and verification in `src/guppy/api/auth.py` (`compat_shims/guppy_api_auth.py` remains only as a fallback shim)
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
