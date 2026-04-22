# Guppy Security Gate

This document describes the threat model for the Guppy desktop assistant, the
trust boundaries we enforce, how secrets are managed, and the five explicit
launch-gate checks implemented in
`src/guppy/launcher_application/security_gate.py`.

---

## 1. Threat Model Summary

Guppy is a **local-first desktop assistant** running on a user's Windows PC.
It does not host a public API, serve end-users over the internet, or store
user data on a remote server.  That shapes the threat model significantly.

**Who are the threats?**

| Threat actor | Goal | Likelihood |
|---|---|---|
| Malware / other processes on the same machine | Steal API keys, OAuth tokens, or the local bearer token to impersonate the user with external services (Gmail, Spotify, CRM) | High |
| Malicious local scripts | Read secrets from plaintext files in the repo or runtime directory | High |
| Compromised dependency (supply-chain) | Exfiltrate secrets, modify prompts, or establish persistence | Medium |
| Network attacker on the local LAN | Reach the local API endpoint and issue requests without a valid JWT | Low (localhost-only bind) |
| Phishing / social engineering | Trick the user into exposing the repair token or bearer token | Low |

**What is the attack surface?**

1. The FastAPI process listening on `127.0.0.1:<port>` — reachable only from
   localhost, protected by JWT bearer authentication on every non-repair route.
2. The OS credential store — protected by the Windows login session.
3. The connector secrets (Gmail OAuth tokens, Spotify tokens, CRM API keys) —
   stored via the OS keyring or environment variables.
4. The `runtime/` directory — written during execution; must not contain
   plaintext secret files.
5. Third-party Python packages — the dependency graph is a supply-chain
   surface.

---

## 2. Trust Boundary

```
[Launcher UI] ──bearer JWT──> [FastAPI on 127.0.0.1:808x]
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
              [OS keyring]    [connector actions]  [Ollama/Lemonade
                                     │              on localhost]
                         ┌───────────┴────────┐
                   [Gmail OAuth]    [CRM/Spotify/VOIP APIs]
                   (external HTTPS)          (external HTTPS)
```

**Localhost-only:**
- The FastAPI server binds to `127.0.0.1` and will not accept connections from
  other hosts on the network.
- The repair token endpoint (`/repair-token/refresh`) actively rejects requests
  whose source IP is not a loopback address (enforced in route middleware).
- Local AI runtimes (Ollama, Lemonade) also bind localhost.

**Requires auth:**
- Every route except `/auth/token` and `/auth/turnstile` requires a valid,
  unexpired JWT bearer token signed with the server's secret key.
- The `/repair` endpoint additionally requires a separate 64-character hex
  repair token that is rotated on each server startup.

**External calls:**
- Connector actions (Gmail, Calendar, Spotify, CRM, VOIP) make HTTPS calls to
  third-party APIs, but only when the user has explicitly configured credentials
  and the connector's `auth_state` is `ready` or `optional`.

---

## 3. Secret Storage

Secrets are stored in the following priority order:

1. **Windows Credential Manager** (via the `keyring` library) — the default
   and preferred backend on Windows.  Credentials are encrypted at rest and
   scoped to the current Windows user session.
2. **Environment variable fallback** — if `keyring` is unavailable or the
   backend resolves to a null/fail backend, the secret store reads from
   environment variables.  This is logged as a degraded mode.
3. **Plaintext file (repair token only, ephemeral)** — `runtime/repair_token.txt`
   is written as a fallback when the OS keyring is unavailable.  The security
   gate's `build_posture` check does not flag repair token files by name; the
   flag patterns target broader accidental plaintext leaks (`.env`, `*.key`,
   `*.pem`, `secrets.*`).

**Implications of the env-var fallback:**
- Environment variables are visible to any process running as the same user.
- Users who rely on the env-var fallback have a weaker isolation guarantee.
- The `secret_storage` gate check warns (fails) when keyring resolves to a
  degraded backend so operators are made aware before launch.

**What is never stored:**
- JWT signing keys are not persisted; they are read from the environment on
  startup and held in memory.
- Anthropic/OpenAI API keys are held in environment variables or keyring only;
  they are not written to any file in `runtime/`.

---

## 4. Connector Least Privilege

Each connector type has a constrained scope:

