# JavaScript / TypeScript SDK

The **Sentinel Auth JS SDK** is a family of three npm packages that integrate JavaScript and TypeScript applications with the Sentinel Auth service. It handles PKCE OAuth flows, token management, JWT verification, and permission/role checks so you can focus on your application logic.

## Packages

| Package | Purpose | Runtime |
|---------|---------|---------|
| `@sentinel-auth/js` | Core auth client + server utilities | Browser, Node.js, Edge |
| `@sentinel-auth/react` | React provider, hooks, components | Browser (React 18+) |
| `@sentinel-auth/nextjs` | Next.js Edge Middleware + server helpers | Next.js 14+ |

## What the SDK Provides

### Browser Auth Client

`SentinelAuth` is the core browser class that encapsulates the full OAuth2 + PKCE + workspace-selection flow:

- **PKCE login** -- generates code verifier/challenge, redirects to OAuth provider
- **Workspace selection** -- fetches available workspaces, completes token exchange
- **Token management** -- stores tokens, auto-refreshes before expiry
- **Auth-aware fetch** -- injects `Authorization: Bearer` header, retries on 401

### React Bindings

Provider, hooks, and components for React applications:

- **`SentinelAuthProvider`** -- React context provider wrapping `SentinelAuth`
- **`useAuth`** -- full auth context (login, logout, fetch, user)
- **`useUser`** -- current authenticated user (throws if not authenticated)
- **`useHasRole`** -- workspace role hierarchy check
- **`useAuthFetch`** -- shortcut to the auth-aware `fetch` wrapper
- **`AuthGuard`** -- conditional rendering based on auth state
- **`AuthCallback`** -- OAuth callback route handler with workspace selection

### Server Utilities

Node.js and Edge-compatible utilities for backend use:

- **`verifyToken`** -- JWT verification via JWKS (uses `jose`, Edge-compatible)
- **`PermissionClient`** -- Zanzibar-style permission checks (mirrors the Python SDK)
- **`RoleClient`** -- RBAC action checks (mirrors the Python SDK)

### Next.js Integration

Edge Middleware and server helpers for Next.js applications:

- **`createSentinelMiddleware`** -- Edge Middleware for JWT validation with JWKS
- **`getUser` / `requireUser`** -- read user from middleware-set headers in Server Components
- **`withAuth`** -- HOC for Route Handlers requiring authentication

## Quick Start

=== "React"

    ```bash
    npm install @sentinel-auth/js @sentinel-auth/react
    ```

    ```tsx
    import { SentinelAuthProvider, AuthGuard, useAuth } from '@sentinel-auth/react'

    function App() {
      return (
        <SentinelAuthProvider config={{ sentinelUrl: 'http://localhost:9003' }}>
          <AuthGuard fallback={<LoginPage />}>
            <Dashboard />
          </AuthGuard>
        </SentinelAuthProvider>
      )
    }

    function LoginPage() {
      const { login } = useAuth()
      return <button onClick={() => login('google')}>Sign in</button>
    }
    ```

=== "Next.js"

    ```bash
    npm install @sentinel-auth/js @sentinel-auth/react @sentinel-auth/nextjs
    ```

    ```typescript
    // middleware.ts
    import { createSentinelMiddleware } from '@sentinel-auth/nextjs/middleware'

    export default createSentinelMiddleware({
      jwksUrl: 'http://localhost:9003/.well-known/jwks.json',
      publicPaths: ['/login', '/auth/callback'],
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
- [Auth Client](auth-client.md) -- configure the browser auth client
- [React Integration](react.md) -- provider, hooks, and components
- [Next.js Integration](nextjs.md) -- Edge Middleware and server helpers
- [Server Utilities](server.md) -- JWT verification, permission and role clients
