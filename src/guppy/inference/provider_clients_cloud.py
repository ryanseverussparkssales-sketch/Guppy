"""Cloud provider client implementations for inference.

Subclasses of CloudProviderClient for:
    - Anthropic (Claude models)
    - OpenAI (GPT models)
    - Google (Gemini models)
    - Cohere (Command models)
    - Mistral (Mistral models)

Each provider implements:
    - infer() - Execute inference via provider's API
    - health_check() - Check provider health
    - list_models() - List available models
    - estimate_cost() - Estimate inference cost
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from .provider_client import CloudProviderClient, InferenceMetadata

logger = logging.getLogger(__name__)


class AnthropicClient(CloudProviderClient):
    """Anthropic Claude provider client.

    Supports Claude models via Anthropic API.
    Docs: https://docs.anthropic.com/
    """

    def __init__(self, model: str = "claude-opus-4-6", timeout: float = 30.0, api_key: Optional[str] = None):
        """Initialize Anthropic client.

        Args:
            model: Claude model ID (default: claude-opus-4-6)
            timeout: Request timeout in seconds
            api_key: API key (optional; falls back to ANTHROPIC_API_KEY env var)
        """
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "").strip()
        super().__init__(
            provider_id="anthropic",
            model=model,
            api_key=api_key,
            timeout=timeout,
        )

        # Anthropic API configuration
        self.api_url = "https://api.anthropic.com/v1/messages"
        self.api_version = "2024-06-15"

        # Token counting and cost
        self.cost_per_1k_input = 0.003  # Opus 4.6 pricing (approx)
        self.cost_per_1k_output = 0.015

    async def infer(
        self,
        prompt: str,
        system_prompt: str = "",
        task_type: str = "simple",
        max_tokens: int = 4096,
        **kwargs,
    ) -> Tuple[str, InferenceMetadata]:
        """Execute inference via Anthropic API.

        Args:
            prompt: User message
            system_prompt: System context
            task_type: Task classification
            max_tokens: Max output tokens
            **kwargs: Additional inference options

        Returns:
            (response_text, InferenceMetadata)

        Raises:
            RuntimeError: If API call fails
        """
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")

        start_time = datetime.utcnow()

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "x-api-key": self.api_key,
                    "anthropic-version": self.api_version,
                    "content-type": "application/json",
                }

                payload = {
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": prompt}],
                }

                async with session.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as resp:
                    if resp.status != 200:
                        error_data = await resp.text()
                        raise RuntimeError(f"Anthropic API error {resp.status}: {error_data}")

                    data = await resp.json()

                    # Extract response
                    response_text = data["content"][0]["text"]
                    input_tokens = data.get("usage", {}).get("input_tokens", 0)
                    output_tokens = data.get("usage", {}).get("output_tokens", 0)

                    # Calculate cost
                    input_cost = (input_tokens / 1000) * self.cost_per_1k_input
                    output_cost = (output_tokens / 1000) * self.cost_per_1k_output
                    total_cost = input_cost + output_cost

                    latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

                    metadata = InferenceMetadata(
                        provider="anthropic",
                        model=self.model,
                        prompt_tokens=input_tokens,
                        completion_tokens=output_tokens,
                        latency_ms=latency_ms,
                        cost=total_cost,
                        timestamp=start_time,
                        success=True,
                    )

                    logger.info(
                        f"[ANTHROPIC] Inference succeeded "
                        f"({input_tokens} input, {output_tokens} output, "
                        f"{latency_ms:.0f}ms, ${total_cost:.6f})"
                    )

                    return response_text, metadata

        except asyncio.TimeoutError:
            raise RuntimeError(f"Anthropic API timeout after {self.timeout}s")
        except Exception as e:
            logger.error(f"[ANTHROPIC] Inference failed: {e}")
            raise RuntimeError(f"Anthropic inference failed: {e}")

    async def _lightweight_health_check(self) -> bool:
        """Check Anthropic API health via lightweight OPTIONS request.

        Phase 4a: Uses OPTIONS request instead of minimal inference.
        - No token consumption
        - Expected latency: 50-100ms (was 500-2000ms with inference)
        - Free/included in API quota
        """
        if not self.api_key:
            return False

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "x-api-key": self.api_key,
                    "anthropic-version": self.api_version,
                }

                # OPTIONS request to check API connectivity
                # Returns 405 Method Not Allowed or other status codes indicating server is reachable
                async with session.options(
                    self.api_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=3.0),
                ) as resp:
                    # 200, 401, 405 all indicate API is reachable
                    # 401 = invalid key but API exists
                    # 405 = method not allowed but API exists
                    return resp.status in (200, 401, 405)

        except asyncio.TimeoutError:
            logger.debug(f"[ANTHROPIC] Health check timeout")
            return False
        except Exception as e:
            logger.debug(f"[ANTHROPIC] Health check failed: {e}")
            return False

    async def list_models(self) -> List[str]:
        """List available Claude models."""
        return [
            "claude-opus-4-6",
            "claude-sonnet-4-6",
            "claude-haiku-4-5-20251001",
            "claude-3-5-sonnet-20241022",
            "claude-3-opus-20250219",
        ]


class OpenAIClient(CloudProviderClient):
    """OpenAI GPT provider client.

    Supports GPT models via OpenAI API.
    Docs: https://platform.openai.com/docs/
    """

    def __init__(self, model: str = "gpt-4o-mini", timeout: float = 30.0, api_key: Optional[str] = None):
        """Initialize OpenAI client.

        Args:
            model: GPT model ID (default: gpt-4o-mini)
            timeout: Request timeout in seconds
            api_key: API key (optional; falls back to OPENAI_API_KEY env var)
        """
        api_key = api_key or os.environ.get("OPENAI_API_KEY", "").strip()
        super().__init__(
            provider_id="openai",
            model=model,
            api_key=api_key,
            timeout=timeout,
        )

        # OpenAI API configuration
        self.api_url = "https://api.openai.com/v1/chat/completions"

        # Token pricing (approximate for gpt-4o-mini)
        self.cost_per_1k_input = 0.00015
        self.cost_per_1k_output = 0.0006

    async def infer(
        self,
        prompt: str,
        system_prompt: str = "",
        task_type: str = "simple",
        max_tokens: int = 4096,
        **kwargs,
    ) -> Tuple[str, InferenceMetadata]:
        """Execute inference via OpenAI API."""
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")

        start_time = datetime.utcnow()

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }

                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                payload = {
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                }

                async with session.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as resp:
                    if resp.status != 200:
                        error_data = await resp.text()
                        raise RuntimeError(f"OpenAI API error {resp.status}: {error_data}")

                    data = await resp.json()

                    # Extract response
                    response_text = data["choices"][0]["message"]["content"]
                    input_tokens = data["usage"]["prompt_tokens"]
                    output_tokens = data["usage"]["completion_tokens"]

                    # Calculate cost
                    input_cost = (input_tokens / 1000) * self.cost_per_1k_input
                    output_cost = (output_tokens / 1000) * self.cost_per_1k_output
                    total_cost = input_cost + output_cost

                    latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

                    metadata = InferenceMetadata(
                        provider="openai",
                        model=self.model,
                        prompt_tokens=input_tokens,
                        completion_tokens=output_tokens,
                        latency_ms=latency_ms,
                        cost=total_cost,
                        timestamp=start_time,
                        success=True,
                    )

                    logger.info(
                        f"[OPENAI] Inference succeeded "
                        f"({input_tokens} input, {output_tokens} output, "
                        f"{latency_ms:.0f}ms, ${total_cost:.6f})"
                    )

                    return response_text, metadata

        except asyncio.TimeoutError:
            raise RuntimeError(f"OpenAI API timeout after {self.timeout}s")
        except Exception as e:
            logger.error(f"[OPENAI] Inference failed: {e}")
            raise RuntimeError(f"OpenAI inference failed: {e}")

    async def _lightweight_health_check(self) -> bool:
        """Check OpenAI API health via /models endpoint.

        Phase 4a: Uses GET /v1/models (model listing) instead of minimal inference.
        - No token consumption
        - Expected latency: 30-80ms (was 500-2000ms with inference)
        - Free/included in API quota
        """
        if not self.api_key:
            return False

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }

                # GET /v1/models to check API connectivity
                # Lists available models, fast and free
                async with session.get(
                    "https://api.openai.com/v1/models",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=3.0),
                ) as resp:
                    return resp.status == 200

        except asyncio.TimeoutError:
            logger.debug(f"[OPENAI] Health check timeout")
            return False
        except Exception as e:
            logger.debug(f"[OPENAI] Health check failed: {e}")
            return False

    async def list_models(self) -> List[str]:
        """List available GPT models."""
        return [
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
        ]


class GoogleClient(CloudProviderClient):
    """Google Gemini provider client.

    Supports Gemini models via Google AI API.
    Docs: https://ai.google.dev/
    """

    def __init__(self, model: str = "gemini-2.0-flash", timeout: float = 30.0, api_key: Optional[str] = None):
        """Initialize Google client.

        Args:
            model: Gemini model ID (default: gemini-2.0-flash)
            timeout: Request timeout in seconds
            api_key: API key (optional; falls back to GOOGLE_API_KEY env var)
        """
        api_key = api_key or os.environ.get("GOOGLE_API_KEY", "").strip()
        super().__init__(
            provider_id="google",
            model=model,
            api_key=api_key,
            timeout=timeout,
        )

        # Google AI API configuration
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

        # Token pricing (approximate for Gemini 2.0 Flash)
        self.cost_per_1k_input = 0.0000375
        self.cost_per_1k_output = 0.00015

    async def infer(
        self,
        prompt: str,
        system_prompt: str = "",
        task_type: str = "simple",
        max_tokens: int = 4096,
        **kwargs,
    ) -> Tuple[str, InferenceMetadata]:
        """Execute inference via Google Gemini API."""
        if not self.api_key:
            raise RuntimeError("GOOGLE_API_KEY not configured")

        start_time = datetime.utcnow()

        try:
            async with aiohttp.ClientSession() as session:
                # Google uses query parameter for API key
                params = {"key": self.api_key}

                contents = []
                if system_prompt:
                    contents.append({"role": "user", "parts": [{"text": system_prompt}]})
                    contents.append(
                        {
                            "role": "model",
                            "parts": [{"text": "I understand. I'll follow these instructions."}],
                        }
                    )
                contents.append({"role": "user", "parts": [{"text": prompt}]})

                payload = {
                    "contents": contents,
                    "generationConfig": {"maxOutputTokens": max_tokens},
                }

                async with session.post(
                    self.api_url,
                    json=payload,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as resp:
                    if resp.status != 200:
                        error_data = await resp.text()
                        raise RuntimeError(f"Google API error {resp.status}: {error_data}")

                    data = await resp.json()

                    # Extract response
                    response_text = data["candidates"][0]["content"]["parts"][0]["text"]

                    # Google doesn't always return token counts; estimate based on character count
                    input_tokens = len(prompt) // 4  # Rough estimate
                    output_tokens = len(response_text) // 4

                    # Calculate cost
                    input_cost = (input_tokens / 1000) * self.cost_per_1k_input
                    output_cost = (output_tokens / 1000) * self.cost_per_1k_output
                    total_cost = input_cost + output_cost

                    latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

                    metadata = InferenceMetadata(
                        provider="google",
                        model=self.model,
                        prompt_tokens=input_tokens,
                        completion_tokens=output_tokens,
                        latency_ms=latency_ms,
                        cost=total_cost,
                        timestamp=start_time,
                        success=True,
                    )

                    logger.info(
                        f"[GOOGLE] Inference succeeded "
                        f"({input_tokens} input est., {output_tokens} output est., "
                        f"{latency_ms:.0f}ms, ${total_cost:.6f})"
                    )

                    return response_text, metadata

        except asyncio.TimeoutError:
            raise RuntimeError(f"Google API timeout after {self.timeout}s")
        except Exception as e:
            logger.error(f"[GOOGLE] Inference failed: {e}")
            raise RuntimeError(f"Google inference failed: {e}")

    async def _lightweight_health_check(self) -> bool:
        """Check Google Gemini API health via /models endpoint.

        Phase 4a: Uses GET /v1beta/models (model listing) instead of minimal inference.
        - No token consumption
        - Expected latency: 50-100ms (was 500-2000ms with inference)
        - Free/included in API quota
        """
        if not self.api_key:
            return False

        try:
            async with aiohttp.ClientSession() as session:
                params = {"key": self.api_key}

                # GET /v1beta/models to check API connectivity
                # Lists available models, fast and free
                async with session.get(
                    "https://generativelanguage.googleapis.com/v1beta/models",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=3.0),
                ) as resp:
                    return resp.status == 200

        except asyncio.TimeoutError:
            logger.debug(f"[GOOGLE] Health check timeout")
            return False
        except Exception as e:
            logger.debug(f"[GOOGLE] Health check failed: {e}")
            return False

    async def list_models(self) -> List[str]:
        """List available Gemini models."""
        return [
            "gemini-2.0-flash",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-pro",
        ]


class CohereClient(CloudProviderClient):
    """Cohere provider client.

    Supports Cohere Command models via Cohere API.
    Docs: https://docs.cohere.ai/
    """

    def __init__(self, model: str = "command-r-plus-08-2024", timeout: float = 30.0, api_key: Optional[str] = None):
        """Initialize Cohere client.

        Args:
            model: Cohere model ID (default: command-r-plus-08-2024)
            timeout: Request timeout in seconds
            api_key: API key (optional; falls back to COHERE_API_KEY env var)
        """
        api_key = api_key or os.environ.get("COHERE_API_KEY", "").strip()
        super().__init__(
            provider_id="cohere",
            model=model,
            api_key=api_key,
            timeout=timeout,
        )

        # Cohere API configuration
        self.api_url = "https://api.cohere.ai/v2/chat"

        # Token pricing (approximate for Command R Plus)
        self.cost_per_1k_input = 0.001
        self.cost_per_1k_output = 0.002

    async def infer(
        self,
        prompt: str,
        system_prompt: str = "",
        task_type: str = "simple",
        max_tokens: int = 4096,
        **kwargs,
    ) -> Tuple[str, InferenceMetadata]:
        """Execute inference via Cohere API."""
        if not self.api_key:
            raise RuntimeError("COHERE_API_KEY not configured")

        start_time = datetime.utcnow()

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }

                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                payload = {
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                }

                async with session.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as resp:
                    if resp.status != 200:
                        error_data = await resp.text()
                        raise RuntimeError(f"Cohere API error {resp.status}: {error_data}")

                    data = await resp.json()

                    # Extract response
                    response_text = data["message"]["content"][0]["text"]

                    # Cohere returns token counts
                    input_tokens = data.get("usage", {}).get("input_tokens", 0)
                    output_tokens = data.get("usage", {}).get("output_tokens", 0)

                    # Calculate cost
                    input_cost = (input_tokens / 1000) * self.cost_per_1k_input
                    output_cost = (output_tokens / 1000) * self.cost_per_1k_output
                    total_cost = input_cost + output_cost

                    latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

                    metadata = InferenceMetadata(
                        provider="cohere",
                        model=self.model,
                        prompt_tokens=input_tokens,
                        completion_tokens=output_tokens,
                        latency_ms=latency_ms,
                        cost=total_cost,
                        timestamp=start_time,
                        success=True,
                    )

                    logger.info(
                        f"[COHERE] Inference succeeded "
                        f"({input_tokens} input, {output_tokens} output, "
                        f"{latency_ms:.0f}ms, ${total_cost:.6f})"
                    )

                    return response_text, metadata

        except asyncio.TimeoutError:
            raise RuntimeError(f"Cohere API timeout after {self.timeout}s")
        except Exception as e:
            logger.error(f"[COHERE] Inference failed: {e}")
            raise RuntimeError(f"Cohere inference failed: {e}")

    async def _lightweight_health_check(self) -> bool:
        """Check Cohere API health via HEAD request.

        Phase 4a: Uses HEAD /v2/chat (connectivity check) instead of minimal inference.
        - No token consumption
        - Expected latency: 40-90ms (was 500-2000ms with inference)
        - Free/included in API quota
        """
        if not self.api_key:
            return False

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }

                # HEAD request to check API connectivity
                # Returns 200 or error status indicating server is reachable
                async with session.head(
                    self.api_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=3.0),
                ) as resp:
                    # 200 = OK, 400 = bad request but API exists, 401 = auth error but API exists
                    return resp.status in (200, 400, 401)

        except asyncio.TimeoutError:
            logger.debug(f"[COHERE] Health check timeout")
            return False
        except Exception as e:
            logger.debug(f"[COHERE] Health check failed: {e}")
            return False

    async def list_models(self) -> List[str]:
        """List available Cohere models."""
        return [
            "command-r-plus-08-2024",
            "command-r-plus",
            "command-r",
            "command",
            "command-light",
            "aya-23-35b",
            "aya-23-8b",
        ]


class MistralClient(CloudProviderClient):
    """Mistral provider client.

    Supports Mistral models via Mistral API.
    Docs: https://docs.mistral.ai/
    """

    def __init__(self, model: str = "mistral-large-latest", timeout: float = 30.0, api_key: Optional[str] = None):
        """Initialize Mistral client.

        Args:
            model: Mistral model ID (default: mistral-large-latest)
            timeout: Request timeout in seconds
            api_key: API key (optional; falls back to MISTRAL_API_KEY env var)
        """
        api_key = api_key or os.environ.get("MISTRAL_API_KEY", "").strip()
        super().__init__(
            provider_id="mistral",
            model=model,
            api_key=api_key,
            timeout=timeout,
        )

        # Mistral API configuration
        self.api_url = "https://api.mistral.ai/v1/chat/completions"

        # Token pricing (approximate for Mistral Large)
        self.cost_per_1k_input = 0.0002
        self.cost_per_1k_output = 0.0006

    async def infer(
        self,
        prompt: str,
        system_prompt: str = "",
        task_type: str = "simple",
        max_tokens: int = 4096,
        **kwargs,
    ) -> Tuple[str, InferenceMetadata]:
        """Execute inference via Mistral API."""
        if not self.api_key:
            raise RuntimeError("MISTRAL_API_KEY not configured")

        start_time = datetime.utcnow()

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }

                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                payload = {
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                }

                async with session.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as resp:
                    if resp.status != 200:
                        error_data = await resp.text()
                        raise RuntimeError(f"Mistral API error {resp.status}: {error_data}")

                    data = await resp.json()

                    # Extract response
                    response_text = data["choices"][0]["message"]["content"]
                    input_tokens = data["usage"]["prompt_tokens"]
                    output_tokens = data["usage"]["completion_tokens"]

                    # Calculate cost
                    input_cost = (input_tokens / 1000) * self.cost_per_1k_input
                    output_cost = (output_tokens / 1000) * self.cost_per_1k_output
                    total_cost = input_cost + output_cost

                    latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

                    metadata = InferenceMetadata(
                        provider="mistral",
                        model=self.model,
                        prompt_tokens=input_tokens,
                        completion_tokens=output_tokens,
                        latency_ms=latency_ms,
                        cost=total_cost,
                        timestamp=start_time,
                        success=True,
                    )

                    logger.info(
                        f"[MISTRAL] Inference succeeded "
                        f"({input_tokens} input, {output_tokens} output, "
                        f"{latency_ms:.0f}ms, ${total_cost:.6f})"
                    )

                    return response_text, metadata

        except asyncio.TimeoutError:
            raise RuntimeError(f"Mistral API timeout after {self.timeout}s")
        except Exception as e:
            logger.error(f"[MISTRAL] Inference failed: {e}")
            raise RuntimeError(f"Mistral inference failed: {e}")

    async def _lightweight_health_check(self) -> bool:
        """Check Mistral API health via /models endpoint.

        Phase 4a: Uses GET /v1/models (model listing) instead of minimal inference.
        - No token consumption
        - Expected latency: 30-80ms (was 500-2000ms with inference)
        - Free/included in API quota
        """
        if not self.api_key:
            return False

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }

                # GET /v1/models to check API connectivity
                # Lists available models, fast and free
                async with session.get(
                    "https://api.mistral.ai/v1/models",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=3.0),
                ) as resp:
                    return resp.status == 200

        except asyncio.TimeoutError:
            logger.debug(f"[MISTRAL] Health check timeout")
            return False
        except Exception as e:
            logger.debug(f"[MISTRAL] Health check failed: {e}")
            return False

    async def list_models(self) -> List[str]:
        """List available Mistral models."""
        return [
            "mistral-large-latest",
            "mistral-medium-latest",
            "mistral-small-latest",
            "codestral-latest",
            "nemo-2407",
            "pixtral-12b-2409",
            "mixtral-8x22b-v0.1",
        ]
