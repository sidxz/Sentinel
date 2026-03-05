# Quickstart

This guide assumes you have completed the [Installation](installation.md) steps. You will configure an OAuth provider, start the service, and verify everything works.

## 1. Configure an OAuth Provider

You need at least one OAuth provider for user authentication. **Google** is the easiest to get started with.

### Google (recommended for development)

1. Go to the [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
2. Create an OAuth 2.0 Client ID (application type: **Web application**).
3. Add `http://localhost:9003/auth/callback/google` as an **Authorized redirect URI**.
4. Copy the client ID and secret into your `.env`:

```dotenv
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
```

!!! tip "Other providers"
    GitHub and Microsoft EntraID are also supported. See the [Configuration](configuration.md) reference for their environment variables. You can enable multiple providers simultaneously.

## 2. Set the Session Secret

The service uses server-side sessions for the OAuth flow. Generate a secure secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Paste the output into your `.env`:

```dotenv
SESSION_SECRET_KEY=your-generated-secret-here
```

!!! danger "Do not skip this in production"
    The default value (`dev-only-change-me-in-production`) is intentionally insecure. Always set a unique, random secret for any non-local environment.

## 3. Start the Service

```bash
make start
```

This runs the FastAPI application with hot-reload on **port 9003**. Database migrations are applied automatically on startup.

## 4. Verify It's Running

```bash
curl http://localhost:9003/health
```

You should get a `200 OK` response confirming the service is healthy.

## 5. Explore the API

Open the interactive Swagger UI in your browser:

> [http://localhost:9003/docs](http://localhost:9003/docs)

This documents every endpoint, including auth flows, user management, workspace operations, group management, and the permission system.

## 6. Try the Auth Flow

Navigate to the Google login endpoint in your browser:

> [http://localhost:9003/auth/login/google](http://localhost:9003/auth/login/google)

This will redirect you to Google's consent screen. After you authorize, the service creates a user record (if it's your first login) and returns JWT tokens.

## Optional: Seed Data and Admin UI

### Load test data

```bash
make seed
```

This populates the database with sample users, workspaces, groups, and permissions -- useful for exploring the API without manually creating resources.

### Start the Admin UI

```bash
make admin
```

The admin panel runs on **port 9004** at [http://localhost:9004](http://localhost:9004). It provides a dashboard with user management, workspace administration, and a permissions browser.

!!! note "Admin access"
    To access the admin UI, your user's email must be listed in the `ADMIN_EMAILS` environment variable (comma-separated). You can also promote a user with `make create-admin`.

## Try the Demo App

The repository includes a complete demo application ("Team Notes") that showcases all identity service features — JWT auth, workspace roles, entity ACLs, and custom RBAC — with a React frontend and FastAPI backend.

```bash
# Terminal 1: Identity service (if not already running)
make start

# Terminal 2: Demo backend
cd demo/backend && uv sync && uv run python -m src.main

# Terminal 3: Demo frontend
cd demo/frontend && npm install && npm run dev
```

Open [http://localhost:9101](http://localhost:9101) and sign in with Google. See the [Tutorial](../guide/tutorial.md) for a detailed walkthrough of how the demo is built.

## Next Steps

- Review all available settings in the [Configuration](configuration.md) reference.
- Read the [Architecture](../guide/architecture.md) section to understand how the service is structured.
- Follow the [Tutorial](../guide/tutorial.md) to build your own app with the SDK.
- Integrate your application using the [SDK guide](../sdk/index.md).
