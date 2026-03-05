# API Reference

> **Tip:** For interactive API exploration, visit `/docs` (Swagger UI) when the service is running.

This is the complete API reference for the Daikon Identity Service. All endpoints are documented with their authentication requirements, request/response schemas, and usage examples.

## Base URL

| Environment | URL |
|---|---|
| Development | `http://localhost:9003` |
| Production | Set via `BASE_URL` environment variable |

## Authentication Methods

The API uses four authentication tiers depending on the endpoint group:

| Endpoint Group | Auth Method | Route Prefix | Description |
|---|---|---|---|
| Auth | None / JWT | `/auth` | OAuth login flows (public) and logout (JWT) |
| Users | JWT (Bearer token) | `/users` | Current user profile management |
| Workspaces | JWT (Bearer token) | `/workspaces` | Workspace CRUD and member management |
| Groups | JWT (Bearer token) | `/workspaces/{id}/groups` | Group CRUD and membership |
| Permissions | Service Key [+ JWT] | `/permissions` | Resource permission checks and ACL management |
| Roles | Service Key [+ JWT] | `/roles` | RBAC action registration and checks |
| Admin | Admin Cookie | `/admin` | Admin panel backend endpoints |

### JWT Bearer Token

Include the access token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

### Service Key

Include the service API key in the `X-Service-Key` header. Some permission endpoints also require a JWT alongside the service key (dual auth):

```
X-Service-Key: <your_service_key>
Authorization: Bearer <access_token>
```

### Admin Cookie

Admin endpoints authenticate via an `admin_token` cookie set during the admin OAuth login flow. This is an HttpOnly, Secure, SameSite=strict cookie.

## Rate Limits

The following rate limits are enforced per client IP:

| Endpoint | Limit |
|---|---|
| `GET /auth/login/{provider}` | 10 requests/minute |
| `GET /auth/callback/{provider}` | 10 requests/minute |
| `POST /auth/refresh` | 10 requests/minute |
| `GET /auth/admin/login/{provider}` | 5 requests/minute |
| `GET /auth/admin/callback/{provider}` | 5 requests/minute |

When a rate limit is exceeded, the API returns `429 Too Many Requests`.

## Standard Error Format

All error responses follow a consistent JSON structure:

```json
{
  "detail": "error message"
}
```

Common HTTP status codes:

| Code | Meaning |
|---|---|
| `400` | Bad request (invalid input, misconfigured provider) |
| `401` | Unauthorized (missing or invalid token) |
| `403` | Forbidden (insufficient role or workspace mismatch) |
| `404` | Resource not found |
| `429` | Rate limit exceeded |
| `500` | Internal server error |

## API Sections

- [Auth](auth.md) -- OAuth login, token refresh, logout, and admin auth
- [Users](users.md) -- Current user profile retrieval and updates
- [Workspaces](workspaces.md) -- Workspace CRUD, member invitations, and role management
- [Groups](groups.md) -- Group CRUD and group membership
- [Permissions](permissions.md) -- Resource registration, permission checks, sharing, and ACLs
- [Roles](roles.md) -- RBAC action registration, action checks, and user action queries
- [Schemas](schemas.md) -- Consolidated reference for all request/response models
