"""Security, Authentication, and Tenant Context Management."""

from typing import List, Optional
from fastapi import Header, HTTPException, status
from pydantic import BaseModel


class TenantContext(BaseModel):
    user_id: str
    org_id: str
    workspace_id: str
    role: str = "member"  # owner, admin, member, auditor
    is_platform_admin: bool = False
    allowed_models: Optional[List[str]] = None


async def get_tenant_context(
    x_user_id: Optional[str] = Header(default=None, alias="X-User-ID"),
    x_org_id: Optional[str] = Header(default=None, alias="X-Org-ID"),
    x_workspace_id: Optional[str] = Header(default=None, alias="X-Workspace-ID"),
    x_user_role: Optional[str] = Header(default="member", alias="X-User-Role"),
    authorization: Optional[str] = Header(default=None),
) -> TenantContext:
    """Extract and validate tenant context from request headers or auth token."""
    # For Day 1 foundation, allow headers with safe defaults for local dev / tests
    user_id = x_user_id or "usr_dev_default"
    org_id = x_org_id or "org_dev_default"
    workspace_id = x_workspace_id or "ws_dev_default"
    role = x_user_role or "member"

    # Enforce non-empty IDs
    if not user_id.strip() or not org_id.strip() or not workspace_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required tenant identity context (user, organization, or workspace).",
        )

    return TenantContext(
        user_id=user_id,
        org_id=org_id,
        workspace_id=workspace_id,
        role=role,
        is_platform_admin=(role == "platform_admin"),
        allowed_models=["mock-model-v1", "gemini-2.5-pro", "gemini-2.5-flash"],
    )


def require_role(allowed_roles: List[str]):
    """Authorization dependency verifying required role within the tenant."""
    async def role_checker(ctx: TenantContext = None):
        if ctx and not ctx.is_platform_admin and ctx.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Action requires one of roles: {allowed_roles}. Current role: {ctx.role}",
            )
        return ctx
    return role_checker
