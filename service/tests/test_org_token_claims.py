"""Org claims (oid/oslug/opub) on access + authz tokens."""

import uuid

from src.auth.jwt import (
    _AUD_ACCESS,
    create_access_token,
    decode_token,
)


def test_access_token_carries_org_claims():
    org_id = uuid.uuid4()
    token = create_access_token(
        user_id=uuid.uuid4(),
        email="alice@tamu.edu",
        name="Alice",
        workspace_id=uuid.uuid4(),
        workspace_slug="acme",
        workspace_role="editor",
        groups=[],
        org_id=str(org_id),
        org_slug="tamu",
        org_is_public=False,
    )
    payload = decode_token(token, audience=_AUD_ACCESS)
    assert payload["oid"] == str(org_id)
    assert payload["oslug"] == "tamu"
    assert payload["opub"] is False


def test_access_token_public_org_flag():
    token = create_access_token(
        user_id=uuid.uuid4(),
        email="bob@gmail.com",
        name="Bob",
        workspace_id=uuid.uuid4(),
        workspace_slug="acme",
        workspace_role="viewer",
        groups=[],
        org_id=str(uuid.uuid4()),
        org_slug="public",
        org_is_public=True,
    )
    payload = decode_token(token, audience=_AUD_ACCESS)
    assert payload["opub"] is True
