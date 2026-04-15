from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from ._router_fragment_core import InferenceRouter

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
    """Code-specialist inference via guppy-code (qwen2.5-coder:14b) + optional Haiku review."""
    router = get_router()
    result = router.query_with_boost(
        system_prompt=system_prompt,
        user_text=user_text,
        model=router.LOCAL_CODE_MODEL,
        boost_mode=router.HAIKU_BOOST_CODE_REVIEW,
        tools=tools,
    )
    if result is None:
        raise RuntimeError("[CODE] guppy-code unavailable")
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
    """Local-only inference â€” no cloud calls, ever.

    Args:
        paired: If True, runs the 7B sketch â†’ 32B refine pipeline.
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
        raise RuntimeError("[LOCAL_ONLY] Ollama unavailable â€” no cloud fallback in local-only mode")

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
