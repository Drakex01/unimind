"""Unit Tests for Declarative Plugin Manifest Schema Validation."""

import pytest
from pydantic import ValidationError

from plugin_sdk.manifest import (
    PluginCompatibility,
    PluginManifest,
    PluginMetadata,
    RetrievalConfig,
    SafetyConfig,
)


def test_valid_manifest_creation():
    manifest_data = {
        "schema_version": "1.0",
        "plugin": {
            "id": "cybersecurity",
            "name": "Cybersecurity Assistant",
            "version": "1.0.0",
            "description": "Analyzes security logs and architectures.",
            "publisher": "unimind-core",
        },
        "compatibility": {"unimind_min_version": "1.0.0"},
        "capabilities": ["document_analysis", "log_analysis"],
        "instructions": {"path": "instructions.md"},
        "models": {"required": ["text_generation"], "preferred": ["structured_output"]},
        "retrieval": {
            "enabled": True,
            "collection_scope": "tenant",
            "top_k": 6,
            "reranking": True,
            "citation_required": True,
        },
        "tools": {"allowed": ["log_parser"], "approval_required": ["threat_lookup"]},
        "permissions": {
            "network": "restricted",
            "file_access": "knowledge_base_only",
            "code_execution": False,
        },
        "safety": {
            "mode": "informational",
            "require_evidence_for_security_findings": True,
        },
    }

    manifest = PluginManifest.model_validate(manifest_data)
    assert manifest.plugin.id == "cybersecurity"
    assert manifest.plugin.version == "1.0.0"
    assert manifest.retrieval.top_k == 6
    assert manifest.safety.require_evidence_for_security_findings is True


def test_invalid_schema_version_rejected():
    manifest_data = {
        "schema_version": "2.0",
        "plugin": {
            "id": "test_plugin",
            "name": "Test",
            "version": "1.0.0",
            "description": "desc",
            "publisher": "test",
        },
    }
    with pytest.raises(ValidationError) as exc:
        PluginManifest.model_validate(manifest_data)
    assert "Unsupported schema version" in str(exc.value)


def test_invalid_plugin_id_rejected():
    manifest_data = {
        "schema_version": "1.0",
        "plugin": {
            "id": "INVALID ID WITH SPACES!",
            "name": "Test",
            "version": "1.0.0",
            "description": "desc",
            "publisher": "test",
        },
    }
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(manifest_data)


def test_invalid_semantic_version_rejected():
    manifest_data = {
        "schema_version": "1.0",
        "plugin": {
            "id": "test-plugin",
            "name": "Test",
            "version": "v1-beta",
            "description": "desc",
            "publisher": "test",
        },
    }
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(manifest_data)
