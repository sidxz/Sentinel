# Environment Variables

Complete reference for all environment variables accepted by the Sentinel Auth. Variables are loaded from a `.env` file in the project root or from the process environment.

## Required for Production

These variables have insecure defaults and must be explicitly set in any non-development environment.

| Variable | Description | Default |
|----------|-------------|---------|
| `SESSION_SECRET_KEY` | Signs OAuth2 state cookies. Generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"` | `dev-only-change-me-in-production` |
| `COOKIE_SECURE` | Set `true` to add the `Secure` flag to cookies (requires HTTPS). | `false` |
| `ALLOWED_HOSTS` | Derived from `BASE_URL` + `ADMIN_URL` hostnames. Override with comma-separated hostnames. | `""` (derived) |

!!! note "Service API keys"
    Service API keys are managed via the admin panel (`/admin/service-apps`), not environment variables. Register at least one service app before deploying to production.

## Database

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string using the `asyncpg` driver. | `postgresql+asyncpg://identity:identity_dev@localhost:9001/identity` |

The connection string must use the `postgresql+asyncpg://` scheme. The service uses SQLAlchemy 2.0 async, which requires the asyncpg driver.

## Redis

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_URL` | Redis connection string. Used for auth codes, refresh tokens, access token denylist, and rate limiting. | `redis://localhost:9002/0` |

In production, Redis must be authenticated and encrypted. Use the `rediss://` scheme (double s) for TLS and include a password:

```ini
# Development (default)
REDIS_URL=redis://localhost:9002/0

# Production (password + TLS)
REDIS_URL=rediss://:your-strong-password@redis-host:6380/0
```

The service validates Redis connectivity, authentication, and TLS at startup. With `DEBUG=false`, it refuses to start if any check fails. See the [production checklist](production.md#8-secure-redis) for details.

## JWT

| Variable | Description | Default |
|----------|-------------|---------|
| `JWT_PRIVATE_KEY_PATH` | Path to PEM-encoded RSA private key for signing tokens. | `keys/private.pem` |
| `JWT_PUBLIC_KEY_PATH` | Path to PEM-encoded RSA public key for verifying tokens. | `keys/public.pem` |
| `JWT_ALGORITHM` | JWT signing algorithm. | `RS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime in minutes. | `15` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime in days. | `7` |

Generate an RSA key pair:

```bash
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
| `BASE_URL` | Public URL of the identity service. Used for OAuth callback URLs. | `http://localhost:9003` |
| `FRONTEND_URL` | URL of the frontend application. Used for post-login redirects. | `http://localhost:3000` |

## Security

| Variable | Description | Default |
|----------|-------------|---------|
| `CORS_ORIGINS` | Comma-separated list of static CORS origins. Combined with origins from registered client apps at runtime. | `http://localhost:3000,http://localhost:9101` |
| `COOKIE_SECURE` | Whether cookies require HTTPS. | `false` |
| `ALLOWED_HOSTS` | Derived from `BASE_URL` + `ADMIN_URL` hostnames. Override with comma-separated hostnames. Falls back to `*` if no hostnames found. | `""` (derived) |

## Admin

| Variable | Description | Default |
|----------|-------------|---------|
| `ADMIN_EMAILS` | Comma-separated email addresses that are automatically granted admin access. | `""` |
| `ADMIN_URL` | URL of the admin panel. Used for CORS and redirects. | `http://localhost:9004` |
