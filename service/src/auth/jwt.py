import uuid
from datetime import UTC, datetime, timedelta

import jwt

from src.config import settings

_private_key: str | None = None
_public_key: str | None = None


def _get_private_key() -> str:
    global _private_key
    if _private_key is None:
        _private_key = settings.jwt_private_key_path.read_text()
    return _private_key


def _get_public_key() -> str:
    global _public_key
    if _public_key is None:
        _public_key = settings.jwt_public_key_path.read_text()
    return _public_key


def get_public_key() -> str:
    return _get_public_key()


def create_access_token(
    user_id: uuid.UUID,
    email: str,
    name: str,
    workspace_id: uuid.UUID,
    workspace_slug: str,
    workspace_role: str,
    groups: list[uuid.UUID],
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "email": email,
        "name": name,
        "wid": str(workspace_id),
        "wslug": workspace_slug,
        "wrole": workspace_role,
        "groups": [str(g) for g in groups],
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "type": "access",
    }
    return jwt.encode(payload, _get_private_key(), algorithm=settings.jwt_algorithm)


def create_admin_token(user_id: uuid.UUID, email: str, name: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "email": email,
        "name": name,
        "admin": True,
        "iat": now,
        "exp": now + timedelta(hours=8),
        "type": "admin_access",
    }
    return jwt.encode(payload, _get_private_key(), algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: uuid.UUID) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(days=settings.refresh_token_expire_days),
        "type": "refresh",
    }
    return jwt.encode(payload, _get_private_key(), algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(token, _get_public_key(), algorithms=[settings.jwt_algorithm])
