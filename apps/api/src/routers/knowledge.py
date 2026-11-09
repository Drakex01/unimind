"""Knowledge Base and Document Management Router."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db_session
from ..core.security import TenantContext, get_tenant_context
from ..models.entities import AuditEvent, Document, KnowledgeBase
from ..services.ingestion import IngestionService
from ..services.storage import LocalStorageService, StorageService
from ..services.vector_store import InMemoryVectorStore, VectorStore

router = APIRouter(tags=["Knowledge & Documents"])

# Singletons for storage and vector store
_storage: StorageService = LocalStorageService()
_vector_store: VectorStore = InMemoryVectorStore()
_ingestion: IngestionService = IngestionService(_storage, _vector_store)


def get_vector_store() -> VectorStore:
    return _vector_store


def get_storage_service() -> StorageService:
    return _storage


def get_ingestion_service() -> IngestionService:
    return _ingestion


class CreateKBRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None


class KBResponse(BaseModel):
    id: str
    org_id: str
    workspace_id: str
    name: str
    description: Optional[str] = None


class DocumentResponse(BaseModel):
    id: str
    knowledge_base_id: str
    filename: str
    file_size: int
    mime_type: str
    status: str
    chunk_count: int
    error_message: Optional[str] = None


@router.post("/api/v1/knowledge-bases", response_model=KBResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    payload: CreateKBRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new named knowledge base strictly scoped to the tenant workspace."""
    kb = KnowledgeBase(
        org_id=ctx.org_id,
        workspace_id=ctx.workspace_id,
        name=payload.name,
        description=payload.description,
    )
    db.add(kb)

    audit = AuditEvent(
        org_id=ctx.org_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        action="knowledge_base_created",
        resource_type="knowledge_base",
        resource_id=kb.id,
        details={"name": kb.name},
    )
    db.add(audit)
    await db.commit()

    return KBResponse(
        id=kb.id,
        org_id=kb.org_id,
        workspace_id=kb.workspace_id,
        name=kb.name,
        description=kb.description,
    )


@router.get("/api/v1/knowledge-bases", response_model=List[KBResponse])
async def list_knowledge_bases(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    """List knowledge bases belonging to the current tenant and workspace."""
    stmt = select(KnowledgeBase).where(
        KnowledgeBase.org_id == ctx.org_id,
        KnowledgeBase.workspace_id == ctx.workspace_id,
    )
    res = await db.execute(stmt)
    kbs = res.scalars().all()
    return [
        KBResponse(
            id=k.id,
            org_id=k.org_id,
            workspace_id=k.workspace_id,
            name=k.name,
            description=k.description,
        )
        for k in kbs
    ]


@router.post(
    "/api/v1/knowledge-bases/{kb_id}/documents/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    ctx: TenantContext = Depends(get_tenant_context),
    storage: StorageService = Depends(get_storage_service),
    ingestion: IngestionService = Depends(get_ingestion_service),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Securely upload a document, validate MIME/extension, store in tenant directory,
    and trigger ingestion & vector indexing.
    """
    # Verify Knowledge Base exists and belongs to this tenant
    kb = await db.get(KnowledgeBase, kb_id)
    if not kb or kb.org_id != ctx.org_id or kb.workspace_id != ctx.workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge base '{kb_id}' not found in this workspace.",
        )

    doc_id = str(uuid.uuid4())

    # Save to isolated storage
    storage_path, file_size, checksum = await storage.save_upload(
        upload=file,
        org_id=ctx.org_id,
        workspace_id=ctx.workspace_id,
        doc_id=doc_id,
    )

    doc = Document(
        id=doc_id,
        org_id=ctx.org_id,
        workspace_id=ctx.workspace_id,
        knowledge_base_id=kb_id,
        filename=file.filename or "document",
        file_size=file_size,
        mime_type=file.content_type or "application/octet-stream",
        storage_path=storage_path,
        checksum_sha256=checksum,
        status="pending",
    )
    db.add(doc)
    await db.commit()

    # Trigger ingestion
    await ingestion.process_document(document_id=doc_id, db=db)
    await db.refresh(doc)

    return DocumentResponse(
        id=doc.id,
        knowledge_base_id=doc.knowledge_base_id,
        filename=doc.filename,
        file_size=doc.file_size,
        mime_type=doc.mime_type,
        status=doc.status,
        chunk_count=doc.chunk_count,
        error_message=doc.error_message,
    )


@router.get("/api/v1/documents/{doc_id}/status", response_model=DocumentResponse)
async def get_document_status(
    doc_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    """Check ingestion status of a specific document (enforces tenant isolation)."""
    doc = await db.get(Document, doc_id)
    if not doc or doc.org_id != ctx.org_id or doc.workspace_id != ctx.workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{doc_id}' not found in this workspace.",
        )

    return DocumentResponse(
        id=doc.id,
        knowledge_base_id=doc.knowledge_base_id,
        filename=doc.filename,
        file_size=doc.file_size,
        mime_type=doc.mime_type,
        status=doc.status,
        chunk_count=doc.chunk_count,
        error_message=doc.error_message,
    )


@router.get("/api/v1/knowledge-bases/{kb_id}/documents", response_model=List[DocumentResponse])
async def list_documents_in_kb(
    kb_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    """List all documents indexed in a knowledge base."""
    kb = await db.get(KnowledgeBase, kb_id)
    if not kb or kb.org_id != ctx.org_id or kb.workspace_id != ctx.workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge base '{kb_id}' not found.",
        )

    stmt = select(Document).where(
        Document.knowledge_base_id == kb_id,
        Document.org_id == ctx.org_id,
        Document.workspace_id == ctx.workspace_id,
    )
    res = await db.execute(stmt)
    docs = res.scalars().all()
    return [
        DocumentResponse(
            id=d.id,
            knowledge_base_id=d.knowledge_base_id,
            filename=d.filename,
            file_size=d.file_size,
            mime_type=d.mime_type,
            status=d.status,
            chunk_count=d.chunk_count,
            error_message=d.error_message,
        )
        for d in docs
    ]
