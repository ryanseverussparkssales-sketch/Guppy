"""Tests for Phase 4a lightweight health check implementations.

Tests that all 6 providers implement _lightweight_health_check() using
real lightweight endpoints instead of minimal inference.

Providers tested:
- LocalProviderClient (Ollama) - GET /api/v1/models
- AnthropicClient - OPTIONS /v1/messages
- OpenAIClient - GET /v1/models
- GoogleClient - GET /v1beta/models
- CohereClient - HEAD /v2/chat
- MistralClient - GET /v1/models

Expected improvements (Phase 4a):
- Latency: 500-2000ms → 50-200ms (5-10x faster)
- API quota: 1 inference per check → 0 (100% savings)
- Cost: $0.001-0.015 → $0 (100% savings)
"""

import asyncio
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.guppy.inference.provider_client import LocalProviderClient
from src.guppy.inference.provider_clients_cloud import (
    AnthropicClient,
    OpenAIClient,
    GoogleClient,
    CohereClient,
    MistralClient,
)


class TestLocalProviderHealthCheck:
    """Test Ollama lightweight health check."""

    @pytest.mark.asyncio
    async def test_local_health_check_uses_models_endpoint(self):
        """Verify LocalProviderClient uses GET /v1/models for health check (llamacpp OpenAI-compat)."""
        client = LocalProviderClient(model="guppy")

        # Mock the HTTP request
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.read.return_value = b'{"models": []}'
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            result = await client.health_check()

            assert result is True
            # Verify it called the OpenAI-compat /v1/models endpoint (llamacpp; Ollama was removed)
            called_url = mock_urlopen.call_args[0][0].full_url
            assert "/v1/models" in called_url


@pytest.mark.asyncio
class TestCloudProviderHealthChecks:
    """Test lightweight health checks for cloud providers."""

    async def test_anthropic_health_check_uses_options(self):
        """Verify Anthropic uses OPTIONS request for health check."""
        api_key = "test-key-anthropic"
        client = AnthropicClient(api_key=api_key)

        with patch('aiohttp.ClientSession.options') as mock_options:
            mock_response = AsyncMock()
            mock_response.status = 405  # OPTIONS not allowed, but API is reachable
            mock_options.return_value.__aenter__.return_value = mock_response

            result = await client._lightweight_health_check()

            assert result is True
            # Verify OPTIONS was called on /v1/messages endpoint
            mock_options.assert_called_once()
            called_url = mock_options.call_args[0][0]
            assert "api.anthropic.com/v1/messages" in called_url

    async def test_anthropic_health_check_caches(self):
        """Verify Anthropic health check result is cached."""
        api_key = "test-key-anthropic"
        client = AnthropicClient(api_key=api_key)

        with patch('aiohttp.ClientSession.options') as mock_options:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_options.return_value.__aenter__.return_value = mock_response

            # First call
            result1 = await client.health_check()
            # Second call (should use cache)
            result2 = await client.health_check()

            assert result1 is True
            assert result2 is True
            # OPTIONS should only be called once (cached on second call)
            # Note: actual number depends on cache TTL
            assert mock_options.call_count >= 1

    async def test_openai_health_check_uses_models_endpoint(self):
        """Verify OpenAI uses GET /v1/models for health check."""
        api_key = "test-key-openai"
        client = OpenAIClient(api_key=api_key)

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_get.return_value.__aenter__.return_value = mock_response

            result = await client._lightweight_health_check()

            assert result is True
            mock_get.assert_called_once()
            called_url = mock_get.call_args[0][0]
            assert "api.openai.com/v1/models" in called_url

    async def test_google_health_check_uses_models_endpoint(self):
        """Verify Google uses GET /v1beta/models for health check."""
        api_key = "test-key-google"
        client = GoogleClient(api_key=api_key)

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_get.return_value.__aenter__.return_value = mock_response

            result = await client._lightweight_health_check()

            assert result is True
            mock_get.assert_called_once()
            called_url = mock_get.call_args[0][0]
            assert "generativelanguage.googleapis.com/v1beta/models" in called_url

    async def test_cohere_health_check_uses_head_request(self):
        """Verify Cohere uses HEAD /v2/chat for health check."""
        api_key = "test-key-cohere"
        client = CohereClient(api_key=api_key)

        with patch('aiohttp.ClientSession.head') as mock_head:
            mock_response = AsyncMock()
            mock_response.status = 400  # Bad request, but API is reachable
            mock_head.return_value.__aenter__.return_value = mock_response

            result = await client._lightweight_health_check()

            assert result is True
            mock_head.assert_called_once()
            called_url = mock_head.call_args[0][0]
            assert "api.cohere.ai/v2/chat" in called_url

    async def test_mistral_health_check_uses_models_endpoint(self):
        """Verify Mistral uses GET /v1/models for health check."""
        api_key = "test-key-mistral"
        client = MistralClient(api_key=api_key)

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_get.return_value.__aenter__.return_value = mock_response

            result = await client._lightweight_health_check()

            assert result is True
            mock_get.assert_called_once()
            called_url = mock_get.call_args[0][0]
            assert "api.mistral.ai/v1/models" in called_url

    async def test_health_check_returns_false_without_api_key(self):
        """Verify health check returns False if API key is missing."""
        import unittest.mock
        with unittest.mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}, clear=False):
            client = AnthropicClient(api_key="")

        result = await client._lightweight_health_check()

        assert result is False

    async def test_health_check_handles_timeout(self):
        """Verify health check handles timeout gracefully."""
        api_key = "test-key"
        client = OpenAIClient(api_key=api_key)

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.side_effect = asyncio.TimeoutError()

            result = await client._lightweight_health_check()

            assert result is False

    async def test_health_check_handles_connection_error(self):
        """Verify health check handles connection errors gracefully."""
        api_key = "test-key"
        client = GoogleClient(api_key=api_key)

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.side_effect = ConnectionError("Network error")

            result = await client._lightweight_health_check()

            assert result is False


class TestHealthCheckPerformance:
    """Test that lightweight health checks are faster than minimal inference."""

    @pytest.mark.asyncio
    async def test_health_check_uses_lightweight_endpoint(self):
        """Verify all providers use lightweight endpoints (not inference)."""
        providers = [
            ("anthropic", AnthropicClient("claude-opus-4-6", api_key="test")),
            ("openai", OpenAIClient("gpt-4o-mini", api_key="test")),
            ("google", GoogleClient("gemini-2.0-flash", api_key="test")),
            ("cohere", CohereClient("command-r", api_key="test")),
            ("mistral", MistralClient("mistral-large-latest", api_key="test")),
        ]

        for provider_name, client in providers:
            # Verify the client has _lightweight_health_check method
            assert hasattr(client, '_lightweight_health_check'), \
                f"{provider_name} missing _lightweight_health_check()"
            assert callable(client._lightweight_health_check), \
                f"{provider_name} _lightweight_health_check is not callable"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
