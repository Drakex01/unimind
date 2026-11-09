"""Integration Tests for Multi-Domain Plugins and Bounded Workflow Orchestration."""

import uuid
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient
from plugin_sdk.registry import PluginRegistry
from apps.api.src.core.database import engine
from apps.api.src.models.entities import Base
from apps.api.src.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def setup_test_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest.mark.asyncio
async def test_all_domain_plugins_discovered_and_valid():
    """Verify all 4 initial domain plugins load without schema violations."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/plugins")
        assert res.status_code == 200
        plugins = res.json()
        plugin_ids = {p["plugin"]["id"] for p in plugins}

        expected = {"cybersecurity", "education", "finance", "engineering"}
        assert expected.issubset(plugin_ids), f"Missing domain plugins: {expected - plugin_ids}"


@pytest.mark.asyncio
async def test_bounded_workflow_orchestration():
    """Test 4-step bounded agent workflow execution."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        suffix = uuid.uuid4().hex[:6]
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"architect.{suffix}@systemcorp.org",
                "password": "PasswordArch123!",
                "full_name": "Chief Architect",
            },
        )
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Execute Engineering Workflow
        wf_payload = {
            "task_description": "Design an idempotent distributed payment reconciliation worker pool.",
            "domain_plugin_id": "engineering",
            "model_id": "mock-model-v1",
            "max_steps": 4,
        }
        res = await client.post("/api/v1/workflows/execute", json=wf_payload, headers=headers)
        assert res.status_code == 200
        data = res.json()

        assert data["status"] == "completed"
        assert len(data["steps"]) == 4
        step_names = [s["name"] for s in data["steps"]]
        assert step_names == [
            "task_planning",
            "knowledge_retrieval",
            "analytical_synthesis",
            "verification_and_safety_audit",
        ]
        assert data["total_duration_ms"] >= 0


def test_extensibility_add_new_domain_without_code_changes(tmp_path: Path):
    """
    Verifies Section 21 Day 4 Step 8:
    A new domain plugin (e.g. 'biotech') can be declared via YAML manifest
    and loaded dynamically by the PluginRegistry without any core pipeline modifications.
    """
    new_plugin_dir = tmp_path / "biotech"
    new_plugin_dir.mkdir()

    manifest_yaml = """
schema_version: "1.0"
plugin:
  id: "biotech"
  name: "Biotechnology & Genomics Assistant"
  version: "1.0.0"
  description: "Assists with CRISPR target guides and sequence analysis."
  publisher: "community"
compatibility:
  unimind_min_version: "1.0.0"
capabilities:
  - sequence_analysis
instructions:
  path: "instructions.md"
models:
  required:
    - text_generation
retrieval:
  enabled: true
  collection_scope: "tenant"
  top_k: 4
tools:
  allowed: []
permissions:
  network: "none"
  file_access: "knowledge_base_only"
  code_execution: false
safety:
  mode: "strict"
"""
    (new_plugin_dir / "plugin.yaml").write_text(manifest_yaml.strip(), encoding="utf-8")
    (new_plugin_dir / "instructions.md").write_text("# Biotech Instructions\nVerify primers.", encoding="utf-8")

    registry = PluginRegistry()
    manifest = registry.load_from_directory(new_plugin_dir)

    assert manifest.plugin.id == "biotech"
    assert manifest.safety.mode == "strict"
    assert "sequence_analysis" in manifest.capabilities
    assert registry.get_instructions("biotech") == "# Biotech Instructions\nVerify primers."
