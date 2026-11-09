"""Vector Database Interface and Tenant-Filtered Semantic Search."""

import math
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class VectorRecord(BaseModel):
    id: str
    org_id: str
    workspace_id: str
    knowledge_base_id: str
    document_id: str
    chunk_index: int
    page_number: int
    content: str
    embedding: List[float]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SearchResult(BaseModel):
    record: VectorRecord
    score: float


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


class VectorStore(ABC):
    @abstractmethod
    async def add_records(self, records: List[VectorRecord]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def search(
        self,
        query_embedding: List[float],
        org_id: str,
        workspace_id: str,
        knowledge_base_id: Optional[str] = None,
        top_k: int = 5,
    ) -> List[SearchResult]:
        raise NotImplementedError

    @abstractmethod
    async def delete_by_document(self, document_id: str) -> int:
        raise NotImplementedError


class InMemoryVectorStore(VectorStore):
    """
    In-memory vector store enforcing strict tenant and workspace boundaries.
    Used for unit testing, fast local execution, and standalone demonstrations.
    """

    def __init__(self):
        self._records: List[VectorRecord] = []

    async def add_records(self, records: List[VectorRecord]) -> None:
        self._records.extend(records)

    async def search(
        self,
        query_embedding: List[float],
        org_id: str,
        workspace_id: str,
        knowledge_base_id: Optional[str] = None,
        top_k: int = 5,
    ) -> List[SearchResult]:
        # 1. Mandatory Tenant Boundary Filter
        candidates = [
            r for r in self._records
            if r.org_id == org_id and r.workspace_id == workspace_id
        ]

        # 2. Knowledge Base Scope Filter (if specified)
        if knowledge_base_id:
            candidates = [c for c in candidates if c.knowledge_base_id == knowledge_base_id]

        # 3. Cosine Ranking
        scored: List[SearchResult] = []
        for cand in candidates:
            sim = cosine_similarity(query_embedding, cand.embedding)
            scored.append(SearchResult(record=cand, score=round(sim, 4)))

        scored.sort(key=lambda s: s.score, reverse=True)
        return scored[:top_k]

    async def delete_by_document(self, document_id: str) -> int:
        initial = len(self._records)
        self._records = [r for r in self._records if r.document_id != document_id]
        return initial - len(self._records)


class EmbeddingService:
    """Generates normalized vector embeddings for queries and document chunks."""

    @staticmethod
    def get_embedding(text: str, dim: int = 64) -> List[float]:
        """
        Generates a deterministic pseudo-semantic dense vector from text tokens.
        If an external GenAI key is configured, client.models.embed_content can be substituted.
        """
        words = text.lower().split()
        vec = [0.0] * dim
        for w in words:
            h = hash(w)
            for i in range(dim):
                vec[i] += (float((h >> (i % 32)) & 0xFF) / 255.0) - 0.5

        # Normalize
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [round(x / norm, 5) for x in vec]
        return vec
