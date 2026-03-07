# Quickstart

This guide assumes you have completed the [Installation](installation.md) steps. You will configure an identity provider, register a service app, and run the demo app to verify the full authorization flow.

## 1. Configure an Identity Provider

You need at least one identity provider for user authentication. **Google** is the easiest to get started with.

### Google (recommended for development)

1. Go to the [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
2. Create an **OAuth 2.0 Client ID** (application type: **Web application**).
3. Add the following to **Authorized JavaScript origins**:
    - `http://localhost:5174` (demo frontend)
4. Add the following to **Authorized redirect URIs**:
    - `http://localhost:9003/auth/callback/google` (admin panel login only)
5. Copy the client ID and secret into `service/.env`:

```dotenv
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
```

!!! tip "Other providers"
    GitHub and Microsoft EntraID are also supported. See the [Configuration](configuration.md) reference for their environment variables. You can enable multiple providers simultaneously.

!!! info "Why both origins and redirect URIs?"
    **Authorized JavaScript origins** are for your frontend apps that use Google Sign-In directly in the browser. **Authorized redirect URIs** are only needed for the admin panel, which uses a server-side OAuth callback.

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

## 5. Register a Service App

Register a **service app** for your frontend and backend. This gives your backend an API key for server-side calls and configures origin-based auth for your frontend.

=== "Admin Panel"

    1. Navigate to **Service Apps** in the sidebar.
    2. Click **Register Service App**.
    3. Set a name (e.g. `team-notes`) and a service name (e.g. `team-notes`).
    4. Add `http://localhost:5174` to **Allowed Origins**.
    5. Save and copy the generated `sk_...` key.

=== "curl"

    ```bash
    curl -X POST http://localhost:9003/admin/service-apps \
      -H "Content-Type: application/json" \
      -H "Cookie: admin_token=YOUR_ADMIN_TOKEN" \
      -H "X-Requested-With: XMLHttpRequest" \
      -d '{
        "name": "team-notes",
        "service_name": "team-notes",
        "allowed_origins": ["http://localhost:5174"]
      }'
    ```

!!! info "Service key vs. origin-based auth"
    The **service key** (`sk_...`) is for backend-to-backend calls -- permissions, roles, and resource registration. Browser clients use **origin-based auth** instead: Sentinel validates the request's `Origin` header against the service app's allowed origins. No API key is needed from the browser.

## 6. Try the Demo App

The repository includes a complete demo application ("Team Notes") that showcases the authorization flow with Google Sign-In, workspace roles, entity ACLs, and custom RBAC.

### Start the backend

```bash
cd demo-authz/backend
uv sync
cp .env.example .env
# Edit .env: set SERVICE_API_KEY=sk_... (the key from step 5)
uv run python -m src.main
```

The backend starts on **port 9200**.

### Start the frontend

In a new terminal:

```bash
cd demo-authz/frontend
npm install
cp .env.example .env
# Edit .env: set VITE_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
npm run dev
```

The frontend starts on **port 5174**.

### Sign in

Open [http://localhost:5174](http://localhost:5174) and sign in with Google. The demo shows:

- Google Sign-In button for authentication
- Workspace selection after first login
- Notes CRUD with role-based access control

## 7. What Just Happened

Here is the flow that ran when you signed in:

1. The frontend rendered a **Google Sign-In** button (using `@react-oauth/google`).
2. After you signed in, the frontend received a **Google ID token** directly from Google.
3. The frontend called Sentinel's **`POST /authz/resolve`** with the ID token and provider name. This uses origin-based auth -- no service key needed from the browser.
4. Sentinel **validated the token** against Google's JWKS, JIT-provisioned the user if it was their first login, and returned the list of workspaces.
5. After workspace selection, Sentinel returned a signed **authz JWT** containing workspace roles and RBAC actions.
6. The frontend sends **both tokens** on every API call to the backend: the IdP token in the `Authorization` header, and the authz token in the `X-Authz-Token` header.
7. The backend's `AuthzMiddleware` **validates both tokens** independently (IdP token against Google's public keys, authz token against Sentinel's public key) and verifies that the `idp_sub` claims match -- binding the two tokens to the same user.

```
Browser                     Sentinel (:9003)              Backend (:9200)
-------                     ----------------              ---------------
Google Sign-In
  -> Google ID token

POST /authz/resolve  -----> Validate IdP token
  { idp_token, provider }   JIT provision user
                       <---- { authz_token, workspaces }

Select workspace
POST /authz/resolve  -----> Issue authz JWT with
  { ..., workspace_id }     workspace roles + actions
                       <---- { authz_token }

GET /api/notes        ------------------------------------> Validate IdP token
  Authorization: Bearer <idp_token>                         Validate authz token
  X-Authz-Token: <authz_token>                              Check idp_sub binding
                                                            Authorize request
                       <------------------------------------ { notes: [...] }
```

## 8. Optional: Seed Data

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

## 9. Explore the API

Open the interactive Swagger UI:

> [http://localhost:9003/docs](http://localhost:9003/docs)

This documents every endpoint, including the `/authz/resolve` authorization flow, user management, workspace operations, group management, and the permission system.

## 10. Next Steps

- Follow the [Tutorial](../guide/tutorial.md) to build your own app with Google Sign-In and the authz flow.
- Review all available settings in the [Configuration](configuration.md) reference.
- Read the [Architecture](../guide/architecture.md) section to understand how the service is structured.
- Integrate your application using the [Python SDK](../sdk/index.md) or [JS/TS SDK](../js-sdk/index.md).
