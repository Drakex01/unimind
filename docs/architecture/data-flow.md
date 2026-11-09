# UniMind Data Flow & Execution Pipelines

## 1. Tenant-Aware Request Flow

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Gateway as API Gateway
    participant Auth as Tenant RBAC
    participant Router as Request Router
    participant Plugin as Plugin Registry
    participant ModelGW as Model Gateway
    participant Provider as Foundation Model
    participant Audit as Database & Audit

    User->>Gateway: POST /api/v1/chat (Bearer JWT)
    Gateway->>Auth: Extract & Validate Token Signature
    Auth->>Auth: Verify Organization Membership
    Gateway->>Router: Dispatch with TenantContext
    Router->>Plugin: Resolve Domain Plugin & Instructions
    Router->>ModelGW: Check Capability & Tenant Allowlist
    ModelGW->>Provider: Invocate Model (or Stream SSE)
    Provider-->>ModelGW: Model Response & Token Usage
    ModelGW->>Audit: Record Audit Event & Usage Accounting
    ModelGW-->>User: Validated Grounded Response + Citations
```

## 2. Document Ingestion Pipeline

1. **Upload**: Client sends multipart file to `/api/v1/knowledge-bases/{kb_id}/documents/upload`.
2. **Validation**: Enforces allowed extensions (`.pdf`, `.txt`, `.md`, `.docx`) and size limits (< 50MB). Sanitizes filenames to eliminate directory traversal.
3. **Storage**: Saves file to isolated tenant directory path: `./storage/uploads/{org_id}/{workspace_id}/{doc_id}_{filename}`.
4. **Extraction**: `DocumentExtractor` parses text and page boundaries (using `pypdf` for PDF files).
5. **Chunking**: Splits pages into overlapping segments (e.g. 500 characters with 80 character overlap) preserving source filename and page numbers.
6. **Embedding & Indexing**: Generates dense semantic vector embeddings and stores records in `VectorStore` tagged with `org_id`, `workspace_id`, and `knowledge_base_id`.
7. **Status Update**: Updates `Document.status` to `indexed` and records `chunk_count`.
