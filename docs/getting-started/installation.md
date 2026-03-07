# Installation

## Quick Start with Docker (recommended)

### 1. Clone the repository

```bash
git clone <repo-url> sentinel && cd sentinel
```

### 2. Run setup

```bash
make setup
```

This generates:

- **JWT keys** — `keys/private.pem`, `keys/public.pem` (RS256 signing)
- **TLS certificates** — `keys/tls/` (internal CA + server cert for Postgres and Redis)
- **Dev env** — `service/.env` with random session secret
- **Prod env** — `.env.prod` with random DB/Redis passwords + session secret

### 3. Configure for production

```bash
vim .env.prod
```

Set `BASE_URL`, `ADMIN_URL`, OAuth provider credentials, `ADMIN_EMAILS`, and `CORS_ORIGINS`.

### 4. Deploy

```bash
docker compose -f docker-compose.prod.yml up -d
# or with Docker Swarm:
docker stack deploy -c docker-compose.prod.yml sentinel
```

This starts PostgreSQL (with SSL), Redis (with TLS + auth), and the Sentinel service. Database migrations run automatically on first boot. All TLS certs and keys are mounted as Docker secrets.

### 5. Verify

```bash
docker compose -f docker-compose.prod.yml ps
curl http://localhost:9003/health
```

You should see all three containers healthy and a `200 OK` from the health endpoint.

<details>
<summary>Manual setup (without <code>make setup</code>)</summary>

If you prefer to generate keys and env files manually:

```bash
# JWT keys
mkdir -p keys
openssl genrsa -out keys/private.pem 2048
openssl rsa -in keys/private.pem -pubout -out keys/public.pem

# TLS certs for Postgres + Redis
mkdir -p keys/tls
openssl req -x509 -newkey rsa:2048 \
  -keyout keys/tls/ca.key -out keys/tls/ca.crt \
  -days 3650 -nodes -subj "/CN=Sentinel Internal CA"
openssl req -newkey rsa:2048 \
  -keyout keys/tls/server.key -out /tmp/sentinel-server.csr \
  -nodes -subj "/CN=sentinel-internal"
openssl x509 -req -in /tmp/sentinel-server.csr \
  -CA keys/tls/ca.crt -CAkey keys/tls/ca.key -CAcreateserial \
  -out keys/tls/server.crt -days 3650 \
  -extfile <(printf "subjectAltName=DNS:postgres,DNS:redis,DNS:localhost,IP:127.0.0.1")
rm -f /tmp/sentinel-server.csr keys/tls/ca.srl
chmod 600 keys/tls/server.key keys/tls/ca.key

# Prod env file
cp .env.prod.example .env.prod
# Fill in POSTGRES_PASSWORD, REDIS_PASSWORD, SESSION_SECRET_KEY, BASE_URL, etc.
```

</details>

---

## Building from Source (contributors)

Use this path if you want to develop the service itself or run the admin panel locally.

### Quick path

```bash
git clone <repo-url> sentinel
cd sentinel
make setup
```

`make setup` generates JWT keys, TLS certs, env files (dev + prod), installs all dependencies (service + SDK + admin UI), and starts PostgreSQL and Redis in Docker with TLS.

After setup completes, follow the printed instructions:

1. Edit `service/.env` — add OAuth credentials (`GOOGLE_CLIENT_ID`, etc.) and `ADMIN_EMAILS`
2. `make start` — start Sentinel on `:9003`
3. `make admin` — start the admin panel on `:9004`

Jump to the [Quickstart](quickstart.md) for the full walkthrough.

<details>
<summary>Manual step-by-step</summary>

#### 1. Clone the repository

```bash
git clone <repo-url> sentinel
cd sentinel
```

#### 2. Install dependencies

The project uses a **uv workspace** with two members (`service/` and `sdk/`):

```bash
uv sync
```

This creates a virtual environment and installs both the FastAPI service and the `sentinel-auth-sdk` package in editable mode.

#### 3. Generate keys and certs

```bash
# JWT keys
mkdir -p keys
openssl genrsa -out keys/private.pem 2048
openssl rsa -in keys/private.pem -pubout -out keys/public.pem
```

TLS certs for Postgres/Redis are generated automatically by `make setup`. If setting up manually, see the Docker manual setup section above for cert generation commands.

#### 4. Create your env file

If you ran `make setup`, `service/.env` already exists with correct key paths and a random session secret — skip to step 5. Otherwise, create it manually:

```bash
cp .env.dev.example service/.env
```

Then edit `service/.env`:

- Set `JWT_PRIVATE_KEY_PATH=../keys/private.pem` and `JWT_PUBLIC_KEY_PATH=../keys/public.pem` (paths are relative to the `service/` directory)
- Set `REDIS_TLS_CA_CERT=../keys/tls/ca.crt`
- Generate a `SESSION_SECRET_KEY` (see the [Quickstart](quickstart.md#2-verify-the-session-secret))
- Add your OAuth credentials and `ADMIN_EMAILS`

#### 5. Start infrastructure

```bash
docker compose up -d identity-postgres identity-redis
```

Default ports:

| Service | Port | Transport |
|---------|------|-----------|
| PostgreSQL | `9001` | SSL |
| Redis | `9002` | TLS + password auth |

Wait for PostgreSQL to report healthy:

```bash
docker compose ps
```

#### 6. Database migrations

No manual step required — the service runs Alembic migrations automatically on startup.

</details>

---

## Verify the installation

=== "Docker"

    - [x] All three containers running (`docker compose -f docker-compose.prod.yml ps`)
    - [x] RSA key pair in `keys/`
    - [x] TLS certificates in `keys/tls/`
    - [x] Health check passes (`curl http://localhost:9003/health`)
    - [x] `.env.prod` with secrets, OAuth credentials, and `ADMIN_EMAILS` configured

=== "From Source"

    - [x] Python dependencies installed (`uv run python -c "import sentinel_auth"`)
    - [x] RSA key pair in `keys/`
    - [x] TLS certificates in `keys/tls/` (generated by `make setup`)
    - [x] PostgreSQL and Redis running in Docker with TLS
    - [x] `service/.env` file with OAuth credentials and `ADMIN_EMAILS` configured

Next: [Quickstart](quickstart.md) -- configure an OAuth provider, register your apps, and start the service.
