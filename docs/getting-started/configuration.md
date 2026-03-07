# Configuration

All configuration is done through environment variables, loaded from `service/.env` (dev) or `.env.prod` (production). The service uses [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) for validation and type coercion.

```bash
# make setup generates both automatically; manual alternative:
cp .env.dev.example service/.env     # local development
cp .env.prod.example .env.prod       # production deployment
```

---

## Database

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DATABASE_URL` | `str` | `postgresql+asyncpg://identity:identity_dev@localhost:9001/identity?ssl=require` | Async PostgreSQL connection string. Must use the `asyncpg` driver. |
| `REDIS_URL` | `str` | `rediss://:sentinel_dev@localhost:9002/0` | Redis connection string. `rediss://` enables TLS. |
| `REDIS_TLS_CA_CERT` | `str` | `""` | Path to CA cert for Redis TLS verification (e.g. `keys/tls/ca.crt`). |

!!! note "Docker Compose defaults"
    The default values match the `docker-compose.yml` configuration. If you change ports or credentials in your compose file, update these accordingly.

---

## JWT

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `JWT_PRIVATE_KEY_PATH` | `Path` | `keys/private.pem` | Path to the RSA private key used for signing access tokens. |
| `JWT_PUBLIC_KEY_PATH` | `Path` | `keys/public.pem` | Path to the RSA public key used for verifying access tokens. |
| `JWT_ALGORITHM` | `str` | `RS256` | Signing algorithm. Only `RS256` is supported. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `int` | `15` | Access token lifetime in minutes. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `int` | `7` | Refresh token lifetime in days. |
| `ADMIN_TOKEN_EXPIRE_MINUTES` | `int` | `60` | Admin token lifetime in minutes. |

!!! tip "Key generation"
    Generate a key pair with:
    ```bash
    mkdir -p keys
    openssl genrsa -out keys/private.pem 2048
    openssl rsa -in keys/private.pem -pubout -out keys/public.pem
    ```
    Or just run `make setup`, which handles this automatically.

!!! warning "Token lifetimes"
    Short-lived access tokens (15 minutes) with longer refresh tokens (7 days) is the recommended default. The service supports refresh token rotation with reuse detection -- if a refresh token is used twice, all tokens for that session are revoked.

---

## OAuth Providers

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `GOOGLE_CLIENT_ID` | `str` | *(empty)* | Google OAuth 2.0 client ID. |
| `GOOGLE_CLIENT_SECRET` | `str` | *(empty)* | Google OAuth 2.0 client secret. |
| `GITHUB_CLIENT_ID` | `str` | *(empty)* | GitHub OAuth app client ID. |
| `GITHUB_CLIENT_SECRET` | `str` | *(empty)* | GitHub OAuth app client secret. |
| `ENTRA_CLIENT_ID` | `str` | *(empty)* | Microsoft Entra ID (Azure AD) application client ID. |
| `ENTRA_CLIENT_SECRET` | `str` | *(empty)* | Microsoft Entra ID application client secret. |
| `ENTRA_TENANT_ID` | `str` | *(empty)* | Microsoft Entra ID tenant ID. Required if using Entra. |

!!! info "Provider activation"
    A provider is enabled automatically when both its client ID and client secret are set. You can enable any combination of providers simultaneously. At least one provider is required for the service to be useful.

### Callback URLs

When registering your OAuth application with each provider, use the following redirect URIs:

| Provider | Redirect URI |
|----------|-------------|
| Google | `{BASE_URL}/auth/callback/google` |
| GitHub | `{BASE_URL}/auth/callback/github` |
| Entra ID | `{BASE_URL}/auth/callback/entra` |

Replace `{BASE_URL}` with your service URL (default: `http://localhost:9003`).

---

## Service

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SERVICE_HOST` | `str` | `0.0.0.0` | Host address the service binds to. |
| `SERVICE_PORT` | `int` | `9003` | Port the service listens on. |
| `BASE_URL` | `str` | `http://localhost:9003` | Public URL of Sentinel. Used to construct OAuth callback URLs. |
| `FRONTEND_URL` | `str` | `http://localhost:3000` | URL of the frontend application. Used for post-login redirects. |

---

## Security

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SESSION_SECRET_KEY` | `str` | `dev-only-change-me-in-production` | Secret key for signing server-side sessions used during OAuth flows. |
| `CORS_ORIGINS` | `str` | `http://localhost:3000,http://localhost:9101` | Comma-separated list of static CORS origins. Combined with origins from registered client apps at runtime. |
| `COOKIE_SECURE` | `bool` | `false` | Set to `true` in production to mark cookies as `Secure` (requires HTTPS). |
| `ALLOWED_HOSTS` | `str` | *(empty)* | Derived from `BASE_URL` and `ADMIN_URL` hostnames. Falls back to `*` (allow all) only if no hostnames found. Override with comma-separated hostnames. |
| `DEBUG` | `bool` | `false` | Set `true` for local development. Enables `/docs` and `/redoc`, relaxes startup validation to warnings instead of hard failures. |
| `BEHIND_PROXY` | `bool` | `false` | Set `true` when behind a reverse proxy (nginx, Caddy, ALB). Enables proxy-aware rate limiting using `X-Forwarded-For`. |

!!! danger "Production security checklist"
    Before deploying to production, you **must**:

    - Set `SESSION_SECRET_KEY` to a unique, random value (`python -c "import secrets; print(secrets.token_urlsafe(32))"`)
    - Set `COOKIE_SECURE=true` (your deployment must use HTTPS)
    - Set `ALLOWED_HOSTS` to your actual domain(s)
    - Register at least one service app via the admin panel (`/admin/service-apps`)
    - Restrict `CORS_ORIGINS` to your frontend domain(s)

!!! info "Comma-separated values"
    `CORS_ORIGINS` and `ALLOWED_HOSTS` accept multiple values separated by commas:
    ```dotenv
    CORS_ORIGINS=https://app.example.com,https://admin.example.com
    ALLOWED_HOSTS=api.example.com,identity.example.com
    ```

!!! note "Service API keys"
    Service API keys are configured through the admin panel under **Service Apps** (`/admin/service-apps`), not via environment variables. Each key is scoped to a `service_name` and stored as a SHA-256 hash. See the [Service Authentication guide](../guide/service-auth.md) for details.

---

## Admin

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ADMIN_EMAILS` | `str` | *(empty)* | Comma-separated list of email addresses granted admin access. |
| `ADMIN_URL` | `str` | `http://localhost:9004` | URL where the admin UI is served. Used for CORS and redirect configuration. |

!!! tip "Granting admin access"
    Add email addresses to `ADMIN_EMAILS` to allow those users to access the admin panel after logging in via OAuth. You can also use the `make create-admin` command to promote an existing user interactively.
