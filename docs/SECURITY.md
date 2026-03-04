# Security Plan — Daikon Identity Service

## Current State (Dev Only)

All communication is plain HTTP over localhost. No service-to-service authentication.
JWT signatures are cryptographically sound (RS256) but tokens travel in plaintext.

## Production Requirements

### 1. Transport Encryption (TLS)

All service-to-service communication must use HTTPS. Options:

- **Reverse proxy with TLS termination** (recommended for dev/small deployments):
  Caddy or Traefik in front of both identity-service and consuming apps.
  Services communicate over the Docker network in plaintext, proxy handles TLS at the edge.

- **mTLS between services** (recommended for production/multi-host):
  Each service has its own TLS certificate. Services verify each other's identity.
  Can be managed via a service mesh (Linkerd, Istio) or manually with self-signed CAs.

### 2. Service-to-Service Authentication

The permission endpoints (`/permissions/*`) should only be callable by registered services,
not by end users directly. Options:

- **API key header**: Each consuming app gets a `SERVICE_API_KEY` that it sends in an
  `X-Service-Key` header. The identity service validates it. Simple, effective for small
  deployments.

- **OAuth2 client credentials flow**: Each consuming app is an OAuth2 client with its own
  client_id/client_secret. More standard, better for many services.

- **mTLS client certificates**: Service identity verified at the transport layer. Most
  secure, highest ops overhead.

**Recommendation**: Start with API key header (Phase 1), migrate to client credentials
or mTLS when the number of consuming services grows beyond 3-4.

### 3. Token Transport Security

- Access tokens in browser: Use `HttpOnly`, `Secure`, `SameSite=Strict` cookies
  instead of localStorage (prevents XSS token theft).
- Refresh tokens: Store in Redis server-side, send only a session cookie to the browser.
- All cookie flags require HTTPS to be effective.

### 4. Permission API Access Control

Separate two types of callers:

| Caller | Endpoints they can access | Auth method |
|--------|--------------------------|-------------|
| **End users** (via JWT) | `/auth/*`, `/users/me`, `/workspaces/*`, `/workspaces/*/groups/*` | JWT in Authorization header |
| **Service backends** (via API key) | `/permissions/*` | API key in X-Service-Key header |

The `/permissions/check`, `/permissions/register`, and share endpoints should reject
requests that don't have a valid service API key, even if they have a valid JWT.

### 5. Implementation Plan

#### Phase A: API Key for Service-to-Service
- Add `SERVICE_API_KEYS` config (comma-separated list of valid keys)
- Add `require_service_key` dependency to permission routes
- Update SDK's `PermissionClient` to send `X-Service-Key` header
- Update `.env.example` with `SERVICE_API_KEY` variable

#### Phase B: HTTPS via Reverse Proxy
- Add Caddy to docker-compose.yml with automatic TLS (self-signed for dev)
- Update service URLs to use HTTPS
- Add `Secure` and `HttpOnly` flags to cookie-based token transport

#### Phase C: Token Storage Hardening
- Move from Authorization header to HttpOnly cookies for browser clients
- Implement CSRF protection for cookie-based auth
- Add token rotation for refresh tokens (one-time use)

#### Phase D: mTLS (Optional, for Production)
- Generate CA + per-service certificates
- Configure services to verify client certificates
- Remove API key mechanism (replaced by cert identity)
