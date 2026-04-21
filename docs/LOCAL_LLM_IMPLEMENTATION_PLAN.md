# Local LLM Implementation Plan

Last updated: 2026-04-15

## Decision Summary

Guppy should start a serious local-model modernization track now, but it should not replace the current local stack blindly.

Immediate policy:

1. Freeze the current stack as the benchmark baseline.
2. Add a pinned manifest and benchmark harness before changing defaults.
3. Evaluate MemPalace as a memory challenger, not a blind replacement.
4. Evaluate runtime challengers only after the harness exists.

## Repo Artifacts Landed In This Planning Pass

1. [config/local_llm/models.json](../config/local_llm/models.json)
   - Pinned local-model and runtime manifest.
2. [config/local_llm/benchmark_prompts.json](../config/local_llm/benchmark_prompts.json)
   - Starter benchmark prompt pack.
3. [docs/LOCAL_LLM_BENCHMARK_SPEC.md](LOCAL_LLM_BENCHMARK_SPEC.md)
   - Promotion rules, metrics, and artifact layout.

## Phase Plan

### Phase 0 - Baseline Freeze

Goal:
Define the current stack as the thing challengers must beat.

Deliverables:

1. Manifest committed and reviewed.
2. `tools/verify_ollama_runtime.py` reads the manifest instead of an ad-hoc list.
3. Benchmark artifact paths reserved under `runtime/local_llm_benchmarks/`.

### Phase 1 - Harness

Goal:
Measure current local quality and stability before changing defaults.

Deliverables:

1. `tools/local_llm_harness.py`
2. JSON output to `runtime/local_llm_benchmarks/latest.json`
3. Append-only history at `runtime/local_llm_benchmarks/history.jsonl`
4. A small review loop for usefulness notes

### Phase 2 - Memory Directory And Adapter

Goal:
Make local memory rebuildable and testable.

Deliverables:

1. Create a dedicated local-memory directory plan:
   - `runtime/local_memory/raw/`
   - `runtime/local_memory/index/`
   - `runtime/local_memory/palace/`
   - `runtime/local_memory/wal/`
   - `runtime/local_memory/snapshots/`
2. Add an adapter seam so `semantic-sqlite` and `mempalace-adapter` can be compared without rewriting the prompt path.
3. Run the first MemPalace-vs-semantic recall spike.

### Phase 3 - Challenger Runs

Goal:
Evaluate better local models and better local runtimes with evidence.

Priority challengers:

1. `qwen3:8b`
2. `qwen3:30b`
3. `mistral-small3.1:24b`
4. `gemma3:12b`
5. `mxbai-embed-large:latest`
6. `llama.cpp`
7. `lemonade`

### Phase 4 - Product Surface

Goal:
Ship a dedicated Local LLM page only after there is real data to show.

Deliverables:

1. Local fleet status
2. Memory backend status
3. Benchmark summaries
4. Readiness and fallback evidence
5. A narrow opt-in runtime lane so challengers like Lemonade can be exercised inside Guppy before any default promotion call

Current truth:

1. The first Lemonade product seam now exists in the API server.
2. It is opt-in through explicit `local` mode rather than a silent swap of `ollama` mode.
3. The first lane is intentionally chat-only until tool-loop parity is proven.

## First Implementation Tasks

### Task 1 - Manifest Loader

Targets:

1. `tools/verify_ollama_runtime.py`
2. New helper module under `src/guppy/` or `utils/`

Acceptance:

1. Default verify path reads `config/local_llm/models.json`
2. Alias handling remains intact
3. Snapshot output includes manifest metadata

### Task 2 - Harness Runner

Targets:

1. `tools/local_llm_harness.py`
2. `config/local_llm/benchmark_prompts.json`

Acceptance:

1. Can run baseline prompts against the current Ollama fleet
2. Writes latest + history artifacts
3. Records failure modes cleanly

### Task 3 - Memory Adapter Seam

Targets:

1. `src/guppy/memory/semantic.py`
2. New local-memory adapter module

Acceptance:

1. Existing semantic path still works
2. Memory backend is swappable for benchmark runs
3. No chat API contract change required

### Task 4 - Launcher/Docs Truth

Targets:

1. `docs/PROJECT_BRIEF.md`
2. `docs/archive/root-history/ROADMAP_2026-04-17.md`

Acceptance:

1. Local LLM track has a clear sequence in the active project brief
2. Historical sequencing remains discoverable in the archived roadmap log

## Guardrails

1. No default-model swap without benchmark artifacts.
2. No runtime swap without cold-start and warm-start evidence.
3. No Local LLM page rename before a real page exists.
4. No memory-backend promotion without a direct recall comparison.
