"""Async HTTP client for checking permissions against the identity service."""

import uuid
from dataclasses import dataclass

import httpx


@dataclass
class PermissionCheck:
    service_name: str
    resource_type: str
    resource_id: uuid.UUID
    action: str  # 'view' | 'edit'


@dataclass
class PermissionResult:
    service_name: str
    resource_type: str
    resource_id: uuid.UUID
    action: str
    allowed: bool


class PermissionClient:
    """Client for the identity service's permission API."""

    def __init__(
        self, base_url: str, service_name: str, service_key: str | None = None
    ):
        self.base_url = base_url.rstrip("/")
        self.service_name = service_name
        self.service_key = service_key
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=5.0)

    def _headers(self, token: str | None = None) -> dict[str, str]:
        """Build request headers with service key and optional user JWT."""
        h: dict[str, str] = {}
        if self.service_key:
            h["X-Service-Key"] = self.service_key
        if token:
            h["Authorization"] = f"Bearer {token}"
        return h

    async def check(
        self,
        token: str,
        checks: list[PermissionCheck],
    ) -> list[PermissionResult]:
        """Batch check permissions. Pass the user's JWT as the token."""
        response = await self._client.post(
            "/permissions/check",
            headers=self._headers(token),
            json={
                "checks": [
                    {
                        "service_name": c.service_name,
                        "resource_type": c.resource_type,
                        "resource_id": str(c.resource_id),
                        "action": c.action,
                    }
                    for c in checks
                ]
            },
        )
        response.raise_for_status()
        data = response.json()
        return [
            PermissionResult(
                service_name=r["service_name"],
                resource_type=r["resource_type"],
                resource_id=uuid.UUID(r["resource_id"]),
                action=r["action"],
                allowed=r["allowed"],
            )
            for r in data["results"]
        ]

    async def can(
        self,
        token: str,
        resource_type: str,
        resource_id: uuid.UUID,
        action: str,
    ) -> bool:
        """Convenience: check a single permission."""
        results = await self.check(
            token,
            [PermissionCheck(self.service_name, resource_type, resource_id, action)],
        )
        return results[0].allowed if results else False

    async def register_resource(
        self,
        resource_type: str,
        resource_id: uuid.UUID,
        workspace_id: uuid.UUID,
        owner_id: uuid.UUID,
        visibility: str = "workspace",
    ) -> dict:
        """Register a new resource (service-key only, no user JWT needed)."""
        response = await self._client.post(
            "/permissions/register",
            headers=self._headers(),
            json={
                "service_name": self.service_name,
                "resource_type": resource_type,
                "resource_id": str(resource_id),
                "workspace_id": str(workspace_id),
                "owner_id": str(owner_id),
                "visibility": visibility,
            },
        )
        response.raise_for_status()
        return response.json()

    async def accessible(
        self,
        token: str,
        resource_type: str,
        action: str,
        workspace_id: uuid.UUID,
        limit: int | None = None,
    ) -> tuple[list[uuid.UUID], bool]:
        """Lookup accessible resource IDs for the current user.

        Returns (resource_ids, has_full_access). When has_full_access is True
        and no limit was set, resource_ids is empty — the caller should skip
        filtering entirely.
        """
        payload: dict = {
            "service_name": self.service_name,
            "resource_type": resource_type,
            "action": action,
            "workspace_id": str(workspace_id),
        }
        if limit is not None:
            payload["limit"] = limit
        response = await self._client.post(
            "/permissions/accessible",
            headers=self._headers(token),
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return (
            [uuid.UUID(rid) for rid in data["resource_ids"]],
            data["has_full_access"],
        )

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
