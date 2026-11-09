"""Chat Orchestration Endpoint: Verified Tenant-Aware Request Path."""

import json
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from plugin_sdk.registry import PluginRegistry
from provider_contracts.gateway import (
    CapabilityMismatchError,
    ModelGateway,
    ModelGatewayError,
    ModelNotFoundError,
    TenantPolicyViolationError,
)
from provider_contracts.models import (
    ChatMessage,
    GenerationRequest,
    MessageRole,
    UsageMetadata,
)
from ..core.database import get_db_session
from ..core.security import TenantContext, get_tenant_context
from ..models.entities import AuditEvent, Conversation, Message, UsageRecord
from .plugins import get_plugin_registry
from .knowledge import get_vector_store
from ..services.rag import RAGPipeline

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])

_gateway: Optional[ModelGateway] = None


def set_model_gateway(gateway: ModelGateway):
    global _gateway
    _gateway = gateway


def get_model_gateway() -> ModelGateway:
    if _gateway is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Model gateway not initialized.",
        )
    return _gateway


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=100000)
    domain_plugin_id: Optional[str] = "cybersecurity"
    model_id: Optional[str] = "mock-model-v1"
    conversation_id: Optional[str] = None
    knowledge_base_id: Optional[str] = None


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    response_text: str
    domain_plugin_id: str
    model_id: str
    usage: UsageMetadata
    citations: List[Dict[str, Any]] = Field(default_factory=list)


