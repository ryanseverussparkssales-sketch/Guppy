from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from src.guppy.inference.local_client import local_chat

logger = logging.getLogger(__name__)

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
    - Simple tasks (lookup, format, summarize) â†’ Haiku (2-3s)
    - Complex tasks (research, code, design) â†’ Sonnet (5-10s)
    - Teaching tasks (explain, learn) â†’ guppy-teach/Ollama (Socratic, local)
    - Fallback: Haiku timeout â†’ Sonnet â†’ give up

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
        # Route to guppy-teach/Ollama for Socratic teaching
        logger.info("[SMART] Teaching task -> trying Ollama/guppy-teach (Socratic)")
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
    - verify      â€” correct errors, fill factual gaps, add missing depth
    - code_review â€” scan code blocks for bugs, security issues, quick wins
    - enrich      â€” add missing metadata fields to structured output
    - structure   â€” reformat as clean JSON (last resort if vault-scraper drifted)

    Returns the enhanced response string, or the original if Haiku is unavailable/fails.
    """
    if not self.anthropic_available:
        return local_response

    BOOST_PROMPTS: Dict[str, str] = {
        self.HAIKU_BOOST_VERIFY: (
            "A local AI answered the following question. Your job is to briefly review the answer: "
            "correct any factual errors, fill critical gaps, and add one sentence of depth if it would "
            "genuinely help. Do NOT rewrite the whole thing â€” make surgical additions only. "
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
            "Return only the enriched JSON â€” no prose, no markdown fences.\n\n"
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
        logger.warning(f"[HAIKU_BOOST] failed ({boost_mode}): {e} â€” returning local response")
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
    The local model always runs first â€” Haiku is additive, not a fallback.
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
    """Local-only tiered dispatch: picks guppy-fast / guppy / guppy-teach by task_type."""
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
    """Two-pass local pipeline: 7B extracts intent â†’ 32B answers with that context.

    Pass 1 â€” guppy-fast (7B) distils the query into a 2-3 sentence intent sketch.
    Pass 2 â€” guppy / guppy-teach (32B) receives the original query + sketch as context.

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
    """Local inference call with circuit breaker and retry via local_chat."""
    _timeout = timeout if timeout is not None else self.OLLAMA_TIMEOUT
    all_msgs = messages if messages is not None else [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]

    for candidate in self._candidate_local_models(model):
        if candidate != model:
            logger.info(f"[LOCAL] alias {model} -> {candidate}")
        result = local_chat(
            candidate,
            all_msgs,
            tools=tools,
            timeout=_timeout,
            num_predict=self.local_num_predict,
        )
        if result is not None:
            result["requested_model"] = model
            result["resolved_model"] = candidate
            result.setdefault("metadata", {}).update(
                {"requested_model": model, "resolved_model": candidate}
            )
            return result

    logger.warning(f"[LOCAL] all candidates failed for {model}")
    return None

def query_openai(self, system_prompt: str, user_text: str, tools: Optional[list] = None) -> Optional[Dict[str, Any]]:
    """Query OpenAI (gpt-4o-mini default). Returns response dict or None."""
    if not self.openai_available or self.openai_client is None:
        logger.warning("[OPENAI] Not configured. Skipping.")
        return None
    try:
        logger.info(f"[OPENAI] Querying {self.openai_model}...")
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}]
        kwargs: Dict[str, Any] = {"model": self.openai_model, "messages": messages, "max_tokens": 4096}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        response = self.openai_client.chat.completions.create(**kwargs)
        content = (response.choices[0].message.content or "").strip() if response.choices else ""
        if not content:
            logger.warning("[OPENAI] Empty response.")
            return None
        logger.info(f"[OPENAI] ok tokens={response.usage.completion_tokens if response.usage else '?'}")
        return {
            "response": content,
            "model": self.openai_model,
            "source": "openai",
            "tool_calls": [],
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "usage": {
                    "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "output_tokens": response.usage.completion_tokens if response.usage else 0,
                },
            },
        }
    except Exception as e:
        logger.error(f"[OPENAI] Error: {e}")
        return None


def query_gemini(self, system_prompt: str, user_text: str, tools: Optional[list] = None) -> Optional[Dict[str, Any]]:
    """Query Google Gemini. Returns response dict or None."""
    if not self.google_available:
        logger.warning("[GOOGLE] Not configured. Skipping.")
        return None
    try:
        from google import genai
        from google.genai import types as gtypes
        logger.info(f"[GOOGLE] Querying {self.google_model}...")
        client = genai.Client(api_key=self._google_api_key)
        response = client.models.generate_content(
            model=self.google_model,
            contents=[gtypes.Content(role="user", parts=[gtypes.Part(text=user_text)])],
            config=gtypes.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=4096,
            ),
        )
        content = (response.text or "").strip()
        if not content:
            logger.warning("[GOOGLE] Empty response.")
            return None
        logger.info("[GOOGLE] ok")
        return {
            "response": content,
            "model": self.google_model,
            "source": "google",
            "tool_calls": [],
            "metadata": {"timestamp": datetime.now().isoformat()},
        }
    except Exception as e:
        logger.error(f"[GOOGLE] Error: {e}")
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
            "model": self.haiku_model_override,
            "max_tokens": 2048,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_text}],
        }

        if tools:
            kwargs["tools"] = tools

        response = self.anthropic_client.messages.create(**kwargs)

        logger.info(f"[HAIKU] âœ“ Success. Tokens: {response.usage.output_tokens}")

        response_text = response.content[0].text if response.content else ""
        if not str(response_text).strip():
            logger.warning("[HAIKU] Empty response payload. Escalating to next backend.")
            return None

        return {
            "response": response_text,
            "model": self.haiku_model_override,
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
            "model": self.sonnet_model_override,
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_text}],
        }

        if tools:
            kwargs["tools"] = tools

        response = self.anthropic_client.messages.create(**kwargs)

        logger.info(f"[SONNET] âœ“ Success. Tokens: {response.usage.output_tokens}")

        response_text = response.content[0].text if response.content else ""
        if not str(response_text).strip():
            logger.warning("[SONNET] Empty response payload. Falling through to fallback backend.")
            return None

        return {
            "response": response_text,
            "model": self.sonnet_model_override,
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
        prefer_local: If True, try local first (classic-chain mode only).
        prefer_fallback: Cloud fallback preference ("haiku" or "sonnet") for classic-chain mode.
        mode: "legacy" (local-first) or "smart" (haiku-first, task-aware)

    Returns:
        (response_text, source, metadata)
        where source is "local", "haiku", or "sonnet"
    """
    if mode == "smart":
        return self.query_smart(system_prompt, user_text, tools, messages)

    # Classic chain (mode=legacy): local -> haiku -> sonnet
    logger.info("=" * 70)
    logger.info(f"INFERENCE ROUTER (CLASSIC CHAIN: legacy) | Primary: {self.current_primary}")
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

def attach_router_execution_methods(cls) -> None:
    cls.query_smart = query_smart
    cls._haiku_boost = _haiku_boost
    cls.query_with_boost = query_with_boost
    cls.query_local_tiered = query_local_tiered
    cls.query_local_paired = query_local_paired
    cls._ollama_call = _ollama_call
    cls.query_local = query_local
    cls.query_openai = query_openai
    cls.query_gemini = query_gemini
    cls.query_haiku = query_haiku
    cls.query_sonnet = query_sonnet
    cls.query = query
