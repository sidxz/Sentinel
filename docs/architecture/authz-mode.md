# Sentinel Authorization Mode (AuthZ Mode)

## Overview

Sentinel operates in two modes. **AuthZ Mode** is the primary integration model. Full Proxy Mode is available for simpler deployments.

### AuthZ Mode (Primary)

Client apps authenticate users directly with their IdP (Google, GitHub, EntraID). Sentinel validates the IdP token server-to-server, provisions the user, and issues a **signed authorization JWT** containing workspace roles and RBAC actions. Sentinel never handles the OAuth redirect flow — the client does.

```
User → Client App → IdP (Google/GitHub/EntraID) → Client App has IdP token
                                                        │
                    POST /authz/resolve ────────────────▶│
                    { idp_token, provider, workspace_id } │
                                                         │
                    Sentinel validates IdP token ◀────────┘
                    against IdP's JWKS (server-to-server)
                    provisions user, resolves workspace
                    signs authz JWT (authorization only)
                                                         │
                    ◀── { authz_token, user }  ───────────┘

Client App holds two tokens:
  - IdP token     → proves identity (signed by Google/GitHub)
  - Authz token   → proves authorization (signed by Sentinel)

Downstream services validate BOTH:
  1. IdP token signature   (IdP's public key)
  2. Authz token signature (Sentinel's public key)
  3. Binding: idp_sub match between tokens
```

### Full Proxy Mode (Secondary)

Sentinel handles the entire OAuth flow — redirect, callback, token exchange, JWT issuance. Client apps redirect to Sentinel and receive a single JWT containing both identity and authorization claims. This is the simpler integration but couples the client to Sentinel's auth flow.

```
User → Client App → Sentinel → IdP → Sentinel → JWT → Client App
```

---

## Why AuthZ Mode Is Primary

### Security Properties

| Property | AuthZ Mode | Full Proxy Mode |
|---|---|---|
| Sentinel signing key compromise | Privilege escalation only (traceable) | Full identity forgery (invisible) |
| Attacker needs real IdP account? | Yes — cannot forge identity | No — can forge any identity |
| Attacker traceable? | Yes — real IdP identity in token | No — impersonates victim |
| Custom auth flow code in Sentinel | None | ~400 lines (CRITICAL) |
| Auth primitives (PKCE, refresh, codes) | Handled by IdP | Custom in Sentinel |

### Dual-Token Binding

The authz token contains an `idp_sub` claim that binds it to the IdP token:

```json
// IdP token (signed by Google)
{
  "sub": "google|789",
  "email": "alice@acme.com",
  "iss": "https://accounts.google.com"
}

// Authz token (signed by Sentinel)
{
  "idp_sub": "google|789",      // ← binds to IdP token
  "sub": "sentinel-user-uuid",
  "wid": "workspace-uuid",
  "wrole": "editor",
  "actions": ["read", "write", "reports:export"],
  "aud": "sentinel:authz",
  "exp": 1709856000
}
```

