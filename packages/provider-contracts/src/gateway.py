"""Model Gateway: Capability-aware, policy-constrained routing and execution."""

import asyncio
import logging
from typing import AsyncIterator, Dict, List, Optional
from .models import (
    GenerationChunk,
    GenerationRequest,
    GenerationResponse,
    ModelCapabilities,
    ModelProvider,
)

logger = logging.getLogger("unimind.model_gateway")


class ModelGatewayError(Exception):
    """Base exception for gateway failures."""
    pass


class ModelNotFoundError(ModelGatewayError):
    """Raised when no registered model satisfies the request."""
    pass


class CapabilityMismatchError(ModelGatewayError):
    """Raised when requested capabilities exceed the model's declared limits."""
    pass


class TenantPolicyViolationError(ModelGatewayError):
    """Raised when tenant policy prohibits routing to the model."""
    pass


class ModelGateway:
    """Central gateway routing requests to validated, policy-compliant model providers."""

    def __init__(self):
        self._providers: Dict[str, ModelProvider] = {}
        self._circuit_breakers: Dict[str, int] = {}  # model_id -> consecutive failure count
        self.failure_threshold = 3

    def register_provider(self, provider: ModelProvider) -> None:
        """Register a model provider."""
        caps = provider.capabilities()
        self._providers[caps.model_id] = provider
        logger.info(f"Registered model provider: {caps.provider_name} for model: {caps.model_id}")

    def list_available_models(self) -> List[ModelCapabilities]:
        """List capabilities of all registered models."""
        return [p.capabilities() for p in self._providers.values()]

    def get_provider(self, model_id: str) -> Optional[ModelProvider]:
        return self._providers.get(model_id)

    def validate_capabilities(
        self,
        capabilities: ModelCapabilities,
        request: GenerationRequest,
        required_capabilities: Optional[List[str]] = None,
    ) -> None:
        """Verify that provider satisfies request requirements."""
        if required_capabilities:
            for req in required_capabilities:
                if not getattr(capabilities, req, False):
                    raise CapabilityMismatchError(
                        f"Model '{capabilities.model_id}' does not support required capability: '{req}'"
                    )

        if request.stream and not capabilities.streaming:
            raise CapabilityMismatchError(
                f"Model '{capabilities.model_id}' does not support streaming"
            )

        if request.tools and not capabilities.tool_calling:
            raise CapabilityMismatchError(
                f"Model '{capabilities.model_id}' does not support tool calling"
            )

        if request.response_schema and not capabilities.structured_output:
            raise CapabilityMismatchError(
                f"Model '{capabilities.model_id}' does not support structured output"
            )

    async def generate(
        self,
        request: GenerationRequest,
        required_capabilities: Optional[List[str]] = None,
        allowed_models: Optional[List[str]] = None,
    ) -> GenerationResponse:
        """Route and execute a generation request with policy verification and retries."""
        if allowed_models and request.model_id not in allowed_models:
            raise TenantPolicyViolationError(
                f"Model '{request.model_id}' is not in tenant's allowed models: {allowed_models}"
            )

        provider = self.get_provider(request.model_id)
        if not provider:
            raise ModelNotFoundError(f"Model '{request.model_id}' not found in registered providers.")

        # Circuit breaker check
        failures = self._circuit_breakers.get(request.model_id, 0)
        if failures >= self.failure_threshold:
            raise ModelGatewayError(
                f"Circuit breaker OPEN for model '{request.model_id}' ({failures} consecutive failures)."
            )

        caps = provider.capabilities()
        self.validate_capabilities(caps, request, required_capabilities)

        # Retry with exponential backoff for transient errors
        max_retries = 2
        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                response = await provider.generate(request)
                self._circuit_breakers[request.model_id] = 0  # reset on success
                return response
            except Exception as exc:
                last_exception = exc
                logger.warning(
                    f"Attempt {attempt + 1} failed for model '{request.model_id}': {exc}"
                )
                if attempt < max_retries:
                    await asyncio.sleep(0.1 * (2 ** attempt))

        # Record failure in circuit breaker
        self._circuit_breakers[request.model_id] = failures + 1
        raise ModelGatewayError(
            f"Execution failed for model '{request.model_id}' after {max_retries + 1} attempts: {last_exception}"
        ) from last_exception

    async def stream(
        self,
        request: GenerationRequest,
        required_capabilities: Optional[List[str]] = None,
        allowed_models: Optional[List[str]] = None,
    ) -> AsyncIterator[GenerationChunk]:
        """Stream response chunks from the validated provider."""
        if allowed_models and request.model_id not in allowed_models:
            raise TenantPolicyViolationError(
                f"Model '{request.model_id}' is not in tenant's allowed models: {allowed_models}"
            )

        provider = self.get_provider(request.model_id)
        if not provider:
            raise ModelNotFoundError(f"Model '{request.model_id}' not registered.")

        caps = provider.capabilities()
        self.validate_capabilities(caps, request, required_capabilities)

        async for chunk in provider.stream(request):
            yield chunk
