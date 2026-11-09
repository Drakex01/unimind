"""Google Gemini API Provider Adapter using official google-genai SDK."""

import logging
from typing import AsyncIterator, Optional
from .models import (
    ChatMessage,
    GenerationChunk,
    GenerationRequest,
    GenerationResponse,
    MessageRole,
    ModelCapabilities,
    ModelProvider,
    UsageMetadata,
)

logger = logging.getLogger("unimind.provider.gemini")

SUPPORTED_MODELS = {
    "gemini-3.8-flash": {
        "max_context": 1048576,
        "cost_in": 0.15,
        "cost_out": 0.60,
    },
    "gemini-3.5-flash-lite": {
        "max_context": 1048576,
        "cost_in": 0.075,
        "cost_out": 0.30,
    },
    "gemini-4-argon": {
        "max_context": 1048576,
        "cost_in": 1.25,
        "cost_out": 5.00,
    },
}


class GeminiModelProvider(ModelProvider):
    """Production adapter for Google Gemini foundation models via google-genai SDK."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: str = "gemini-3.8-flash",
    ):
        self._api_key = api_key or ""
        self._model_id = model_id
        self._client = None

        if self._api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self._api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize google-genai Client: {e}")

    def capabilities(self) -> ModelCapabilities:
        meta = SUPPORTED_MODELS.get(
            self._model_id,
            {"max_context": 1048576, "cost_in": 0.15, "cost_out": 0.60},
        )
        return ModelCapabilities(
            provider_name="google-gemini",
            model_id=self._model_id,
            text_generation=True,
            vision=True,
            audio_input=True,
            audio_output=False,
            video=True,
            tool_calling=True,
            structured_output=True,
            streaming=True,
            max_context_tokens=meta["max_context"],
            max_output_tokens=8192,
            cost_per_million_input_tokens=meta["cost_in"],
            cost_per_million_output_tokens=meta["cost_out"],
        )

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        if not self._client:
            raise RuntimeError(
                f"Google Gemini provider for '{self._model_id}' is not configured with an API key."
            )

        # Extract system prompt if present and build prompt content
        system_instruction = None
        user_parts = []
        for msg in request.messages:
            if msg.role == MessageRole.SYSTEM:
                system_instruction = msg.content
            else:
                user_parts.append(msg.content)

        combined_input = "\n\n".join(user_parts) if user_parts else "Hello"

        config_args = {}
        if system_instruction:
            config_args["system_instruction"] = system_instruction
        if request.temperature is not None:
            config_args["temperature"] = request.temperature
        if request.max_tokens is not None:
            config_args["max_output_tokens"] = request.max_tokens

        try:
            interaction = self._client.interactions.create(
                model=self._model_id,
                input=combined_input,
                config=config_args if config_args else None,
            )
            resp_text = interaction.output_text or ""
        except Exception as exc:
            logger.error(f"Gemini API generation failed for {self._model_id}: {exc}")
            raise RuntimeError(f"Gemini API call failed: {exc}") from exc

        # Calculate token approximation & cost
        prompt_tokens = max(1, len(combined_input) // 4)
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
            provider_name="google-gemini",
        )

    async def stream(self, request: GenerationRequest) -> AsyncIterator[GenerationChunk]:
        # For full streaming using client.interactions or client.models.generate_content_stream
        if not self._client:
            raise RuntimeError("Gemini API key is not configured.")

        # Non-blocking generation fallback for stream chunking
        full_resp = await self.generate(request)
        words = full_resp.text.split(" ")
        for word in words:
            yield GenerationChunk(delta_text=word + " ")
        yield GenerationChunk(delta_text="", finish_reason="stop", usage=full_resp.usage)

    async def health_check(self) -> bool:
        if not self._client or not self._api_key:
            return False
        return True
