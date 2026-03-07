---
title: Sentinel Auth
description: Authentication, workspace management, and Zanzibar-style permissions for your applications
---

![Sentinel Auth](assets/images/splash.png)

# Sentinel Auth

**An open source identity service for Python applications.** Sentinel Auth handles OAuth2/OIDC authentication, multi-tenant workspace management, and fine-grained Zanzibar-style permissions so you can focus on your application logic.

Built with **FastAPI**, **SQLAlchemy 2.0** (async), **PostgreSQL 16**, **Redis 7**, and **Authlib**.

---

## Key Features

<div class="grid cards" markdown>

-   :material-shield-lock:{ .lg .middle } **OAuth2 / OIDC Authentication**

    ---

    Sign in with Google, GitHub, and Microsoft EntraID out of the box. PKCE S256 on supported providers, RS256 JWT tokens with refresh rotation and reuse detection.

    [:octicons-arrow-right-24: Authentication guide](guide/authentication.md)

-   :material-office-building:{ .lg .middle } **Multi-Tenant Workspaces**

    ---

    Isolate users, groups, and resources by workspace. Role-based access control at the workspace level with `owner`, `admin`, `editor`, and `viewer` roles embedded in every JWT.

    [:octicons-arrow-right-24: Workspace management](guide/workspaces.md)

-   :material-lock-check:{ .lg .middle } **Zanzibar-Style Permissions**

    ---

    Generic resource permissions with `service_name`, `resource_type`, and `resource_id`. Check access, list accessible resources, and share via ACLs -- all through a simple API.

    [:octicons-arrow-right-24: Permissions model](guide/permissions.md)

-   :material-language-python:{ .lg .middle } **Python SDK**

    ---

    Install `sentinel-auth-sdk` and integrate in minutes. The SDK handles JWT validation, permission checks, and resource registration with a clean, typed Python API.

    [:octicons-arrow-right-24: SDK reference](sdk/index.md)

-   :material-language-typescript:{ .lg .middle } **JavaScript / TypeScript SDK**

    ---

    Three npm packages for browser, React, and Next.js. PKCE auth flow, token management, auth-aware fetch, React hooks, Edge Middleware, and server-side JWT verification.

    [:octicons-arrow-right-24: JS/TS SDK](js-sdk/index.md)

-   :material-key-chain:{ .lg .middle } **Service-to-Service Auth**

    ---

    Secure inter-service communication with API keys via the `X-Service-Key` header. Three auth tiers -- user JWT, dual (service key + JWT), and service-key-only -- for flexible access control.

    [:octicons-arrow-right-24: Security model](security.md)

-   :material-view-dashboard:{ .lg .middle } **Admin Panel**

    ---

    Built-in admin interface for managing users, workspaces, groups, and permissions. Activity logging, CSV import/export, and a dashboard for operational visibility.

    [:octicons-arrow-right-24: Admin guide](guide/admin.md)

</div>

---

## Get Started

Choose your path based on what you need to do:

<div class="grid cards" markdown>

-   :material-puzzle:{ .lg .middle } **I want to integrate the SDK**

    ---

    Add authentication and permission checks to your application using the Sentinel Auth SDKs.

    **Python** -- `pip install sentinel-auth-sdk` [:octicons-arrow-right-24: Python SDK](sdk/index.md)

    **JavaScript / TypeScript** -- `npm install @sentinel-auth/js` [:octicons-arrow-right-24: JS/TS SDK](js-sdk/index.md)

-   :material-server:{ .lg .middle } **I want to run the service**

    ---

    Deploy Sentinel Auth as your authentication and authorization backend.

    1. Generate RS256 key pair for JWT signing
    2. Create `.env` from the template
    3. `docker compose -f docker-compose.prod.yml up -d`
    4. Register OAuth2 credentials with your identity providers
    5. Register client apps and service apps via the admin panel

    [:octicons-arrow-right-24: Getting started](getting-started/index.md)

</div>

---
> **BETA SOFTWARE WARNING**  
> This software is currently in beta and **not fully production ready**. While functional and actively developed, it may contain bugs, incomplete features, or breaking changes. Use in production environments at your own risk. Contributions and feedback are welcome!

## Architecture at a Glance

Sentinel Auth sits between your frontend applications and your backend microservices:

```
Frontend App          Sentinel Auth                  Your Microservices
-----------           -----------------------          ------------------
                      +---------------------+
  Login via    -----> | OAuth2/OIDC (Authlib)|
  Google/GitHub/      | Session + PKCE       |
  EntraID             +---------------------+
                              |
                      +---------------------+
  JWT in Auth  <----- | JWT Issuance (RS256) |
  header              | Access + Refresh     |
                      +---------------------+
                              |
  API calls    -----> +---------------------+          +------------------+
  with Bearer         | User / Workspace /  | -------> | Permission checks|
  token               | Group Management    |          | via SDK or API   |
                      +---------------------+          +------------------+
                              |
                      +---------------------+
                      | Zanzibar Permissions |
                      | register / check /   |
                      | share / accessible   |
                      +---------------------+
```

**No local passwords.** Users always authenticate through external identity providers. Sentinel Auth manages their identity, workspace membership, group assignments, and fine-grained resource permissions.

---

