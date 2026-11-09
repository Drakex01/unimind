"""Provider contracts and gateway package."""

from .models import (
    ChatMessage,
    GenerationChunk,
    GenerationRequest,
    GenerationResponse,
    MessageRole,
    ModelCapabilities,
    ModelProvider,
    ToolCall,
    UsageMetadata,
)
from .mock_provider import MockModelProvider
from .gateway import (
    CapabilityMismatchError,
    ModelGateway,
    ModelGatewayError,
    ModelNotFoundError,
    TenantPolicyViolationError,
)

__all__ = [
    "ChatMessage",
    "GenerationChunk",
    "GenerationRequest",
    "GenerationResponse",
    "MessageRole",
    "ModelCapabilities",
    "ModelProvider",
    "ToolCall",
    "UsageMetadata",
    "MockModelProvider",
    "CapabilityMismatchError",
    "ModelGateway",
    "ModelGatewayError",
    "ModelNotFoundError",
    "TenantPolicyViolationError",
]
