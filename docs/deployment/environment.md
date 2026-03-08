# Environment Variables

Complete reference for all variables accepted by Sentinel. Loaded from `service/.env` (development) or the process environment / `.env.prod` (production).

---

## Required for Production

These have insecure defaults and must be set explicitly in non-development environments.

| Variable | Default | Description |
|----------|---------|-------------|
| `SESSION_SECRET_KEY` | `dev-only-change-me-in-production` | Signs OAuth2 state cookies. Generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `COOKIE_SECURE` | `false` | Set `true` to add `Secure` flag to cookies and enable HSTS. Requires HTTPS. |
| `DEBUG` | `false` | Set `false` for production. Disables `/docs` and `/redoc`, enables fail-closed startup validation. |

!!! note "Service API keys"
    Service API keys are managed via the admin panel (`/admin/service-apps`), not environment variables.

---

## Database

| Variable | Default | Required |
|----------|---------|----------|
| `DATABASE_URL` | `postgresql+asyncpg://identity:identity_dev@localhost:9001/identity?ssl=require` | Yes |

Must use `postgresql+asyncpg://` scheme. Append `?ssl=require` for encrypted connections.

---

## Redis

| Variable | Default | Required |
|----------|---------|----------|
| `REDIS_URL` | `rediss://:sentinel_dev@localhost:9002/0` | Yes |
| `REDIS_TLS_CA_CERT` | `""` | No |
| `REDIS_TLS_VERIFY` | `none` | No |

- `REDIS_URL` -- use `rediss://` for TLS. Include password in URL (`rediss://:password@host:port/db`).
- `REDIS_TLS_CA_CERT` -- path to CA cert for server certificate verification. Empty = encrypted but no cert verification.
- `REDIS_TLS_VERIFY` -- set `required` in production to verify the server certificate against the CA.

---

## JWT

| Variable | Default | Required |
|----------|---------|----------|
| `JWT_PRIVATE_KEY_PATH` | `keys/private.pem` | Yes |
| `JWT_PUBLIC_KEY_PATH` | `keys/public.pem` | Yes |
| `JWT_ALGORITHM` | `RS256` | No |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | No |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | No |
| `ADMIN_TOKEN_EXPIRE_MINUTES` | `60` | No |
| `AUTHZ_TOKEN_EXPIRE_MINUTES` | `5` | No |

`make setup` generates the RSA key pair. To generate manually:

```bash
openssl genrsa -out keys/private.pem 2048
openssl rsa -in keys/private.pem -pubout -out keys/public.pem
```

---

## OAuth Providers

Configure at least one provider to enable user login. Leave variables empty to disable a provider.

### Google

| Variable | Default | Required |
|----------|---------|----------|
| `GOOGLE_CLIENT_ID` | `""` | No |
| `GOOGLE_CLIENT_SECRET` | `""` | No |

### GitHub

| Variable | Default | Required |
|----------|---------|----------|
| `GITHUB_CLIENT_ID` | `""` | No |
| `GITHUB_CLIENT_SECRET` | `""` | No |

### Microsoft Entra ID

| Variable | Default | Required |
|----------|---------|----------|
| `ENTRA_CLIENT_ID` | `""` | No |
| `ENTRA_CLIENT_SECRET` | `""` | No |
| `ENTRA_TENANT_ID` | `""` | No |

---

## Service

| Variable | Default | Required |
|----------|---------|----------|
| `SERVICE_HOST` | `0.0.0.0` | No |
| `SERVICE_PORT` | `9003` | No |
| `BASE_URL` | `http://localhost:9003` | Yes |
| `FRONTEND_URL` | `http://localhost:3000` | No |

`BASE_URL` is used for OAuth callback URLs. Set to the public URL of your Sentinel instance.

---

## Security

| Variable | Default | Required |
|----------|---------|----------|
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:9101` | No |
| `ALLOWED_HOSTS` | `""` (derived from `BASE_URL` + `ADMIN_URL`) | No |
| `BEHIND_PROXY` | `false` | No |

- `CORS_ORIGINS` -- comma-separated static origins. Combined with origins derived from registered client app redirect URIs at runtime.
- `ALLOWED_HOSTS` -- comma-separated hostnames. If empty, derived from `BASE_URL` and `ADMIN_URL`. Falls back to `*` if no hostnames found (blocked by startup validation in production).
- `BEHIND_PROXY` -- set `true` when behind a reverse proxy. Rate limiting reads `X-Forwarded-For` instead of TCP connection address.

---

## Admin

| Variable | Default | Required |
|----------|---------|----------|
| `ADMIN_EMAILS` | `""` | No |
| `ADMIN_URL` | `http://localhost:9004` | No |

- `ADMIN_EMAILS` -- comma-separated email addresses automatically granted admin access on login.
- `ADMIN_URL` -- used for CORS and redirect configuration.

---

## Docker / Infrastructure

These are used by `docker-compose.prod.yml` and `.env.prod`. They are not read by the FastAPI application.

| Variable | Default | Required |
|----------|---------|----------|
| `POSTGRES_DB` | `sentinel` | Yes |
| `POSTGRES_USER` | `sentinel` | Yes |
| `POSTGRES_PASSWORD` | *(none)* | Yes |
| `REDIS_PASSWORD` | *(none)* | Yes |
| `SENTINEL_PORT` | `9003` | No |