Validation requires:
1. IdP token valid (IdP's public key, not expired, correct audience)
2. Authz token valid (Sentinel's public key, not expired, `aud: sentinel:authz`)
3. `idp_sub` in authz token == `sub` in IdP token

Even if Sentinel's signing key is compromised, the attacker must authenticate with a real IdP account. They cannot impersonate another user — only escalate their own privileges. And their real identity is logged via the IdP token.

---

## API

### `POST /authz/resolve`

Validate an IdP token, provision the user, and return authorization context. Optionally issues a signed authz JWT for a specific workspace.

**Auth:** One of:

- `X-Service-Key` header — for backend-to-backend calls
- `Origin` header — for browser clients. The origin must match a registered service app's `allowed_origins`. No service key needed.

**Request:**
```json
{
  "idp_token": "eyJ...",
  "provider": "google",
  "workspace_id": "uuid (optional)"
}
```

**Response (with workspace_id):**
```json
{
  "user": {
    "id": "uuid",
    "email": "alice@acme.com",
    "name": "Alice"
  },
  "workspace": {
    "id": "uuid",
    "slug": "acme-corp",
    "role": "editor"
  },
  "authz_token": "eyJ...",
  "expires_in": 300
}
```

**Response (without workspace_id — workspace selection):**
```json
{
  "user": {
    "id": "uuid",
    "email": "alice@acme.com",
    "name": "Alice"
  },
  "workspaces": [
    { "id": "uuid", "name": "Acme Corp", "slug": "acme-corp", "role": "editor" },
    { "id": "uuid", "name": "Side Project", "slug": "side-project", "role": "owner" }
  ]
}
```

**Flow:**
1. Sentinel validates `idp_token` against the provider's JWKS (Google/GitHub/EntraID)
2. Extracts user identity (email, name, provider_user_id) from verified token
3. Finds or creates user in DB (JIT provisioning with IdP binding)
4. If `workspace_id` provided: resolves membership + RBAC actions, signs authz JWT
5. If no `workspace_id`: returns workspace list for client to select from

**Errors:**
- `401` — Invalid or missing service key
- `400` — Unsupported provider, invalid/expired IdP token
- `403` — User not a member of requested workspace
- `404` — User inactive

### Refreshing the authz token

To refresh an expiring authz token, call `POST /authz/resolve` again with the same IdP token and `workspace_id`. This re-validates the IdP token and issues a fresh authz JWT. The JS SDK handles this automatically via `autoRefresh`.

---

## Supported IdP Providers

AuthZ mode validates IdP tokens for configured providers only:

| Provider | Token Type | Validation Method |
|---|---|---|
| Google | OIDC ID token (JWT) | JWKS from `accounts.google.com/.well-known/openid-configuration` |
| EntraID | OIDC ID token (JWT) | JWKS from `login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration` |
| GitHub | OAuth access token (opaque) | Introspection via `api.github.com/user` + `/user/emails` |

Adding a new IdP requires configuring its JWKS URL (for OIDC) or introspection endpoint (for OAuth2) in Sentinel's settings.

---

## SDK Integration

### AuthZ Mode (Primary)

```python
from sentinel_auth import Sentinel

sentinel = Sentinel(
    base_url="http://localhost:9003",
    service_name="docustore",
    service_key="sk_...",
    mode="authz",                              # AuthZ mode
    idp_jwks_url="https://accounts.google.com/.well-known/jwks",  # IdP's public keys
)

app = FastAPI(lifespan=sentinel.lifespan)
sentinel.protect(app)  # Validates IdP token + authz token on each request

@app.get("/documents")
async def list_docs(auth: RequestAuth = Depends(sentinel.get_auth)):
    # auth.user is authenticated (IdP token verified)
    # auth.workspace_role is authorized (authz token verified)
    if await auth.can("document", doc_id, "edit"):
        ...
```

### Full Proxy Mode (Secondary)

```python
sentinel = Sentinel(
    base_url="http://localhost:9003",
    service_name="docustore",
    service_key="sk_...",
    # mode="proxy" is the default for backwards compatibility
)
```

---

## Comparison

| | AuthZ Mode | Full Proxy Mode |
|---|---|---|
| Client handles OIDC flow | Yes | No — Sentinel handles it |
| Sentinel holds signing key | Yes (authz only) | Yes (identity + authz) |
| Key compromise impact | Privilege escalation | Full impersonation |
| Tokens per request | 2 (IdP + authz) | 1 (Sentinel JWT) |
| Stateless validation | Yes (both tokens validated locally) | Yes (single JWT validated locally) |
| IdP flexibility | Client picks IdP independently | Must use Sentinel's configured providers |
| Mobile/CLI support | Native (any OIDC client works) | Requires browser redirect |
| Custom auth flow code | 0 lines | ~400 lines in Sentinel |
