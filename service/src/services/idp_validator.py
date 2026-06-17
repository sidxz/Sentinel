"""IdP token validator — validates tokens from external identity providers.

Supports:
- Google OIDC (JWT with JWKS verification)
- EntraID OIDC (JWT with JWKS verification)
- GitHub OAuth (opaque token validated via API calls)
"""

from __future__ import annotations

import base64
import os
import time
from typing import Any

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from jwt.algorithms import RSAAlgorithm

from src.config import settings
from src.services.auth_service import is_email_verified_claim

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


def _load_pem_pubkey(raw: str):
    """Load an RSA public key from raw PEM or base64-encoded PEM (rig env convenience)."""
    pem = raw if "BEGIN" in raw else base64.b64decode(raw).decode()
    return serialization.load_pem_public_key(pem.encode())


def _register_test_provider() -> None:
    """Register a gated, static-key 'test_oidc' enrichment provider when the rig env var
    ``TEST_TRUSTED_ISSUER_PUBKEY`` is set. UNSET (prod default) => not registered =>
    /authz/resolve returns 'Unsupported provider' (fail closed). Validates exactly like a real
    OIDC provider (signature + issuer + audience + email_verified + nonce) but against a
    statically-configured public key instead of a fetched JWKS — the seam used by the Layer-2
    trust-boundary pentest to present validly-signed-but-malicious-claim tokens.

    Read from os.environ (not Settings) on purpose: a test-only hook must NOT enter the prod
    config surface (e.g. /admin/system/settings). Mirrors the existing out-of-band
    ``_override_key`` test hook. Pubkey may be raw PEM or base64-encoded PEM."""
    raw = os.getenv("TEST_TRUSTED_ISSUER_PUBKEY", "").strip()
    if not raw:
        _PROVIDER_CONFIG.pop("test_oidc", None)
        return
    _PROVIDER_CONFIG["test_oidc"] = {
        "static_pubkey": raw,
        "issuer": os.getenv("TEST_TRUSTED_ISSUER", ""),
        "audience": os.getenv("TEST_TRUSTED_AUDIENCE", ""),
    }


_register_test_provider()

# ---------------------------------------------------------------------------
# JWKS cache (with TTL)
# ---------------------------------------------------------------------------

_JWKS_CACHE_TTL = 3600  # 1 hour — Google rotates keys roughly every 6 hours

_jwks_cache: dict[str, tuple[list[dict], float]] = {}


async def _fetch_jwks(provider: str) -> list[dict]:
    """Fetch and cache JWKS public keys for the given OIDC provider."""
    cached = _jwks_cache.get(provider)
    if cached:
        keys, fetched_at = cached
        if time.monotonic() - fetched_at < _JWKS_CACHE_TTL:
            return keys

    config = _PROVIDER_CONFIG[provider]
    jwks_uri = config["jwks_uri"]
    if callable(jwks_uri):
        jwks_uri = jwks_uri()

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(jwks_uri)
        resp.raise_for_status()
        keys = resp.json()["keys"]

    _jwks_cache[provider] = (keys, time.monotonic())
    return keys


# ---------------------------------------------------------------------------
# OIDC token validation (Google / EntraID)
# ---------------------------------------------------------------------------


async def _validate_oidc_token(
    idp_token: str,
    provider: str,
    *,
    expected_nonce: str | None = None,
    _override_key: Any | None = None,
) -> dict[str, Any]:
    """Validate an OIDC JWT and return normalised claims."""
    config = _PROVIDER_CONFIG[provider]
    static_pubkey = config.get("static_pubkey")

    if static_pubkey is not None:
        # Gated test provider — verify the signature against a statically-configured public
        # key, but enforce issuer + audience (and the shared email_verified / nonce checks
        # below) exactly like a real OIDC provider.
        audience = (
            config["audience"]() if callable(config["audience"]) else config["audience"]
        )
        issuer = config["issuer"]() if callable(config["issuer"]) else config["issuer"]
        try:
            payload = jwt.decode(
                idp_token,
                _load_pem_pubkey(static_pubkey),
                algorithms=["RS256"],
                audience=audience,
                issuer=issuer,
            )
        except jwt.ExpiredSignatureError:
            raise IdpValidationError("Token expired")
        except jwt.PyJWTError as exc:
            raise IdpValidationError(f"Invalid token: {exc}")
    elif _override_key is not None:
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

    # Require verified email — strict True (rejects stringified "true"/"false" from buggy IdPs)
    if not is_email_verified_claim(payload):
        raise IdpValidationError("Email not verified")

    # Replay protection: if caller supplied a nonce, require the IdP token to carry it.
    if expected_nonce is not None and payload.get("nonce") != expected_nonce:
        raise IdpValidationError("Nonce mismatch")

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
    # Fail closed if GitHub IdP isn't configured for this deployment — without
    # client credentials we cannot verify the token was issued to Sentinel's
    # OAuth app, so we cannot trust the token at all.
    if not settings.github_client_id or not settings.github_client_secret:
        raise IdpValidationError("GitHub IdP not configured on this deployment")

    headers = {
        "Authorization": f"Bearer {idp_token}",
        "Accept": "application/vnd.github+json",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        # App-binding check: GitHub access tokens are opaque and `/user`
        # authenticates the underlying user regardless of which OAuth app
        # holds the token. Without this step, any token from an
        # attacker-registered OAuth app that the victim consented to can be
        # replayed to impersonate the victim against Sentinel. The
        # `/applications/{client_id}/token` endpoint authenticates as the
        # OAuth app (HTTP Basic with client_id:client_secret) and returns 200
        # only when the submitted token was issued to *that* app; 404
        # otherwise. This is the OIDC `aud` equivalent for opaque tokens.
        binding_resp = await client.post(
            f"https://api.github.com/applications/{settings.github_client_id}/token",
            auth=(settings.github_client_id, settings.github_client_secret),
            headers={"Accept": "application/vnd.github+json"},
            json={"access_token": idp_token},
        )
        if binding_resp.status_code != 200:
            raise IdpValidationError("GitHub token was not issued to this application")

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
    expected_nonce: str | None = None,
    _override_key: Any | None = None,
) -> dict[str, Any]:
    """Validate an IdP token and return normalised user claims.

    Parameters
    ----------
    idp_token:
        The raw token string (JWT for OIDC providers, opaque for GitHub).
    provider:
        One of ``"google"``, ``"entra_id"``, ``"github"``.
    expected_nonce:
        If provided (OIDC providers only), require the token's ``nonce``
        claim to match this value. Ignored for GitHub (opaque token).
    _override_key:
        **Test hook** — when provided, uses this key instead of fetching JWKS
        and skips audience/issuer verification.

    Returns
    -------
    dict with keys: ``sub``, ``email``, ``name``, ``email_verified``, ``picture``.

    Raises
    ------
    IdpValidationError
        If the token is invalid, expired, the email is not verified, or the
        nonce claim does not match ``expected_nonce``.
    """
    if provider in _PROVIDER_CONFIG:
        return await _validate_oidc_token(
            idp_token,
            provider,
            expected_nonce=expected_nonce,
            _override_key=_override_key,
        )
    elif provider == "github":
        return await _validate_github_token(idp_token)
    else:
        raise IdpValidationError(f"Unsupported provider: {provider}")
