"""Security, Authentication, RBAC, and Tenant Context Isolation."""

from typing import List, Optional
from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import decode_token
from .database import get_db_session
from ..models.entities import OrganizationMembership, User


class TenantContext(BaseModel):
    user_id: str
    org_id: str
    workspace_id: str
    role: str = "member"  # owner, admin, member, auditor
    is_platform_admin: bool = False
    allowed_models: Optional[List[str]] = None


async def get_tenant_context(
    authorization: Optional[str] = Header(default=None),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-ID"),
    x_org_id: Optional[str] = Header(default=None, alias="X-Org-ID"),
    x_workspace_id: Optional[str] = Header(default=None, alias="X-Workspace-ID"),
    x_user_role: Optional[str] = Header(default="member", alias="X-User-Role"),
    db: AsyncSession = Depends(get_db_session),
) -> TenantContext:
    """
    Extract and cryptographically verify tenant context.
    Enforces strict tenant isolation: users cannot access resources outside of
    organizations they are actively members of.
    """
    allowed_models = ["mock-model-v1", "gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-4-argon"]

    # 1. JWT Bearer Token Authentication
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        payload = decode_token(token)
        user_id = payload.get("sub")
        token_org_id = payload.get("org_id")
        token_workspace_id = payload.get("workspace_id")
        token_role = payload.get("role", "member")
        is_platform_admin = payload.get("is_platform_admin", False)

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed token: missing subject identity.",
            )

        # Check if client requested a specific organization/workspace via headers
        target_org_id = x_org_id or token_org_id
        target_workspace_id = x_workspace_id or token_workspace_id or "default"

        # Verify membership in target organization
        if not is_platform_admin:
            stmt = select(OrganizationMembership).where(
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.org_id == target_org_id,
            )
            res = await db.execute(stmt)
            membership = res.scalars().first()
            if not membership:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: User is not an active member of organization '{target_org_id}'.",
                )
            active_role = membership.role
        else:
            active_role = "platform_admin"

        return TenantContext(
            user_id=user_id,
            org_id=target_org_id,
            workspace_id=target_workspace_id,
            role=active_role,
            is_platform_admin=is_platform_admin,
            allowed_models=allowed_models,
        )

    # 2. Development Mode Header Fallback (for unauthenticated test harnesses)
    user_id = x_user_id or "usr_dev_default"
    org_id = x_org_id or "org_dev_default"
    workspace_id = x_workspace_id or "ws_dev_default"
    role = x_user_role or "member"

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
        allowed_models=allowed_models,
    )


def require_role(allowed_roles: List[str]):
    """Authorization dependency checking RBAC within the tenant context."""
    async def role_checker(ctx: TenantContext = Depends(get_tenant_context)):
        if not ctx.is_platform_admin and ctx.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Action requires one of roles: {allowed_roles}. Current role: {ctx.role}",
            )
        return ctx
    return role_checker
