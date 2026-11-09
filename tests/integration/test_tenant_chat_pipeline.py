"""Integration Tests for UniMind API, Tenant Boundaries, and Chat Pipeline."""

import pytest
from httpx import ASGITransport, AsyncClient
from apps.api.src.core.database import init_db
from apps.api.src.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Ensure database schema is created for integration tests."""
    await init_db()


@pytest.mark.asyncio
async def test_health_endpoints():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        live_res = await client.get("/health/live")
        assert live_res.status_code == 200
        assert live_res.json()["status"] == "alive"

        ready_res = await client.get("/health/ready")
        assert ready_res.status_code == 200
        assert ready_res.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_plugin_discovery_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/plugins")
        assert res.status_code == 200
        plugins = res.json()
        assert len(plugins) >= 1
        ids = [p["plugin"]["id"] for p in plugins]
        assert "cybersecurity" in ids


@pytest.mark.asyncio
async def test_verified_tenant_chat_execution():
    headers_tenant_a = {
        "X-Org-ID": "org_alpha",
        "X-Workspace-ID": "ws_alpha_prod",
        "X-User-ID": "usr_alice",
        "X-User-Role": "admin",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "message": "Review CVE-2024-3094 implications on SSH services.",
            "domain_plugin_id": "cybersecurity",
            "model_id": "mock-model-v1",
        }
        res = await client.post("/api/v1/chat", json=payload, headers=headers_tenant_a)
        assert res.status_code == 200
        data = res.json()
        assert data["domain_plugin_id"] == "cybersecurity"
        assert data["model_id"] == "mock-model-v1"
        assert data["conversation_id"] is not None
        assert data["usage"]["total_tokens"] > 0
        conv_id = data["conversation_id"]

        # Follow-up message in same conversation
        followup_payload = {
            "message": "What mitigation patch was issued?",
            "domain_plugin_id": "cybersecurity",
            "model_id": "mock-model-v1",
            "conversation_id": conv_id,
        }
        res_followup = await client.post("/api/v1/chat", json=followup_payload, headers=headers_tenant_a)
        assert res_followup.status_code == 200
        assert res_followup.json()["conversation_id"] == conv_id


@pytest.mark.asyncio
async def test_cross_tenant_isolation_enforcement():
    """Ensure Tenant Beta cannot access or mutate Tenant Alpha's conversation."""
    headers_tenant_a = {
        "X-Org-ID": "org_alpha",
        "X-Workspace-ID": "ws_alpha_prod",
        "X-User-ID": "usr_alice",
    }
    headers_tenant_b = {
        "X-Org-ID": "org_beta",
        "X-Workspace-ID": "ws_beta_prod",
        "X-User-ID": "usr_bob",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Tenant Alpha creates conversation
        payload = {
            "message": "Tenant Alpha confidential security analysis.",
            "domain_plugin_id": "cybersecurity",
            "model_id": "mock-model-v1",
        }
        res_a = await client.post("/api/v1/chat", json=payload, headers=headers_tenant_a)
        assert res_a.status_code == 200
        tenant_a_conv_id = res_a.json()["conversation_id"]

        # 2. Tenant Beta attempts to access Tenant Alpha's conversation ID
        payload_b = {
            "message": "Attempting cross-tenant unauthorized injection.",
            "domain_plugin_id": "cybersecurity",
            "model_id": "mock-model-v1",
            "conversation_id": tenant_a_conv_id,
        }
        res_b = await client.post("/api/v1/chat", json=payload_b, headers=headers_tenant_b)

        # Cross-tenant access must be rejected with 404 (Not Found in Tenant B's workspace)
        assert res_b.status_code == 404
        assert "not found in this workspace" in res_b.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_domain_plugin_rejected():
    headers = {
        "X-Org-ID": "org_gamma",
        "X-Workspace-ID": "ws_gamma",
        "X-User-ID": "usr_carol",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "message": "Hello",
            "domain_plugin_id": "non_existent_domain_plugin",
            "model_id": "mock-model-v1",
        }
        res = await client.post("/api/v1/chat", json=payload, headers=headers)
        assert res.status_code == 404
        assert "is not installed" in res.json()["detail"]
