# Intermediate Stack Audit

Date: 2026-04-17

## Scope

Reviewed the interim local stack and repo buckets that were acting as stand-ins during Guppy development:

1. `vendor/lemonade/`
2. `vendor/mempalace/`
3. `web/`
4. `tests/runtime/`

## Decision Summary

### `vendor/lemonade/`

Decision: remove from the repo

Reason:

1. Guppy's Lemonade support is endpoint-based, not source-tree-based.
2. The live runtime path uses a configured base URL plus OpenAI-compatible endpoints.
3. The vendored tree was only helping evaluation and host probing, not the shipped build.

### `vendor/mempalace/`

Decision: remove from the repo

Reason:

1. Guppy's live memory path already goes through `src/guppy/memory/mempalace_adapter.py`.
2. Durable memory now lives in user-data storage, not the repo tree.
3. The vendored tree was an upstream evaluation copy, not a required product dependency.

### `web/`

Decision: remove from the repo

Reason:

1. The supported product surface is the launcher-first desktop UI.
2. The old repo-local web UI no longer owns any supported daily path.
3. Turnstile setup now updates `.env` only and does not require repo-local web assets.

### `tests/runtime/`

Decision: remove from the repo

Reason:

1. Checked-in stress reports are runtime evidence, not source fixtures.
2. Runtime evidence should live under `runtime/stress_reports/`.
3. Tests now anchor on explicit fixture content or temporary runtime dirs, not checked-in report dumps.

## Future Merge / Bob Guidance

Keep future merge points on stable contracts:

1. external runtime endpoints
2. memory adapters
3. approved-root library metadata
4. runtime evidence under `runtime/`

Avoid merge points based on:

1. vendored upstream repos
2. repo-local databases
3. orphaned sidecar UIs
