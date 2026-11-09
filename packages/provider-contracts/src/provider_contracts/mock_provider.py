"""Deterministic Mock Model Provider for Testing and Local Verification."""

import asyncio
from typing import AsyncIterator, Optional
from .models import (
    ChatMessage,
    GenerationChunk,
    GenerationRequest,
    GenerationResponse,
    ModelCapabilities,
    ModelProvider,
    UsageMetadata,
)


class MockModelProvider(ModelProvider):
    """Deterministic model provider used for unit testing, CI, and local dev."""

    def __init__(
        self,
        provider_name: str = "mock-provider",
        model_id: str = "mock-model-v1",
        default_response_text: Optional[str] = None,
        should_fail_health: bool = False,
    ):
        self._provider_name = provider_name
        self._model_id = model_id
        self._default_response_text = default_response_text
        self._should_fail_health = should_fail_health
        self.invocation_count = 0

    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            provider_name=self._provider_name,
            model_id=self._model_id,
            text_generation=True,
            vision=True,
            audio_input=False,
            audio_output=False,
            video=False,
            tool_calling=True,
            structured_output=True,
            streaming=True,
            max_context_tokens=32768,
            max_output_tokens=4096,
            cost_per_million_input_tokens=0.50,
            cost_per_million_output_tokens=1.50,
        )

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        self.invocation_count += 1
        prompt_len = sum(len(m.content) for m in request.messages)
        prompt_tokens = max(1, prompt_len // 4)

        if self._default_response_text:
            resp_text = self._default_response_text
        else:
            last_msg = request.messages[-1].content if request.messages else "empty"
            resp_text = f"[MockResponse from {self._model_id}] Processed: {last_msg[:80]}"

        completion_tokens = max(1, len(resp_text) // 4)
        caps = self.capabilities()
        cost = (
            (prompt_tokens * caps.cost_per_million_input_tokens)
            + (completion_tokens * caps.cost_per_million_output_tokens)
        ) / 1_000_000

        return GenerationResponse(
            text=resp_text,
            finish_reason="stop",
            usage=UsageMetadata(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                estimated_cost_usd=round(cost, 6),
            ),
            model_id=self._model_id,
            provider_name=self._provider_name,
        )

    async def stream(self, request: GenerationRequest) -> AsyncIterator[GenerationChunk]:
        self.invocation_count += 1
        words = ["UniMind", "mock", "stream", "token", "delivery", "successful."]
        for word in words:
            await asyncio.sleep(0.01)
            yield GenerationChunk(delta_text=word + " ")
        yield GenerationChunk(delta_text="", finish_reason="stop")

    async def health_check(self) -> bool:
        return not self._should_fail_health
