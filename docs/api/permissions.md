# Permission Endpoints

Zanzibar-style resource ACLs. All routes under `/permissions`.

Two auth tiers:

- **Dual auth** -- `X-Service-Key` + Bearer JWT (or authz token). Service acts on behalf of a user.
- **Service-only** -- `X-Service-Key` only. Backend-to-backend operations.

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/permissions/register` | Service-only | Register a resource |
| POST | `/permissions/check` | Dual | Check permissions |
| POST | `/permissions/accessible` | Dual | List accessible resource IDs |
| POST | `/permissions/{id}/share` | Dual | Share a resource |
| DELETE | `/permissions/{id}/share` | Service-only | Revoke a share |
| PATCH | `/permissions/{id}/visibility` | Service-only | Update visibility |
| GET | `/permissions/resource/{svc}/{type}/{id}` | Service-only | Get resource ACL |

---

## POST /permissions/register

Registers a resource in the permission system. Call this when creating a resource in your service.

**Auth:** Service key only.

**Request Body:**

```json
{
  "service_name": "docu-store",
  "resource_type": "document",
  "resource_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
  "workspace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "owner_id": "550e8400-e29b-41d4-a716-446655440000",
  "visibility": "workspace"
}
```

`visibility`: `"private"` or `"workspace"` (default: `"workspace"`).

**Response:** `201 Created` -- `ResourcePermissionResponse`.

```bash
curl -X POST http://localhost:9003/permissions/register \
  -H "X-Service-Key: sk_your_key" \
  -H "Content-Type: application/json" \
  -d '{"service_name":"docu-store","resource_type":"document","resource_id":"c3d4e5f6-...","workspace_id":"a1b2c3d4-...","owner_id":"550e8400-..."}'
```

---

## POST /permissions/check

Batch-checks whether the user has specific permissions on resources. Evaluates ownership, workspace visibility, group shares, and direct user shares.

**Auth:** Dual (service key + JWT/authz token).

**Request Body:**

```json
{
  "checks": [
    {
      "service_name": "docu-store",
      "resource_type": "document",
      "resource_id": "c3d4e5f6-...",
      "action": "view"
    }
  ]
}
```

`action`: `"view"` or `"edit"`. Max 100 checks per request.

**Response:** `200 OK`

```json
{
  "results": [
    {
      "service_name": "docu-store",
      "resource_type": "document",
      "resource_id": "c3d4e5f6-...",
      "action": "view",
      "allowed": true
    }
  ]
}
```

```bash
curl -X POST http://localhost:9003/permissions/check \
  -H "X-Service-Key: sk_your_key" \
  -H "Authorization: Bearer eyJhbGciOi..." \
  -H "Content-Type: application/json" \
  -d '{"checks":[{"service_name":"docu-store","resource_type":"document","resource_id":"c3d4e5f6-...","action":"view"}]}'
```

---

## POST /permissions/accessible

Returns resource IDs the user can access. If the user's workspace role grants blanket access, `has_full_access` is `true` and `resource_ids` may be empty.

**Auth:** Dual.

**Request Body:**

```json
{
  "service_name": "docu-store",
  "resource_type": "document",
  "action": "view",
  "workspace_id": "a1b2c3d4-...",
  "limit": 100
}
```

`workspace_id` must match the JWT's workspace. `limit`: 1--10000, optional.

**Response:** `200 OK`

```json
{"resource_ids": ["c3d4e5f6-...", "d4e5f6a7-..."], "has_full_access": false}
```

**Errors:** `403` cross-workspace lookup.

---

## POST /permissions/{id}/share

Grants a user or group access to a resource. Caller must be the resource owner or a workspace admin/owner.

**Auth:** Dual.

**Request Body:**

```json
{
  "grantee_type": "user",
  "grantee_id": "660e8400-...",
  "permission": "view"
}
```

`grantee_type`: `"user"` or `"group"`. `permission`: `"view"` or `"edit"`.

**Response:** `201 Created` -- `{"status": "ok"}`.

```bash
curl -X POST http://localhost:9003/permissions/e5f6a7b8-.../share \
  -H "X-Service-Key: sk_your_key" \
  -H "Authorization: Bearer eyJhbGciOi..." \
  -H "Content-Type: application/json" \
  -d '{"grantee_type":"user","grantee_id":"660e8400-...","permission":"edit"}'
```

---

## DELETE /permissions/{id}/share

Revokes a share. Uses `grantee_type` and `grantee_id` to identify the share to remove.

**Auth:** Service key only.

**Request Body:**

```json
{
  "grantee_type": "user",
  "grantee_id": "660e8400-...",
  "permission": "view"
}
```

**Response:** `200 OK` -- `{"status": "ok"}`.

---

## PATCH /permissions/{id}/visibility

Changes resource visibility between `private` and `workspace`.

**Auth:** Service key only.

**Request Body:**

```json
{"visibility": "private"}
```

**Response:** `200 OK` -- `ResourcePermissionResponse`.

```bash
curl -X PATCH http://localhost:9003/permissions/e5f6a7b8-.../visibility \
  -H "X-Service-Key: sk_your_key" \
  -H "Content-Type: application/json" \
  -d '{"visibility":"private"}'
```

---

## GET /permissions/resource/{service_name}/{resource_type}/{resource_id}

Retrieves the full permission record including all shares.

**Auth:** Service key only.

**Response:** `200 OK` -- `ResourcePermissionResponse` with `shares` array.

**Errors:** `404` resource not found.

```bash
curl http://localhost:9003/permissions/resource/docu-store/document/c3d4e5f6-... \
  -H "X-Service-Key: sk_your_key"
```
