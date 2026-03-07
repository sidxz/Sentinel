"""IdP token validator — validates tokens from external identity providers.

Supports:
- Google OIDC (JWT with JWKS verification)
- EntraID OIDC (JWT with JWKS verification)
- GitHub OAuth (opaque token validated via API calls)
"""

from __future__ import annotations

from typing import Any

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm

from src.config import settings

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class IdpValidationError(Exception):
    """Raised when an IdP token fails validation."""


# ---------------------------------------------------------------------------
# Provider configuration (OIDC only — GitHub is handled separately)
# ---------------------------------------------------------------------------

_PROVIDER_CONFIG: dict[str, dict[str, Any]] = {
    "google": {
        "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs",
        "issuer": "https://accounts.google.com",
        "audience": lambda: settings.google_client_id,
    },
    "entra_id": {
        "jwks_uri": lambda: (
            f"https://login.microsoftonline.com/{settings.entra_tenant_id}"
            f"/discovery/v2.0/keys"
        ),
        "issuer": lambda: (
            f"https://login.microsoftonline.com/{settings.entra_tenant_id}/v2.0"
        ),
        "audience": lambda: settings.entra_client_id,
    },
}

# ---------------------------------------------------------------------------
# JWKS cache
# ---------------------------------------------------------------------------

_jwks_cache: dict[str, list[dict]] = {}


async def _fetch_jwks(provider: str) -> list[dict]:
    """Fetch and cache JWKS public keys for the given OIDC provider."""
    if provider in _jwks_cache:
        return _jwks_cache[provider]

    config = _PROVIDER_CONFIG[provider]
    jwks_uri = config["jwks_uri"]
    if callable(jwks_uri):
        jwks_uri = jwks_uri()

    async with httpx.AsyncClient() as client:
        resp = await client.get(jwks_uri)
        resp.raise_for_status()
        keys = resp.json()["keys"]

    _jwks_cache[provider] = keys
    return keys


def clear_jwks_cache() -> None:
    """Clear the cached JWKS keys (useful for key rotation)."""
    _jwks_cache.clear()


# ---------------------------------------------------------------------------
# OIDC token validation (Google / EntraID)
# ---------------------------------------------------------------------------


async def _validate_oidc_token(
    idp_token: str,
    provider: str,
    *,
    _override_key: Any | None = None,
) -> dict[str, Any]:
    """Validate an OIDC JWT and return normalised claims."""
    config = _PROVIDER_CONFIG[provider]

    if _override_key is not None:
        # Test mode — skip audience/issuer verification, use supplied key
        try:
            payload = jwt.decode(
                idp_token,
                _override_key,
                algorithms=["RS256"],
                options={
                    "verify_aud": False,
                    "verify_iss": False,
                },
            )
        except jwt.ExpiredSignatureError:
            raise IdpValidationError("Token expired")
        except jwt.PyJWTError as exc:
            raise IdpValidationError(f"Invalid token: {exc}")
    else:
        audience = config["audience"]
        if callable(audience):
            audience = audience()
        issuer = config["issuer"]
        if callable(issuer):
            issuer = issuer()

        jwks = await _fetch_jwks(provider)

        payload = None
        last_error: Exception | None = None
        for key_data in jwks:
            public_key = RSAAlgorithm.from_jwk(key_data)
            try:
                payload = jwt.decode(
                    idp_token,
                    public_key,
                    algorithms=["RS256"],
                    audience=audience,
                    issuer=issuer,
                )
                break  # successfully decoded
            except jwt.ExpiredSignatureError:
                # Don't try other keys — the token is definitively expired
                raise IdpValidationError("Token expired")
            except jwt.PyJWTError as exc:
                last_error = exc
                continue

        if payload is None:
            raise IdpValidationError(
                f"Invalid token: {last_error}" if last_error else "Invalid token"
            )

    # Require verified email
    if not payload.get("email_verified", False):
        raise IdpValidationError("Email not verified")

    return {
        "sub": payload["sub"],
        "email": payload["email"],
        "name": payload.get("name", ""),
        "email_verified": payload.get("email_verified", False),
        "picture": payload.get("picture"),
    }


# ---------------------------------------------------------------------------
# GitHub token validation (opaque OAuth token → API calls)
# ---------------------------------------------------------------------------


async def _validate_github_token(idp_token: str) -> dict[str, Any]:
    """Validate a GitHub OAuth token via the GitHub API."""
    headers = {
        "Authorization": f"Bearer {idp_token}",
        "Accept": "application/vnd.github+json",
    }

    async with httpx.AsyncClient() as client:
        # Fetch user profile
        profile_resp = await client.get("https://api.github.com/user", headers=headers)
        if profile_resp.status_code != 200:
            raise IdpValidationError("Invalid GitHub token")
        profile = profile_resp.json()

        # Fetch user emails
        emails_resp = await client.get(
            "https://api.github.com/user/emails", headers=headers
        )
        if emails_resp.status_code != 200:
            raise IdpValidationError("Could not fetch GitHub emails")
        emails = emails_resp.json()

    # Find the primary verified email
    primary_email = None
    for entry in emails:
        if entry.get("primary") and entry.get("verified"):
            primary_email = entry["email"]
            break

    if primary_email is None:
        raise IdpValidationError("Email not verified")

    return {
        "sub": f"github|{profile['id']}",
        "email": primary_email,
        "name": profile.get("name") or profile.get("login", ""),
        "email_verified": True,
        "picture": profile.get("avatar_url"),
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def validate_idp_token(
    idp_token: str,
    provider: str,
    *,
    _override_key: Any | None = None,
) -> dict[str, Any]:
    """Validate an IdP token and return normalised user claims.

    Parameters
    ----------
    idp_token:
        The raw token string (JWT for OIDC providers, opaque for GitHub).
    provider:
        One of ``"google"``, ``"entra_id"``, ``"github"``.
    _override_key:
        **Test hook** — when provided, uses this key instead of fetching JWKS
        and skips audience/issuer verification.

    Returns
    -------
    dict with keys: ``sub``, ``email``, ``name``, ``email_verified``, ``picture``.

    Raises
    ------
    IdpValidationError
        If the token is invalid, expired, or the email is not verified.
    """
    if provider in _PROVIDER_CONFIG:
        return await _validate_oidc_token(
            idp_token, provider, _override_key=_override_key
        )
    elif provider == "github":
        return await _validate_github_token(idp_token)
    else:
        raise IdpValidationError(f"Unsupported provider: {provider}")
