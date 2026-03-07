# Production Checklist

Follow this checklist before deploying the Sentinel Auth to a production environment. Each item addresses a specific security or reliability concern.

## 1. Run `make setup`

`make setup` generates JWT keys, TLS certificates, and both dev (`service/.env`) and prod (`.env.prod`) environment files with random secrets in a single command.

After running setup, edit `.env.prod` to set your production values:

```bash
vim .env.prod
# Set: BASE_URL, ADMIN_URL, OAuth credentials, ADMIN_EMAILS, CORS_ORIGINS
```

## 2. Set a strong session secret

`make setup` generates a cryptographically random `SESSION_SECRET_KEY` automatically. If you need to regenerate:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

```ini
SESSION_SECRET_KEY=your-generated-value-here
```

This key signs the OAuth2 state parameter during login flows. If left at the default, an attacker could forge OAuth state and perform CSRF attacks.

## 3. Register service apps

Service API keys are managed via the admin panel (`/admin/service-apps`), not environment variables. Each consuming service needs its own service app:

1. Log in to the admin panel
2. Navigate to **Service Apps**
3. Create a service app for each consuming service (e.g., "docu-store", "analytics")
4. Copy the plaintext key shown at creation -- it cannot be retrieved again

When no active service apps exist in the database, all service-key endpoints return 401. The service logs a warning at startup as a reminder.

## 4. Enable secure cookies

```ini
COOKIE_SECURE=true
```

This sets the `Secure` flag on all cookies, ensuring they are only sent over HTTPS connections. You must have TLS termination in place before enabling this.

## 5. Restrict allowed hosts

```ini
ALLOWED_HOSTS=identity.yourdomain.com
```

This enables the `TrustedHostMiddleware`, which rejects requests with a `Host` header that does not match. Setting this to `*` disables the check (development only).

## 6. Configure CORS origins

```ini
CORS_ORIGINS=https://app.yourdomain.com
```

Set this to the exact origin(s) of your frontend. Do not use wildcards in production. Multiple origins can be comma-separated.

## 7. Deploy behind a TLS-terminating reverse proxy

Sentinel does not handle TLS itself. Place it behind a reverse proxy that terminates HTTPS:

=== "Caddy (recommended)"

    ```
    identity.yourdomain.com {
        reverse_proxy localhost:9003
    }
    ```

    Caddy automatically provisions and renews TLS certificates via Let's Encrypt.

=== "Nginx"

    ```nginx
    server {
        listen 443 ssl;
        server_name identity.yourdomain.com;

        ssl_certificate     /etc/ssl/certs/identity.crt;
        ssl_certificate_key /etc/ssl/private/identity.key;

        location / {
            proxy_pass http://localhost:9003;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
    ```

When deploying behind a reverse proxy, set `BEHIND_PROXY=true` so the rate limiter reads the real client IP from `X-Forwarded-For` instead of the proxy's IP.

## 8. TLS for internal connections

The provided `docker-compose.prod.yml` encrypts PostgreSQL and Redis connections using TLS certificates mounted as Docker secrets. `make setup` generates these certificates automatically in `keys/tls/`.

!!! info "TLS by default"
    Both `docker-compose.yml` (dev) and `docker-compose.prod.yml` (prod) configure PostgreSQL with SSL and Redis with TLS + password authentication out of the box. If you are using the provided compose files, internal connections are already encrypted.

If you manage your own infrastructure, ensure:

- PostgreSQL accepts SSL connections (`ssl=on`)
- Redis uses TLS (`--tls-port`, `--port 0`)
- The service's `DATABASE_URL` includes `?ssl=require`
- The service's `REDIS_URL` uses the `rediss://` scheme

## 9. Secure Redis

Redis stores auth codes, refresh tokens, and the access token denylist. In production, it must be authenticated and encrypted:

```ini
REDIS_URL=rediss://:your-strong-password@redis-host:6380/0
```

| Requirement | How |
|-------------|-----|
| Authentication | Include password in URL: `rediss://:password@host:port/db` |
| TLS encryption | Use the `rediss://` scheme (double s) |
| Network isolation | Bind Redis to private network, not `0.0.0.0` |

The service validates Redis connectivity, authentication, and TLS at startup. With `DEBUG=false`, it refuses to start if any check fails.

## 10. Configure rate limiting

Rate limiting uses two layers:

1. **Global**: `GlobalRateLimitMiddleware` — 30 req/min per IP, Redis-backed sliding window
2. **Per-endpoint**: slowapi — Redis-backed counters via `REDIS_URL`

For multi-worker deployments, all rate limit counters are shared via Redis automatically.

!!! tip "Proxy-aware rate limiting"
    When `BEHIND_PROXY=true`, the rate limiter extracts the client IP from the `X-Forwarded-For` header instead of the TCP connection address.

## 11. Rotate any credentials that were in git history

If you previously committed secrets (API keys, session secrets, database passwords) to the repository, those values are still in git history even after deletion. Generate new values for all such credentials.

## 12. Use separate database credentials per environment

Do not reuse the development database credentials (`identity` / `identity_dev`) in production. Create a dedicated PostgreSQL user with a strong password:

```sql
CREATE USER sentinel WITH PASSWORD 'strong-random-password';
CREATE DATABASE sentinel OWNER sentinel;
```

```ini
DATABASE_URL=postgresql+asyncpg://sentinel:strong-random-password@db-host:5432/sentinel?ssl=require
```

## 13. Generate production JWT keys

Generate a fresh RSA key pair for production. Do not reuse development keys:

```bash
openssl genrsa -out private.pem 2048
openssl rsa -in private.pem -pubout -out public.pem
```

Store these securely (e.g., mounted from a secrets manager) and set the paths:

```ini
JWT_PRIVATE_KEY_PATH=/run/secrets/jwt_private_key
JWT_PUBLIC_KEY_PATH=/run/secrets/jwt_public_key
```

## Summary Checklist

- [ ] `make setup` run (generates keys, certs, env files)
- [ ] `.env.prod` configured with production values
- [ ] `SESSION_SECRET_KEY` set to a random 32-byte string
- [ ] At least one service app registered via admin panel with strong keys
- [ ] `COOKIE_SECURE=true`
- [ ] `DEBUG=false`
- [ ] `ALLOWED_HOSTS` set to your domain(s)
- [ ] `CORS_ORIGINS` set to your frontend origin(s)
- [ ] `BEHIND_PROXY=true` if behind a reverse proxy
- [ ] Service deployed behind TLS-terminating reverse proxy
- [ ] TLS certificates generated for Postgres and Redis (`keys/tls/`)
- [ ] PostgreSQL connection uses SSL (`?ssl=require` in `DATABASE_URL`)
- [ ] Redis authenticated (password in URL) and encrypted (`rediss://` scheme)
- [ ] Fresh JWT RSA key pair generated for production
- [ ] All previously-committed secrets rotated
- [ ] Separate database credentials per environment
