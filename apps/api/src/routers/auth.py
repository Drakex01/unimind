"""Authentication and Identity Router."""

import re
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from ..core.database import get_db_session
from ..core.security import TenantContext, get_tenant_context
from ..models.entities import AuditEvent, Organization, OrganizationMembership, User, Workspace

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=100)
    organization_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    org_id: str
    workspace_id: str
    role: str


class UserProfileResponse(BaseModel):
    id: str
    email: str
    full_name: str
    is_active: bool
    is_platform_admin: bool
    memberships: List[Dict[str, Any]]


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "org"


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Register a new user, provisioning an organization, workspace, and owner role."""
    # Check if email is already taken
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email address is already registered.",
        )

    # Create user
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # Create Organization
    org_name = payload.organization_name or f"{payload.full_name}'s Org"
    org_slug = f"{slugify(org_name)}-{uuid.uuid4().hex[:6]}"
    org = Organization(
        name=org_name,
        slug=org_slug,
    )
    db.add(org)
    await db.flush()

    # Create default Workspace
    workspace = Workspace(
        org_id=org.id,
        name="Default Workspace",
        slug="default",
    )
    db.add(workspace)
    await db.flush()

    # Create Owner Membership
    membership = OrganizationMembership(
        org_id=org.id,
        user_id=user.id,
        role="owner",
    )
    db.add(membership)

    # Audit Registration
    audit = AuditEvent(
        org_id=org.id,
        workspace_id=workspace.id,
        user_id=user.id,
        action="user_registered",
        resource_type="user",
        resource_id=user.id,
        details={"email": user.email, "org_name": org.name},
    )
    db.add(audit)
    await db.commit()

    # Generate JWT tokens
    token_claims = {
        "sub": user.id,
        "email": user.email,
        "org_id": org.id,
        "workspace_id": workspace.id,
        "role": "owner",
        "is_platform_admin": user.is_platform_admin,
    }
    access_token = create_access_token(token_claims)
    refresh_token = create_refresh_token(token_claims)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        org_id=org.id,
        workspace_id=workspace.id,
        role="owner",
    )


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login_user(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Authenticate with email and password, issuing signed JWT tokens."""
    res = await db.execute(select(User).where(User.email == payload.email))
    user = res.scalars().first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This user account has been disabled.",
        )

    # Fetch user's primary membership
    m_stmt = (
        select(OrganizationMembership, Workspace)
        .join(Workspace, Workspace.org_id == OrganizationMembership.org_id)
        .where(OrganizationMembership.user_id == user.id)
        .order_by(OrganizationMembership.created_at)
    )
    m_res = await db.execute(m_stmt)
    primary = m_res.first()

    if not primary:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User has no associated organizations.",
        )

    membership, workspace = primary

    token_claims = {
        "sub": user.id,
        "email": user.email,
        "org_id": membership.org_id,
        "workspace_id": workspace.id,
        "role": membership.role,
        "is_platform_admin": user.is_platform_admin,
    }
    access_token = create_access_token(token_claims)
    refresh_token = create_refresh_token(token_claims)

    # Audit login
    audit = AuditEvent(
        org_id=membership.org_id,
        workspace_id=workspace.id,
        user_id=user.id,
        action="user_login",
        resource_type="user",
        resource_id=user.id,
    )
    db.add(audit)
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        org_id=membership.org_id,
        workspace_id=workspace.id,
        role=membership.role,
    )


@router.post("/refresh", response_model=Dict[str, str], status_code=status.HTTP_200_OK)
async def refresh_access_token(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Issue a new access token from a valid refresh token."""
    decoded = decode_token(payload.refresh_token)
    if decoded.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provided token is not a refresh token.",
        )

    user_id = decoded.get("sub")
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer active or exists.",
        )

    token_claims = {
        "sub": user.id,
        "email": user.email,
        "org_id": decoded.get("org_id"),
        "workspace_id": decoded.get("workspace_id"),
        "role": decoded.get("role", "member"),
        "is_platform_admin": user.is_platform_admin,
    }
    new_access = create_access_token(token_claims)
    return {"access_token": new_access, "token_type": "bearer"}


@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    """Retrieve authenticated user identity and organization memberships."""
    user = await db.get(User, ctx.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    stmt = (
        select(OrganizationMembership, Organization)
        .join(Organization, Organization.id == OrganizationMembership.org_id)
        .where(OrganizationMembership.user_id == user.id)
    )
    res = await db.execute(stmt)
    memberships = [
        {
            "org_id": org.id,
            "org_name": org.name,
            "org_slug": org.slug,
            "role": mem.role,
        }
        for mem, org in res.all()
    ]

    return UserProfileResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_platform_admin=user.is_platform_admin,
        memberships=memberships,
    )
