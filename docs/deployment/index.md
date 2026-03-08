# Deployment

Sentinel is a stateless FastAPI application. Multiple instances can run behind a load balancer as long as they share the same PostgreSQL database, Redis instance, and JWT signing keys.

## Architecture

```
                ┌─────────────┐
                │  Reverse    │
  HTTPS ───────>│  Proxy      │
                │  (Caddy)    │
                └──────┬──────┘
                       │ HTTP :9003
                ┌──────v──────┐
                │  Sentinel   │
                │  Auth       │
                └──┬──────┬───┘
                   │      │
          ┌────────v┐  ┌──v────────┐
          │ Postgres │  │   Redis   │
          │   :5432  │  │   :6379   │
          └──────────┘  └───────────┘
```

---

## Development (Docker Compose)

The default `docker-compose.yml` starts PostgreSQL 16 and Redis 7 with TLS and health checks:

```bash
make setup    # Generate keys, TLS certs, .env files, install deps, start containers
make start    # Start Sentinel on :9003 (auto-migrates)
make admin    # Start admin panel on :9004
```

`make setup` handles everything:

- Generates RS256 JWT signing keys (`keys/`)
- Generates TLS certs for Postgres and Redis (`keys/tls/`) using a self-signed CA
- Creates `service/.env` with a random `SESSION_SECRET_KEY`
- Creates `.env.prod` with random database and Redis passwords
- Installs Python and Node dependencies
- Starts database containers

### Container Ports

| Service | Container Port | Host Port |
|---------|---------------|-----------|
| PostgreSQL | 5432 | 9001 |
| Redis | 6379 | 9002 |
| Sentinel | 9003 | 9003 |

### Data Persistence

PostgreSQL data is stored in the `identity_pg_data` Docker volume. To wipe everything:

```bash
make clean    # Stop containers and delete volumes
make nuke     # Full reset: volumes + keys + env files + deps
```

---

## Production Docker Compose

The production compose file (`docker-compose.prod.yml`) uses `.env.prod` for configuration. Generate it with `make setup`, then edit:

```bash
vim .env.prod   # Set BASE_URL, ADMIN_URL, OAuth creds, ADMIN_EMAILS
```

Deploy:

```bash
docker stack deploy -c docker-compose.prod.yml sentinel
```

Both PostgreSQL and Redis run with TLS enabled. The service connects via `?ssl=require` (Postgres) and `rediss://` (Redis).

---

## Production Checklist

### TLS

- [ ] Reverse proxy (nginx, Caddy, ALB) handles TLS termination
- [ ] `BEHIND_PROXY=true` so rate limiting reads `X-Forwarded-For`
- [ ] PostgreSQL connection uses `?ssl=require`
- [ ] Redis uses `rediss://` with `REDIS_TLS_VERIFY=required`
- [ ] TLS certs generated for internal services (`keys/tls/`)

### Secrets

- [ ] `SESSION_SECRET_KEY` is cryptographically random (not the default)
- [ ] `POSTGRES_PASSWORD` and `REDIS_PASSWORD` are strong, randomly generated
- [ ] RS256 private key has restrictive permissions (`chmod 600`)
- [ ] At least one service app registered via the admin panel

### Cookie and Security Flags

- [ ] `COOKIE_SECURE=true`
- [ ] `DEBUG=false` (disables `/docs`, `/redoc`, enables fail-closed startup)
- [ ] `ALLOWED_HOSTS` set to actual domain(s)
- [ ] `CORS_ORIGINS` lists only your frontend origin(s)
- [ ] `ADMIN_EMAILS` configured

### Workers

Sentinel is stateless. Run multiple uvicorn workers or container replicas behind a load balancer:

```bash
uvicorn src.main:app --host 0.0.0.0 --port 9003 --workers 4
```

All instances must share the same JWT keys, PostgreSQL, and Redis.

### Backup

- PostgreSQL: use `pg_dump` or continuous archiving (WAL-G, pgBackRest)
- Redis: enable RDB snapshots or AOF persistence
- JWT keys: back up `keys/private.pem` -- losing it invalidates all issued tokens

---

## Health Check

The service exposes `GET /health` which returns `{"status": "ok"}`. Use this for load balancer health checks and container orchestration.

### OpenAPI

`/docs`, `/redoc`, and `/openapi.json` are only available when `DEBUG=true`. They are disabled in production.
