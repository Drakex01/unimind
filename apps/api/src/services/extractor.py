"""Document Text Extractor and Chunking Pipeline."""

import io
from pathlib import Path
from typing import Any, Dict, List
from pydantic import BaseModel


class ExtractedPage(BaseModel):
    page_number: int
    text: str


class ChunkData(BaseModel):
    chunk_index: int
    page_number: int
    content: str
    metadata: Dict[str, Any]


class DocumentExtractor:
    @staticmethod
    def extract_pages(content_bytes: bytes, filename: str, mime_type: str) -> List[ExtractedPage]:
        ext = Path(filename).suffix.lower()

        if ext == ".pdf" or mime_type == "application/pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(io.BytesIO(content_bytes))
                pages = []
                for idx, page in enumerate(reader.pages):
                    text = page.extract_text() or ""
                    pages.append(ExtractedPage(page_number=idx + 1, text=text.strip()))
                return pages if pages else [ExtractedPage(page_number=1, text="")]
            except Exception as e:
                raise ValueError(f"Failed to parse PDF document: {e}") from e

        # Plain text, Markdown, CSV, JSON
        try:
            text = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = content_bytes.decode("latin-1", errors="replace")

        return [ExtractedPage(page_number=1, text=text.strip())]

    @staticmethod
    def chunk_document(
        pages: List[ExtractedPage],
        chunk_size: int = 600,
        chunk_overlap: int = 100,
        extra_metadata: Dict[str, Any] = None,
    ) -> List[ChunkData]:
        """Split extracted pages into overlapping semantic chunks with page provenance."""
        chunks: List[ChunkData] = []
        chunk_idx = 0
        extra_meta = extra_metadata or {}

        for page in pages:
            text = page.text
            if not text:
                continue

            start = 0
            text_len = len(text)
            while start < text_len:
                end = min(start + chunk_size, text_len)
                chunk_text = text[start:end].strip()
                if chunk_text:
                    chunks.append(
                        ChunkData(
                            chunk_index=chunk_idx,
                            page_number=page.page_number,
                            content=chunk_text,
                            metadata={
                                **extra_meta,
                                "page_number": page.page_number,
                                "start_char": start,
                                "end_char": end,
                            },
                        )
                    )
                    chunk_idx += 1

                if end >= text_len:
                    break
                start += chunk_size - chunk_overlap

        return chunks
