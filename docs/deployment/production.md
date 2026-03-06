# Production Checklist

Follow this checklist before deploying the Sentinel Auth to a production environment. Each item addresses a specific security or reliability concern.

## 1. Set a strong session secret

Generate a cryptographically random 32-byte string and set it as `SESSION_SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

```ini
SESSION_SECRET_KEY=your-generated-value-here
```

This key signs the OAuth2 state parameter during login flows. If left at the default, an attacker could forge OAuth state and perform CSRF attacks.

## 2. Register service apps

Service API keys are managed via the admin panel (`/admin/service-apps`), not environment variables. Each consuming service needs its own service app:

1. Log in to the admin panel
2. Navigate to **Service Apps**
3. Create a service app for each consuming service (e.g., "docu-store", "analytics")
4. Copy the plaintext key shown at creation -- it cannot be retrieved again

When no active service apps exist in the database, service-key authentication is disabled entirely (acceptable only in development).

## 3. Enable secure cookies

```ini
COOKIE_SECURE=true
```

This sets the `Secure` flag on all cookies, ensuring they are only sent over HTTPS connections. You must have TLS termination in place before enabling this.

## 4. Restrict allowed hosts

```ini
ALLOWED_HOSTS=identity.yourdomain.com
```

This enables the `TrustedHostMiddleware`, which rejects requests with a `Host` header that does not match. Setting this to `*` disables the check (development only).

## 5. Configure CORS origins

```ini
CORS_ORIGINS=https://app.yourdomain.com
```

Set this to the exact origin(s) of your frontend. Do not use wildcards in production. Multiple origins can be comma-separated.

## 6. Deploy behind a TLS-terminating reverse proxy

The identity service does not handle TLS itself. Place it behind a reverse proxy that terminates HTTPS:

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

## 7. Configure rate limiting for multi-worker deployments

The identity service uses [slowapi](https://github.com/laurentS/slowapi) for rate limiting. By default, rate limit counters are stored in-process memory, which does not work correctly with multiple workers (each worker tracks limits independently).

For multi-worker deployments, configure slowapi to use Redis as its backend so all workers share the same counters. Ensure `REDIS_URL` is set and reachable from all instances.

## 8. Secure Redis

Redis stores auth codes, refresh tokens, and the access token denylist. In production, it must be authenticated and encrypted:

```ini
# With password and TLS
REDIS_URL=rediss://:your-strong-password@redis-host:6380/0
```

| Requirement | How |
|-------------|-----|
| Authentication | Include password in URL: `redis://:password@host:port/db` |
| TLS encryption | Use the `rediss://` scheme (double s) |
| Network isolation | Bind Redis to private network, not `0.0.0.0` |

The service validates Redis connectivity, authentication, and TLS at startup. With `DEBUG=false`, it refuses to start if any check fails.

## 9. Rotate any credentials that were in git history

If you previously committed secrets (API keys, session secrets, database passwords) to the repository, those values are still in git history even after deletion. Generate new values for all such credentials.

## 10. Use separate database credentials per environment

Do not reuse the development database credentials (`identity` / `identity_dev`) in production. Create a dedicated PostgreSQL user with a strong password:

```sql
CREATE USER identity_prod WITH PASSWORD 'strong-random-password';
CREATE DATABASE identity_prod OWNER identity_prod;
```

```ini
DATABASE_URL=postgresql+asyncpg://identity_prod:strong-random-password@db-host:5432/identity_prod
```

## 11. Generate production JWT keys

Generate a fresh RSA key pair for production. Do not reuse development keys:

```bash
openssl genrsa -out private.pem 2048
openssl rsa -in private.pem -pubout -out public.pem
```

Store these securely (e.g., mounted from a secrets manager) and set the paths:

```ini
JWT_PRIVATE_KEY_PATH=/run/secrets/jwt_private.pem
JWT_PUBLIC_KEY_PATH=/run/secrets/jwt_public.pem
```

## Summary Checklist

- [ ] `SESSION_SECRET_KEY` set to a random 32-byte string
- [ ] At least one service app registered via admin panel with strong keys
- [ ] `COOKIE_SECURE=true`
- [ ] `ALLOWED_HOSTS` set to your domain(s)
- [ ] `CORS_ORIGINS` set to your frontend origin(s)
- [ ] Service deployed behind TLS-terminating reverse proxy
- [ ] Rate limiting configured for multi-worker (Redis backend)
- [ ] Redis authenticated (password in URL) and encrypted (`rediss://` scheme)
- [ ] Fresh JWT RSA key pair generated for production
- [ ] All previously-committed secrets rotated
- [ ] Separate database credentials per environment
