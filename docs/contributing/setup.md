# Dev Setup

This guide walks through setting up a local development environment for the Sentinel Auth.

## Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** -- Python package manager
- **Docker** and **Docker Compose** -- for PostgreSQL and Redis
- **Node.js 18+** and **npm** -- only needed if working on the admin panel

## One-Time Setup

Run the setup command from the project root:

```bash
make setup
```

This performs the following steps:

1. **Generates JWT RSA keys** in `keys/private.pem` and `keys/public.pem` (skipped if keys already exist)
2. **Generates TLS certificates** in `keys/tls/` — an internal CA + server cert covering `localhost`, `postgres`, `redis`, and `127.0.0.1` (used by both dev and prod Docker containers)
3. **Creates `service/.env`** from `.env.dev.example` with a random `SESSION_SECRET_KEY` and correct key paths
4. **Creates `.env.prod`** from `.env.prod.example` with random Postgres/Redis passwords and session secret
5. **Installs Python dependencies** via `uv sync` for the workspace and the service
6. **Installs admin panel dependencies** via `npm install` in the `admin/` directory
7. **Starts PostgreSQL and Redis** containers with Docker Compose (both with TLS enabled)
8. **Waits for PostgreSQL** to become healthy before returning
9. **Prints next steps** — prompts you to add OAuth credentials and `ADMIN_EMAILS` to `service/.env`

After setup completes, you will see:

```
Setup complete!

  Next:
    1. vim service/.env   — add OAuth creds (GOOGLE_*, GITHUB_*, etc.) + ADMIN_EMAILS
    2. make start         — start identity service (:9003)
    3. make admin         — start admin UI (:9004)
    make seed             — populate with test data (optional)
```

## Environment Configuration

`make setup` generates `service/.env` from `.env.dev.example` automatically. To do it manually:

```bash
cp .env.dev.example service/.env
```

The defaults work out of the box for local development. See the [Environment Variables](../deployment/environment.md) reference for all available options.

## Available Commands

| Command | Description |
|---------|-------------|
| `make setup` | First-time setup: generate keys, install deps, start DB |
| `make start` | Start Sentinel on port 9003 with hot reload |
| `make admin` | Start the admin UI dev server on port 9004 |
| `make seed` | Populate the database with test data |
| `make create-admin` | Create or promote a user to admin |
| `make status` | Check what services and containers are running |
| `make clean` | Stop containers and wipe the database |
| `make nuke` | Full reset: wipe everything including deps and keys |

## Starting the Service

```bash
make start
```

This runs `uvicorn` with `--reload` so the server restarts automatically when you change code. The service is available at `http://localhost:9003`.

On startup, the service automatically runs Alembic migrations, so the database schema is always up to date.

## Starting the Admin Panel

```bash
make admin
```

The admin panel runs on `http://localhost:9004`. It communicates with the Sentinel API at `:9003`.

## Seeding Test Data

```bash
make seed
```

This runs `scripts/seed.py`, which populates the database with sample users, workspaces, groups, and permissions for development and testing.

## Checking Status

```bash
make status
```

This shows the state of Docker containers, whether Sentinel is responding on `:9003`, and whether the admin panel is running on `:9004`.

## Resetting

To stop containers and wipe the database (but keep installed dependencies and keys):

```bash
make clean
```

For a complete reset that removes everything — virtual environments, `node_modules` (including JS SDK packages), JWT keys, TLS certs, and generated env files (`service/.env`, `.env.prod`):

```bash
make nuke
```

After a nuke, run `make setup` to start fresh.
