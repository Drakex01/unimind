"""Unit Tests for Google Gemini Model Provider Adapter."""

import pytest
from provider_contracts.gemini_provider import GeminiModelProvider
from provider_contracts.models import (
    ChatMessage,
    GenerationRequest,
    MessageRole,
)


def test_gemini_provider_capabilities():
    provider = GeminiModelProvider(api_key="", model_id="gemini-3.8-flash")
    caps = provider.capabilities()

    assert caps.provider_name == "google-gemini"
    assert caps.model_id == "gemini-3.8-flash"
    assert caps.text_generation is True
    assert caps.vision is True
    assert caps.video is True
    assert caps.streaming is True
    assert caps.tool_calling is True
    assert caps.max_context_tokens == 1048576


@pytest.mark.asyncio
async def test_gemini_unconfigured_api_key_health_and_execution():
    provider = GeminiModelProvider(api_key="", model_id="gemini-3.8-flash")
    is_healthy = await provider.health_check()
    assert is_healthy is False

    req = GenerationRequest(
        model_id="gemini-3.8-flash",
        messages=[ChatMessage(role=MessageRole.USER, content="Hello Gemini")],
    )
    with pytest.raises(RuntimeError) as exc:
        await provider.generate(req)
    assert "not configured with an API key" in str(exc.value)
