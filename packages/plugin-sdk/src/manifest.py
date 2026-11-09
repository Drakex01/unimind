"""Declarative Plugin Manifest Schemas and Validators."""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class PluginMetadata(BaseModel):
    id: str = Field(..., pattern=r"^[a-z0-9_-]+$", description="Unique plugin identifier")
    name: str = Field(..., min_length=2, max_length=100)
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$", description="Semantic version string")
    description: str = Field(..., max_length=1000)
    publisher: str = Field(..., min_length=2, max_length=100)


class PluginCompatibility(BaseModel):
    unimind_min_version: str = Field(default="1.0.0")


class InstructionsConfig(BaseModel):
    path: str = Field(default="instructions.md")


class ModelsRequirement(BaseModel):
    required: List[str] = Field(default_factory=lambda: ["text_generation"])
    preferred: List[str] = Field(default_factory=list)


class RetrievalConfig(BaseModel):
    enabled: bool = False
    collection_scope: str = Field(default="tenant")  # tenant | workspace | public
    top_k: int = Field(default=5, ge=1, le=50)
    reranking: bool = False
    citation_required: bool = True


class ToolsConfig(BaseModel):
    allowed: List[str] = Field(default_factory=list)
    approval_required: List[str] = Field(default_factory=list)


class PermissionsConfig(BaseModel):
    network: str = Field(default="restricted")  # none | restricted | allow_all
    file_access: str = Field(default="knowledge_base_only")
    code_execution: bool = False


class SafetyConfig(BaseModel):
    mode: str = Field(default="informational")  # informational | strict | advisory
    require_evidence_for_security_findings: bool = False


class PluginManifest(BaseModel):
    """Complete declarative plugin specification adhering to UniMind specification."""

    schema_version: str = Field(default="1.0")
    plugin: PluginMetadata
    compatibility: PluginCompatibility = Field(default_factory=PluginCompatibility)
    capabilities: List[str] = Field(default_factory=list)
    instructions: InstructionsConfig = Field(default_factory=InstructionsConfig)
    models: ModelsRequirement = Field(default_factory=ModelsRequirement)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    permissions: PermissionsConfig = Field(default_factory=PermissionsConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, v: str) -> str:
        if v != "1.0":
            raise ValueError(f"Unsupported schema version: '{v}'. Expected '1.0'")
        return v
