"""Tests for the IdP token validator service."""

from __future__ import annotations

import time

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from src.services.idp_validator import IdpValidationError, validate_idp_token


# ---------------------------------------------------------------------------
# RSA keypair fixture (module-scoped — expensive to generate)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def rsa_keypair():
    """Generate an RSA keypair for signing test JWTs."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    return private_key, public_key


# ---------------------------------------------------------------------------
# Token helper fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def make_token(rsa_keypair):
    """Factory fixture that creates signed JWTs with given claims."""
    private_key, _ = rsa_keypair

    def _make(claims: dict, *, exp_offset: int = 3600) -> str:
        now = int(time.time())
        payload = {
            "iat": now,
            "exp": now + exp_offset,
            **claims,
        }
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return pyjwt.encode(payload, pem, algorithm="RS256")

    return _make


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_google_token(rsa_keypair, make_token):
    """A valid Google-style OIDC token returns normalised claims."""
    _, public_key = rsa_keypair

    token = make_token(
        {
            "sub": "google-user-123",
            "email": "user@example.com",
            "name": "Test User",
            "email_verified": True,
            "picture": "https://example.com/photo.jpg",
        }
    )

    result = await validate_idp_token(
        token, "google", _override_key=public_key
    )

    assert result["sub"] == "google-user-123"
    assert result["email"] == "user@example.com"
    assert result["name"] == "Test User"
    assert result["email_verified"] is True
    assert result["picture"] == "https://example.com/photo.jpg"


@pytest.mark.asyncio
async def test_expired_token_rejected(rsa_keypair, make_token):
    """An expired OIDC token raises IdpValidationError with 'expired'."""
    _, public_key = rsa_keypair

    token = make_token(
        {
            "sub": "google-user-123",
            "email": "user@example.com",
            "name": "Test User",
            "email_verified": True,
        },
        exp_offset=-3600,  # expired 1 hour ago
    )

    with pytest.raises(IdpValidationError, match="expired"):
        await validate_idp_token(token, "google", _override_key=public_key)


@pytest.mark.asyncio
async def test_unsupported_provider_rejected():
    """An unsupported provider raises IdpValidationError with 'Unsupported'."""
    with pytest.raises(IdpValidationError, match="Unsupported"):
        await validate_idp_token("some-token", "myspace")


@pytest.mark.asyncio
async def test_unverified_email_rejected(rsa_keypair, make_token):
    """An OIDC token with email_verified=False raises with 'not verified'."""
    _, public_key = rsa_keypair

    token = make_token(
        {
            "sub": "google-user-456",
            "email": "unverified@example.com",
            "name": "Unverified User",
            "email_verified": False,
        }
    )

    with pytest.raises(IdpValidationError, match="not verified"):
        await validate_idp_token(token, "google", _override_key=public_key)
