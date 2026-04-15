# MemPalace Evaluation

Last updated: 2026-04-14

## Decision

MemPalace looks feasible for Guppy, but not as a blind replacement for the current memory stack.

Best fit:

1. Treat it as a local-memory upgrade track for local LLM workflows.
2. Start with an adapter / sidecar integration.
3. Prove value on Guppy local chat recall before folding it deeper into startup prompts or cross-workspace memory.

## What MemPalace Brings

Based on the cloned repo in [vendor/mempalace](../vendor/mempalace):

1. Local-first verbatim memory instead of summary-first memory.
2. Chroma-backed retrieval with hybrid ranking and scoped search.
3. A layered recall model in [vendor/mempalace/mempalace/layers.py](../vendor/mempalace/mempalace/layers.py).
4. A local SQLite knowledge graph in [vendor/mempalace/mempalace/knowledge_graph.py](../vendor/mempalace/mempalace/knowledge_graph.py).
5. A real MCP/tool surface in [vendor/mempalace/mempalace/mcp_server.py](../vendor/mempalace/mempalace/mcp_server.py).
6. MIT licensing, so integration/adaptation is allowed.

## Where It Overlaps With Guppy

Guppy already has:

1. Persistent SQLite fact memory in [src/guppy/memory/memory.py](../src/guppy/memory/memory.py).
2. Semantic memory with SQLite or Chroma backends in [src/guppy/memory/semantic.py](../src/guppy/memory/semantic.py).
3. Prompt-time memory injection in [guppy_core/system_prompt.py](../guppy_core/system_prompt.py).
4. Tool-level semantic recall through `semantic_remember` and `semantic_recall`.

So this is not a “we finally get memory” situation.

This is a “we may be able to replace or augment the weaker local semantic-recall layer with a better structured local recall system” situation.

## Why It Is Interesting

MemPalace’s strongest ideas are:

1. Verbatim storage as the retrieval floor.
2. Scoped retrieval instead of one flat semantic bucket.
3. Layered wake-up context instead of always stuffing one generic semantic block into prompts.
4. A clean split between storage, retrieval, graph facts, and tool access.

Those ideas line up well with Guppy’s local-first direction and with the current need to make local models feel more dependable without forcing cloud routing.

## Risks And Caveats

1. The headline benchmark story is retrieval-heavy, not end-to-end Guppy chat quality.
   Source: [vendor/mempalace/README.md](../vendor/mempalace/README.md) and [vendor/mempalace/benchmarks/BENCHMARKS.md](../vendor/mempalace/benchmarks/BENCHMARKS.md)
2. MemPalace assumes its own palace taxonomy, ingest flow, and storage layout.
3. Guppy already carries Chroma as an optional path, so a full embed adds dependency and lifecycle overlap unless we consolidate.
4. Raw verbatim recall can increase prompt noise if we inject it too aggressively.
5. Windows file-lock and persistence behavior need validation because both Guppy and MemPalace touch local storage heavily.
6. Guppy workspaces, personas, and runtime policies are product concepts MemPalace does not know about.

## Recommendation

Implement this in phases.

### Phase 0 — Evaluation Spike

Goal:
Prove whether MemPalace improves local recall for Guppy without touching the main chat path.

Work:

1. Mine a bounded set of Guppy chat/session history into a dedicated local palace.
2. Compare MemPalace retrieval against `semantic_recall` on real Guppy follow-up prompts.
3. Measure latency, token overhead, and answer usefulness on local Ollama routes.

### Phase 1 — Adapter, Not Replacement

Goal:
Add MemPalace as an optional local memory backend for local LLM workflows.

Work:

1. Build a Guppy adapter module instead of importing MemPalace everywhere.
2. Feed only approved local-chat / workspace history into the palace.
3. Expose a small local-memory API:
   - wake-up summary
   - scoped search
   - related memory lookup
4. Keep the current Guppy memory path as fallback.

### Phase 2 — Local LLM Page

Goal:
Give local models their own product surface in the launcher.

Work:

1. Add a dedicated Local LLM page in the launcher.
2. Show local model fleet, memory backend, recall readiness, and memory health there.
3. Keep Home/assistant chat calm while Local LLM becomes the place for local-model trust and tuning.

### Phase 3 — Deeper Runtime Integration

Goal:
Use MemPalace-derived context in the real local prompt path only where it clearly helps.

Work:

1. Add optional layered wake-up context for local sessions.
2. Add workspace-scoped recall instead of one global semantic bucket.
3. Consider selective graph/fact integration only after retrieval is proven useful.

## Recommended Product Framing

If this lands well, MemPalace should not be surfaced as a random vendor name in the main UI.

Recommended framing:

1. User-facing: `Local Memory`, `Memory Palace`, or `Local Recall`
2. Internal/implementation: MemPalace adapter/backend

## Immediate Repo Actions

1. Keep the clone in `vendor/mempalace` for evaluation only.
2. Add the Local LLM + local-memory track to the roadmap.
3. Switch the launcher app icon to the fish mark now.
4. Do not relabel Home as `Local LLM` until a real dedicated local-model surface exists.

