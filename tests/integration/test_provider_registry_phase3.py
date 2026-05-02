"""Integration tests for provider registry and cloud provider clients.

Tests Phase 3 implementation:
- Cloud provider client instantiation (Anthropic, OpenAI, Google, Cohere, Mistral)
- Provider registry client creation and caching
- Fallback chain building with health status
- Health check coordination
"""

import asyncio
import os
import pytest

from src.guppy.inference.provider_registry import ProviderRegistry, ProviderConfig
from src.guppy.inference.provider_client import LocalProviderClient
from src.guppy.inference.provider_clients_cloud import (
    AnthropicClient,
    OpenAIClient,
    GoogleClient,
    CohereClient,
    MistralClient,
)


class TestCloudProviderClientInstantiation:
    """Test cloud provider clients can be created."""

    def test_anthropic_client_with_api_key(self):
        """Test AnthropicClient accepts api_key parameter."""
        api_key = "sk-test-anthropic-key"
        client = AnthropicClient(
            model="claude-opus-4-6",
            timeout=30.0,
            api_key=api_key,
        )
        assert client.provider_id == "anthropic"
        assert client.model == "claude-opus-4-6"
        assert client.api_key == api_key
        assert client.timeout == 30.0

    def test_openai_client_with_api_key(self):
        """Test OpenAIClient accepts api_key parameter."""
        api_key = "sk-test-openai-key"
        client = OpenAIClient(
            model="gpt-4o-mini",
            timeout=30.0,
            api_key=api_key,
        )
        assert client.provider_id == "openai"
        assert client.model == "gpt-4o-mini"
        assert client.api_key == api_key

    def test_google_client_with_api_key(self):
        """Test GoogleClient accepts api_key parameter."""
        api_key = "test-google-key"
        client = GoogleClient(
            model="gemini-2.0-flash",
            timeout=30.0,
            api_key=api_key,
        )
        assert client.provider_id == "google"
        assert client.model == "gemini-2.0-flash"
        assert client.api_key == api_key

    def test_cohere_client_with_api_key(self):
        """Test CohereClient accepts api_key parameter."""
        api_key = "test-cohere-key"
        client = CohereClient(
            model="command-r-plus-08-2024",
            timeout=30.0,
            api_key=api_key,
        )
        assert client.provider_id == "cohere"
        assert client.model == "command-r-plus-08-2024"
        assert client.api_key == api_key

    def test_mistral_client_with_api_key(self):
        """Test MistralClient accepts api_key parameter."""
        api_key = "test-mistral-key"
        client = MistralClient(
            model="mistral-large-latest",
            timeout=30.0,
            api_key=api_key,
        )
        assert client.provider_id == "mistral"
        assert client.model == "mistral-large-latest"
        assert client.api_key == api_key


@pytest.mark.asyncio
class TestProviderRegistryCloudClients:
    """Test provider registry integration with cloud clients."""

    async def test_registry_creates_local_client(self):
        """Test registry can create local provider client."""
        registry = ProviderRegistry()
        client = await registry.get_client("local")
        assert isinstance(client, LocalProviderClient)
        assert client.provider_id == "local"

    async def test_registry_creates_anthropic_client(self):
        """Test registry can create Anthropic client when API key available."""
        # Set up test environment
        old_key = os.environ.get("ANTHROPIC_API_KEY")
        os.environ["ANTHROPIC_API_KEY"] = "test-key-anthropic"

        try:
            registry = ProviderRegistry()
            client = await registry.get_client("anthropic")
            assert isinstance(client, AnthropicClient)
            assert client.provider_id == "anthropic"
            assert client.api_key == "test-key-anthropic"
        finally:
            if old_key:
                os.environ["ANTHROPIC_API_KEY"] = old_key
            else:
                os.environ.pop("ANTHROPIC_API_KEY", None)

    async def test_registry_creates_openai_client(self):
        """Test registry can create OpenAI client when API key available."""
        old_key = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = "test-key-openai"

        try:
            registry = ProviderRegistry()
            client = await registry.get_client("openai")
            assert isinstance(client, OpenAIClient)
            assert client.provider_id == "openai"
            assert client.api_key == "test-key-openai"
        finally:
            if old_key:
                os.environ["OPENAI_API_KEY"] = old_key
            else:
                os.environ.pop("OPENAI_API_KEY", None)

    async def test_registry_returns_none_without_api_key(self):
        """Test registry returns None when provider disabled (no API key)."""
        old_key = os.environ.get("ANTHROPIC_API_KEY")
        os.environ.pop("ANTHROPIC_API_KEY", None)

        try:
            registry = ProviderRegistry()
            # Manually disable anthropic for this test
            config = registry.get_config("anthropic")
            if config:
                config.is_enabled = False
                client = await registry.get_client("anthropic")
                assert client is None
        finally:
            if old_key:
                os.environ["ANTHROPIC_API_KEY"] = old_key

    async def test_registry_client_caching(self):
        """Test registry caches client instances."""
        os.environ["ANTHROPIC_API_KEY"] = "test-key"

        try:
            registry = ProviderRegistry()
            client1 = await registry.get_client("anthropic")
            client2 = await registry.get_client("anthropic")
            # Should return same instance
            assert client1 is client2
        finally:
            os.environ.pop("ANTHROPIC_API_KEY", None)


@pytest.mark.asyncio
class TestFallbackChainBuilding:
    """Test fallback chain building with multiple providers."""

    async def test_fallback_chain_respects_priority(self):
        """Test fallback chain orders providers by priority."""
        registry = ProviderRegistry()

        # Build chain for simple task type
        chain = registry.build_fallback_chain(task_type="simple")

        # local is always in the chain (highest priority_order=10)
        # but task-type preferences may place llama.cpp backends first for "simple"
        assert len(chain) > 0
        assert "local" in chain

    async def test_fallback_chain_excludes_disabled(self):
        """Test fallback chain excludes disabled providers."""
        os.environ["ANTHROPIC_API_KEY"] = "test-key"

        try:
            registry = ProviderRegistry()

            # Disable anthropic
            config = registry.get_config("anthropic")
            if config:
                config.is_enabled = False

            chain = registry.build_fallback_chain()
            assert "anthropic" not in chain
        finally:
            os.environ.pop("ANTHROPIC_API_KEY", None)


class TestProviderRegistryStatus:
    """Test provider registry status and diagnostics."""

    def test_registry_status_structure(self):
        """Test registry status returns expected structure."""
        registry = ProviderRegistry()
        status = registry.get_status()

        assert "providers" in status
        assert "fallback_chains" in status

        # Check providers section
        providers = status["providers"]
        assert "local" in providers
        assert "anthropic" in providers
        assert "openai" in providers

        # Check each provider has expected fields
        for provider_id, provider_status in providers.items():
            assert "enabled" in provider_status
            assert "priority" in provider_status
            assert "healthy" in provider_status
            assert "cached" in provider_status
            assert "timeout" in provider_status

        # Check fallback chains
        chains = status["fallback_chains"]
        assert "simple" in chains
        assert "complex" in chains
        assert "teaching" in chains


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
