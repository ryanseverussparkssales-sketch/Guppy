"""
inference_router.py — Guppy Inference Priority Router
========================================================

Routes all inference requests through a priority chain:
1. LOCAL: guppy model via Ollama (primary - free, fast)
2. HAIKU: Claude Haiku (secondary - low cost cloud fallback)
3. SONNET: Claude Sonnet (last resort - high reasoning fallback)

This module is imported by guppy_api.py and handles all model selection
automatically with intelligent fallback.

Usage:
    from inference_router import InferenceRouter

    router = InferenceRouter()
    result = router.query(system_prompt, user_text, tools=TOOLS)
    # Returns: (response_text, source, metadata)
"""

import os
import json
import logging
import socket
import urllib.error
import urllib.request
import re
from typing import Optional, Tuple, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Valid modes for inference routing
VALID_MODES = ("auto", "claude", "ollama", "local", "code", "teaching", "vault")
VALID_MODES_DISPLAY = ("AUTO", "CLAUDE", "OLLAMA", "LOCAL", "CODE", "TEACHING", "VAULT")
LAUNCHER_MODES = ("auto", "claude", "ollama", "local", "code", "teaching")
LAUNCHER_MODES_DISPLAY = ("AUTO", "CLAUDE", "OLLAMA", "LOCAL", "CODE", "TEACHING")

