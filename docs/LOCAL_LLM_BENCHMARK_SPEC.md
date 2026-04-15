# Local LLM Benchmark Spec

Last updated: 2026-04-15

## Purpose

This spec defines how Guppy will decide whether to keep, replace, or expand the current local-model stack.

The goal is not "try newer models." The goal is:

1. Make the local lane dependable enough to feel industrial-grade.
2. Promote models and memory backends only with measured evidence.
3. Keep Home and the assistant experience stable while local infrastructure evolves behind it.

## Current Baseline

The current pinned baseline is captured in [config/local_llm/models.json](../config/local_llm/models.json):

1. `guppy-fast` for fast daily turns.
2. `guppy` for complex local reasoning.
3. `guppy-code` for code-heavy work.
4. `guppy-teach` for teaching/tutoring.
5. `nomic-embed-text` for embeddings.
6. `semantic-sqlite` as the default local memory backend.

No default should change until this baseline has benchmark artifacts committed to `runtime/local_llm_benchmarks/`.

## Candidate Matrix

### Runtime candidates

1. `ollama`
   - Baseline.
   - Keep until a challenger proves better on this machine.
2. `llama.cpp`
   - First high-priority direct runtime challenger.
   - Best control and benchmark fidelity candidate.
3. `lemonade`
   - High-priority platform challenger.
   - Evaluate as a future local substrate, not a drop-in dependency.
4. `vllm-rocm`
   - Research track for Linux/ROCm industrial serving.

### Model candidates

1. `qwen3:8b`
2. `qwen3:30b`
3. `mistral-small3.1:24b`
4. `gemma3:12b`
5. `mxbai-embed-large:latest`

### Memory candidates

1. `semantic-sqlite`
   - Baseline.
2. `mempalace-adapter`
   - First retrieval challenger.
3. `semantic-chroma`
   - Comparison path only; not the target by default.

## Benchmark Tracks

Each run must cover all five tracks:

1. `daily_chat`
   - Fast daily assistant turns.
   - Focus: tone, usefulness, latency, low-friction answers.
2. `code_repo`
   - Repo-aware planning, review, and implementation reasoning.
   - Focus: correctness, specificity, and structured output.
3. `tool_use`
   - Capability-aware prompts and runtime/action shaping.
   - Focus: safe tool framing, policy obedience, action clarity.
4. `memory_recall`
   - Follow-up continuity and local-memory usefulness.
   - Focus: recall usefulness versus prompt noise.
5. `stability`
   - Warm/cold behavior, timeout risk, cancellation, and steady-state readiness.
   - Focus: reliability, not just model intelligence.

Starter prompts for each track live in [config/local_llm/benchmark_prompts.json](../config/local_llm/benchmark_prompts.json).

## Required Metrics

Every benchmark run should capture:

1. `duration_ms`
   - End-to-end wall-clock duration.
2. `first_token_ms`
   - When available.
   - If exact streaming timing is not available yet, record `null` and fill this later.
3. `success`
   - Boolean: usable response returned.
4. `failure_mode`
   - `timeout`, `empty`, `policy`, `tool_error`, `runtime_error`, or `none`.
5. `route`
   - Runtime + model used.
6. `memory_backend`
   - `semantic-sqlite`, `semantic-chroma`, or `mempalace-adapter`.
7. `review_score`
   - 1-5 human review score for usefulness.
8. `notes`
   - Short reviewer note for regressions, hallucinations, or recall noise.

## Artifact Layout

Benchmark outputs should land here:

1. `runtime/local_llm_benchmarks/latest.json`
   - Latest aggregate run.
2. `runtime/local_llm_benchmarks/history.jsonl`
   - Append-only run history.
3. `runtime/local_llm_benchmarks/reviews/`
   - Optional per-run review notes.

## Promotion Rules

### Model promotion

A challenger model can replace a baseline only if:

1. It completes all five tracks.
2. It matches or improves usefulness on `daily_chat` and `code_repo`.
3. It does not materially regress timeout/cold-start behavior.
4. The evidence is written to the benchmark artifact path.

### Memory promotion

A challenger memory backend can replace the current path only if:

1. It is compared against `semantic_recall` on real Guppy follow-up prompts.
2. It improves recall usefulness without materially increasing prompt noise.
3. It remains rebuildable from raw local history.
4. The result is recorded in the benchmark artifact path and summarized in the roadmap handoff log.

### Runtime promotion

A runtime challenger can replace Ollama only if:

1. It passes at least one cold-start and one warm-start run on this machine.
2. It covers the required baseline roles.
3. It does not break the current launcher/API assumptions without a documented migration plan.

## First Implementation Slice

The first code tranche should be:

1. Manifest loader
   - Add a loader/validator for `config/local_llm/models.json`.
   - First target: `tools/verify_ollama_runtime.py`
2. Harness runner
   - Add `tools/local_llm_harness.py` that reads the prompt pack and writes benchmark artifacts.
3. Memory comparison seam
   - Add an adapter surface so `semantic-sqlite` and `mempalace-adapter` can be benchmarked side by side.
4. Launcher-facing evidence
   - Only after artifacts exist, start the dedicated Local LLM page.

## Non-Goals For This Phase

1. Do not rename Home to `Local LLM`.
2. Do not swap Ollama out immediately.
3. Do not promote a new model family without artifacts.
4. Do not spread local-memory details back into Home.
