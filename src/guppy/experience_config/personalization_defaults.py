"""Default personalization payloads and shared constants."""

from __future__ import annotations

from typing import Any


MAIN_GUPPY_PERSONA_ID = "main_guppy"
DEFAULT_ASSISTANT_NAME = "Guppy"
MAIN_GUPPY_PROFILE_SUMMARY = (
    "- Ryan prefers concise, high-signal answers with low filler.\n"
    "- Keep the tone calm, exact, proactive, and quietly confident. Aim for a Jarvis-like feel without theatrical phrasing.\n"
    "- Preserve continuity across coding, launcher UX, automation, and workspace work so progress feels cumulative.\n"
    "- Keep Home calm and chat-first. Move heavier runtime, routing, recovery, and logs detail into App Mgmt or dedicated surfaces.\n"
    "- Never pretend an action, tool result, or state change happened unless it was actually executed."
)


DEFAULT_PERSONA_CONFIG: dict[str, Any] = {
    "version": 1,
    "default_persona_id": MAIN_GUPPY_PERSONA_ID,
    "personas": [
        {
            "id": MAIN_GUPPY_PERSONA_ID,
            "name": DEFAULT_ASSISTANT_NAME,
            "scope": "global",
            "system_prompt": (
                f"You are {DEFAULT_ASSISTANT_NAME}, Ryan's primary day-to-day assistant. "
                "Be calm, dependable, practical, and quietly confident. "
                "Keep the Jarvis-like feel understated and never theatrical."
            ),
            "traits": {
                "tone": "butler",
                "verbosity": "medium",
                "response_style": "direct",
            },
            "teaching": {
                "enabled": True,
                "socratic_bias": 35,
                "example_bias": 60,
            },
            "profile_summary": MAIN_GUPPY_PROFILE_SUMMARY,
        }
    ],
    "assignments": {
        "global": MAIN_GUPPY_PERSONA_ID,
        "by_model": {},
    },
}


