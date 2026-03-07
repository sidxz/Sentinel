# JavaScript / TypeScript SDK

The **Sentinel Auth JS SDK** is a family of three npm packages that integrate JavaScript and TypeScript applications with the Sentinel Auth service. It supports two integration modes: **authz mode** (recommended), where your app handles IdP sign-in directly and Sentinel provides authorization tokens, and **proxy mode**, where Sentinel manages the full OAuth2 redirect flow.

## Packages

| Package | Purpose | Runtime |
|---------|---------|---------|
| `@sentinel-auth/js` | Core auth client + server utilities | Browser, Node.js, Edge |
| `@sentinel-auth/react` | React provider, hooks, components | Browser (React 18+) |
| `@sentinel-auth/nextjs` | Next.js Edge Middleware + server helpers | Next.js 14+ |

## What the SDK Provides

### Browser Auth Client (AuthZ Mode)

`SentinelAuthz` is the primary browser class for authz mode -- the recommended integration pattern:

- **IdP sign-in** -- use your IdP's client SDK (Google Sign-In, MSAL, etc.) to get an identity token
- **Resolve** -- call `resolve()` to validate the IdP token with Sentinel and get workspace options
- **Workspace selection** -- call `selectWorkspace()` to get a signed authz JWT
- **Token management** -- stores both tokens, auto-refreshes authz token before expiry
- **Auth-aware fetch** -- injects both `Authorization: Bearer` and `X-Authz-Token` headers, retries on 401

### Browser Auth Client (Full Proxy Mode)

`SentinelAuth` handles the full OAuth2 + PKCE redirect flow for apps that want Sentinel to manage the entire auth process (login redirect, callback, token exchange).

### React Bindings

- **`AuthzProvider`** -- React context provider wrapping `SentinelAuthz` (authz mode)
- **`useAuthz`** -- full authz context (resolve, selectWorkspace, user, fetch, fetchJson)
- **`useAuthzUser`** -- current user from authz token
- **`useAuthzHasRole`** -- workspace role check
- **`useAuthzFetch`** -- shortcut to dual-header fetch
- **`AuthzGuard`** -- conditional rendering based on authz state
- Also includes proxy-mode components: `SentinelAuthProvider`, `useAuth`, `AuthGuard`, `AuthCallback`

### Server Utilities

Node.js and Edge-compatible utilities for backend use:

- **`verifyToken`** -- JWT verification via JWKS (uses `jose`, Edge-compatible)
- **`PermissionClient`** -- Zanzibar-style permission checks (mirrors the Python SDK)
- **`RoleClient`** -- RBAC action checks (mirrors the Python SDK)

### Next.js Integration

Edge Middleware and server helpers for Next.js applications:

- **`createSentinelAuthzMiddleware`** -- Edge Middleware for dual-token validation (IdP + authz + binding)
- **`createSentinelMiddleware`** -- Edge Middleware for single-token validation (proxy mode)
- **`getUser` / `requireUser`** -- read user from middleware headers (works with either middleware)
- **`withAuth`** -- HOC for Route Handlers

## Quick Start

=== "React (AuthZ Mode)"

    ```bash
    npm install @sentinel-auth/js @sentinel-auth/react @react-oauth/google
    ```

    ```tsx
    import { GoogleOAuthProvider, GoogleLogin } from '@react-oauth/google'
    import { AuthzProvider, useAuthz } from '@sentinel-auth/react'

    function App() {
      return (
        <GoogleOAuthProvider clientId="your-google-client-id">
          <AuthzProvider config={{ sentinelUrl: 'http://localhost:9003' }}>
            <LoginPage />
          </AuthzProvider>
        </GoogleOAuthProvider>
      )
    }

    function LoginPage() {
      const { resolve, selectWorkspace, isAuthenticated, user } = useAuthz()

      if (isAuthenticated) return <p>Welcome, {user?.name}!</p>

      return (
        <GoogleLogin onSuccess={async (r) => {
          const result = await resolve(r.credential!, 'google')
          if (result.workspaces?.length === 1) {
            await selectWorkspace(r.credential!, 'google', result.workspaces[0].id)
          }
        }} />
      )
    }
    ```

=== "Next.js (AuthZ Mode)"

    ```bash
    npm install @sentinel-auth/js @sentinel-auth/nextjs @react-oauth/google
    ```

    ```typescript
    // middleware.ts
    import { createSentinelAuthzMiddleware } from '@sentinel-auth/nextjs/authz-middleware'

    export default createSentinelAuthzMiddleware({
      sentinelUrl: 'http://localhost:9003',
      idpJwksUrl: 'https://www.googleapis.com/oauth2/v3/certs',
      publicPaths: ['/login'],
    })

    export const config = { matcher: ['/((?!_next|favicon.ico).*)'] }
    ```

=== "Node.js Server"

    ```bash
    npm install @sentinel-auth/js
    ```

    ```typescript
    import { verifyToken, PermissionClient } from '@sentinel-auth/js/server'

    const permissions = new PermissionClient(
      'http://localhost:9003',
      'my-service',
      'sk_my_service_key',
    )

    // Verify a JWT from a request
    const payload = await verifyToken(token, {
      jwksUrl: 'http://localhost:9003/.well-known/jwks.json',
    })

    // Check permissions
    const canView = await permissions.can(token, 'document', docId, 'view')
    ```

## Next Steps

- [Installation](installation.md) -- install the packages
- [AuthZ Client](authz-client.md) -- configure the authz-mode browser client (recommended)
- [Auth Client](auth-client.md) -- configure the proxy-mode browser client
- [React Integration](react.md) -- provider, hooks, and components
- [Next.js Integration](nextjs.md) -- Edge Middleware and server helpers
- [Server Utilities](server.md) -- JWT verification, permission and role clients
