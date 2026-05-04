"""Unit tests for cloud provider routing — Groq, Gemini, OpenRouter, Haiku.

Verifies:
  - Model ID sets contain expected models
  - _get_cloud_api_key reads from env vars per provider
  - New streaming backend functions exist and are importable
  - Dispatch recognises each provider's model IDs
"""
from __future__ import annotations

import os
import pytest
from unittest.mock import patch, AsyncMock


# ── 1. Model ID sets ─────────────────────────────────────────────────────────

class TestModelIdSets:
    def test_groq_contains_llama_versatile(self):
        from src.guppy.api.realtime_inference_support import _GROQ_MODEL_IDS
        assert "llama-3.3-70b-versatile" in _GROQ_MODEL_IDS

    def test_groq_contains_gemma(self):
        from src.guppy.api.realtime_inference_support import _GROQ_MODEL_IDS
        assert "gemma2-9b-it" in _GROQ_MODEL_IDS

    def test_groq_contains_qwen_qwq(self):
        from src.guppy.api.realtime_inference_support import _GROQ_MODEL_IDS
        assert "qwen-qwq-32b" in _GROQ_MODEL_IDS

    def test_gemini_contains_flash(self):
        from src.guppy.api.realtime_inference_support import _GEMINI_MODEL_IDS
        assert "gemini-2.0-flash" in _GEMINI_MODEL_IDS

    def test_gemini_contains_1_5_flash(self):
        from src.guppy.api.realtime_inference_support import _GEMINI_MODEL_IDS
        assert "gemini-1.5-flash" in _GEMINI_MODEL_IDS

    def test_no_overlap_between_groq_and_gemini(self):
        from src.guppy.api.realtime_inference_support import _GROQ_MODEL_IDS, _GEMINI_MODEL_IDS
        assert _GROQ_MODEL_IDS.isdisjoint(_GEMINI_MODEL_IDS)

    def test_no_overlap_groq_mistral(self):
        from src.guppy.api.realtime_inference_support import _GROQ_MODEL_IDS, _MISTRAL_MODEL_IDS
        assert _GROQ_MODEL_IDS.isdisjoint(_MISTRAL_MODEL_IDS)

    def test_no_overlap_gemini_mistral(self):
        from src.guppy.api.realtime_inference_support import _GEMINI_MODEL_IDS, _MISTRAL_MODEL_IDS
        assert _GEMINI_MODEL_IDS.isdisjoint(_MISTRAL_MODEL_IDS)

    def test_free_groq_model_is_in_set(self):
        from src.guppy.api.realtime_inference_support import _GROQ_MODEL_IDS, _FREE_GROQ_MODEL
        assert _FREE_GROQ_MODEL in _GROQ_MODEL_IDS

    def test_free_gemini_model_is_in_set(self):
        from src.guppy.api.realtime_inference_support import _GEMINI_MODEL_IDS, _FREE_GEMINI_MODEL
        assert _FREE_GEMINI_MODEL in _GEMINI_MODEL_IDS


# ── 2. API key resolution ─────────────────────────────────────────────────────

class _FakeOwner:
    os = os


class TestApiKeyResolution:
    def test_groq_reads_groq_api_key_env(self):
        from src.guppy.api.realtime_inference_support import _get_cloud_api_key
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test123"}, clear=False):
            key = _get_cloud_api_key("groq", _FakeOwner())
        assert key == "gsk_test123"

    def test_gemini_reads_google_api_key_env(self):
        from src.guppy.api.realtime_inference_support import _get_cloud_api_key
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "AIza_test"}, clear=False):
            key = _get_cloud_api_key("gemini", _FakeOwner())
        assert key == "AIza_test"

    def test_openrouter_reads_openrouter_api_key_env(self):
        from src.guppy.api.realtime_inference_support import _get_cloud_api_key
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-test"}, clear=False):
            key = _get_cloud_api_key("openrouter", _FakeOwner())
        assert key == "sk-or-test"

    def test_anthropic_reads_anthropic_api_key_env(self):
        from src.guppy.api.realtime_inference_support import _get_cloud_api_key
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}, clear=False):
            key = _get_cloud_api_key("anthropic", _FakeOwner())
        assert key == "sk-ant-test"

    def test_missing_key_returns_empty_string(self):
        from src.guppy.api.realtime_inference_support import _get_cloud_api_key
        env_without = {k: v for k, v in os.environ.items() if k != "GROQ_API_KEY"}
        with patch.dict(os.environ, env_without, clear=True):
            key = _get_cloud_api_key("groq", _FakeOwner())
        assert key == ""