| Connector | What it can do | What it cannot do |
|---|---|---|
| Gmail | Read unread count, list messages, fetch thread content | Send mail, delete messages (OAuth scope is read-only unless user grants write) |
| Calendar | List upcoming events | Create or delete events unless user explicitly grants edit scope |
| Spotify | Read current playback state | Modify playlists or purchases |
| CRM | Read/write contacts for the configured provider only | Access other CRM providers or other users' data |
| VOIP | Initiate calls for the configured provider | Access call recordings, billing, or account settings |
| YouTube | Read channel metadata | Upload video or access private analytics |

Connector policy is enforced by `src/guppy/workspace_governance` at the
workspace level.  Before any connector action runs, the governance module
evaluates `auth_state` and the workspace binding to determine whether the
action is permitted.  Policy denials are logged to `runtime/integration_events.jsonl`.

---

## 5. Packaged Build Posture

The packaged Guppy executable is built with PyInstaller from `bin/Guppy.spec`.

**What ships in the packaged build:**
- Python standard library and all declared dependencies from `requirements.txt`.
- The `runtime/` directory (empty scaffold; user data accumulates at runtime).
- The `src/guppy/`, `ui/`, and `utils/` application code.

**What does not ship:**
- `.env` files, `*.key`, `*.pem`, or any `secrets.*` files — the build gate
  blocks these.
- Developer tooling (`tools/`, `tests/`, `.tmp/`).
- The OS keyring backend itself — this is provided by the OS; the packaged app
  uses the Windows Credential Manager via the `keyring` package.
- Source `.git/` history.

**Network posture of the packaged build:**
- The packaged binary makes the same localhost-only API bind as the dev build.
- No telemetry or analytics are sent from the packaged build without user
  consent.
- The only external HTTPS calls are connector actions explicitly triggered by
  the user.

---

## 6. Launch Gate Checks

The gate is implemented in `src/guppy/launcher_application/security_gate.py`
and executed via `run_security_gate()`.  A launch is considered **ready** only
when all five checks pass.

| # | Name | Category | Pass Criteria |
|---|---|---|---|
| 1 | `secret_storage` | SECRET_STORAGE | `keyring.get_keyring()` returns a non-degraded backend (not `FailKeyring`, `NullKeyring`, `PlaintextKeyring`, or chainer to same) |
| 2 | `network_boundary` | NETWORK_BOUNDARY | `server_runtime.py` contains `HOST = "127.0.0.1"` and has no line setting `HOST` to `0.0.0.0` |
| 3 | `connector_scope` | CONNECTOR_SCOPE | `connector_manager.py` references `auth_state` gating and secret reads, and contains no raw `urllib.request.urlopen` / `requests.get` / `requests.post` calls |
| 4 | `build_posture` | BUILD_POSTURE | `runtime/` contains no files matching `*.env`, `.env`, `*.key`, `*.pem`, `secrets.*`, or `secret.*` |
| 5 | `dependency_hygiene` | DEPENDENCY | `requirements.txt` or `pyproject.toml` exists in the repo root and contains at least one line with a pinned (`==`) version specifier |

All checks are **non-blocking by design**: each `check_fn` catches all
exceptions and returns `(False, "<detail>")` rather than raising.  A check
failure does not crash the launcher; it surfaces in the gate report.

---

## 7. Known Gaps

The following security concerns are **not** covered by the current launch gate
and are acknowledged as out-of-scope for this tranche:

1. **OAuth PKCE enforcement** — The Gmail and Calendar connectors use an OAuth
   flow that was not audited for PKCE compliance.  Connectors using implicit
   or auth-code flows without PKCE are vulnerable to authorization-code
   interception on localhost redirects.

2. **Full penetration test** — No external penetration test has been conducted.
   The threat model above is based on design-time analysis, not adversarial
   testing.

3. **Rate-limit bypass via localhost** — The rate-limiter applies to all routes,
   but a local attacker with process-level access can trivially reset the
   in-memory rate-limit store.  This is a deliberate trade-off for a local-only
   app.

4. **Repair token file exposure** — When the OS keyring is unavailable,
   `runtime/repair_token.txt` is written in plaintext.  The `build_posture`
   check does not flag this file by name.  Operators running in degraded
   keyring mode should be aware of this exposure.

6. **Audit log integrity** — `runtime/integration_events.jsonl` is append-only
   but not cryptographically signed.  A local attacker could tamper with the
   audit log.
