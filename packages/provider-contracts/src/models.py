"""Foundation Model Contracts and Data Types for UniMind."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional
from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: Dict[str, Any]


class ChatMessage(BaseModel):
    role: MessageRole
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None


class ModelCapabilities(BaseModel):
    provider_name: str
    model_id: str
    text_generation: bool = True
    vision: bool = False
    audio_input: bool = False
    audio_output: bool = False
    video: bool = False
    tool_calling: bool = False
    structured_output: bool = False
    streaming: bool = True
    max_context_tokens: int = 8192
    max_output_tokens: int = 4096
    cost_per_million_input_tokens: float = 0.0
    cost_per_million_output_tokens: float = 0.0


class UsageMetadata(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


class GenerationRequest(BaseModel):
    model_id: str
    messages: List[ChatMessage]
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    stop_sequences: Optional[List[str]] = None
    tools: Optional[List[Dict[str, Any]]] = None
    response_schema: Optional[Dict[str, Any]] = None
    stream: bool = False
    tenant_id: Optional[str] = None
    correlation_id: Optional[str] = None


class GenerationChunk(BaseModel):
    delta_text: str
    finish_reason: Optional[str] = None
    usage: Optional[UsageMetadata] = None


class GenerationResponse(BaseModel):
    text: str
    finish_reason: str = "stop"
    usage: UsageMetadata = Field(default_factory=UsageMetadata)
    tool_calls: Optional[List[ToolCall]] = None
    model_id: str
    provider_name: str


class ModelProvider(ABC):
    """Abstract interface for all model provider integrations."""

    @abstractmethod
    def capabilities(self) -> ModelCapabilities:
        """Return provider capabilities and limits."""
        raise NotImplementedError

    @abstractmethod
    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Execute a non-streaming completion."""
        raise NotImplementedError

    @abstractmethod
    async def stream(self, request: GenerationRequest) -> AsyncIterator[GenerationChunk]:
        """Execute a streaming completion."""
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> bool:
        """Check provider connectivity and health."""
        raise NotImplementedError
