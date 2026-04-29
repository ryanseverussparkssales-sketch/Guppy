"""
inference_router.py â€” Guppy Inference Priority Router
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

    1. Classic chain (legacy mode): local -> haiku -> sonnet (backward compatibility)
    2. Smart chain: haiku-first -> sonnet -> ollama (for butler UX, <3s latency)
       - Task-aware routing: simple -> Haiku, complex -> Sonnet, teaching -> guppy-teach/Ollama
       - 3s timeout on Haiku (not 30s on Ollama)
       - No retry loops: once fallback starts, don't retry failed backend
    """

    # Configuration
    OLLAMA_API = "http://127.0.0.1:11434/api/chat"
    OLLAMA_TIMEOUT = 10       # fallback path timeout (cloud-first modes)
    OLLAMA_LOCAL_TIMEOUT = 60 # local-only mode â€” allow full 32B inference time

    # Local model roster -- llama.cpp backends (primary); Ollama is no longer in the routing path.
    # Route aliases: “hermes-4-14b” -> llamacpp-hermes4 (8086), “hermes-3-8b-lorablated” -> llamacpp-hermes3 (8087)
    LOCAL_MODEL       = “hermes-4-14b”           # complex butler tasks -- always-on workspace agent
    LOCAL_FAST_MODEL  = “hermes-3-8b-lorablated” # simple/fast -- uncensored 8B
    LOCAL_TEACH_MODEL = “hermes-4-14b”           # teaching -- quality over speed
    LOCAL_CODE_MODEL  = “hermes-4-14b”           # code review/debug
    LOCAL_VAULT_MODEL = “vault-scraper”           # structured media extraction (Ollama-only special case)

    LOCAL_TIER_MAP: Dict[str, str] = {
        “simple”:    LOCAL_FAST_MODEL,   # hermes3 -- fast 8B
        “complex”:   LOCAL_MODEL,        # hermes4 -- 14B quality
        “teaching”:  LOCAL_TEACH_MODEL,  # hermes4 -- 14B quality
        “agentic”:   LOCAL_MODEL,        # hermes4 fallback (Qwen3 intercept fires first)
        “tool_call”: LOCAL_FAST_MODEL,   # hermes3 fallback (xLAM intercept fires first)
    }

    # Haiku boost modes â€” targeted Haiku pass that supplements local output
    HAIKU_BOOST_VERIFY      = "verify"       # fact-check / fill gaps
    HAIKU_BOOST_CODE_REVIEW = "code_review"  # scan generated code for bugs
    HAIKU_BOOST_ENRICH      = "enrich"       # add missing metadata fields
    HAIKU_BOOST_STRUCTURE   = "structure"    # reformat as clean JSON

    HAIKU_MODEL = "claude-haiku-4-5-20251001"
    SONNET_MODEL = "claude-sonnet-4-6"

    HAIKU_TIMEOUT_SMART = 8   # API cold-start + network can easily hit 2-3 s; 3 was too aggressive
    SONNET_TIMEOUT_SMART = 20 # Sonnet is slower â€” give it room

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
        self._classification_cache: dict[tuple[str, str], str] = {}
        self._classification_cache_max = 256
        # Freeze semantic-classifier mode at construction time so test helpers
        # and long-lived router instances do not change behavior mid-lifecycle
        # when unrelated code mutates process-level environment variables.
        self.semantic_classifier_enabled = self._bool_env("GUPPY_SEMANTIC_CLASSIFIER", True)
        self._legacy_model_aliases = {
            "guppy-teach": "merlin",
            "guppy-code": "merlin-code",
        }

        # Runtime model overrides for low-compute/night runs.
        self.low_compute_mode = self._bool_env("GUPPY_LOW_COMPUTE_MODE", False)
        default_complex_model = self.LOCAL_FAST_MODEL if self.low_compute_mode else self.LOCAL_MODEL
        default_code_model = "hermes-4-14b"
        default_teach_model = self.LOCAL_FAST_MODEL if self.low_compute_mode else "hermes-4-14b"

        self.LOCAL_FAST_MODEL = (os.environ.get("GUPPY_LOCAL_FAST_MODEL", self.LOCAL_FAST_MODEL) or self.LOCAL_FAST_MODEL).strip()
        self.LOCAL_MODEL = (os.environ.get("GUPPY_LOCAL_COMPLEX_MODEL", default_complex_model) or default_complex_model).strip()
        self.LOCAL_TEACH_MODEL = (os.environ.get("GUPPY_LOCAL_TEACH_MODEL", default_teach_model) or default_teach_model).strip()
        self.LOCAL_CODE_MODEL = (os.environ.get("GUPPY_LOCAL_CODE_MODEL", default_code_model) or default_code_model).strip()
        self.LOCAL_VAULT_MODEL = (os.environ.get("GUPPY_LOCAL_VAULT_MODEL", self.LOCAL_VAULT_MODEL) or self.LOCAL_VAULT_MODEL).strip()

        self.LOCAL_TIER_MAP = {
            "simple":   self.LOCAL_FAST_MODEL,   # hermes3 — fast 8B
            "complex":  self.LOCAL_MODEL,         # hermes4 — 14B quality
            "teaching": self.LOCAL_TEACH_MODEL,   # hermes4 — 14B quality
            "agentic":  self.LOCAL_MODEL,         # hermes4 fallback (Qwen3 intercept fires first)
        }

        default_predict = "320" if self.low_compute_mode else "512"
        try:
            self.local_num_predict = max(128, int(os.environ.get("GUPPY_LOCAL_NUM_PREDICT", default_predict)))
        except Exception:
            self.local_num_predict = int(default_predict)

        # Anthropic model overrides (consolidate env reads into instance vars)
        self.haiku_model_override = (os.environ.get("ANTHROPIC_HAIKU_MODEL", "").strip() or self.HAIKU_MODEL)
        self.sonnet_model_override = (os.environ.get("ANTHROPIC_MODEL", "").strip() or self.SONNET_MODEL)

        # Anthropic
        try:
            import anthropic
            self.anthropic_client = anthropic.Anthropic(
                api_key=os.environ.get("ANTHROPIC_API_KEY", "").strip()
            )
            self.anthropic_available = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
        except ImportError:
            self.anthropic_client = None
            self.anthropic_available = False

        # OpenAI
        self.openai_model = (os.environ.get("OPENAI_MODEL", "").strip() or "gpt-4o-mini")
        try:
            from openai import OpenAI
            _openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
            self.openai_client = OpenAI(api_key=_openai_key) if _openai_key else None
            self.openai_available = bool(_openai_key)
        except ImportError:
            self.openai_client = None
            self.openai_available = False

        # Google Gemini
        self.google_model = (os.environ.get("GOOGLE_MODEL", "").strip() or "gemini-2.0-flash")
        try:
            from google import genai as _genai  # noqa: F401
            _google_key = os.environ.get("GOOGLE_API_KEY", "").strip()
            self.google_available = bool(_google_key)
            self._google_api_key = _google_key
        except ImportError:
            self.google_available = False
            self._google_api_key = ""

    def _should_use_haiku_boost(self, api_available: bool) -> bool:
        """Check if haiku boost should be used."""
        if not api_available:
            return False
        return self._bool_env("GUPPY_HAIKU_BOOST", True)

    def _candidate_local_models(self, model: str) -> list[str]:
        candidates = [model]
        aliases = getattr(self, "_legacy_model_aliases", {}) or {}
        alias = aliases.get(model)
        if alias and alias not in candidates:
            candidates.append(alias)
        return candidates

    @staticmethod
    def _is_rate_limited_error(error: Exception | str) -> bool:
        txt = str(error or "").lower()
        return "429" in txt or "rate limit" in txt or "too many requests" in txt

    def _classify_task(self, user_text: str, system_prompt: str = "") -> str:
        """Classify task into simple/complex/teaching using semantic + fallback heuristic."""
        cache_key = ((user_text or "").strip(), (system_prompt or "")[:400].strip())
        cached = self._classification_cache.get(cache_key)
        if cached in {"simple", "complex", "teaching", "agentic", "tool_call"}:
            return cached

        if self.semantic_classifier_enabled and self.anthropic_available:
            task = self._classify_task_semantic(user_text=user_text, system_prompt=system_prompt)
            if task in {"simple", "complex", "teaching", "agentic", "tool_call"}:
                self._classification_cache[cache_key] = task
                if len(self._classification_cache) > self._classification_cache_max:
                    self._classification_cache.pop(next(iter(self._classification_cache)))
                return task
        task = self._classify_task_heuristic(user_text=user_text, system_prompt=system_prompt)
        self._classification_cache[cache_key] = task
        if len(self._classification_cache) > self._classification_cache_max:
            self._classification_cache.pop(next(iter(self._classification_cache)))
        return task

    def _classify_task_semantic(self, user_text: str, system_prompt: str = "") -> str:
        """Use Haiku to classify intent with strict JSON output."""
        try:
            prompt = (
                "Classify this request for routing into exactly one label: simple, complex, agentic, teaching, tool_call.\n"
                "Rules:\n"
                "- tool_call: single explicit tool invocation — user names a specific tool, database, or external service (web search, calibre, screenpipe, wikipedia, weather, translate, calculate)\n"
                "- simple: factual lookups, reminders, short transforms, status checks, lightweight Q&A (no tool needed)\n"
                "- complex: multi-step reasoning, architecture/debugging/code planning, deep analysis\n"
                "- agentic: requires multiple sequential tool calls — reading/scanning files, collecting data across sources, iterating over a set, building profiles from many inputs\n"
                "- teaching: user explicitly wants instruction/tutoring/concept walkthrough\n"
                "Prefer tool_call over simple when the user is asking to fetch live data or use a named system.\n"
                "Return JSON only: {\"task_type\":\"simple|complex|agentic|teaching|tool_call\",\"confidence\":0..1}\n"
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
            if task_type in {"simple", "complex", "teaching", "agentic"}:
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

        # Tool-call keywords: explicit single-tool invocation. Routed to
        # xLAM-2-8B (port 8089) when alive; falls back to Hermes 4 via llamacpp.
        tool_call_keywords = {
            # Explicit tool language
            "use the tool", "call the tool", "invoke the tool",
            "run the tool", "execute the tool",
            # Web / search
            "use the web search", "search the web", "search online",
            "google that", "google it", "look it up online",
            "browse the web", "web search for", "search for on",
            "bing it", "duckduckgo", "look it up on",
            # Guppy-specific tool names
            "use the calibre", "search my library", "add to calibre", "search calibre",
            "send to kindle", "search gutenberg", "search openlibrary",
            "use screenpipe", "search screenpipe", "search my screen",
            # Wikipedia / reference lookups
            "find on wikipedia", "search wikipedia", "what does wikipedia say",
            "look up on wikipedia",
            # Live data (single API call)
            "check the weather", "current weather", "weather for", "weather in",
            "what's the weather", "whats the weather",
            "current time in", "what time is it in",
            # Translation / conversion / calculation
            "translate this", "translate to", "convert this to",
            "calculate this", "compute this", "what is the exchange rate",
            # Download / fetch single item
            "download the book", "download it", "fetch the page",
        }
        if any(k in combined_lower for k in tool_call_keywords):
            return "tool_call"

        # Agentic keywords (multi-step tool execution over collections)
        # These tasks must never land on small 7–8B models — they hallucinate
        # fake results instead of actually calling tools.
        agentic_keywords = {
            "read all", "scan all", "every file", "all files", "all folders",
            "read every", "scan every", "go through all", "go through every",
            "for each file", "for each folder", "for each item",
            "collect all", "gather all", "process all", "iterate over",
            "build a profile", "index all", "list and read",
            "walk through all", "loop through", "analyze all files", "review all files",
            "check all files", "check every file", "read each", "scan each",
        }
        if any(k in combined_lower for k in agentic_keywords):
            return "agentic"

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

        question_text = (user_text or "").strip()
        question_lower = question_text.lower()
        if question_lower.startswith("what is "):
            tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9.+-]*", question_text)
            has_acronym = any(token.isupper() and len(token) >= 2 for token in tokens)
            factual_what_is_cues = {
                "capital",
                "population",
                "weather",
                "price",
                "status",
                "date",
                "time",
            }
            if has_acronym or any(cue in question_lower for cue in factual_what_is_cues):
                return "simple"
            return "teaching"

        # Simple keywords (fast with Haiku)
        simple_keywords = {
            "what time", "what date", "remind me", "list", "format",
            "summarize", "rewrite", "shorten", "expand", "check",
            "find", "look up", "search", "when is", "where is",
            "tell me about", "news", "weather", "quick",
        }
        if any(k in combined_lower for k in simple_keywords):
            return "simple"

        # Teaching keywords should only win when the user is explicitly asking
        # for instruction instead of a plain factual lookup.
        teaching_keywords = {
            "explain", "teach me", "how does", "why is",
            "help me understand", "concept", "introduce", "intro to",
            "define", "meaning of", "learn about", "guide me",
        }
        if any(k in combined_lower for k in teaching_keywords):
            return "teaching"

        # Length heuristic: very short messages are usually simple once they
        # have failed the explicit complex/teaching intent checks above.
        if len(user_text or "") < 50:
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
                    "system_profile": "guppy",
                    "model": self.LOCAL_TEACH_MODEL,
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

        # teaching â€” force teaching profile and route irrespective of classifier noise
        if normalized_mode == "teaching":
            if has_api:
                return {
                    "task_type": "teaching",
                    "route": "claude_teaching",
                    "route_reason": "manual teaching mode requested",
                    "executor": "claude",
                    "system_profile": "guppy",
                    "model": os.environ.get("ANTHROPIC_HAIKU_MODEL", self.HAIKU_MODEL),
                    "backup_model": os.environ.get("ANTHROPIC_MODEL", self.SONNET_MODEL),
                }
            return {
                "task_type": "teaching",
                "route": "llamacpp_teaching",
                "route_reason": "manual teaching mode requested (no API key) -> hermes4",
                "executor": "llamacpp",
                "system_profile": "guppy",
                "model": self.LOCAL_TEACH_MODEL,
                "backup_model": "",
            }

        # local — tier-aware local-only routing (no cloud fallback), llama.cpp primary
        # simple→hermes3, complex/teaching→hermes4
        if normalized_mode == “local”:
            model = self.LOCAL_TIER_MAP.get(task_type, self.LOCAL_MODEL)
            return {
                “task_type”: task_type,
                “route”: f”local_{task_type}”,
                “route_reason”: f”local-only mode — {task_type} tier → {model}”,
                “executor”: “llamacpp”,
                “system_profile”: “guppy”,
                “model”: model,
                “backup_model”: “”,
                “timeout”: self.OLLAMA_LOCAL_TIMEOUT,
                “local_only”: True,
            }

        # code — dedicated code session via Hermes4, optional Haiku boost
        if normalized_mode == “code”:
            haiku_boost = self._should_use_haiku_boost(has_api)
            return {
                “task_type”: task_type,
                “route”: “local_code”,
                “route_reason”: “code mode -> hermes4 (llamacpp, uncensored)”,
                “executor”: “llamacpp”,
                “system_profile”: “guppy”,
                “model”: self.LOCAL_CODE_MODEL,
                “backup_model”: “”,
                “timeout”: self.OLLAMA_LOCAL_TIMEOUT,
                “local_only”: True,
                “haiku_boost”: haiku_boost,
                “haiku_boost_mode”: self.HAIKU_BOOST_CODE_REVIEW,
            }

        # vault â€” structured media extraction via vault-scraper, optional Haiku enrich pass
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

        # local_paired â€” 7B sketches intent, 32B refines (no cloud fallback)
        # For simple tasks the sketch IS the answer (no second pass needed).
        if normalized_mode == "local_paired":
            sketch_model = self.LOCAL_FAST_MODEL
            if task_type == "simple":
                return {
                    "task_type": task_type,
                    "route": "local_paired_simple",
                    "route_reason": "local_paired â€” simple task, single 7B pass sufficient",
                    "executor": "ollama",
                    "system_profile": "guppy",
                    "model": sketch_model,
                    "backup_model": "",
                    "timeout": self.OLLAMA_LOCAL_TIMEOUT,
                    "local_only": True,
                    "paired": False,
                }
            refine_model = self.LOCAL_TEACH_MODEL if task_type == "teaching" else self.LOCAL_MODEL
            return {
                "task_type": task_type,
                "route": f"local_paired_{task_type}",
                "route_reason": (
                    f"local_paired â€” {task_type}: {sketch_model} sketches intent, "
                    f"{refine_model} refines"
                ),
                "executor": "ollama_paired",
                "system_profile": "guppy",
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
                    "route_reason": "teaching task, cloud mode via Haiku + Guppy teaching profile",
                    "executor": "claude",
                    "system_profile": "guppy",
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
                    "system_profile": "guppy",
                    "model": self.haiku_model_override,
                    "backup_model": self.sonnet_model_override,
                }
            return {
                "task_type": task_type,
                "route": "llamacpp_teaching",
                "route_reason": "teaching task -> hermes4 (llamacpp, always-on)",
                "executor": "llamacpp",
                "system_profile": "guppy",
                "model": self.LOCAL_TEACH_MODEL,
                "backup_model": "",
            }

        if not has_api:
            return {
                "task_type": task_type,
                "route": "llamacpp_fallback",
                "route_reason": "no API key -> hermes4 (llamacpp, always-on)",
                "executor": "llamacpp",
                "system_profile": "guppy",
                "model": self.LOCAL_MODEL,
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
