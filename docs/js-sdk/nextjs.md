# Next.js Integration

The `@sentinel-auth/nextjs` package provides Edge Middleware for JWT validation, server helpers for Server Components and Route Handlers, and client-side re-exports from `@sentinel-auth/react`. It supports both **authz mode** (recommended) and **proxy mode**.

## AuthZ Mode Edge Middleware (Recommended)

For apps using authz mode (direct IdP sign-in + Sentinel authorization), use `createSentinelAuthzMiddleware`. It validates both the IdP token and the Sentinel authz token at the edge.

### Setup

Create `middleware.ts` in your project root:

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

### Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sentinelUrl` | `string` | *required* | Sentinel URL (derives JWKS endpoint) |
| `idpJwksUrl` | `string` | *required* | IdP's JWKS URL for token validation |
| `publicPaths` | `string[]` | `[]` | Paths that skip authentication |
| `loginPath` | `string` | `"/login"` | Redirect for unauthenticated pages |

### Behavior

1. **Public paths** pass through
2. Validates IdP token (`Authorization: Bearer`) against IdP JWKS
3. Validates authz token (`X-Authz-Token`) against Sentinel JWKS
4. Checks `idp_sub` binding between tokens
5. Sets `x-sentinel-*` headers on success
6. **API routes** (`/api/*`) get 401, **page routes** redirect to `loginPath`

### Client Components

The default import re-exports authz components from `@sentinel-auth/react`:

```tsx
'use client'

import { useAuthz, useAuthzUser, AuthzGuard, AuthzProvider } from '@sentinel-auth/nextjs'
```

---

## Full Proxy Mode Edge Middleware

For apps using Sentinel's OAuth redirect flow instead of direct IdP sign-in.

### Setup

Create `middleware.ts` in your project root:

```typescript
import { createSentinelMiddleware } from '@sentinel-auth/nextjs/middleware'

export default createSentinelMiddleware({
  jwksUrl: 'http://localhost:9003/.well-known/jwks.json',
  publicPaths: ['/login', '/auth/callback'],
})

export const config = {
  matcher: ['/((?!_next|favicon.ico).*)'],
}
```

### Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `jwksUrl` | `string` | *required* | URL to the Sentinel JWKS endpoint |
| `publicPaths` | `string[]` | `[]` | Paths that skip authentication |
| `loginPath` | `string` | `"/login"` | Redirect target for unauthenticated page requests |
| `audience` | `string` | `"sentinel:access"` | Expected JWT audience |
| `allowedWorkspaces` | `string[]` | -- | Optional workspace ID allowlist |

### Behavior

1. **Public paths** are passed through without authentication
2. Token is extracted from the `Authorization: Bearer` header or the `sentinel_access_token` cookie
3. Token is verified against the JWKS endpoint using `jose`
4. On success, user info is forwarded via `x-sentinel-*` response headers
5. On failure:
    - **API routes** (`/api/*`) receive a `401 Unauthorized` JSON response
    - **Page routes** are redirected to `loginPath`

---

## Headers Set

Both middleware variants set these headers on successful verification, readable in Server Components and Route Handlers:

| Header | Description |
|--------|-------------|
| `x-sentinel-user-id` | User ID |
| `x-sentinel-email` | Email address |
| `x-sentinel-name` | Display name |
| `x-sentinel-workspace-id` | Workspace ID |
| `x-sentinel-workspace-slug` | Workspace slug |
| `x-sentinel-workspace-role` | Workspace role |

## Server Helpers

Read user information set by the middleware in Server Components and Route Handlers. These work with either middleware variant.

### `getUser`

Returns the current user or `null` if not authenticated.

```typescript
import { getUser } from '@sentinel-auth/nextjs/server'

export default async function DashboardPage() {
  const user = await getUser()
  if (!user) return <p>Not authenticated</p>
  return <p>Welcome, {user.name}!</p>
}
```

### `requireUser`

Returns the current user or throws an error (for use with error boundaries or try/catch).

```typescript
import { requireUser } from '@sentinel-auth/nextjs/server'

export default async function ProfilePage() {
  const user = await requireUser()
  return <p>{user.email}</p>
}
```

### `getToken`

Get the raw JWT from the `Authorization` header.

```typescript
import { getToken } from '@sentinel-auth/nextjs/server'

export default async function ApiPage() {
  const token = await getToken()
  // Use token for downstream API calls
}
```

