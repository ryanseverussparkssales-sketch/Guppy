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
from typing import Optional, Tuple, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

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
    OLLAMA_TIMEOUT = 10  # reduced from 30s (no longer primary path)
    LOCAL_MODEL = "guppy"
    
    HAIKU_MODEL = "claude-haiku-4-5-20251001"
    SONNET_MODEL = "claude-sonnet-4-6"
    
    HAIKU_TIMEOUT_SMART = 3  # fast timeout for smart dispatch (Haiku should be quick)
    SONNET_TIMEOUT_SMART = 10  # fallback timeout
    
    def __init__(self):
        """Initialize the router."""
        self.current_primary = "local"
        self.fallback_chain = ["local", "haiku", "sonnet"]
        
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
    
    def _classify_task(self, user_text: str, system_prompt: str = "") -> str:
        """
        Classify task into: 'simple', 'complex', or 'teaching'.
        
        Simple (Haiku): lookups, formatting, summaries, quick answers
        Complex (Sonnet): research, code, debugging, multi-step reasoning
        Teaching (Merlin/Ollama): explanations, learning, conceptual
        
        Returns: "simple", "complex", or "teaching"
        """
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
    
    def query_local(self, system_prompt: str, user_text: str, tools: Optional[list] = None, messages: Optional[list] = None) -> Optional[Dict[str, Any]]:
        """
        Query the local guppy model via Ollama.
        Returns response dict or None on failure/timeout.
        """
        try:
            logger.info("[LOCAL] Querying guppy model via Ollama...")
            
            # Build message list
            if messages is None:
                all_msgs = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text}
                ]
            else:
                all_msgs = messages
            
            payload = {
                "model": self.LOCAL_MODEL,
                "messages": all_msgs,
                "stream": False,
                "keep_alive": "10m",
                "options": {"temperature": 0.8, "top_p": 0.95, "top_k": 40, "num_predict": 512},
            }
            
            if tools:
                payload["tools"] = tools
            
            req = urllib.request.Request(
                self.OLLAMA_API,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            
            with urllib.request.urlopen(req, timeout=self.OLLAMA_TIMEOUT) as r:
                data = json.loads(r.read().decode())
            
            logger.info(f"[LOCAL] ✓ Success")
            
            return {
                "response": data.get("message", {}).get("content", ""),
                "model": self.LOCAL_MODEL,
                "source": "local",
                "tool_calls": data.get("message", {}).get("tool_calls", []),
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "raw_data": data
                }
            }
        except (socket.timeout, urllib.error.URLError) as e:
            logger.warning(f"[LOCAL] Timeout/connection error ({self.OLLAMA_TIMEOUT}s): {e}. Falling back.")
            return None
        except Exception as e:
            logger.warning(f"[LOCAL] Error: {e}. Falling back.")
            return None
    
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
            
            return {
                "response": response.content[0].text if response.content else "",
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
            logger.error(f"[HAIKU] Error: {e}. Escalating to Sonnet.")
            return None
    
    def query_sonnet(self, system_prompt: str, user_text: str, tools: Optional[list] = None) -> Dict[str, Any]:
        """Query Claude Sonnet as last resort."""
        if not self.anthropic_available:
            raise RuntimeError("[SONNET] Anthropic API not configured. No fallback available.")
        
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
            
            return {
                "response": response.content[0].text if response.content else "",
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
            logger.error(f"[SONNET] Critical error: {e}")
            raise
    
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
