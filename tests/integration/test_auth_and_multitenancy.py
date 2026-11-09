"""Integration Tests for Authentication, Organizations, RBAC, and Streaming Chat."""

import json
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
    """Ensure clean isolated database for each test run."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest.mark.asyncio
async def test_full_auth_and_tenant_lifecycle():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Register User Alpha
        suffix = uuid.uuid4().hex[:6]
        reg_payload_a = {
            "email": f"alpha.admin.{suffix}@enterprise.com",
            "password": "SecurePassword123!",
            "full_name": "Alpha Administrator",
            "organization_name": "Alpha Cybersecurity Group",
        }
        res_a = await client.post("/api/v1/auth/register", json=reg_payload_a)
        assert res_a.status_code == 201
        data_a = res_a.json()
        token_a = data_a["access_token"]
        org_a_id = data_a["org_id"]
        ws_a_id = data_a["workspace_id"]
        assert data_a["role"] == "owner"
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # 2. Get User Profile via JWT Bearer Auth
        profile_res = await client.get("/api/v1/auth/me", headers=headers_a)
        assert profile_res.status_code == 200
        profile = profile_res.json()
        assert profile["email"] == f"alpha.admin.{suffix}@enterprise.com"
        assert len(profile["memberships"]) == 1
        assert profile["memberships"][0]["org_id"] == org_a_id

        # 3. Create Additional Workspace in Org Alpha
        ws_res = await client.post(
            f"/api/v1/organizations/{org_a_id}/workspaces",
            json={"name": "Threat Hunting Workspace"},
            headers=headers_a,
        )
        assert ws_res.status_code == 201
        ws_2_id = ws_res.json()["id"]

        # 4. Register User Beta (Belongs to separate Tenant Beta)
        beta_email = f"beta.user.{suffix}@othercorp.com"
        reg_payload_b = {
            "email": beta_email,
            "password": "BetaPassword456!",
            "full_name": "Beta Analyst",
            "organization_name": "Beta Research Labs",
        }
        res_b = await client.post("/api/v1/auth/register", json=reg_payload_b)
        assert res_b.status_code == 201
        token_b = res_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # 5. Cross-Tenant Authorization Test:
        # User Beta attempts to list or create workspaces in Org Alpha -> MUST be rejected with 403 Forbidden!
        bad_ws_list = await client.get(
            f"/api/v1/organizations/{org_a_id}/workspaces",
            headers=headers_b,
        )
        assert bad_ws_list.status_code == 403
        assert "Access denied" in bad_ws_list.json()["detail"]

        bad_ws_create = await client.post(
            f"/api/v1/organizations/{org_a_id}/workspaces",
            json={"name": "Hacked Workspace"},
            headers=headers_b,
        )
        assert bad_ws_create.status_code == 403

        # 6. Add User Beta to Org Alpha as a Member (Owner/Admin action)
        add_mem_res = await client.post(
            f"/api/v1/organizations/{org_a_id}/members",
            json={"email": beta_email, "role": "member"},
            headers=headers_a,
        )
        assert add_mem_res.status_code == 201
        assert add_mem_res.json()["role"] == "member"

        # 7. Now User Beta can switch context to Org Alpha using header
        headers_b_scoped_a = {
            "Authorization": f"Bearer {token_b}",
            "X-Org-ID": org_a_id,
            "X-Workspace-ID": ws_a_id,
        }
        ws_list_now = await client.get(
            f"/api/v1/organizations/{org_a_id}/workspaces",
            headers=headers_b_scoped_a,
        )
        assert ws_list_now.status_code == 200
        assert len(ws_list_now.json()) >= 2


@pytest.mark.asyncio
async def test_streaming_chat_execution():
    """Verify Server-Sent Events (SSE) streaming chat endpoint."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        suffix = uuid.uuid4().hex[:6]
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"stream.user.{suffix}@unimind.io",
                "password": "StreamPassword789!",
                "full_name": "Stream Tester",
            },
        )
        assert reg_res.status_code == 201
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        payload = {
            "message": "Stream a response about defensive packet inspection.",
            "domain_plugin_id": "cybersecurity",
            "model_id": "mock-model-v1",
        }

        res = await client.post("/api/v1/chat/stream", json=payload, headers=headers)
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]

        body = res.text
        lines = [line.strip() for line in body.split("\n") if line.startswith("data: ")]
        assert len(lines) >= 1

        first_data = json.loads(lines[0].replace("data: ", ""))
        assert "delta" in first_data or "done" in first_data
