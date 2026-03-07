# Environment Variables

Complete reference for all environment variables accepted by the Sentinel Auth. Variables are loaded from `service/.env` (development) or from the process environment / `.env.prod` (production Docker).

## Required for Production

These variables have insecure defaults and must be explicitly set in any non-development environment.

| Variable | Description | Default |
|----------|-------------|---------|
| `SESSION_SECRET_KEY` | Signs OAuth2 state cookies. `make setup` generates this automatically. | `dev-only-change-me-in-production` |
| `COOKIE_SECURE` | Set `true` to add the `Secure` flag to cookies (requires HTTPS). | `false` |
| `DEBUG` | Set `false` for production. Disables `/docs` and `/redoc`, enables fail-closed startup validation. | `false` |

!!! note "Service API keys"
    Service API keys are managed via the admin panel (`/admin/service-apps`), not environment variables. Register at least one service app before deploying to production.

## Database

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string using the `asyncpg` driver. | `postgresql+asyncpg://identity:identity_dev@localhost:9001/identity?ssl=require` |

The connection string must use the `postgresql+asyncpg://` scheme. The `?ssl=require` parameter encrypts the connection (without certificate verification, which is safe for self-signed dev certs).

## Redis

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_URL` | Redis connection string. Used for auth codes, refresh tokens, access token denylist, and rate limiting. | `rediss://:sentinel_dev@localhost:9002/0` |
| `REDIS_TLS_CA_CERT` | Path to CA certificate for Redis TLS verification. When empty, cert verification is skipped (connection is still encrypted). | `""` |
| `REDIS_TLS_VERIFY` | Redis TLS certificate verification mode. Set to `required` in production to verify the server certificate against the CA; set to `none` to encrypt without verification. | `none` |

Both dev and prod use TLS (`rediss://`) by default. The dev compose auto-configures Redis with password auth and TLS using self-signed certs from `keys/tls/`.

When `REDIS_TLS_CA_CERT` is set, the service verifies the Redis server certificate against the specified CA. When empty, certificate verification is skipped but the connection remains encrypted.

The service validates Redis connectivity, authentication, and TLS at startup. With `DEBUG=false`, it refuses to start if any check fails. See the [production checklist](production.md#9-secure-redis) for details.

## JWT

| Variable | Description | Default |
|----------|-------------|---------|
| `JWT_PRIVATE_KEY_PATH` | Path to PEM-encoded RSA private key for signing tokens. | `keys/private.pem` |
| `JWT_PUBLIC_KEY_PATH` | Path to PEM-encoded RSA public key for verifying tokens. | `keys/public.pem` |
| `JWT_ALGORITHM` | JWT signing algorithm. | `RS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime in minutes. | `15` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime in days. | `7` |
| `ADMIN_TOKEN_EXPIRE_MINUTES` | Admin session token lifetime in minutes. | `60` |

`make setup` generates the RSA key pair automatically. To generate manually:

```bash
mkdir -p keys
openssl genrsa -out keys/private.pem 2048
openssl rsa -in keys/private.pem -pubout -out keys/public.pem
```

## OAuth Providers

Configure at least one provider to enable user login. Leave a provider's variables empty to disable it.

### Google

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_CLIENT_ID` | OAuth2 client ID from Google Cloud Console. | `""` |
| `GOOGLE_CLIENT_SECRET` | OAuth2 client secret. | `""` |

### GitHub

| Variable | Description | Default |
|----------|-------------|---------|
| `GITHUB_CLIENT_ID` | OAuth App client ID from GitHub Developer Settings. | `""` |
| `GITHUB_CLIENT_SECRET` | OAuth App client secret. | `""` |

### Microsoft Entra ID

| Variable | Description | Default |
|----------|-------------|---------|
| `ENTRA_CLIENT_ID` | Application (client) ID from Azure portal. | `""` |
| `ENTRA_CLIENT_SECRET` | Client secret value. | `""` |
| `ENTRA_TENANT_ID` | Directory (tenant) ID. | `""` |

## Service

| Variable | Description | Default |
|----------|-------------|---------|
| `SERVICE_HOST` | Host address the service binds to. | `0.0.0.0` |
| `SERVICE_PORT` | Port the service listens on. | `9003` |
| `BASE_URL` | Public URL of Sentinel. Used for OAuth callback URLs. | `http://localhost:9003` |
| `FRONTEND_URL` | URL of the frontend application. Used for post-login redirects. | `http://localhost:3000` |

## Security

| Variable | Description | Default |
|----------|-------------|---------|
| `CORS_ORIGINS` | Comma-separated list of static CORS origins. Combined with origins from registered client apps at runtime. | `http://localhost:3000,http://localhost:9101` |
| `ALLOWED_HOSTS` | Derived from `BASE_URL` + `ADMIN_URL` hostnames. Override with comma-separated hostnames. Falls back to `*` if no hostnames found. | `""` (derived) |
| `BEHIND_PROXY` | Set `true` when behind a reverse proxy. Enables proxy-aware rate limiting using `X-Forwarded-For`. | `false` |

## Admin

| Variable | Description | Default |
|----------|-------------|---------|
| `ADMIN_EMAILS` | Comma-separated email addresses that are automatically granted admin access. | `""` |
| `ADMIN_URL` | URL of the admin panel. Used for CORS and redirects. | `http://localhost:9004` |

## Docker / Production Infrastructure

These variables are used by `docker-compose.prod.yml` and `.env.prod`. They are not read by the FastAPI application itself but configure the containerized PostgreSQL, Redis, and service port mapping.

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_DB` | Name of the PostgreSQL database created by the container. | `sentinel` |
| `POSTGRES_USER` | PostgreSQL user created by the container. | `sentinel` |
| `POSTGRES_PASSWORD` | Password for the PostgreSQL user. Generate with `openssl rand -base64 24`. | *(none — must be set)* |
| `REDIS_PASSWORD` | Password for Redis authentication. Generate with `openssl rand -base64 24`. | *(none — must be set)* |
| `REDIS_TLS_VERIFY` | Redis TLS certificate verification mode (`required` or `none`). In production compose, set to `required`. | `required` |
| `SENTINEL_PORT` | Host port mapped to the Sentinel container's port 9003. | `9003` |
