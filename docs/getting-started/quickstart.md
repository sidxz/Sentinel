# Quickstart

This guide assumes you have completed the [Installation](installation.md) steps. You will configure an OAuth provider, register client and service apps, and verify the full auth flow.

## 1. Configure an OAuth Provider

You need at least one OAuth provider for user authentication. **Google** is the easiest to get started with.

### Google (recommended for development)

1. Go to the [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
2. Create an OAuth 2.0 Client ID (application type: **Web application**).
3. Add `http://localhost:9003/auth/callback/google` as an **Authorized redirect URI**.
4. Copy the client ID and secret into `service/.env`:

```dotenv
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
```

!!! tip "Other providers"
    GitHub and Microsoft EntraID are also supported. See the [Configuration](configuration.md) reference for their environment variables. You can enable multiple providers simultaneously.

## 2. Verify the Session Secret

`make setup` generates a random `SESSION_SECRET_KEY` in `service/.env` automatically. If you set up manually, generate one:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Paste the output into `service/.env`:

```dotenv
SESSION_SECRET_KEY=your-generated-secret-here
```

!!! danger "Do not skip this in production"
    The default value (`dev-only-change-me-in-production`) is intentionally insecure. `make setup` generates a unique value for both dev and prod env files.

## 3. Start the Service

=== "Docker"

    If you followed the Docker installation, the service is already running. After updating `.env.prod` with OAuth credentials, restart to pick up the changes:

    ```bash
    docker compose -f docker-compose.prod.yml up -d
    ```

=== "From Source"

    ```bash
    make start
    ```

    This runs the FastAPI application with hot-reload on **port 9003**. Database migrations are applied automatically on startup.

Verify it's running:

```bash
curl http://localhost:9003/health
```

## 4. Access the Admin Panel

=== "Docker"

    Open [http://localhost:9003/admin](http://localhost:9003/admin) in your browser.

=== "From Source"

    Start the admin panel separately:

    ```bash
    make admin
    ```

    Then open [http://localhost:9004](http://localhost:9004).

!!! warning "Set ADMIN_EMAILS before first login"
    Your email must be listed in the `ADMIN_EMAILS` variable in `service/.env` (comma-separated) before you sign in for the first time. `make setup` prints a reminder for this. You can also promote a user with `make create-admin` (from-source only).

Sign in through the admin panel using your OAuth provider to create your initial user account.

## 5. Register a Client App

Every frontend that authenticates through Sentinel must be registered as a **client app** with its redirect URI(s). This prevents unauthorized apps from initiating OAuth flows.

=== "Admin Panel"

    1. Navigate to **Client Apps** in the sidebar.
    2. Click **Add Client App**.
    3. Set a name (e.g., `dev-frontend`) and add the redirect URI: `http://localhost:3000/auth/callback`.
    4. Save.

=== "curl"

    ```bash
    curl -X POST http://localhost:9003/admin/client-apps \
      -H "Content-Type: application/json" \
      -H "Cookie: admin_token=YOUR_ADMIN_TOKEN" \
      -H "X-Requested-With: XMLHttpRequest" \
      -d '{"name": "dev-frontend", "redirect_uris": ["http://localhost:3000/auth/callback"]}'
    ```

!!! info "Why client apps?"
    Client apps control the redirect URI allowlist. Sentinel will reject any `redirect_uri` that doesn't match a registered client app. This protects against open-redirect attacks.

## 6. Register a Service App

If your backend needs to call Sentinel's API (for permissions, roles, or resource registration), register a **service app** to get an API key.

=== "Admin Panel"

    1. Navigate to **Service Apps** in the sidebar.
    2. Click **Add Service App**.
    3. Set a name and service name for your backend.
    4. Copy the generated `sk_...` key — you'll need it for your backend's `.env`.

!!! info "Service apps are database-managed"
    Service API keys are created and managed through the admin panel. There is no environment variable for service keys.

## 7. Verify the Auth Flow

Navigate to the login endpoint with the redirect URI you registered:

> `http://localhost:9003/auth/login/google?redirect_uri=http://localhost:3000/auth/callback`

This redirects you to Google's consent screen. After you authorize, the service creates a user record (if it's your first login) and redirects to your `redirect_uri` with an authorization code (`?code=X`).

Exchange it for JWT tokens:

```bash
curl -X POST http://localhost:9003/auth/token \
  -H "Content-Type: application/json" \
  -d '{"code": "CODE_FROM_REDIRECT", "workspace_id": "YOUR_WS_ID", "code_verifier": "YOUR_CODE_VERIFIER"}'
```

!!! note "PKCE"
    The `code_verifier` is required for PKCE validation. In practice, the JS and Python SDKs handle PKCE automatically. For manual testing, generate a `code_verifier` before the login redirect and pass `code_challenge` + `code_challenge_method=S256` as query params.

## 8. Explore the API

Open the interactive Swagger UI:

> [http://localhost:9003/docs](http://localhost:9003/docs)

This documents every endpoint, including auth flows, user management, workspace operations, group management, and the permission system.

## Optional: Seed Data

Load test data to explore the API without manually creating resources:

=== "Docker"

    ```bash
    docker compose -f docker-compose.prod.yml exec sentinel python -m scripts.seed
    ```

=== "From Source"

    ```bash
    make seed
    ```

This populates the database with sample users, workspaces, groups, and permissions.

## Try the Demo App

The repository includes a complete demo application ("Team Notes") that showcases JWT auth, workspace roles, entity ACLs, and custom RBAC with a React frontend using `@sentinel-auth/react` and a FastAPI backend.

!!! note "Prerequisites"
    Before the demo app can authenticate, register a client app with redirect URI `http://localhost:9101/auth/callback` (see step 5 above) and a service app for the demo backend (see step 6).

```bash
# Demo backend
cd demo/backend && uv sync && uv run python -m src.main

# Demo frontend (in another terminal)
cd demo/frontend && npm install && npm run dev
```

Open [http://localhost:9101](http://localhost:9101) and sign in with Google. See the [Tutorial](../guide/tutorial.md) for a detailed walkthrough of how the demo is built.

## Next Steps

- Review all available settings in the [Configuration](configuration.md) reference.
- Read the [Architecture](../guide/architecture.md) section to understand how the service is structured.
- Follow the [Tutorial](../guide/tutorial.md) to build your own app with the SDK.
- Integrate your application using the [SDK guide](../sdk/index.md).
