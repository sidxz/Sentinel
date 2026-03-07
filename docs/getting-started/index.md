# Getting Started

This section walks you through setting up Sentinel Auth from scratch to a running instance with IdP-based authentication and authorization.

## Prerequisites

### Docker (recommended)

| Tool | Version | Purpose |
|------|---------|---------|
| **Docker** & **Docker Compose** | latest | Runs the Sentinel container, PostgreSQL 16, and Redis 7 |
| **OpenSSL** | any | Generates RSA key pair for JWT signing |

### From Source (contributors)

All of the above, plus:

| Tool | Version | Purpose |
|------|---------|---------|
| **Python** | 3.12+ | Runtime for the FastAPI service and SDK |
| **uv** | latest | Python package manager and workspace tool |
| **Node.js** | 18+ | Admin panel and demo frontend |

You will also need **OAuth credentials** from at least one identity provider (Google is the easiest to set up) to enable user authentication.

!!! note "Google Sign-In setup"
    Your frontend authenticates users directly with Google (or another IdP). To set this up, go to the [Google Cloud Console](https://console.cloud.google.com/apis/credentials), create an **OAuth 2.0 Client ID** (Web application), and add your frontend's URL (e.g. `http://localhost:5174`) to the **Authorized JavaScript origins**. The [Quickstart](quickstart.md) covers this in detail.

## What's Covered

- **[Installation](installation.md)** -- Pull the Docker image (or clone the repo for development), generate JWT keys, and start the full stack.
- **[Quickstart](quickstart.md)** -- Configure an identity provider, register a service app, and run the demo app end to end.
- **[Configuration](configuration.md)** -- Complete reference for every environment variable, organized by category.
