# MemPalace Evaluation

Last updated: 2026-04-17

## Decision

MemPalace remains a feasible local-memory upgrade track for Guppy, but the integration should stay adapter-first and repo-light.

Current position:

1. Keep Guppy's live memory path independent from any vendored MemPalace source tree.
2. Use `src/guppy/memory/mempalace_adapter.py` plus user-data storage as the integration seam.
3. Treat any future upstream MemPalace clone as an external evaluation input, not a required part of the Guppy build.

## What Still Matters

The useful ideas from MemPalace are product and retrieval ideas, not "keep a giant vendor folder in the repo" ideas:

1. Local-first verbatim memory instead of summary-first memory only.
2. Scoped retrieval instead of one flat semantic bucket.
3. Layered wake-up context for local sessions.
4. A cleaner split between storage, retrieval, graph facts, and tool access.

Those ideas still line up well with Guppy's local-first direction, especially for local coding, study, and file-heavy workflows.

## Where Guppy Already Covers The Basics

Guppy already has:

1. Persistent SQLite fact memory in `src/guppy/memory/memory.py`.
2. Semantic memory with SQLite or Chroma-backed storage in `src/guppy/memory/semantic.py`.
3. A live MemPalace adapter seam in `src/guppy/memory/mempalace_adapter.py`.
4. Durable local storage under the Guppy user-data root instead of the repo tree.

So this is not a "we finally get memory" situation.

This is a "we may improve the weaker local semantic-recall layer with a better structured local recall system" situation.

## Risks And Caveats

1. Retrieval wins do not automatically translate into better end-to-end Guppy chat quality.
2. Raw verbatim recall can increase prompt noise if injected too aggressively.
3. Guppy workspaces, personas, and runtime policies are product concepts a generic memory sidecar does not understand on its own.
4. Windows file locking and local persistence behavior still need validation whenever a sidecar stack is added.

## Recommended Implementation Path

### Phase 0 - External evaluation spike

1. Mine a bounded set of Guppy chat/session history into a dedicated local palace.
2. Compare adapter-backed recall against `semantic_recall` on real follow-up prompts.
3. Measure latency, token overhead, and answer usefulness on local routes.

### Phase 1 - Adapter, not replacement

1. Keep Guppy importing only its adapter module.
2. Feed only approved local-chat or workspace history into the palace.
3. Expose a small local-memory API:
   - wake-up summary
   - scoped search
   - related memory lookup
4. Keep the current Guppy memory path as fallback.

### Phase 2 - Productized local-memory surface

1. Show local-memory readiness on the Local LLM or Library surface.
2. Keep Home calm while local-memory tuning stays in deeper product surfaces.
3. Avoid surfacing vendor names in user-facing copy.

## Product Framing

If this lands well:

1. User-facing labels should be `Local Memory`, `Memory Palace`, or `Local Recall`.
2. Internal implementation can still refer to the MemPalace adapter/backend.

## Repo Rule

The Guppy build should not require `vendor/mempalace/` to exist.

If upstream evaluation work is needed again later, keep it outside the shipped repo or re-clone it temporarily as an external reference. Guppy's supported build path should stay anchored on:

1. adapter seams under `src/guppy/`
2. durable user-data storage
3. explicit external integration contracts
