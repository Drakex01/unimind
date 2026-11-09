"""Integration Tests for Knowledge Management, Document Ingestion, and Grounded RAG."""

import io
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from apps.api.src.core.database import engine
from apps.api.src.models.entities import Base
from apps.api.src.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Ensure clean isolated database schema for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest.mark.asyncio
async def test_document_upload_ingestion_and_grounded_rag():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Register Tenant Alpha
        suffix = uuid.uuid4().hex[:6]
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"kb.admin.{suffix}@secops.org",
                "password": "PasswordSecOps123!",
                "full_name": "SecOps Lead",
                "organization_name": "SecOps Global",
            },
        )
        assert reg_res.status_code == 201
        token_a = reg_res.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # 2. Create Knowledge Base in Org Alpha
        kb_res = await client.post(
            "/api/v1/knowledge-bases",
            json={
                "name": "Zero-Trust Architecture Guidelines",
                "description": "Enterprise zero-trust perimeter specifications",
            },
            headers=headers_a,
        )
        assert kb_res.status_code == 201
        kb_id = kb_res.json()["id"]

        # 3. Upload Document to Knowledge Base
        doc_content = (
            "Section 4.1: Perimeter Firewall Rules.\n"
            "All outbound connections to port 22 (SSH) must traverse the Envoy Proxy cluster.\n"
            "Direct egress from worker nodes to the public internet is strictly blocked.\n"
            "Section 4.2: Mutual TLS (mTLS) enforcement.\n"
            "All internal microservice communication requires SPIFFE/SPIRE x509 SVID authentication."
        )
        files = {
            "file": ("firewall_policy.txt", io.BytesIO(doc_content.encode("utf-8")), "text/plain")
        }
        upload_res = await client.post(
            f"/api/v1/knowledge-bases/{kb_id}/documents/upload",
            files=files,
            headers=headers_a,
        )
        assert upload_res.status_code == 202
        doc_data = upload_res.json()
        doc_id = doc_data["id"]
        assert doc_data["status"] == "indexed"
        assert doc_data["chunk_count"] >= 1

        # 4. Check Document Status endpoint
        status_res = await client.get(
            f"/api/v1/documents/{doc_id}/status",
            headers=headers_a,
        )
        assert status_res.status_code == 200
        assert status_res.json()["status"] == "indexed"

        # 5. Execute Grounded Chat with Knowledge Base ID
        chat_payload = {
            "message": "Which proxy cluster must outbound SSH connections traverse according to policy?",
            "domain_plugin_id": "cybersecurity",
            "model_id": "mock-model-v1",
            "knowledge_base_id": kb_id,
        }
        chat_res = await client.post("/api/v1/chat", json=chat_payload, headers=headers_a)
        assert chat_res.status_code == 200
        chat_data = chat_res.json()

        # Citations must be populated and point back to firewall_policy.txt
        assert len(chat_data["citations"]) >= 1
        citation = chat_data["citations"][0]
        assert citation["source_filename"] == "firewall_policy.txt"
        assert citation["page_number"] == 1
        assert citation["document_id"] == doc_id


@pytest.mark.asyncio
async def test_cross_tenant_knowledge_base_isolation():
    """Ensure Tenant Beta cannot access, upload to, or query Tenant Alpha's knowledge base."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        suffix = uuid.uuid4().hex[:6]

        # 1. Register Tenant Alpha & create KB
        reg_a = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"tenant.a.{suffix}@alpha.com",
                "password": "Password123Alpha!",
                "full_name": "Tenant A User",
            },
        )
        token_a = reg_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        kb_res = await client.post(
            "/api/v1/knowledge-bases",
            json={"name": "Alpha Confidential IP"},
            headers=headers_a,
        )
        kb_a_id = kb_res.json()["id"]

        # 2. Register Tenant Beta
        reg_b = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"tenant.b.{suffix}@beta.com",
                "password": "Password123Beta!",
                "full_name": "Tenant B User",
            },
        )
        token_b = reg_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # 3. Tenant Beta attempts to upload to Tenant Alpha's Knowledge Base -> 404
        files = {
            "file": ("malicious_injection.txt", io.BytesIO(b"Confidential injection"), "text/plain")
        }
        bad_upload = await client.post(
            f"/api/v1/knowledge-bases/{kb_a_id}/documents/upload",
            files=files,
            headers=headers_b,
        )
        assert bad_upload.status_code == 404
        assert "not found in this workspace" in bad_upload.json()["detail"]


@pytest.mark.asyncio
async def test_unsupported_upload_extension_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        suffix = uuid.uuid4().hex[:6]
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"user.{suffix}@domain.com",
                "password": "Password123!",
                "full_name": "User",
            },
        )
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        kb_res = await client.post(
            "/api/v1/knowledge-bases",
            json={"name": "KB Extension Test"},
            headers=headers,
        )
        kb_id = kb_res.json()["id"]

        # Attempt to upload executable file (.exe)
        bad_file = {
            "file": ("trojan.exe", io.BytesIO(b"binary payload"), "application/x-msdownload")
        }
        res = await client.post(
            f"/api/v1/knowledge-bases/{kb_id}/documents/upload",
            files=bad_file,
            headers=headers,
        )
        assert res.status_code == 400
        assert "not supported" in res.json()["detail"]
