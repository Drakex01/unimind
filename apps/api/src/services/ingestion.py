"""Document Ingestion Worker: Extract, Chunk, Embed, and Index."""

import logging
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.entities import AuditEvent, Document, DocumentChunk
from .extractor import DocumentExtractor
from .storage import StorageService
from .vector_store import EmbeddingService, VectorRecord, VectorStore

logger = logging.getLogger("unimind.ingestion")


class IngestionService:
    def __init__(self, storage: StorageService, vector_store: VectorStore):
        self.storage = storage
        self.vector_store = vector_store
        self.embedding_service = EmbeddingService()

    async def process_document(self, document_id: str, db: AsyncSession) -> bool:
        """
        Execute document ingestion pipeline:
        1. Fetch document record
        2. Read file from storage
        3. Extract pages & text
        4. Chunk with overlap
        5. Embed and save to vector store and database
        6. Update document status to 'indexed'
        """
        doc = await db.get(Document, document_id)
        if not doc:
            logger.error(f"Ingestion failed: Document '{document_id}' not found.")
            return False

        doc.status = "processing"
        await db.commit()

        try:
            # 1. Read file bytes
            content_bytes = await self.storage.read_file(doc.storage_path)

            # 2. Extract pages
            pages = DocumentExtractor.extract_pages(
                content_bytes=content_bytes,
                filename=doc.filename,
                mime_type=doc.mime_type,
            )

            # 3. Chunk
            chunks = DocumentExtractor.chunk_document(
                pages=pages,
                chunk_size=500,
                chunk_overlap=80,
                extra_metadata={"filename": doc.filename, "document_id": doc.id},
            )

            # 4. Save Chunks to Database & Vector Store
            vector_records = []
            for c in chunks:
                chunk_id = str(uuid.uuid4())
                embedding = self.embedding_service.get_embedding(c.content)

                db_chunk = DocumentChunk(
                    id=chunk_id,
                    document_id=doc.id,
                    org_id=doc.org_id,
                    workspace_id=doc.workspace_id,
                    knowledge_base_id=doc.knowledge_base_id,
                    chunk_index=c.chunk_index,
                    page_number=c.page_number,
                    content=c.content,
                    metadata_json=c.metadata,
                )
                db.add(db_chunk)

                vector_records.append(
                    VectorRecord(
                        id=chunk_id,
                        org_id=doc.org_id,
                        workspace_id=doc.workspace_id,
                        knowledge_base_id=doc.knowledge_base_id,
                        document_id=doc.id,
                        chunk_index=c.chunk_index,
                        page_number=c.page_number,
                        content=c.content,
                        embedding=embedding,
                        metadata=c.metadata,
                    )
                )

            # 5. Index into Vector Store
            await self.vector_store.add_records(vector_records)

            # 6. Mark Document as Indexed
            doc.status = "indexed"
            doc.chunk_count = len(chunks)
            doc.error_message = None

            audit = AuditEvent(
                org_id=doc.org_id,
                workspace_id=doc.workspace_id,
                user_id=None,
                action="document_indexed",
                resource_type="document",
                resource_id=doc.id,
                details={"filename": doc.filename, "chunks": len(chunks)},
            )
            db.add(audit)
            await db.commit()
            logger.info(f"Successfully indexed document '{doc.id}' ({len(chunks)} chunks).")
            return True

        except Exception as exc:
            logger.exception(f"Document ingestion failed for '{document_id}': {exc}")
            doc.status = "failed"
            doc.error_message = str(exc)
            await db.commit()
            return False