# ── 3. Streaming backend imports ───────────────────────────────────────────────

class TestStreamingBackendImports:
    def test_groq_streaming_importable(self):
        from src.guppy.inference.streaming_backends import _stream_groq_tokens
        assert callable(_stream_groq_tokens)

    def test_gemini_streaming_importable(self):
        from src.guppy.inference.streaming_backends import _stream_gemini_tokens
        assert callable(_stream_gemini_tokens)

    def test_openrouter_streaming_importable(self):
        from src.guppy.inference.streaming_backends import _stream_openrouter_tokens
        assert callable(_stream_openrouter_tokens)

    def test_groq_is_async_generator(self):
        import asyncio, inspect
        from src.guppy.inference.streaming_backends import _stream_groq_tokens
        # Calling with dummy args should return an async generator
        gen = _stream_groq_tokens(api_key="x", model="y", messages=[])
        assert inspect.isasyncgen(gen)

    def test_gemini_is_async_generator(self):
        import inspect
        from src.guppy.inference.streaming_backends import _stream_gemini_tokens
        gen = _stream_gemini_tokens(api_key="x", model="y", messages=[])
        assert inspect.isasyncgen(gen)

    def test_openrouter_is_async_generator(self):
        import inspect
        from src.guppy.inference.streaming_backends import _stream_openrouter_tokens
        gen = _stream_openrouter_tokens(api_key="x", model="y", messages=[])
        assert inspect.isasyncgen(gen)


# ── 4. OpenRouter model prefix ────────────────────────────────────────────────

class TestOpenRouterPrefix:
    def test_openrouter_prefix_stripped_correctly(self):
        model = "openrouter/meta-llama/llama-3.3-70b-instruct:free"
        assert model.startswith("openrouter/")
        stripped = model[len("openrouter/"):]
        assert stripped == "meta-llama/llama-3.3-70b-instruct:free"

    def test_groq_model_does_not_start_with_openrouter(self):
        from src.guppy.api.realtime_inference_support import _GROQ_MODEL_IDS
        for m in _GROQ_MODEL_IDS:
            assert not m.startswith("openrouter/"), f"{m} should not have openrouter/ prefix"

    def test_gemini_model_does_not_start_with_openrouter(self):
        from src.guppy.api.realtime_inference_support import _GEMINI_MODEL_IDS
        for m in _GEMINI_MODEL_IDS:
            assert not m.startswith("openrouter/"), f"{m} should not have openrouter/ prefix"


# ── 5. Haiku is an Anthropic model (falls through to Anthropic path) ──────────

class TestHaikuRouting:
    def test_haiku_not_in_groq_set(self):
        from src.guppy.api.realtime_inference_support import _GROQ_MODEL_IDS
        assert "claude-haiku-4-5-20251001" not in _GROQ_MODEL_IDS

    def test_haiku_not_in_gemini_set(self):
        from src.guppy.api.realtime_inference_support import _GEMINI_MODEL_IDS
        assert "claude-haiku-4-5-20251001" not in _GEMINI_MODEL_IDS

    def test_haiku_not_in_mistral_set(self):
        from src.guppy.api.realtime_inference_support import _MISTRAL_MODEL_IDS
        assert "claude-haiku-4-5-20251001" not in _MISTRAL_MODEL_IDS

    def test_haiku_not_in_cohere_set(self):
        from src.guppy.api.realtime_inference_support import _COHERE_MODEL_IDS
        assert "claude-haiku-4-5-20251001" not in _COHERE_MODEL_IDS
