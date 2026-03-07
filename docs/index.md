---
title: Sentinel Auth
description: Authentication proxy and authorization service. Bring your own identity provider -- Sentinel handles authorization, workspace management, and Zanzibar-style permissions.
---

![Sentinel Auth](assets/images/splash.png)

# Sentinel Auth

**An open source authorization service for Python applications.** Bring your own identity provider -- Sentinel Auth validates IdP tokens, issues authorization JWTs, manages multi-tenant workspaces, and provides fine-grained Zanzibar-style permissions so you can focus on your application logic.

Built with **FastAPI**, **SQLAlchemy 2.0** (async), **PostgreSQL 16**, **Redis 7**, and **Authlib**.

---

## Key Features

<div class="grid cards" markdown>

-   :material-shield-lock:{ .lg .middle } **Bring Your Own IdP**

    ---

    Sign in with Google, GitHub, or Microsoft EntraID using their native SDKs. Sentinel validates IdP tokens and issues authorization JWTs with workspace roles and RBAC actions.

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

    Three npm packages for browser, React, and Next.js. Google Sign-In with `AuthzProvider`, token management, auth-aware fetch, React hooks, and server-side JWT verification.

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

-   :material-rocket-launch:{ .lg .middle } **Quickstart**

    ---

    Set up Sentinel, configure Google Sign-In, and run the demo app end to end.

    [:octicons-arrow-right-24: Quickstart](getting-started/quickstart.md)

-   :material-puzzle:{ .lg .middle } **I want to integrate the SDK**

    ---

    Add authorization and permission checks to your application using the Sentinel Auth SDKs.

    **Python** -- `pip install sentinel-auth-sdk` [:octicons-arrow-right-24: Python SDK](sdk/index.md)

    **JavaScript / TypeScript** -- `npm install @sentinel-auth/js` [:octicons-arrow-right-24: JS/TS SDK](js-sdk/index.md)

-   :material-server:{ .lg .middle } **I want to run the service**

    ---

    Deploy Sentinel Auth as your authorization backend.

    1. Generate RS256 key pair for JWT signing
    2. Create `.env` from the template
    3. `docker compose -f docker-compose.prod.yml up -d`
    4. Configure your identity provider (Google, GitHub, or EntraID)
    5. Register service apps via the admin panel

    [:octicons-arrow-right-24: Getting started](getting-started/index.md)

</div>

---
> **BETA SOFTWARE WARNING**
> This software is currently in beta and **not fully production ready**. While functional and actively developed, it may contain bugs, incomplete features, or breaking changes. Use in production environments at your own risk. Contributions and feedback are welcome!

## Architecture at a Glance

Your frontend authenticates users directly with their identity provider. Sentinel validates the IdP token and issues an authorization JWT:

```
Frontend App          Sentinel Auth                  Your Backend
-----------           -----------------------        ------------------

  Sign in with   ->   (not involved -- client
  Google/GitHub/       handles IdP directly)
  EntraID directly

  Got IdP token  ->   POST /authz/resolve
                      { idp_token, provider }
                      Validates IdP token
                      JIT provisions user
                 <-   { authz_token, workspaces }

  API calls with ->                                  Validates both:
  both tokens:                                        - IdP token (IdP key)
  Authorization:                                      - Authz token (Sentinel key)
  Bearer <idp>                                        - idp_sub binding
  X-Authz-Token:
  <authz>

  Permissions,                                       Uses SDK:
  Roles, ACLs    ->   Zanzibar permissions   ->      sentinel.permissions.can()
                      RBAC actions                   sentinel.require_action()
```

**No local passwords.** Users always authenticate through external identity providers. Sentinel manages their authorization, workspace membership, group assignments, and fine-grained resource permissions.

---
