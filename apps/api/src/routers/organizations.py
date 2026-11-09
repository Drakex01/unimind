"""Organizations, Workspaces, and Membership Management Router."""

import uuid
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db_session
from ..core.security import TenantContext, get_tenant_context, require_role
from ..models.entities import AuditEvent, Organization, OrganizationMembership, User, Workspace
from .auth import slugify

router = APIRouter(prefix="/api/v1/organizations", tags=["Organizations & Workspaces"])


class CreateOrgRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)


class OrgResponse(BaseModel):
    id: str
    name: str
    slug: str
    role: str


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)


class WorkspaceResponse(BaseModel):
    id: str
    org_id: str
    name: str
    slug: str


class AddMemberRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="member", pattern=r"^(admin|member|auditor)$")


class MemberResponse(BaseModel):
    id: str
    user_id: str
    email: str
    full_name: str
    role: str


@router.get("", response_model=List[OrgResponse])
async def list_user_organizations(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    """List organizations the authenticated user belongs to."""
    stmt = (
        select(Organization, OrganizationMembership.role)
        .join(OrganizationMembership, OrganizationMembership.org_id == Organization.id)
        .where(OrganizationMembership.user_id == ctx.user_id)
    )
    res = await db.execute(stmt)
    return [
        OrgResponse(id=org.id, name=org.name, slug=org.slug, role=role)
        for org, role in res.all()
    ]


@router.post("", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: CreateOrgRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new organization and default workspace with owner role."""
    org_slug = f"{slugify(payload.name)}-{uuid.uuid4().hex[:6]}"
    org = Organization(name=payload.name, slug=org_slug)
    db.add(org)
    await db.flush()

    workspace = Workspace(org_id=org.id, name="Default Workspace", slug="default")
    db.add(workspace)

    membership = OrganizationMembership(org_id=org.id, user_id=ctx.user_id, role="owner")
    db.add(membership)

    audit = AuditEvent(
        org_id=org.id,
        workspace_id=workspace.id,
        user_id=ctx.user_id,
        action="organization_created",
        resource_type="organization",
        resource_id=org.id,
        details={"name": org.name},
    )
    db.add(audit)
    await db.commit()

    return OrgResponse(id=org.id, name=org.name, slug=org.slug, role="owner")


@router.get("/{org_id}/workspaces", response_model=List[WorkspaceResponse])
async def list_workspaces(
    org_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    """List workspaces within an organization (requires membership)."""
    # Verify tenant isolation: must be member of target org
    if not ctx.is_platform_admin and ctx.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: Not authorized for organization '{org_id}'.",
        )

    stmt = select(Workspace).where(Workspace.org_id == org_id)
    res = await db.execute(stmt)
    workspaces = res.scalars().all()
    return [
        WorkspaceResponse(id=ws.id, org_id=ws.org_id, name=ws.name, slug=ws.slug)
        for ws in workspaces
    ]


@router.post("/{org_id}/workspaces", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    org_id: str,
    payload: CreateWorkspaceRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    """Create a workspace within an organization (requires owner/admin role)."""
    if not ctx.is_platform_admin and (ctx.org_id != org_id or ctx.role not in ["owner", "admin"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permissions required to create workspaces in this organization.",
        )

    ws_slug = f"{slugify(payload.name)}-{uuid.uuid4().hex[:4]}"
    ws = Workspace(org_id=org_id, name=payload.name, slug=ws_slug)
    db.add(ws)

    audit = AuditEvent(
        org_id=org_id,
        workspace_id=ws.id,
        user_id=ctx.user_id,
        action="workspace_created",
        resource_type="workspace",
        resource_id=ws.id,
        details={"name": ws.name},
    )
    db.add(audit)
    await db.commit()

    return WorkspaceResponse(id=ws.id, org_id=ws.org_id, name=ws.name, slug=ws.slug)


@router.post("/{org_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def add_organization_member(
    org_id: str,
    payload: AddMemberRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    """Add a member to an organization (requires owner/admin role)."""
    if not ctx.is_platform_admin and (ctx.org_id != org_id or ctx.role not in ["owner", "admin"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permissions required to invite members.",
        )

    # Locate user
    u_res = await db.execute(select(User).where(User.email == payload.email))
    user = u_res.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with email '{payload.email}' not found.",
        )

    # Check if membership already exists
    mem_stmt = select(OrganizationMembership).where(
        OrganizationMembership.org_id == org_id,
        OrganizationMembership.user_id == user.id,
    )
    mem_res = await db.execute(mem_stmt)
    if mem_res.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User '{payload.email}' is already a member of this organization.",
        )

    membership = OrganizationMembership(
        org_id=org_id,
        user_id=user.id,
        role=payload.role,
    )
    db.add(membership)

    audit = AuditEvent(
        org_id=org_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        action="member_added",
        resource_type="organization_membership",
        resource_id=membership.id,
        details={"email": payload.email, "role": payload.role},
    )
    db.add(audit)
    await db.commit()

    return MemberResponse(
        id=membership.id,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=membership.role,
    )
