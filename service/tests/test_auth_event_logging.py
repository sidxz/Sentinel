"""Tests: auth.* security events are emitted at the correct call sites.

Covers:
- auth.token.reuse_detected (outcome=failure, reason=refresh_reuse) on replay
- auth.token.refreshed (outcome=success) on successful rotation
"""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from structlog.testing import capture_logs

from src.services import auth_service


# ---------------------------------------------------------------------------
# Temp keypair fixture — avoids requiring keys/ on disk in every environment
# ---------------------------------------------------------------------------


def _write_keypair(tmp_path: Path) -> tuple[Path, Path]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    pub = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    priv_path = tmp_path / "private.pem"
    pub_path = tmp_path / "public.pem"
    priv_path.write_bytes(priv)
    pub_path.write_bytes(pub)
    return priv_path, pub_path


@pytest.fixture(autouse=True)
def _ephemeral_keys(tmp_path, monkeypatch):
    """Swap JWT key paths for temp files so tests don't depend on keys/ dir."""
    from src.auth import key_provider
    from src.config import settings

    priv_path, pub_path = _write_keypair(tmp_path)
    monkeypatch.setattr(settings, "jwt_private_key_path", priv_path)
    monkeypatch.setattr(settings, "jwt_public_key_path", pub_path)
    key_provider.reset_cache()
    yield
    key_provider.reset_cache()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_user() -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    user.name = "Test User"
    user.is_active = True
    user.is_admin = False
    user.organization_id = None
    return user


def _fake_db_for_rotate(user, workspace_id) -> MagicMock:
    """Mock DB that lets ``rotate_refresh_token`` progress past its queries."""
    workspace = MagicMock()
    workspace.id = workspace_id
    workspace.slug = "test-ws"

    membership = MagicMock()
    membership.role = "editor"

    db = MagicMock()
    db.get = AsyncMock(side_effect=[user, workspace])

    membership_result = MagicMock()
    membership_result.scalar_one_or_none.return_value = membership

    # workspace_allows_org: empty allowed-org set => open workspace
    allows_org_scalars = MagicMock()
    allows_org_scalars.all.return_value = []
    allows_org_result = MagicMock()
    allows_org_result.scalars.return_value = allows_org_scalars

    groups_result = MagicMock()
    groups_result.all.return_value = []
    db.execute = AsyncMock(
        side_effect=[membership_result, allows_org_result, groups_result]
    )
    return db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_reuse_emits_reuse_detected_event():
    """Replaying a consumed refresh token must emit auth.token.reuse_detected
    with outcome=failure and reason=refresh_reuse.
    """
    from src.auth.jwt import create_refresh_token

    user = _fake_user()
    family_id = str(uuid.uuid4())
    refresh_token = create_refresh_token(user_id=user.id, family_id=family_id)

    db = MagicMock()

    async def fake_consume_none(_jti):
        # Simulate an already-consumed token.
        return None

    async def fake_revoke_family(_fid):
        pass

    with (
        patch(
            "src.services.auth_service.token_service.consume_refresh_token",
            new=fake_consume_none,
        ),
        patch(
            "src.services.auth_service.token_service.revoke_token_family",
            new=fake_revoke_family,
        ),
        capture_logs() as logs,
    ):
        with pytest.raises(ValueError, match="already used or expired"):
            await auth_service.rotate_refresh_token(db, refresh_token)

    security_events = [e for e in logs if e.get("event") == "auth.token.reuse_detected"]
    assert security_events, (
        "Expected auth.token.reuse_detected to be logged on refresh token reuse, "
        "but no such event was found."
    )
    evt = security_events[0]
    assert evt["outcome"] == "failure"
    assert evt["reason"] == "refresh_reuse"
    assert evt["category"] == "security"
    # actor should be the user id from the JWT sub claim
    assert evt.get("actor") == str(user.id)


@pytest.mark.asyncio
async def test_successful_refresh_emits_token_refreshed_event():
    """A successful refresh token rotation must emit auth.token.refreshed
    with outcome=success.
    """
    from src.auth.jwt import create_refresh_token

    user = _fake_user()
    workspace_id = uuid.uuid4()
    family_id = str(uuid.uuid4())
    refresh_token = create_refresh_token(user_id=user.id, family_id=family_id)

    db = _fake_db_for_rotate(user, workspace_id)

    async def fake_consume(_jti):
        return (user.id, family_id, workspace_id, None)

    async def fake_store(**_kwargs):
        pass

    with (
        patch(
            "src.services.auth_service.token_service.consume_refresh_token",
            new=fake_consume,
        ),
        patch(
            "src.services.auth_service.token_service.store_refresh_token",
            new=fake_store,
        ),
        capture_logs() as logs,
    ):
        result = await auth_service.rotate_refresh_token(db, refresh_token)

    assert "access_token" in result
    security_events = [e for e in logs if e.get("event") == "auth.token.refreshed"]
    assert security_events, (
        "Expected auth.token.refreshed to be logged on successful token rotation, "
        "but no such event was found."
    )
    evt = security_events[0]
    assert evt["outcome"] == "success"
    assert evt["category"] == "security"
    assert evt.get("actor") == str(user.id)