DEFAULT_PROVIDER_REGISTRY: dict[str, Any] = {
    "version": 1,
    "default_route": "anthropic/claude-haiku-4-5-20251001",
    "providers": [
        {
            "id": "anthropic",
            "name": "Anthropic",
            "enabled": True,
            "api_base": "https://api.anthropic.com",
            "auth_env": "ANTHROPIC_API_KEY",
            "provider_tier": "supported_optional",
            "models": [
                {
                    "id": "claude-haiku-4-5-20251001",
                    "label": "Claude Haiku 4.5",
                    "enabled": True,
                    "context_window": 200000,
                    "speed_tier": "fast",
                    "tags": ["cheap", "teaching"],
                    "pricing": {"tier": "cheap"},
                },
                {
                    "id": "claude-sonnet-4-6",
                    "label": "Claude Sonnet 4.6",
                    "enabled": True,
                    "context_window": 200000,
                    "speed_tier": "balanced",
                    "tags": ["reasoning"],
                    "pricing": {"tier": "premium"},
                },
            ],
        },
        {
            "id": "openai",
            "name": "OpenAI",
            "enabled": True,
            "api_base": "https://api.openai.com/v1",
            "auth_env": "OPENAI_API_KEY",
            "provider_tier": "supported_optional",
            "models": [
                {
                    "id": "gpt-4.1-mini",
                    "label": "GPT-4.1 Mini",
                    "enabled": True,
                    "context_window": 128000,
                    "speed_tier": "fast",
                    "tags": ["general", "cheap"],
                    "pricing": {"tier": "cheap"},
                },
                {
                    "id": "gpt-4.1",
                    "label": "GPT-4.1",
                    "enabled": True,
                    "context_window": 128000,
                    "speed_tier": "balanced",
                    "tags": ["reasoning"],
                    "pricing": {"tier": "premium"},
                },
            ],
        },
        {
            "id": "gemini",
            "name": "Google Gemini",
            "enabled": True,
            "api_base": "https://generativelanguage.googleapis.com/v1beta",
            "auth_env": "GEMINI_API_KEY",
            "provider_tier": "supported_optional",
            "models": [
                {
                    "id": "gemini-2.0-flash",
                    "label": "Gemini 2.0 Flash",
                    "enabled": True,
                    "context_window": 1000000,
                    "speed_tier": "fast",
                    "tags": ["multimodal", "cheap"],
                    "pricing": {"tier": "cheap"},
                },
                {
                    "id": "gemini-2.5-pro",
                    "label": "Gemini 2.5 Pro",
                    "enabled": True,
                    "context_window": 1000000,
                    "speed_tier": "balanced",
                    "tags": ["reasoning"],
                    "pricing": {"tier": "premium"},
                },
            ],
        },
        {
            "id": "ollama_api",
            "name": "Ollama API (Cloud/Remote)",
            "enabled": True,
            "api_base": "https://ollama.com/api",
            "auth_env": "OLLAMA_API_KEY",
            "provider_tier": "supported_optional",
            "models": [
                {
                    "id": "llama3.1:8b",
                    "label": "Llama 3.1 8B",
                    "enabled": True,
                    "context_window": 32768,
                    "speed_tier": "balanced",
                    "tags": ["general"],
                    "pricing": {"tier": "cheap"},
                }
            ],
        },
        {
            "id": "lmstudio_local",
            "name": "LM Studio (Local)",
            "enabled": True,
            "api_base": "http://127.0.0.1:1234/v1",
            "auth_env": "",
            "provider_tier": "core",
            "models": [
                {
                    "id": "local-model",
                    "label": "LM Studio Active Model",
                    "enabled": True,
                    "context_window": 0,
                    "speed_tier": "balanced",
                    "tags": ["local"],
                    "pricing": {"tier": "local"},
                }
            ],
        },
        {
            "id": "local_harness",
            "name": "Local Harness",
            "enabled": True,
            "api_base": "http://127.0.0.1:8001",
            "auth_env": "",
            "provider_tier": "core",
            "models": [
                {
                    "id": "harness-default",
                    "label": "Harness Default",
                    "enabled": True,
                    "context_window": 0,
                    "speed_tier": "balanced",
                    "tags": ["local", "harness"],
                    "pricing": {"tier": "local"},
                }
            ],
        },
        {
            "id": "lemonade_local",
            "name": "Lemonade (Local)",
            "enabled": False,
            "api_base": "http://127.0.0.1:13305/api/v1",
            "auth_env": "",
            "provider_tier": "experimental",
            "availability_status": "opt_in",
            "models": [
                {
                    "id": "lemonade-default",
                    "label": "Lemonade Active Model",
                    "enabled": True,
                    "context_window": 0,
                    "speed_tier": "balanced",
                    "tags": ["local", "challenger"],
                    "pricing": {"tier": "local"},
                }
            ],
        },
        {
            "id": "anythingllm_local",
            "name": "AnythingLLM (Planned Adapter)",
            "enabled": False,
            "api_base": "http://127.0.0.1:3001/api/v1",
            "auth_env": "",
            "provider_tier": "experimental",
            "availability_status": "planned",
            "models": [
                {
                    "id": "anythingllm-planned",
                    "label": "AnythingLLM Planned Adapter",
                    "enabled": True,
                    "context_window": 0,
                    "speed_tier": "balanced",
                    "tags": ["local", "planned", "adapter"],
                    "pricing": {"tier": "local"},
                }
            ],
        },
        {
            "id": "huggingface_local",
            "name": "Hugging Face Local (Planned Adapter)",
            "enabled": False,
            "api_base": "http://127.0.0.1:8002/v1",
            "auth_env": "",
            "provider_tier": "experimental",
            "availability_status": "planned",
            "models": [
                {
                    "id": "huggingface-local-planned",
                    "label": "Hugging Face Local Planned Adapter",
                    "enabled": True,
                    "context_window": 0,
                    "speed_tier": "balanced",
                    "tags": ["local", "planned", "adapter"],
                    "pricing": {"tier": "local"},
                }
            ],
        },
        {
            "id": "local",
            "name": "Ollama (Local)",
            "enabled": True,
            "api_base": "http://127.0.0.1:11434",
            "auth_env": "",
            "provider_tier": "core",
            "models": [
                {
                    "id": "guppy",
                    "label": "Guppy",
                    "enabled": True,
                    "context_window": 32768,
                    "speed_tier": "balanced",
                    "tags": ["local", "default"],
                    "pricing": {"tier": "local"},
                },
                {
                    "id": "guppy-fast",
                    "label": "Guppy Fast",
                    "enabled": True,
                    "context_window": 32768,
                    "speed_tier": "fast",
                    "tags": ["local", "fast"],
                    "pricing": {"tier": "local"},
                },
                {
                    "id": "guppy-code",
                    "label": "Guppy Code",
                    "enabled": True,
                    "context_window": 32768,
                    "speed_tier": "balanced",
                    "tags": ["local", "code"],
                    "pricing": {"tier": "local"},
                },
            ],
        },
    ],
    "routes": {
        "simple": "anthropic/claude-haiku-4-5-20251001",
        "complex": "anthropic/claude-sonnet-4-6",
        "teaching": "anthropic/claude-haiku-4-5-20251001",
        "fallback_chain": [
            "anthropic/claude-haiku-4-5-20251001",
            "anthropic/claude-sonnet-4-6",
            "local/guppy",
        ],
    },
}


DEFAULT_VOICE_BINDINGS: dict[str, Any] = {
    "version": 1,
    "defaults": {
        "engine": "EDGE TTS",
        "voice_id": "en-GB-RyanNeural",
    },
    "bindings": {
        "by_model": {},
        "by_persona": {
            MAIN_GUPPY_PERSONA_ID: {
                "engine": "EDGE TTS",
                "voice_id": "en-GB-RyanNeural",
            }
        },
    },
    "imports": [],
}


LOCAL_MODEL_IDS: list[str] = [
    "guppy",
    "guppy-fast",
    "guppy-code",
    "guppy-teach",
    "vault-scraper",
]
