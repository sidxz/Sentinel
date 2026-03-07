# Contributing

Welcome to the Sentinel Auth contributor guide. This section covers everything you need to get started contributing to the project.

## Quick Links

| Page | Description |
|------|-------------|
| [Dev Setup](setup.md) | Install prerequisites, run the setup script, and start developing |
| [Project Structure](structure.md) | Full directory tree with annotations explaining every component |
| [Database](database.md) | Schema overview, ERD, migrations, and how to create new tables |
| [Testing](testing.md) | Test structure, running tests, and writing effective test cases |
| [Code Style](code-style.md) | Coding conventions, tooling, and architectural decisions |

## Getting Oriented

The project is structured as a [uv workspace](https://docs.astral.sh/uv/concepts/workspaces/) with three members:

- **`service/`** -- The FastAPI microservice (the core of the project)
- **`sdk/`** -- A pip-installable Python SDK (`sentinel-auth-sdk`) for consuming services
- **`admin/`** -- A React admin panel for managing users, workspaces, and permissions

The fastest way to get running:

```bash
make setup   # One-time: generate keys, install deps, start DB
make start   # Start Sentinel on :9003
```

## Key Principles

- **No local user management.** All users authenticate through external identity providers (Google, GitHub, Microsoft Entra ID). The service never stores passwords.
- **Async everywhere.** The service uses SQLAlchemy 2.0 async, httpx async, and FastAPI's async request handlers throughout.
- **Generic permissions.** The permission system is service-agnostic. Any consuming service can register resources and manage access through the SDK.
- **Soft workspace isolation.** Workspaces share the same database, isolated by `workspace_id` filtering rather than per-workspace databases.