class InferenceRouter:
    """
    Smart inference routing with automatic fallback.
    Two modes:

    1. LEGACY: local -> haiku -> sonnet (for backward compat)
    2. SMART (NEW): haiku-first -> sonnet -> ollama (for butler UX, <3s latency)
       - Task-aware routing: simple -> Haiku, complex -> Sonnet, teaching -> Merlin/Ollama
       - 3s timeout on Haiku (not 30s on Ollama)
       - No retry loops: once fallback starts, don't retry failed backend
    """

    # Configuration
    OLLAMA_API = "http://127.0.0.1:11434/api/chat"
    OLLAMA_TIMEOUT = 10       # fallback path timeout (cloud-first modes)
    OLLAMA_LOCAL_TIMEOUT = 60 # local-only mode — allow full 32B inference time

    # Local model roster
    # Two 7B models share the qwen2.5:7b base blob — no extra VRAM cost for having both.
    # 7B + 14B = ~14 GB → both can be warm simultaneously on the 7900 XTX.
    # 32B needs exclusive VRAM (~20 GB); evicts everything else when loaded.
    LOCAL_MODEL       = "guppy"         # qwen2.5:32b  — complex butler tasks
    LOCAL_FAST_MODEL  = "guppy-fast"    # qwen2.5:7b   — simple/fast butler tasks
    LOCAL_TEACH_MODEL = "merlin"        # qwen2.5:32b  — Socratic teaching
    LOCAL_CODE_MODEL  = "merlin-code"   # qwen2.5-coder:14b — code review/debug
    LOCAL_VAULT_MODEL = "vault-scraper" # qwen2.5:7b   — structured media extraction

    LOCAL_TIER_MAP: Dict[str, str] = {
        "simple":   LOCAL_FAST_MODEL,
        "complex":  LOCAL_MODEL,
        "teaching": LOCAL_TEACH_MODEL,
    }

    # Haiku boost modes — targeted Haiku pass that supplements local output
    HAIKU_BOOST_VERIFY      = "verify"       # fact-check / fill gaps
    HAIKU_BOOST_CODE_REVIEW = "code_review"  # scan generated code for bugs
    HAIKU_BOOST_ENRICH      = "enrich"       # add missing metadata fields
    HAIKU_BOOST_STRUCTURE   = "structure"    # reformat as clean JSON

    HAIKU_MODEL = "claude-haiku-4-5-20251001"
    SONNET_MODEL = "claude-sonnet-4-6"

    HAIKU_TIMEOUT_SMART = 8   # API cold-start + network can easily hit 2-3 s; 3 was too aggressive
    SONNET_TIMEOUT_SMART = 20 # Sonnet is slower — give it room

    @staticmethod
    def _bool_env(name: str, default: bool = True) -> bool:
        """Parse boolean environment variable."""
        val = (os.environ.get(name, "") or "").strip().lower()
        if val in {"1", "true", "yes", "on"}:
            return True
        if val in {"0", "false", "no", "off"}:
            return False
        return default

    def __init__(self):
        """Initialize the router."""
        self.current_primary = "local"
        self.fallback_chain = ["local", "haiku", "sonnet"]

        # Runtime model overrides for low-compute/night runs.
        self.low_compute_mode = self._bool_env("GUPPY_LOW_COMPUTE_MODE", False)
        default_complex_model = self.LOCAL_FAST_MODEL if self.low_compute_mode else self.LOCAL_MODEL
        default_teach_model = self.LOCAL_CODE_MODEL if self.low_compute_mode else self.LOCAL_TEACH_MODEL

        self.LOCAL_FAST_MODEL = (os.environ.get("GUPPY_LOCAL_FAST_MODEL", self.LOCAL_FAST_MODEL) or self.LOCAL_FAST_MODEL).strip()
        self.LOCAL_MODEL = (os.environ.get("GUPPY_LOCAL_COMPLEX_MODEL", default_complex_model) or default_complex_model).strip()
        self.LOCAL_TEACH_MODEL = (os.environ.get("GUPPY_LOCAL_TEACH_MODEL", default_teach_model) or default_teach_model).strip()
        self.LOCAL_CODE_MODEL = (os.environ.get("GUPPY_LOCAL_CODE_MODEL", self.LOCAL_CODE_MODEL) or self.LOCAL_CODE_MODEL).strip()
        self.LOCAL_VAULT_MODEL = (os.environ.get("GUPPY_LOCAL_VAULT_MODEL", self.LOCAL_VAULT_MODEL) or self.LOCAL_VAULT_MODEL).strip()

        self.LOCAL_TIER_MAP = {
            "simple": self.LOCAL_FAST_MODEL,
            "complex": self.LOCAL_MODEL,
            "teaching": self.LOCAL_TEACH_MODEL,
        }

        default_predict = "320" if self.low_compute_mode else "512"
        try:
            self.local_num_predict = max(128, int(os.environ.get("GUPPY_LOCAL_NUM_PREDICT", default_predict)))
        except Exception:
            self.local_num_predict = int(default_predict)

        # Anthropic model overrides (consolidate env reads into instance vars)
        self.haiku_model_override = (os.environ.get("ANTHROPIC_HAIKU_MODEL", "").strip() or self.HAIKU_MODEL)
        self.sonnet_model_override = (os.environ.get("ANTHROPIC_MODEL", "").strip() or self.SONNET_MODEL)

        # Try to import Anthropic
        try:
            import anthropic
            self.anthropic_client = anthropic.Anthropic(
                api_key=os.environ.get("ANTHROPIC_API_KEY", "").strip()
            )
            self.anthropic_available = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
        except ImportError:
            self.anthropic_client = None
            self.anthropic_available = False

    def _should_use_haiku_boost(self, api_available: bool) -> bool:
        """Check if haiku boost should be used."""
        if not api_available:
            return False
        return self._bool_env("GUPPY_HAIKU_BOOST", True)

    @staticmethod
    def _is_rate_limited_error(error: Exception | str) -> bool:
        txt = str(error or "").lower()
        return "429" in txt or "rate limit" in txt or "too many requests" in txt

    def _classify_task(self, user_text: str, system_prompt: str = "") -> str:
        """Classify task into simple/complex/teaching using semantic + fallback heuristic."""
        semantic_enabled = os.environ.get("GUPPY_SEMANTIC_CLASSIFIER", "1").strip().lower() in {
            "1", "true", "yes", "on"
        }
        if semantic_enabled and self.anthropic_available:
            task = self._classify_task_semantic(user_text=user_text, system_prompt=system_prompt)
            if task in {"simple", "complex", "teaching"}:
                return task
        return self._classify_task_heuristic(user_text=user_text, system_prompt=system_prompt)

    def _classify_task_semantic(self, user_text: str, system_prompt: str = "") -> str:
        """Use Haiku to classify intent with strict JSON output."""
        try:
            prompt = (
                "Classify this request for routing into exactly one label: simple, complex, teaching.\n"
                "Rules:\n"
                "- simple: factual lookups, reminders, short transforms, status checks, lightweight Q&A\n"
                "- complex: multi-step reasoning, architecture/debugging/code planning, deep analysis\n"
                "- teaching: user explicitly wants instruction/tutoring/concept walkthrough\n"
                "Return JSON only: {\"task_type\":\"simple|complex|teaching\",\"confidence\":0..1}\n"
                f"System context: {system_prompt[:400]}\n"
                f"User text: {user_text[:1200]}"
            )
            resp = self.anthropic_client.messages.create(
                model=self.HAIKU_MODEL,
                max_tokens=100,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = (resp.content[0].text if resp.content else "").strip()
            raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
            raw = re.sub(r"\s*```$", "", raw)
            data = json.loads(raw)
            task_type = str(data.get("task_type", "")).strip().lower()
            if task_type in {"simple", "complex", "teaching"}:
                logger.info(f"[CLASSIFIER] semantic={task_type}")
                return task_type
        except Exception as e:
            logger.debug(f"[CLASSIFIER] semantic fallback to heuristic: {e}")
        return ""

    @staticmethod
    def _classify_task_heuristic(user_text: str, system_prompt: str = "") -> str:
        """Heuristic fallback classifier for offline/failed semantic classification."""
        text_lower = (user_text or "").lower()
        system_lower = (system_prompt or "").lower()
        combined_lower = text_lower + " " + system_lower

        # Teaching keywords (route to Merlin/Ollama for Socratic responses)
        teaching_keywords = {
            "explain", "teach me", "how does", "why is", "what is",
            "help me understand", "concept", "introduce", "intro to",
            "define", "meaning of", "learn about", "guide me",
        }
        if any(k in combined_lower for k in teaching_keywords):
            return "teaching"

        # Complex keywords (needs Sonnet reasoning)
        complex_keywords = {
            "build", "design", "architect", "refactor", "debug", "fix",
            "research", "analyze", "review code", "write code",
            "optimize", "performance", "security", "strategy",
            "plan", "roadmap", "multi-step", "comprehensive",
            "complex", "production", "incident", "root cause",
            "threat model", "test matrix", "migration", "compliance",
        }
        if any(k in combined_lower for k in complex_keywords):
            return "complex"

        # Length heuristic: very short messages are usually simple
        if len(user_text or "") < 50:
            return "simple"

        # Simple keywords (fast with Haiku)
        simple_keywords = {
            "what time", "what date", "remind me", "list", "format",
            "summarize", "rewrite", "shorten", "expand", "check",
            "find", "look up", "search", "when is", "where is",
            "tell me about", "news", "weather", "quick",
        }
        if any(k in combined_lower for k in simple_keywords):
            return "simple"

        # Default to complex (safer to over-dispatch to Sonnet than under-dispatch)
        return "complex"

    def resolve_ui_route(
        self,
        user_text: str,
        system_prompt: str = "",
        mode: str = "auto",
        voice_triggered: bool = False,
        api_key_available: bool = False,
    ) -> Dict[str, Any]:
        """Return a routing decision for UI workers without executing inference.

        This keeps route policy centralized in inference_router.py while allowing
        UI surfaces to keep their existing streaming/tool-loop implementations.
        """
        task_type = self._classify_task(user_text, system_prompt)
        normalized_mode = (mode or "auto").strip().lower()
        has_api = bool(api_key_available)

        if normalized_mode == "ollama":
            if task_type == "teaching":
                return {
                    "task_type": task_type,
                    "route": "ollama_teaching",
                    "route_reason": "manual local mode via router (teaching)",
                    "executor": "ollama",
                    "system_profile": "merlin",
                    "model": "merlin",
                    "backup_model": "",
                }
            return {
                "task_type": task_type,
                "route": "ollama",
                "route_reason": "manual local mode via router",
                "executor": "ollama",
                "system_profile": "guppy",
                "model": "guppy",
                "backup_model": "",
            }

        # teaching — force teaching profile and route irrespective of classifier noise
        if normalized_mode == "teaching":
            if has_api:
                return {
                    "task_type": "teaching",
                    "route": "claude_teaching",
                    "route_reason": "manual teaching mode requested",
                    "executor": "claude",
                    "system_profile": "merlin",
                    "model": os.environ.get("ANTHROPIC_HAIKU_MODEL", self.HAIKU_MODEL),
                    "backup_model": os.environ.get("ANTHROPIC_MODEL", self.SONNET_MODEL),
                }
            return {
                "task_type": "teaching",
                "route": "ollama_teaching",
                "route_reason": "manual teaching mode requested (no API key)",
                "executor": "ollama",
                "system_profile": "merlin",
                "model": "merlin",
                "backup_model": "",
            }

        # local — tier-aware local-only routing (no cloud fallback)
        # simple→guppy-fast, complex→guppy, teaching→merlin
        if normalized_mode == "local":
            model = self.LOCAL_TIER_MAP.get(task_type, self.LOCAL_MODEL)
            profile = "merlin" if task_type == "teaching" else "guppy"
            return {
                "task_type": task_type,
                "route": f"local_{task_type}",
                "route_reason": f"local-only mode — {task_type} tier → {model}",
                "executor": "ollama",
                "system_profile": profile,
                "model": model,
                "backup_model": "",
                "timeout": self.OLLAMA_LOCAL_TIMEOUT,
                "local_only": True,
            }

        # code — dedicated coder-14B session (merlin-code), optional Haiku boost
        if normalized_mode == "code":
            haiku_boost = self._should_use_haiku_boost(has_api)
            return {
                "task_type": task_type,
                "route": "local_code",
                "route_reason": "code mode -> merlin-code (qwen2.5-coder:14b)",
                "executor": "ollama",
                "system_profile": "merlin",
                "model": self.LOCAL_CODE_MODEL,
                "backup_model": "",
                "timeout": self.OLLAMA_LOCAL_TIMEOUT,
                "local_only": True,
                "haiku_boost": haiku_boost,
                "haiku_boost_mode": self.HAIKU_BOOST_CODE_REVIEW,
            }

        # vault — structured media extraction via vault-scraper, optional Haiku enrich pass
        if normalized_mode == "vault":
            haiku_boost = self._should_use_haiku_boost(has_api)
            return {
                "task_type": "simple",
                "route": "local_vault",
                "route_reason": "vault mode -> vault-scraper (qwen2.5:7b, structured extraction)",
                "executor": "ollama",
                "system_profile": "vault",
                "model": self.LOCAL_VAULT_MODEL,
                "backup_model": "",
                "timeout": self.OLLAMA_LOCAL_TIMEOUT,
                "local_only": True,
                "haiku_boost": haiku_boost,
                "haiku_boost_mode": self.HAIKU_BOOST_ENRICH,
            }

        # local_paired — 7B sketches intent, 32B refines (no cloud fallback)
        # For simple tasks the sketch IS the answer (no second pass needed).
        if normalized_mode == "local_paired":
            sketch_model = self.LOCAL_FAST_MODEL
            if task_type == "simple":
                return {
                    "task_type": task_type,
                    "route": "local_paired_simple",
                    "route_reason": "local_paired — simple task, single 7B pass sufficient",
                    "executor": "ollama",
                    "system_profile": "guppy",
                    "model": sketch_model,
                    "backup_model": "",
                    "timeout": self.OLLAMA_LOCAL_TIMEOUT,
                    "local_only": True,
                    "paired": False,
                }
            refine_model = self.LOCAL_TEACH_MODEL if task_type == "teaching" else self.LOCAL_MODEL
            profile = "merlin" if task_type == "teaching" else "guppy"
            return {
                "task_type": task_type,
                "route": f"local_paired_{task_type}",
                "route_reason": (
                    f"local_paired — {task_type}: {sketch_model} sketches intent, "
                    f"{refine_model} refines"
                ),
                "executor": "ollama_paired",
                "system_profile": profile,
                "model": refine_model,         # primary (refine) model
                "sketch_model": sketch_model,  # fast model runs first
                "backup_model": "",
                "timeout": self.OLLAMA_LOCAL_TIMEOUT,
                "local_only": True,
                "paired": True,
            }

        if normalized_mode == "claude":
            if not has_api:
                return {
                    "task_type": task_type,
                    "route": "cloud_unavailable",
                    "route_reason": "manual cloud mode requested but API key missing",
                    "executor": "error",
                    "error": "cloud_only mode requires ANTHROPIC_API_KEY",
                }

            if task_type == "teaching":
                return {
                    "task_type": task_type,
                    "route": "claude_teaching",
                    "route_reason": "teaching task, cloud mode via Haiku + Merlin system",
                    "executor": "claude",
                    "system_profile": "merlin",
                    "model": self.haiku_model_override,
                    "backup_model": self.sonnet_model_override,
                }

            if voice_triggered or task_type == "simple":
                return {
                    "task_type": task_type,
                    "route": "haiku_voice" if voice_triggered else "haiku",
                    "route_reason": "voice fast-path" if voice_triggered else "simple task classification",
                    "executor": "claude",
                    "system_profile": "guppy",
                    "model": self.haiku_model_override,
                    "backup_model": self.sonnet_model_override,
                }

            return {
                "task_type": task_type,
                "route": "sonnet",
                "route_reason": "complex task classification",
                "executor": "claude",
                "system_profile": "guppy",
                "model": self.sonnet_model_override,
                "backup_model": self.haiku_model_override,
            }

        # auto mode
        if task_type == "teaching":
            if has_api and voice_triggered:
                return {
                    "task_type": task_type,
                    "route": "haiku_voice",
                    "route_reason": "voice-triggered teaching fallback to cloud",
                    "executor": "claude",
                    "system_profile": "merlin",
                    "model": self.haiku_model_override,
                    "backup_model": self.sonnet_model_override,
                }
            return {
                "task_type": task_type,
                "route": "ollama_teaching",
                "route_reason": "teaching task -> Merlin/Ollama",
                "executor": "ollama",
                "system_profile": "merlin",
                "model": "merlin",
                "backup_model": "",
            }

        if not has_api:
            return {
                "task_type": task_type,
                "route": "ollama_fallback",
                "route_reason": "no API key",
                "executor": "ollama",
                "system_profile": "guppy",
                "model": "guppy",
                "backup_model": "",
            }

        if voice_triggered or task_type == "simple":
            return {
                "task_type": task_type,
                "route": "haiku_voice" if voice_triggered else "haiku",
                "route_reason": "voice_triggered fast-path" if voice_triggered else "simple task classification",
                "executor": "claude",
                "system_profile": "guppy",
                "model": self.haiku_model_override,
                "backup_model": self.sonnet_model_override,
            }

        return {
            "task_type": task_type,
            "route": "sonnet",
            "route_reason": "complex task classification",
            "executor": "claude",
            "system_profile": "guppy",
            "model": self.sonnet_model_override,
            "backup_model": self.haiku_model_override,
        }

    def query_smart(
        self,
        system_prompt: str,
        user_text: str,
        tools: Optional[list] = None,
        messages: Optional[list] = None,
    ) -> Tuple[str, str, Dict[str, Any]]:
        """
        NEW SMART DISPATCH (Phase 1): Haiku-first with task-aware routing.

        For BUTLER USE: fast, predictable latency.
        - Simple tasks (lookup, format, summarize) → Haiku (2-3s)
        - Complex tasks (research, code, design) → Sonnet (5-10s)
        - Teaching tasks (explain, learn) → Merlin/Ollama (Socratic, local)
        - Fallback: Haiku timeout → Sonnet → give up

        Args:
            system_prompt: System/context prompt
            user_text: User message
            tools: Optional tool definitions (for Haiku; Sonnet uses different tool format)
            messages: Optional message history (used if Ollama is fallback)

        Returns:
            (response_text, source, metadata)
            where source is "haiku", "sonnet", or "local" (teaching fallback)
        """
        task_type = self._classify_task(user_text, system_prompt)

        logger.info("=" * 70)
        logger.info(f"SMART DISPATCH | Task: {task_type} | User text: {user_text[:60]}...")
        logger.info("=" * 70)

        # Routing decision based on task classification
        if task_type == "teaching":
            # Route to Ollama/Merlin for Socratic teaching
            logger.info("[SMART] Teaching task -> trying Ollama/Merlin (Socratic)")
            result = self.query_local(system_prompt, user_text, tools, messages)
            if result:
                return result["response"], result["source"], result["metadata"]
            # If Ollama unavailable, fall back to Haiku (not ideal for teaching, but available)
            logger.info("[SMART] Ollama unavailable for teaching, falling back to Haiku")
            result = self.query_haiku(system_prompt, user_text, tools)
            if result:
                return result["response"], result["source"], result["metadata"]
            result = self.query_sonnet(system_prompt, user_text, tools)
            if result:
                return result["response"], result["source"], result["metadata"]
            raise RuntimeError("[SMART] All backends failed for teaching task")

        elif task_type == "complex":
            # Complex task -> try Sonnet first (better reasoning), then Haiku, then Ollama
            logger.info("[SMART] Complex task -> trying Sonnet first")
            result = self.query_sonnet(system_prompt, user_text, tools)
            if result:
                self.current_primary = "sonnet"
                return result["response"], result["source"], result["metadata"]
            # Sonnet failed, try Haiku
            logger.info("[SMART] Sonnet failed/timeout, trying Haiku")
            result = self.query_haiku(system_prompt, user_text, tools)
            if result:
                self.current_primary = "haiku"
                return result["response"], result["source"], result["metadata"]
            # Last resort: local
            logger.info("[SMART] Haiku failed/timeout, trying local Ollama")
            result = self.query_local(system_prompt, user_text, tools, messages)
            if result:
                self.current_primary = "local"
                return result["response"], result["source"], result["metadata"]
            raise RuntimeError("[SMART] All backends failed for complex task")

        else:  # simple
            # Simple task -> fast Haiku first, then Sonnet, then Ollama
            logger.info("[SMART] Simple task -> trying Haiku first (2-3s timeout)")
            result = self.query_haiku(system_prompt, user_text, tools)
            if result:
                self.current_primary = "haiku"
                return result["response"], result["source"], result["metadata"]
            # Haiku timeout/failed, try Sonnet
            logger.info("[SMART] Haiku timeout/failed, trying Sonnet")
            result = self.query_sonnet(system_prompt, user_text, tools)
            if result:
                self.current_primary = "sonnet"
                return result["response"], result["source"], result["metadata"]
            # Last resort: local
            logger.info("[SMART] Sonnet failed, trying local Ollama")
            result = self.query_local(system_prompt, user_text, tools, messages)
            if result:
                self.current_primary = "local"
                return result["response"], result["source"], result["metadata"]
            raise RuntimeError("[SMART] All backends failed for simple task")

    def _haiku_boost(
        self,
        original_query: str,
        local_response: str,
        boost_mode: str = "verify",
    ) -> str:
        """Run a targeted Haiku pass that supplements (not replaces) a local model response.

        The local model always answers first. Haiku then does a narrow, focused refinement:
        - verify      — correct errors, fill factual gaps, add missing depth
        - code_review — scan code blocks for bugs, security issues, quick wins
        - enrich      — add missing metadata fields to structured output
        - structure   — reformat as clean JSON (last resort if vault-scraper drifted)

        Returns the enhanced response string, or the original if Haiku is unavailable/fails.
        """
        if not self.anthropic_available:
            return local_response

        BOOST_PROMPTS: Dict[str, str] = {
            self.HAIKU_BOOST_VERIFY: (
                "A local AI answered the following question. Your job is to briefly review the answer: "
                "correct any factual errors, fill critical gaps, and add one sentence of depth if it would "
                "genuinely help. Do NOT rewrite the whole thing — make surgical additions only. "
                "Return the improved answer, preserving the original tone and structure.\n\n"
                f"QUESTION: {original_query}\n\nLOCAL ANSWER:\n{local_response}"
            ),
            self.HAIKU_BOOST_CODE_REVIEW: (
                "A local coding AI generated the following response. Scan any code blocks for: "
                "bugs, off-by-one errors, security issues (injection, unescaped input, hardcoded secrets), "
                "and obvious performance problems. If you find issues, append a brief '### Haiku Code Review' "
                "section listing them. If the code looks clean, append '### Haiku Code Review: no issues found'. "
                "Do not rewrite the prose sections.\n\n"
                f"ORIGINAL QUESTION: {original_query}\n\nLOCAL RESPONSE:\n{local_response}"
            ),
            self.HAIKU_BOOST_ENRICH: (
                "A local extraction agent produced the following structured metadata. "
                "Review it and add any standard fields that can be reasonably inferred but are missing "
                "(e.g. common genre tags, alternate titles, related identifiers). "
                "Return only the enriched JSON — no prose, no markdown fences.\n\n"
                f"SOURCE TEXT: {original_query}\n\nLOCAL EXTRACTION:\n{local_response}"
            ),
            self.HAIKU_BOOST_STRUCTURE: (
                "Reformat the following text as clean, valid JSON. "
                "Infer field names from context. No prose, no markdown fences.\n\n"
                f"{local_response}"
            ),
        }

        prompt = BOOST_PROMPTS.get(boost_mode, BOOST_PROMPTS[self.HAIKU_BOOST_VERIFY])
        try:
            resp = self.anthropic_client.messages.create(
                model=self.HAIKU_MODEL,
                max_tokens=1024,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
            )
            boosted = (resp.content[0].text if resp.content else "").strip()
            logger.info(f"[HAIKU_BOOST] mode={boost_mode} tokens={resp.usage.output_tokens}")
            return boosted if boosted else local_response
        except Exception as e:
            logger.warning(f"[HAIKU_BOOST] failed ({boost_mode}): {e} — returning local response")
            return local_response

    def query_with_boost(
        self,
        system_prompt: str,
        user_text: str,
        model: str,
        boost_mode: str = "verify",
        tools: Optional[list] = None,
        messages: Optional[list] = None,
    ) -> Optional[Dict[str, Any]]:
        """Run a local model query with an optional Haiku refinement pass.

        The boost only fires if GUPPY_HAIKU_BOOST=1 (default) and the API key is available.
        The local model always runs first — Haiku is additive, not a fallback.
        """
        result = self._ollama_call(
            model=model,
            system_prompt=system_prompt,
            user_text=user_text,
            tools=tools,
            messages=messages,
            timeout=self.OLLAMA_LOCAL_TIMEOUT,
        )
        if result is None:
            return None

        boost_enabled = self.anthropic_available and self._should_use_haiku_boost(self.anthropic_available)
        if boost_enabled:
            boosted = self._haiku_boost(
                original_query=user_text,
                local_response=result["response"],
                boost_mode=boost_mode,
            )
            result["response"] = boosted
            result["haiku_boosted"] = True
            result["haiku_boost_mode"] = boost_mode
        else:
            result["haiku_boosted"] = False

        return result

    def query_local_tiered(
        self,
        system_prompt: str,
        user_text: str,
        task_type: str = "complex",
        tools: Optional[list] = None,
        messages: Optional[list] = None,
    ) -> Optional[Dict[str, Any]]:
        """Local-only tiered dispatch: picks guppy-fast / guppy / merlin by task_type."""
        model = self.LOCAL_TIER_MAP.get(task_type, self.LOCAL_MODEL)
        return self._ollama_call(
            model=model,
            system_prompt=system_prompt,
            user_text=user_text,
            tools=tools,
            messages=messages,
            timeout=self.OLLAMA_LOCAL_TIMEOUT,
        )

    def query_local_paired(
        self,
        system_prompt: str,
        user_text: str,
        task_type: str = "complex",
        tools: Optional[list] = None,
        messages: Optional[list] = None,
    ) -> Optional[Dict[str, Any]]:
        """Two-pass local pipeline: 7B extracts intent → 32B answers with that context.

        Pass 1 — guppy-fast (7B) distils the query into a 2-3 sentence intent sketch.
        Pass 2 — guppy / merlin (32B) receives the original query + sketch as context.

        For 'simple' tasks this collapses to a single 7B call (overhead not worth it).
        """
        if task_type == "simple":
            return self._ollama_call(
                model=self.LOCAL_FAST_MODEL,
                system_prompt=system_prompt,
                user_text=user_text,
                tools=tools,
                messages=messages,
                timeout=self.OLLAMA_LOCAL_TIMEOUT,
            )

        # Pass 1: sketch
        sketch_prompt = (
            "You are a query analyst. In 2-3 sentences extract the core intent, "
            "key constraints, and relevant context from the user's request. "
            "Be precise and factual. Do not answer the question."
        )
        sketch_result = self._ollama_call(
            model=self.LOCAL_FAST_MODEL,
            system_prompt=sketch_prompt,
            user_text=user_text,
            timeout=self.OLLAMA_LOCAL_TIMEOUT,
        )
        sketch = sketch_result["response"].strip() if sketch_result else ""
        logger.info(f"[LOCAL_PAIRED] sketch: {sketch[:120]}")

        # Pass 2: refine with sketch context
        refine_model = self.LOCAL_TEACH_MODEL if task_type == "teaching" else self.LOCAL_MODEL
        augmented_prompt = system_prompt
        if sketch:
            augmented_prompt = (
                f"{system_prompt}\n\n"
                f"[Query Intent Analysis]\n{sketch}"
            )
        result = self._ollama_call(
            model=refine_model,
            system_prompt=augmented_prompt,
            user_text=user_text,
            tools=tools,
            messages=messages,
            timeout=self.OLLAMA_LOCAL_TIMEOUT,
        )
        if result:
            result["paired_sketch"] = sketch
            result["sketch_model"] = self.LOCAL_FAST_MODEL
        return result

    def _ollama_call(
        self,
        model: str,
        system_prompt: str,
        user_text: str,
        tools: Optional[list] = None,
        messages: Optional[list] = None,
        timeout: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Shared Ollama HTTP call used by all local query methods."""
        _timeout = timeout if timeout is not None else self.OLLAMA_TIMEOUT
        try:
            logger.info(f"[LOCAL] model={model} timeout={_timeout}s")
            if messages is None:
                all_msgs = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ]
            else:
                all_msgs = messages

            payload: Dict[str, Any] = {
                "model": model,
                "messages": all_msgs,
                "stream": False,
                "keep_alive": "10m",
                "options": {
                    "temperature": 0.8,
                    "top_p": 0.95,
                    "top_k": 40,
                    "num_predict": self.local_num_predict,
                },
            }
            if tools:
                payload["tools"] = tools

            req = urllib.request.Request(
                self.OLLAMA_API,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=_timeout) as r:
                data = json.loads(r.read().decode())

            logger.info(f"[LOCAL] ✓ {model} success")
            return {
                "response": data.get("message", {}).get("content", ""),
                "model": model,
                "source": "local",
                "tool_calls": data.get("message", {}).get("tool_calls", []),
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "raw_data": data,
                },
            }
        except (socket.timeout, urllib.error.URLError) as e:
            logger.warning(f"[LOCAL] Timeout/connection ({_timeout}s) model={model}: {e}")
            return None
        except Exception as e:
            logger.warning(f"[LOCAL] Error model={model}: {e}")
            return None

    def query_local(self, system_prompt: str, user_text: str, tools: Optional[list] = None, messages: Optional[list] = None) -> Optional[Dict[str, Any]]:
        """Query the guppy (32B) model via Ollama. Returns response dict or None."""
        return self._ollama_call(
            model=self.LOCAL_MODEL,
            system_prompt=system_prompt,
            user_text=user_text,
            tools=tools,
            messages=messages,
        )

    def query_haiku(self, system_prompt: str, user_text: str, tools: Optional[list] = None) -> Optional[Dict[str, Any]]:
        """Query Claude Haiku as secondary fallback."""
        if not self.anthropic_available:
            logger.warning("[HAIKU] Anthropic API not configured. Skipping.")
            return None

        try:
            logger.info("[HAIKU] Querying Claude Haiku...")

            kwargs = {
                "model": self.HAIKU_MODEL,
                "max_tokens": 2048,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_text}],
            }

            if tools:
                kwargs["tools"] = tools

            response = self.anthropic_client.messages.create(**kwargs)

            logger.info(f"[HAIKU] ✓ Success. Tokens: {response.usage.output_tokens}")

            response_text = response.content[0].text if response.content else ""
            if not str(response_text).strip():
                logger.warning("[HAIKU] Empty response payload. Escalating to next backend.")
                return None

            return {
                "response": response_text,
                "model": self.HAIKU_MODEL,
                "source": "haiku",
                "tool_calls": [b for b in response.content if getattr(b, "type", None) == "tool_use"],
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "usage": {
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens
                    }
                }
            }
        except Exception as e:
            if self._is_rate_limited_error(e):
                logger.warning(f"[HAIKU] Rate limited: {e}. Escalating to Sonnet/local.")
            else:
                logger.error(f"[HAIKU] Error: {e}. Escalating to Sonnet.")
            return None

    def query_sonnet(self, system_prompt: str, user_text: str, tools: Optional[list] = None) -> Optional[Dict[str, Any]]:
        """Query Claude Sonnet as last resort."""
        if not self.anthropic_available:
            logger.warning("[SONNET] Anthropic API not configured. Skipping.")
            return None

        try:
            logger.info("[SONNET] Querying Claude Sonnet (last resort)...")

            kwargs = {
                "model": self.SONNET_MODEL,
                "max_tokens": 4096,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_text}],
            }

            if tools:
                kwargs["tools"] = tools

            response = self.anthropic_client.messages.create(**kwargs)

            logger.info(f"[SONNET] ✓ Success. Tokens: {response.usage.output_tokens}")

            response_text = response.content[0].text if response.content else ""
            if not str(response_text).strip():
                logger.warning("[SONNET] Empty response payload. Falling through to fallback backend.")
                return None

            return {
                "response": response_text,
                "model": self.SONNET_MODEL,
                "source": "sonnet",
                "tool_calls": [b for b in response.content if getattr(b, "type", None) == "tool_use"],
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "usage": {
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens
                    }
                }
            }
        except Exception as e:
            if self._is_rate_limited_error(e):
                logger.warning(f"[SONNET] Rate limited: {e}. Falling through to fallback backend.")
            else:
                logger.error(f"[SONNET] Critical error: {e}")
            return None

    def query(
        self,
        system_prompt: str,
        user_text: str,
        tools: Optional[list] = None,
        messages: Optional[list] = None,
        prefer_local: bool = True,
        prefer_fallback: str = "haiku",
        mode: str = "legacy"
    ) -> Tuple[str, str, Dict[str, Any]]:
        """
        Main inference method. Supports two modes:

        Args:
            system_prompt: System/context prompt
            user_text: User message
            tools: Optional tool definitions
            messages: Optional message history (for local model)
            prefer_local: If True, try local first (legacy only)
            prefer_fallback: Which cloud model to prefer ("haiku" or "sonnet") - legacy only
            mode: "legacy" (local-first) or "smart" (haiku-first, task-aware)

        Returns:
            (response_text, source, metadata)
            where source is "local", "haiku", or "sonnet"
        """
        if mode == "smart":
            return self.query_smart(system_prompt, user_text, tools, messages)

        # LEGACY MODE: local -> haiku -> sonnet
        logger.info("=" * 70)
        logger.info(f"INFERENCE ROUTER (LEGACY) | Primary: {self.current_primary}")
        logger.info("=" * 70)

        # Step 1: Try local if preferred
        if prefer_local:
            result = self.query_local(system_prompt, user_text, tools, messages)
            if result:
                self.current_primary = "local"
                return result["response"], result["source"], result["metadata"]

        # Step 2: Try cloud fallback (haiku or sonnet)
        if prefer_fallback == "sonnet":
            # Sonnet first, then haiku
            result = self.query_sonnet(system_prompt, user_text, tools)
            if result:
                self.current_primary = "sonnet"
                return result["response"], result["source"], result["metadata"]

            result = self.query_haiku(system_prompt, user_text, tools)
            if result:
                self.current_primary = "haiku"
                return result["response"], result["source"], result["metadata"]
        else:
            # Haiku first, then sonnet
            result = self.query_haiku(system_prompt, user_text, tools)
            if result:
                self.current_primary = "haiku"
                return result["response"], result["source"], result["metadata"]

            result = self.query_sonnet(system_prompt, user_text, tools)
            if result:
                self.current_primary = "sonnet"
                return result["response"], result["source"], result["metadata"]

        raise RuntimeError("All inference backends failed. No response available.")


# Global router instance
_router_instance = None

def get_router() -> InferenceRouter:
    """Get or create the global router instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = InferenceRouter()
    return _router_instance


def route_inference(
    system_prompt: str,
    user_text: str,
    tools: Optional[list] = None,
    messages: Optional[list] = None,
    prefer_local: bool = True
) -> Tuple[str, str]:
    """
    Convenience function for routing inference (LEGACY mode).

    Returns:
        (response_text, source)
    """
    router = get_router()
    response, source, _ = router.query(system_prompt, user_text, tools, messages, prefer_local, mode="legacy")
    return response, source


def route_inference_code(
    system_prompt: str,
    user_text: str,
    tools: Optional[list] = None,
    haiku_boost: bool = True,
) -> Tuple[str, str, Dict[str, Any]]:
    """Code-specialist inference via merlin-code (qwen2.5-coder:14b) + optional Haiku review."""
    router = get_router()
    result = router.query_with_boost(
        system_prompt=system_prompt,
        user_text=user_text,
        model=router.LOCAL_CODE_MODEL,
        boost_mode=router.HAIKU_BOOST_CODE_REVIEW,
        tools=tools,
    )
    if result is None:
        raise RuntimeError("[CODE] merlin-code unavailable")
    return result["response"], result["source"], result.get("metadata", {})


def route_inference_vault(
    raw_text: str,
    haiku_boost: bool = True,
) -> Tuple[str, str, Dict[str, Any]]:
    """Digital Seed Vault extraction: structured JSON metadata from raw media text.

    vault-scraper (qwen2.5:7b, temp=0.1) produces the record.
    Haiku enrich pass fills missing standard fields if API is available.
    """
    router = get_router()
    result = router.query_with_boost(
        system_prompt="",          # vault-scraper's system prompt is baked into the Modelfile
        user_text=raw_text,
        model=router.LOCAL_VAULT_MODEL,
        boost_mode=router.HAIKU_BOOST_ENRICH,
    )
    if result is None:
        raise RuntimeError("[VAULT] vault-scraper unavailable")
    return result["response"], result["source"], result.get("metadata", {})


def route_inference_local(
    system_prompt: str,
    user_text: str,
    tools: Optional[list] = None,
    messages: Optional[list] = None,
    task_type: str = "",
    paired: bool = False,
) -> Tuple[str, str, Dict[str, Any]]:
    """Local-only inference — no cloud calls, ever.

    Args:
        paired: If True, runs the 7B sketch → 32B refine pipeline.
                If False, picks the appropriate tier model directly.
    Returns:
        (response_text, source, metadata)
    """
    router = get_router()
    if not task_type:
        task_type = router._classify_task(user_text, system_prompt)

    if paired:
        result = router.query_local_paired(system_prompt, user_text, task_type, tools, messages)
    else:
        result = router.query_local_tiered(system_prompt, user_text, task_type, tools, messages)

    if result is None:
        raise RuntimeError("[LOCAL_ONLY] Ollama unavailable — no cloud fallback in local-only mode")

    return result["response"], result["source"], result.get("metadata", {})


def route_inference_smart(
    system_prompt: str,
    user_text: str,
    tools: Optional[list] = None,
    messages: Optional[list] = None,
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Convenience function for SMART DISPATCH (Haiku-first, task-aware routing).

    This is the NEW butler-optimized path:
    - Task classification determines model selection
    - Simple tasks use Haiku (<3s)
    - Complex tasks use Sonnet
    - Teaching tasks use Merlin/Ollama
    - Proper fallback chain with no retry loops

    Returns:
        (response_text, source, metadata)
        where source is "haiku", "sonnet", or "local"
    """
    router = get_router()
    response, source, metadata = router.query_smart(system_prompt, user_text, tools, messages)
    return response, source, metadata


def resolve_ui_route(
    user_text: str,
    system_prompt: str = "",
    mode: str = "auto",
    voice_triggered: bool = False,
    api_key_available: bool = False,
) -> Dict[str, Any]:
    """Convenience wrapper for UI route resolution only (no inference call)."""
    router = get_router()
    return router.resolve_ui_route(
        user_text=user_text,
        system_prompt=system_prompt,
        mode=mode,
        voice_triggered=voice_triggered,
        api_key_available=api_key_available,
    )
