"""Unit Tests for Capability-Aware Model Gateway."""

import pytest
from provider_contracts.gateway import (
    CapabilityMismatchError,
    ModelGateway,
    ModelGatewayError,
    ModelNotFoundError,
    TenantPolicyViolationError,
)
from provider_contracts.mock_provider import MockModelProvider
from provider_contracts.models import (
    ChatMessage,
    GenerationRequest,
    MessageRole,
)


@pytest.fixture
def gateway():
    gw = ModelGateway()
    mock_p = MockModelProvider(provider_name="mock-corp", model_id="mock-v1")
    gw.register_provider(mock_p)
    return gw


@pytest.mark.asyncio
async def test_successful_generation_and_cost_accounting(gateway: ModelGateway):
    req = GenerationRequest(
        model_id="mock-v1",
        messages=[
            ChatMessage(role=MessageRole.USER, content="Analyze our Kubernetes firewall rules.")
        ],
    )
    resp = await gateway.generate(req)
    assert resp.model_id == "mock-v1"
    assert resp.provider_name == "mock-corp"
    assert "MockResponse from mock-v1" in resp.text
    assert resp.usage.prompt_tokens > 0
    assert resp.usage.completion_tokens > 0
    assert resp.usage.estimated_cost_usd > 0.0


@pytest.mark.asyncio
async def test_capability_mismatch_raises_error(gateway: ModelGateway):
    req = GenerationRequest(
        model_id="mock-v1",
        messages=[ChatMessage(role=MessageRole.USER, content="Audio transcription task")],
    )
    with pytest.raises(CapabilityMismatchError) as exc:
        await gateway.generate(req, required_capabilities=["audio_input"])
    assert "does not support required capability: 'audio_input'" in str(exc.value)


@pytest.mark.asyncio
async def test_tenant_policy_violation_raises_error(gateway: ModelGateway):
    req = GenerationRequest(
        model_id="mock-v1",
        messages=[ChatMessage(role=MessageRole.USER, content="Hello")],
    )
    with pytest.raises(TenantPolicyViolationError) as exc:
        await gateway.generate(req, allowed_models=["approved-enterprise-model"])
    assert "not in tenant's allowed models" in str(exc.value)


@pytest.mark.asyncio
async def test_unregistered_model_raises_error(gateway: ModelGateway):
    req = GenerationRequest(
        model_id="non-existent-model",
        messages=[ChatMessage(role=MessageRole.USER, content="Hello")],
    )
    with pytest.raises(ModelNotFoundError):
        await gateway.generate(req)


@pytest.mark.asyncio
async def test_streaming_generation(gateway: ModelGateway):
    req = GenerationRequest(
        model_id="mock-v1",
        messages=[ChatMessage(role=MessageRole.USER, content="Stream this")],
        stream=True,
    )
    chunks = []
    async for chunk in gateway.stream(req):
        chunks.append(chunk.delta_text)
    full_text = "".join(chunks)
    assert "UniMind mock stream" in full_text
