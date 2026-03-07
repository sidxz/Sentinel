# Deployment

This section covers how to deploy the Sentinel Auth in different environments, from local Docker setups to production infrastructure.

## Deployment Options

### [Docker](docker.md)

Run the full stack locally or on a server using Docker Compose. This is the recommended approach for development and staging environments. The Compose file defines PostgreSQL, Redis, and the Sentinel Auth with health checks and networking pre-configured.

### [Production](production.md)

A security-focused checklist for running Sentinel Auth in production. Covers secret management, TLS termination, cookie security, CORS configuration, and multi-worker considerations.

### [Environment Variables](environment.md)

Complete reference for every environment variable the service accepts, grouped by category. Use this as a quick lookup when configuring deployments.

## Architecture Overview

A typical production deployment looks like this:

```
                    ┌─────────────┐
                    │  Reverse    │
    HTTPS ─────────►│  Proxy      │
                    │  (Caddy)    │
                    └──────┬──────┘
                           │ HTTP :9003
                    ┌──────▼──────┐
                    │  Sentinel   │
                    │  Auth       │
                    └──┬──────┬───┘
                       │      │
              ┌────────▼┐  ┌──▼────────┐
              │ Postgres │  │   Redis   │
              │   :5432  │  │   :6379   │
              └──────────┘  └───────────┘
```

The Sentinel Auth is a stateless FastAPI application. You can run multiple instances behind a load balancer as long as they share the same PostgreSQL database, Redis instance, and JWT signing keys.