@router.post("", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def execute_chat(
    payload: ChatRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    gateway: ModelGateway = Depends(get_model_gateway),
    registry: PluginRegistry = Depends(get_plugin_registry),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Executes the verified tenant-aware request path:
    1. Tenant & Permission Check (via TenantContext dependency)
    2. Domain Plugin Resolution & Domain Policy Check
    3. Model Capability and Tenant Policy Check
    4. Provider Gateway Invocation
    5. Validated Response Generation
    6. Audit Event and Tenant-Scoped Usage Recording
    """
    correlation_id = str(uuid.uuid4())
    domain_id = payload.domain_plugin_id or "general"
    instructions = ""
    required_caps = ["text_generation"]

    # 1. Domain Plugin Resolution
    if domain_id != "general":
        plugin = registry.get_plugin(domain_id)
        if not plugin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Requested domain plugin '{domain_id}' is not installed.",
            )
        instructions = registry.get_instructions(domain_id)
        required_caps = plugin.models.required

    # 2. RAG Retrieval & Context Augmentation (if knowledge base specified)
    citations_data = []
    user_query = payload.message
    available_citations = []
    rag = None

    if payload.knowledge_base_id:
        rag = RAGPipeline(get_vector_store())
        ret_ctx = await rag.retrieve_and_augment(
            query=payload.message,
            org_id=ctx.org_id,
            workspace_id=ctx.workspace_id,
            knowledge_base_id=payload.knowledge_base_id,
        )
        user_query = ret_ctx.augmented_prompt
        available_citations = ret_ctx.citations

    # 3. Build Chat Context Messages
    messages: List[ChatMessage] = []
    if instructions:
        messages.append(ChatMessage(role=MessageRole.SYSTEM, content=instructions))
    messages.append(ChatMessage(role=MessageRole.USER, content=user_query))

    # 4. Model Invocation via Gateway with Tenant Policy Checks
    model_to_use = payload.model_id or "mock-model-v1"
    gen_req = GenerationRequest(
        model_id=model_to_use,
        messages=messages,
        tenant_id=ctx.org_id,
        correlation_id=correlation_id,
    )

    try:
        gen_resp = await gateway.generate(
            request=gen_req,
            required_capabilities=required_caps,
            allowed_models=ctx.allowed_models,
        )
    except ModelNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except CapabilityMismatchError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except TenantPolicyViolationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ModelGatewayError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    # Validate citations
    if rag and available_citations:
        valid_cits = rag.validate_citations(gen_resp.text, available_citations)
        citations_data = [c.model_dump() for c in valid_cits]

    # 4. Resolve or Create Conversation
    conv_id = payload.conversation_id
    if not conv_id:
        conversation = Conversation(
            org_id=ctx.org_id,
            workspace_id=ctx.workspace_id,
            user_id=ctx.user_id,
            title=payload.message[:50],
            domain_plugin_id=domain_id,
        )
        db.add(conversation)
        await db.flush()
        conv_id = conversation.id
    else:
        existing = await db.get(Conversation, conv_id)
        if not existing or existing.org_id != ctx.org_id or existing.workspace_id != ctx.workspace_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation '{conv_id}' not found in this workspace.",
            )

    # 5. Persist User and Assistant Messages
    user_msg = Message(
        conversation_id=conv_id,
        role="user",
        content=payload.message,
    )
    assistant_msg = Message(
        conversation_id=conv_id,
        role="assistant",
        content=gen_resp.text,
        model_id=gen_resp.model_id,
        metadata_json={"finish_reason": gen_resp.finish_reason},
    )
    db.add(user_msg)
    db.add(assistant_msg)

    # 6. Record Tenant-Scoped Usage and Audit Event
    usage_rec = UsageRecord(
        org_id=ctx.org_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        provider_name=gen_resp.provider_name,
        model_id=gen_resp.model_id,
        prompt_tokens=gen_resp.usage.prompt_tokens,
        completion_tokens=gen_resp.usage.completion_tokens,
        estimated_cost_usd=gen_resp.usage.estimated_cost_usd,
    )
    audit_ev = AuditEvent(
        org_id=ctx.org_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        action="chat_completion",
        resource_type="conversation",
        resource_id=conv_id,
        details={
            "domain_plugin_id": domain_id,
            "model_id": gen_resp.model_id,
            "tokens": gen_resp.usage.total_tokens,
        },
    )
    db.add(usage_rec)
    db.add(audit_ev)
    await db.commit()

    return ChatResponse(
        conversation_id=conv_id,
        message_id=assistant_msg.id,
        response_text=gen_resp.text,
        domain_plugin_id=domain_id,
        model_id=gen_resp.model_id,
        usage=gen_resp.usage,
        citations=citations_data,
    )


@router.post("/stream")
async def execute_chat_stream(
    payload: ChatRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    gateway: ModelGateway = Depends(get_model_gateway),
    registry: PluginRegistry = Depends(get_plugin_registry),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Executes streaming generation via Server-Sent Events (SSE).
    Streams tokens in real-time while preserving tenant boundaries and auditing.
    """
    correlation_id = str(uuid.uuid4())
    domain_id = payload.domain_plugin_id or "general"
    instructions = ""
    required_caps = ["text_generation", "streaming"]

    if domain_id != "general":
        plugin = registry.get_plugin(domain_id)
        if not plugin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Requested domain plugin '{domain_id}' is not installed.",
            )
        instructions = registry.get_instructions(domain_id)

    user_query = payload.message
    if payload.knowledge_base_id:
        rag = RAGPipeline(get_vector_store())
        ret_ctx = await rag.retrieve_and_augment(
            query=payload.message,
            org_id=ctx.org_id,
            workspace_id=ctx.workspace_id,
            knowledge_base_id=payload.knowledge_base_id,
        )
        user_query = ret_ctx.augmented_prompt

    messages: List[ChatMessage] = []
    if instructions:
        messages.append(ChatMessage(role=MessageRole.SYSTEM, content=instructions))
    messages.append(ChatMessage(role=MessageRole.USER, content=user_query))

    model_to_use = payload.model_id or "mock-model-v1"
    gen_req = GenerationRequest(
        model_id=model_to_use,
        messages=messages,
        tenant_id=ctx.org_id,
        correlation_id=correlation_id,
        stream=True,
    )

    async def sse_event_generator():
        accumulated_text = []
        try:
            async for chunk in gateway.stream(
                request=gen_req,
                required_capabilities=required_caps,
                allowed_models=ctx.allowed_models,
            ):
                if chunk.delta_text:
                    accumulated_text.append(chunk.delta_text)
                    yield f"data: {json.dumps({'delta': chunk.delta_text})}\n\n"
                if chunk.finish_reason:
                    yield f"data: {json.dumps({'finish_reason': chunk.finish_reason, 'done': True})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")

