# Auth Endpoints

> **Tip:** For interactive API exploration, visit `/docs` (Swagger UI) when the service is running.

The auth endpoints handle OAuth2/OIDC login flows, token refresh, logout, and admin authentication. All routes are under the `/auth` prefix.

## Endpoints Overview

| Method | Path | Auth | Rate Limit | Description |
|---|---|---|---|---|
| `GET` | `/auth/providers` | None | -- | List configured OAuth providers |
| `GET` | `/auth/login/{provider}` | None | 10/min | Redirect to OAuth provider login |
| `GET` | `/auth/callback/{provider}` | None | 10/min | Handle OAuth callback |
| `GET` | `/auth/workspaces` | None | 10/min | List workspaces for auth code |
| `POST` | `/auth/token` | None | 10/min | Exchange auth code for JWT tokens |
| `POST` | `/auth/refresh` | None | 10/min | Refresh access token |
| `POST` | `/auth/logout` | JWT | -- | Logout and blacklist access token |
| `GET` | `/auth/admin/login/{provider}` | None | 5/min | Redirect to OAuth provider for admin login |
| `GET` | `/auth/admin/callback/{provider}` | None | 5/min | Handle admin OAuth callback |
| `GET` | `/auth/admin/me` | Admin Cookie | -- | Get current admin user info |
| `POST` | `/auth/admin/logout` | None | -- | Clear admin session cookie |

---

## User Auth

### List Providers

Returns the list of configured OAuth providers (e.g., `google`, `github`, `entraid`).

```
GET /auth/providers
```

**Response** `200 OK`

```json
{
  "providers": ["google", "github"]
}
```

**Response Schema:** [ProviderListResponse](schemas.md#providerlistresponse)

---

### Login

Initiates the OAuth2 authorization flow by redirecting the user to the selected provider's consent screen. The `redirect_uri` must be registered on an active client app in the allowlist.

```
GET /auth/login/{provider}?redirect_uri=Y
```

| Parameter | In | Type | Required | Description |
|---|---|---|---|---|
| `provider` | path | string | Yes | OAuth provider name (e.g., `google`, `github`) |
| `redirect_uri` | query | string | Yes | Redirect URI (must be registered on an active client app) |

**Response** `302 Found` -- Redirects to the provider's authorization URL.

**Errors:**

| Code | Detail |
|---|---|
| `400` | `Provider '{provider}' is not configured` |
| `400` | `redirect_uri is not registered for any active app` |
| `429` | Rate limit exceeded |

---

### Callback

Handles the OAuth callback after the user authorizes with the provider. Extracts user profile information, creates or updates the user record, generates a single-use authorization code, and redirects to the client's registered redirect URI.

```
GET /auth/callback/{provider}
```

| Parameter | In | Type | Required | Description |
|---|---|---|---|---|
| `provider` | path | string | Yes | OAuth provider name |

**Response** `302 Found` -- Redirects to `{redirect_uri}?code={authorization_code}`.

The authorization code is a short-lived (5 minute), single-use token stored in Redis. The client uses it to fetch workspaces and exchange for JWT tokens.

**Errors:**

| Code | Detail |
|---|---|
| `400` | `Provider '{provider}' is not configured` |
| `400` | `Missing redirect_uri in session` |
| `400` | `redirect_uri is no longer registered for any active app` |
| `429` | Rate limit exceeded |

---

### List Workspaces (Auth Code)

Lists the workspaces a user belongs to, resolved from an authorization code. Used during the login flow for workspace selection.

```
GET /auth/workspaces?code=X
```

| Parameter | In | Type | Required | Description |
|---|---|---|---|---|
| `code` | query | string | Yes | Authorization code from the OAuth callback |

**Response** `200 OK`

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "My Workspace",
    "slug": "my-workspace",
    "role": "admin"
  }
]
```

**Errors:**

| Code | Detail |
|---|---|
| `400` | `Invalid or expired authorization code` |
| `404` | `User not found` |
| `429` | Rate limit exceeded |

---

### Exchange Token

Exchanges a single-use authorization code and workspace selection for JWT tokens. The authorization code is consumed atomically and cannot be reused.

```
POST /auth/token
```

**Request Body:**

```json
{
  "code": "authorization_code_from_callback",
  "workspace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response** `200 OK` -- [TokenResponse](schemas.md#tokenresponse)

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "refresh_token": "refresh_token_value...",
  "token_type": "bearer",
  "expires_in": 900
}
```

**Errors:**

| Code | Detail |
|---|---|
| `400` | `Invalid or expired authorization code` |
| `403` | User is not a member of the workspace |
| `404` | `User not found` / `Workspace not found` |
| `429` | Rate limit exceeded |

**curl example:**

```bash
curl -X POST http://localhost:9003/auth/token \
  -H "Content-Type: application/json" \
  -d '{"code": "your_auth_code", "workspace_id": "your_workspace_id"}'
```

---

### Refresh Token

Exchanges a valid refresh token for a new access/refresh token pair. The old refresh token is invalidated (rotation with reuse detection).

```
POST /auth/refresh
```

**Request Body:** [RefreshRequest](schemas.md#refreshrequest)

```json
{
  "refresh_token": "dGhpcyBpcyBhIHJlZnJlc2ggdG9rZW4..."
}
```

**Response** `200 OK` -- [TokenResponse](schemas.md#tokenresponse)

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "refresh_token": "new_refresh_token_value...",
  "token_type": "bearer",
  "expires_in": 900
}
```

**Errors:**

| Code | Detail |
|---|---|
| `401` | Invalid or expired refresh token, or reuse detected |
| `429` | Rate limit exceeded |

**curl example:**

```bash
curl -X POST http://localhost:9003/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "your_refresh_token_here"}'
```

---

### Logout

Blacklists the current access token (via its `jti` claim) in Redis so it cannot be reused for the remainder of its TTL.

```
POST /auth/logout
```

**Auth:** JWT Bearer token required.

**Response** `200 OK`

```json
{
  "ok": true
}
```

**curl example:**

```bash
curl -X POST http://localhost:9003/auth/logout \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..."
```

---

## Admin Auth

Admin authentication uses a separate OAuth flow that sets an HttpOnly cookie instead of returning JWT tokens. Only users with `is_admin=True` can complete admin login.

### Admin Login

```
GET /auth/admin/login/{provider}
```

Initiates the admin OAuth flow. Redirects to the provider's consent screen with a callback URL pointing to `/auth/admin/callback/{provider}`.

| Parameter | In | Type | Required | Description |
|---|---|---|---|---|
| `provider` | path | string | Yes | OAuth provider name |

**Response** `302 Found` -- Redirects to provider authorization URL.

---

### Admin Callback

```
GET /auth/admin/callback/{provider}
```

Handles the admin OAuth callback. If the authenticated user has `is_admin=True`, an `admin_token` cookie is set and the user is redirected to the admin panel. Non-admin users are redirected to the login page with an error.

**Response** `302 Found` -- Redirects to `{ADMIN_URL}/` with `admin_token` cookie set (on success), or `{ADMIN_URL}/login?error=not_admin` (on failure).

---

### Admin Me

```
GET /auth/admin/me
```

Returns the current admin user's identity from the admin cookie.

**Auth:** `admin_token` cookie required.

**Response** `200 OK`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "admin@example.com",
  "name": "Admin User"
}
```

---

### Admin Logout

```
POST /auth/admin/logout
```

Clears the `admin_token` cookie.

**Response** `200 OK`

```json
{
  "ok": true
}
```
