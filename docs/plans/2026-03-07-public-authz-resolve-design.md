# Public /authz/resolve with Origin-Based Auth — Design

## Goal

Allow browser frontends to call Sentinel's `/authz/resolve` directly using CORS origin validation instead of a service key, eliminating the backend proxy requirement for authz mode.

## Architecture

```
Browser (https://app.acme.com)              Sentinel
  │                                            │
  │ POST /authz/resolve                        │
  │ Origin: https://app.acme.com  ──────────►  │
  │ { idp_token, provider }                    │ 1. Match Origin → ServiceApp.allowed_origins
  │                                            │ 2. Validate IdP token
  │                                            │ 3. Return workspaces / authz JWT
  │ ◄────────────────────────────────────────  │
  │                                            │

Backend (service-to-service)                Sentinel
  │                                            │
  │ POST /authz/resolve                        │
  │ X-Service-Key: sk_...  ─────────────────►  │
  │ { idp_token, provider }                    │ 1. Validate service key (existing flow)
  │                                            │ 2. Validate IdP token
  │ ◄────────────────────────────────────────  │
```

## Changes

### 1. DB — ServiceApp model
Add `allowed_origins` (ARRAY of Text) to `service_apps` table. Empty by default.

### 2. Service layer
Add `validate_origin(origin, db)` to `service_app_service.py` — looks up origin across active service apps, returns `(service_name, app_id)` or None. Uses Redis cache.

### 3. API — /authz/resolve
Replace `require_service_key` with `require_service_context` that tries:
1. `X-Service-Key` header → existing key validation
2. No key → check `Origin` header against ServiceApp `allowed_origins`
3. Neither → 401

### 4. CORS middleware
Include ServiceApp `allowed_origins` in the dynamic CORS origin set alongside ClientApp redirect URIs.

### 5. Admin API + UI
Update service app CRUD to accept `allowed_origins`. Add origins field to admin UI form.

### 6. JS SDK
Replace `backendUrl` with `sentinelUrl` in `SentinelAuthzConfig`. `resolve()` calls Sentinel directly.

### 7. Demo frontend
Point `SentinelAuthz` at Sentinel URL instead of backend proxy.

## Security

- `Origin` header is enforced by browsers and cannot be forged in browser contexts
- Non-browser clients (curl, backends) must use `X-Service-Key`
- A valid IdP token is still required regardless of auth method
- Users can only see workspaces they are members of
- Same security model as Firebase, Supabase, Auth0 (public API key + origin restriction)
