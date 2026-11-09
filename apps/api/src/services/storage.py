"""Storage Service with Tenant Boundary Isolation and Traversal Protection."""

import hashlib
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, Optional, Tuple
from fastapi import HTTPException, UploadFile, status

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx", ".csv", ".json"}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB


class StorageService(ABC):
    @abstractmethod
    async def save_upload(
        self, upload: UploadFile, org_id: str, workspace_id: str, doc_id: str
    ) -> Tuple[str, int, str]:
        """Save an uploaded file and return (storage_path, file_size, sha256_checksum)."""
        raise NotImplementedError

    @abstractmethod
    async def read_file(self, storage_path: str) -> bytes:
        """Read bytes from storage path."""
        raise NotImplementedError

    @abstractmethod
    async def delete_file(self, storage_path: str) -> bool:
        """Delete file from storage."""
        raise NotImplementedError


class LocalStorageService(StorageService):
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or "./storage/uploads").resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_filename(self, filename: str) -> str:
        # Strip directories and non-alphanumeric chars except dots/dashes
        clean = Path(filename).name
        clean = re.sub(r"[^a-zA-Z0-9_.-]", "_", clean)
        return clean or "unnamed_document"

    async def save_upload(
        self, upload: UploadFile, org_id: str, workspace_id: str, doc_id: str
    ) -> Tuple[str, int, str]:
        ext = Path(upload.filename or "").suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File extension '{ext}' is not supported. Allowed: {list(ALLOWED_EXTENSIONS)}",
            )

        safe_name = self._sanitize_filename(upload.filename or "doc")
        tenant_dir = self.base_dir / org_id / workspace_id
        tenant_dir.mkdir(parents=True, exist_ok=True)

        dest_path = (tenant_dir / f"{doc_id}_{safe_name}").resolve()

        # Prevent Path Traversal attacks
        if not str(dest_path).startswith(str(self.base_dir)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security alert: Path traversal detected.",
            )

        sha256 = hashlib.sha256()
        total_size = 0

        with open(dest_path, "wb") as f:
            while chunk := await upload.read(1024 * 64):
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE_BYTES:
                    f.close()
                    dest_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds maximum allowed limit of {MAX_FILE_SIZE_BYTES / (1024*1024):.0f}MB",
                    )
                sha256.update(chunk)
                f.write(chunk)

        return str(dest_path), total_size, sha256.hexdigest()

    async def read_file(self, storage_path: str) -> bytes:
        p = Path(storage_path).resolve()
        if not str(p).startswith(str(self.base_dir)) or not p.exists():
            raise FileNotFoundError(f"Storage path '{storage_path}' not found or outside root.")
        with open(p, "rb") as f:
            return f.read()

    async def delete_file(self, storage_path: str) -> bool:
        p = Path(storage_path).resolve()
        if str(p).startswith(str(self.base_dir)) and p.exists():
            p.unlink()
            return True
        return False