### `withAuth`

HOC for Route Handlers that require authentication. Extracts the user and passes it to your handler.

```typescript
import { withAuth } from '@sentinel-auth/nextjs/server'

export const GET = withAuth(async (req, user) => {
  return Response.json({ userId: user.userId, workspace: user.workspaceSlug })
})
```

## Client-Side Components

The default import re-exports everything from `@sentinel-auth/react` with `'use client'`, so you can use all React hooks and components in Next.js Client Components:

```tsx
'use client'

import { useAuth, useUser, AuthGuard, AuthCallback } from '@sentinel-auth/nextjs'
import { useAuthz, useAuthzUser, AuthzGuard, AuthzProvider } from '@sentinel-auth/nextjs'
```

See the [React Integration](react.md) docs for full details on these exports.

## Full Example

=== "AuthZ Mode"

    ```typescript
    // middleware.ts
    import { createSentinelAuthzMiddleware } from '@sentinel-auth/nextjs/authz-middleware'

    export default createSentinelAuthzMiddleware({
      sentinelUrl: process.env.SENTINEL_URL!,
      idpJwksUrl: 'https://www.googleapis.com/oauth2/v3/certs',
      publicPaths: ['/login'],
    })

    export const config = { matcher: ['/((?!_next|favicon.ico).*)'] }
    ```

    ```tsx
    // app/login/page.tsx
    'use client'

    import { GoogleOAuthProvider, GoogleLogin } from '@react-oauth/google'
    import { AuthzProvider, useAuthz } from '@sentinel-auth/nextjs'

    function LoginButton() {
      const { resolve, selectWorkspace } = useAuthz()
      return (
        <GoogleLogin onSuccess={async (r) => {
          const result = await resolve(r.credential!, 'google')
          if (result.workspaces?.length === 1) {
            await selectWorkspace(r.credential!, 'google', result.workspaces[0].id)
          }
        }} />
      )
    }

    export default function LoginPage() {
      return (
        <GoogleOAuthProvider clientId={process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID!}>
          <AuthzProvider config={{ sentinelUrl: process.env.NEXT_PUBLIC_SENTINEL_URL! }}>
            <LoginButton />
          </AuthzProvider>
        </GoogleOAuthProvider>
      )
    }
    ```

=== "Proxy Mode"

    ```typescript
    // middleware.ts
    import { createSentinelMiddleware } from '@sentinel-auth/nextjs/middleware'

    export default createSentinelMiddleware({
      jwksUrl: process.env.SENTINEL_JWKS_URL!,
      publicPaths: ['/login', '/auth/callback'],
    })

    export const config = {
      matcher: ['/((?!_next|favicon.ico).*)'],
    }
    ```

    ```tsx
    // app/login/page.tsx
    'use client'

    import { SentinelAuthProvider, useAuth } from '@sentinel-auth/nextjs'

    function LoginButton() {
      const { login } = useAuth()
      return <button onClick={() => login('google')}>Sign in</button>
    }

    export default function LoginPage() {
      return (
        <SentinelAuthProvider config={{ sentinelUrl: process.env.NEXT_PUBLIC_SENTINEL_URL! }}>
          <LoginButton />
        </SentinelAuthProvider>
      )
    }
    ```

=== "Server Component"

    ```tsx
    // app/layout.tsx
    import { getUser } from '@sentinel-auth/nextjs/server'

    export default async function RootLayout({ children }) {
      const user = await getUser()
      return (
        <html>
          <body>
            <nav>{user ? `Hi, ${user.name}` : 'Not signed in'}</nav>
            {children}
          </body>
        </html>
      )
    }
    ```

=== "Route Handler"

    ```typescript
    // app/api/notes/route.ts
    import { withAuth } from '@sentinel-auth/nextjs/server'

    export const GET = withAuth(async (req, user) => {
      const notes = await db.notes.findMany({
        where: { workspaceId: user.workspaceId },
      })
      return Response.json(notes)
    })
    ```

## Next Steps

- [Next.js Tutorial](../guide/tutorial-nextjs.md) -- step-by-step guide building a Team Notes app with Next.js
- [React Integration](react.md) -- hooks, components, and provider
- [AuthZ Client](authz-client.md) -- configure the authz-mode browser client
- [Server Utilities](server.md) -- JWT verification and permission checks
- [Auth Client](auth-client.md) -- proxy-mode browser auth client
