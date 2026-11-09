"""Unit Tests for Authentication and JWT Tokens."""

from datetime import timedelta
import pytest
from fastapi import HTTPException
from apps.api.src.core.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hashing_and_verification():
    plain = "SuperSecurePassword123!"
    hashed = hash_password(plain)
    assert hashed != plain
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_access_token_creation_and_decoding():
    payload = {
        "sub": "user-uuid-1234",
        "email": "analyst@security.org",
        "org_id": "org-uuid-5678",
        "workspace_id": "ws-uuid-9999",
        "role": "admin",
    }
    token = create_access_token(payload, expires_delta=timedelta(minutes=15))
    assert isinstance(token, str)

    decoded = decode_token(token)
    assert decoded["sub"] == "user-uuid-1234"
    assert decoded["email"] == "analyst@security.org"
    assert decoded["org_id"] == "org-uuid-5678"
    assert decoded["role"] == "admin"
    assert decoded["type"] == "access"


def test_jwt_expired_token_raises_401():
    payload = {"sub": "user-123"}
    # Token expired 10 minutes ago
    token = create_access_token(payload, expires_delta=timedelta(minutes=-10))
    with pytest.raises(HTTPException) as exc:
        decode_token(token)
    assert exc.value.status_code == 401
    assert "expired" in exc.value.detail


def test_jwt_invalid_token_raises_401():
    with pytest.raises(HTTPException) as exc:
        decode_token("completely.invalid.jwt-token-string")
    assert exc.value.status_code == 401
