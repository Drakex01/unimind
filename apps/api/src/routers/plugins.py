"""Domain Plugin Management and Discovery Endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from plugin_sdk.manifest import PluginManifest
from plugin_sdk.registry import PluginRegistry
from ..core.security import TenantContext, get_tenant_context

router = APIRouter(prefix="/api/v1/plugins", tags=["Plugins"])

_registry: Optional[PluginRegistry] = None


def set_plugin_registry(registry: PluginRegistry):
    global _registry
    _registry = registry


def get_plugin_registry() -> PluginRegistry:
    if _registry is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Plugin registry not initialized.",
        )
    return _registry


@router.get("", response_model=List[PluginManifest])
async def list_plugins(
    ctx: TenantContext = Depends(get_tenant_context),
    registry: PluginRegistry = Depends(get_plugin_registry),
):
    """List all installed and validated domain plugins."""
    return registry.list_plugins()


@router.get("/{plugin_id}", response_model=PluginManifest)
async def get_plugin_details(
    plugin_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    registry: PluginRegistry = Depends(get_plugin_registry),
):
    """Retrieve metadata and policies for a specific domain plugin."""
    plugin = registry.get_plugin(plugin_id)
    if not plugin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin '{plugin_id}' not found.",
        )
    return plugin
