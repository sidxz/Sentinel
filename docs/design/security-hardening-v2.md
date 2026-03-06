# Security Hardening v2 — Design Notes

Date: 2026-03-05

Three security fixes applied based on penetration testing findings.
These address gaps that were **below industry baseline** for an authorization proxy.

---

## Fix 1: PKCE on Sentinel's Own Auth Code Flow

### Problem
Sentinel issues its own authorization codes as part of the OAuth proxy flow.
The code exchange (`POST /auth/token`) only required `{code, workspace_id}` —
no client proof. If a code leaked (referrer, logs, browser history), anyone
could exchange it for tokens.

Note: PKCE between Sentinel and the IdP (Google/EntraID) already existed.
This fix adds PKCE between **client apps and Sentinel**.

### Design
- `GET /auth/login/{provider}` now requires `code_challenge` (S256) and
  `code_challenge_method` query parameters. Both are stored in the session
  (which already persists through the OAuth round-trip).
- `GET /auth/callback/{provider}` pulls the challenge from the session and
  stores it alongside `{user_id, client_app_id}` in the auth code's Redis
  payload.
- `POST /auth/token` now requires `code_verifier` in the request body.
  Sentinel computes `BASE64URL(SHA256(code_verifier))` and compares it to
  the stored `code_challenge`. Mismatch → 400.
- PKCE is **mandatory** (not optional). We control all client apps and the SDK.

### Files Changed
- `service/src/services/auth_code_service.py` — `create_auth_code` accepts
  `code_challenge`/`code_challenge_method`; new `verify_code_challenge()` helper
- `service/src/api/auth_routes.py` — login stores challenge in session;
  callback passes to auth code; token endpoint verifies
- `service/src/schemas/auth.py` — `SelectWorkspaceRequest` gains `code_verifier`

### Residual Risks (industry-accepted)
- PKCE does not help if the **client app itself** is compromised (attacker
  has the verifier).
- All tokens remain **bearer tokens** — no sender-constraint (DPoP/mTLS).
  This is standard across the industry; only financial-grade APIs (FAPI 2.0)
  use sender-constrained tokens.
- Session fixation could undermine PKCE if an attacker sets the session before
  login initiation. Mitigated by session secret + HTTPS.

---

## Fix 2: Refresh Token Reuse Detection — Family Revocation

### Problem
`rotate_refresh_token()` documented "revoke the entire family on reuse" but
never actually did it. When `GETDEL` returned `None` (reuse detected), the
`family_id` was unknown (only stored in the consumed Redis entry, not in the
JWT), so `revoke_token_family()` was never called. The attacker's attempt
failed, but the **legitimate user's session continued** — leaving the door
open for repeated interception attempts.

### Design
- `create_refresh_token()` now accepts an optional `family_id` parameter and
  embeds it as the `fid` claim in the refresh JWT.
- On initial token issuance (`issue_tokens`), `family_id` is generated inside
  `create_refresh_token` (new UUID) and read back from the decoded JWT.
- On rotation, the existing `family_id` is passed to `create_refresh_token`
  to maintain the chain.
- On reuse detection (`consume_refresh_token` returns `None`), the `fid` is
  extracted from the **already-decoded JWT payload** and
  `revoke_token_family(fid)` is called. This kills the entire family —
  both attacker and legitimate user must re-authenticate.

### Files Changed
- `service/src/auth/jwt.py` — `create_refresh_token` gains `family_id` param,
  adds `fid` claim
- `service/src/services/auth_service.py` — `issue_tokens` reads `fid` from
  JWT; `rotate_refresh_token` revokes family on reuse, passes `family_id`
  on rotation

### Residual Risks
- Access tokens already issued to the attacker remain valid until expiry
  (~15 min). We don't track access tokens by family. Short TTL limits the
  blast window. Fully solving this would require per-family access token
  tracking — added complexity for a narrow window.

---

## Fix 3b: Service Key Scoping to service_name

### Problem
`SERVICE_API_KEYS` was a flat comma-separated list of keys. Any valid key
granted access to **all** service-key-protected endpoints across **all**
services. A compromised docu-store deployment could register resources,
read ACLs, and modify permissions for any service.

Note: The "fail-open" concern (3a) was already mitigated — `main.py` refuses
to start with empty `SERVICE_API_KEYS` when `DEBUG=False`.

### Design
- **Config format change**: `SERVICE_API_KEYS` moves from `key1,key2` to
  `service_name:key` format. Multiple keys per service supported for rotation:
  ```
  SERVICE_API_KEYS=docu-store:sk_abc,docu-store:sk_rotated,analytics:sk_def
  ```
- `config.py`: `service_api_key_set` property replaced with
  `service_api_key_map` returning `dict[str, str]` (key → service_name).
  Invalid format raises `ValueError` at parse time.
- `dependencies.py`: `require_service_key()` now returns a `ServiceKeyContext`
  dataclass containing the bound `service_name`. New `verify_service_scope()`
  helper checks that the request's `service_name` matches the key's binding.
  In dev mode (empty map), all services allowed.
- **All 10 service-key-protected endpoints** now call `verify_service_scope()`:
  - Endpoints with `service_name` in body/path: direct comparison
  - Endpoints with `permission_id`: load permission from DB, compare
    `permission.service_name`
- Admin panel: service key display now shows the bound service name instead of
  a generic index.

### Files Changed
- `service/src/config.py` — new `service_api_key_map` property
- `service/src/api/dependencies.py` — `ServiceKeyContext` dataclass,
  updated `require_service_key()`, new `verify_service_scope()`
- `service/src/api/permission_routes.py` — all 7 endpoints updated
- `service/src/api/role_routes.py` — all 3 endpoints updated
- `service/src/api/admin_routes.py` — service key display updated
- `service/src/services/permission_service.py` — new `get_permission_by_id()`
- `service/src/main.py` — startup check uses `service_api_key_map`
- `.env.example`, `.env.prod.example` — format documentation updated

### Residual Risks
- **No per-workspace scoping** — a docu-store key works across all workspaces.
  This is likely intentional (backend services typically serve all workspaces).
- **No per-endpoint scoping** — a docu-store key can both register and delete.
  Fine-grained endpoint permissions would be over-engineering at this stage.
- **Keys compared in plaintext** — not hashed. Marginal risk given that if the
  env is compromised, the attacker has the plaintext regardless.
- **No service identity audit trail** — resolved service_name should be logged
  in structured logs for incident response (future improvement).

---

## Summary

| Fix | Severity | Approach | Residual |
|-----|----------|----------|----------|
| PKCE on auth codes | Medium | S256 challenge/verifier, mandatory | Bearer tokens (industry norm) |
| Family revocation | High | `fid` in JWT, revoke on reuse | Access tokens valid ~15 min |
| Scoped service keys | Medium-High | `service_name:key` config, per-endpoint validation | No workspace/endpoint granularity |

All residual risks are **at or above industry baseline** for authorization
services. The bearer token limitation is shared by every mainstream OAuth
implementation (Google, GitHub, Auth0, Okta, etc.) and only addressed in
financial-grade (FAPI) specifications via DPoP or mTLS.
