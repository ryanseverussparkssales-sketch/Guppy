# Project Bob Integration Contract

Last updated: 2026-04-17

## Purpose

This note defines the stable seams Guppy should preserve while local sidecars evolve and while a future merge or linking pass with Project Bob is planned.

The goal is simple:

1. no repo-local vendor clones required for the shipped Guppy build
2. no repo-local databases required for durable state
3. all sidecar integration happens through explicit external contracts

## Runtime Contract

Local runtime challengers should integrate through external contracts, not vendored source trees.

### Lemonade-style runtimes

Treat these as external OpenAI-compatible services:

1. configurable base URL
2. `GET /models`
3. `POST /chat/completions`

Guppy should store only:

1. selected backend id
2. base URL
3. role-to-model mapping

That keeps future Bob linking simple because the merge point is the runtime API surface, not a copied repo.

### llama.cpp-style runtimes

Treat these as external installed binaries or externally managed services.

Guppy should care about:

1. binary discovery
2. benchmark/integration readiness
3. user-facing role mapping

It should not depend on a vendored runtime tree.

## Memory Contract

Guppy memory integrations must stay behind adapter seams under `src/guppy/memory/`.

Current rule:

1. durable memory lives under the Guppy user-data root
2. memory adapters own storage layout details
3. upstream memory projects are optional external references, not required build contents

This keeps future Bob merge work focused on adapter compatibility instead of file-tree reconciliation.

## File And Library Contract

Workspace file support should rely on:

1. `library.db`
2. approved local roots
3. indexed artifact storage under user data

The app may connect to repo folders, drives, or sidecar-managed storage, but the contract is metadata plus approved roots, not whole-PC implicit crawling.

## Runtime Evidence Contract

Operational evidence should live under `runtime/`, not under `tests/`.

Current rule:

1. stress reports live in `runtime/stress_reports/`
2. tests use fixtures under `tests/fixtures/`
3. launcher evidence surfaces read runtime outputs, not checked-in report dumps

## UI And Surface Contract

The supported product remains the launcher-first desktop UI.

Deprecated repo-local surfaces that should not return as hard dependencies:

1. vendored upstream runtime repos
2. vendored upstream memory repos
3. the old repo-local web chat surface

If Bob needs web access later, that should land as a deliberate supported surface with its own build path, not by reviving orphaned files.

## Merge Guidance

If Project Bob is introduced later, prefer merge points in this order:

1. local runtime provider contract
2. library and file metadata contract
3. memory adapter contract
4. workspace and persistence contract

Do not merge on:

1. copied vendor repos
2. repo-local database files
3. legacy web-sidecar artifacts
