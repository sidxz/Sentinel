# Next.js Integration

`@sentinel-auth/nextjs` provides Edge Middleware for JWT validation and server helpers for Server Components and Route Handlers.

```bash
npm install @sentinel-auth/js @sentinel-auth/nextjs
```

## AuthZ Middleware

Validates dual tokens (IdP + Sentinel authz) at the edge.

```typescript
// middleware.ts
import { createSentinelAuthzMiddleware } from '@sentinel-auth/nextjs/authz-middleware'

export default createSentinelAuthzMiddleware({
  sentinelUrl: process.env.SENTINEL_URL!,
  idpJwksUrl: 'https://www.googleapis.com/oauth2/v3/certs',
  idpAudience: process.env.GOOGLE_CLIENT_ID!,
  idpIssuer: 'https://accounts.google.com',
  serviceName: 'my-app',
  publicPaths: ['/login', '/auth/callback'],
})
export const config = { matcher: ['/((?!_next|favicon.ico).*)'] }
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `sentinelUrl` | `string` | required | Sentinel URL (derives JWKS endpoint) |
| `idpJwksUrl` | `string` | required | IdP JWKS URL for token verification |
| `idpAudience` | `string \| string[]` | **required** | Your app's OAuth client_id. Rejects tokens minted for any other client of the same IdP. |
| `idpIssuer` | `string` | `undefined` | Expected IdP `iss` claim. Strongly recommended. |
| `serviceName` | `string` | **required** | Your service's name (as registered in Sentinel). Authz token's `svc` claim must equal this — stops cross-service token replay. |
| `effectiveScope` | `string` | `undefined` | Realm slug (this service's shared scope). When set, the authz token's `svc` may equal either `serviceName` or this — so a [realm](../guide/realms.md) member accepts a realm-shared user token (Flow A). Resolve it once at startup with `fetchWhoami` from `@sentinel-auth/js/server`. Omit for standalone apps. |
| `publicPaths` | `string[]` | `[]` | Paths that skip auth |
| `loginPath` | `string` | `"/login"` | Redirect for unauthenticated page requests |

What it does: strips spoofed `x-sentinel-*` headers, verifies IdP token (signature + `aud` + optional `iss`) against IdP JWKS, verifies authz token against Sentinel JWKS, checks `idp_sub` binding, checks `svc` binding, sets `x-sentinel-*` headers for downstream components. API routes get 401 JSON; page routes redirect.

## Proxy Middleware

For Sentinel's redirect-based OAuth flow. Validates a single JWT.

```typescript
// middleware.ts
import { createSentinelMiddleware } from '@sentinel-auth/nextjs/middleware'

export default createSentinelMiddleware({
  jwksUrl: process.env.SENTINEL_JWKS_URL!,
  publicPaths: ['/login', '/auth/callback'],
})
export const config = { matcher: ['/((?!_next|favicon.ico).*)'] }
```

Additional options: `audience` (default `"sentinel:access"`), `allowedWorkspaces` (optional workspace ID allowlist). Reads token from `Authorization: Bearer` header or `sentinel_access_token` cookie.

## Headers set by middleware

Both variants set these on success, readable in Server Components and Route Handlers:

| Header | Value |
|--------|-------|
| `x-sentinel-user-id` | User ID |
| `x-sentinel-email` | Email |
| `x-sentinel-name` | Display name |
| `x-sentinel-workspace-id` | Workspace ID |
| `x-sentinel-workspace-slug` | Workspace slug |
| `x-sentinel-workspace-role` | Workspace role |

## Server helpers

```typescript
import { getUser, requireUser, getToken, withAuth } from '@sentinel-auth/nextjs/server'
```

**getUser()** -- returns `SentinelUser | null` from middleware headers.

```tsx
// app/dashboard/page.tsx (Server Component)
import { getUser } from '@sentinel-auth/nextjs/server'

export default async function DashboardPage() {
  const user = await getUser()
  if (!user) return <p>Not authenticated</p>
  return <p>Welcome, {user.name}!</p>
}
```

**requireUser()** -- returns `SentinelUser` or throws.

**getToken()** -- raw JWT string from Authorization header.

**withAuth(handler)** -- HOC for Route Handlers.

```typescript
// app/api/notes/route.ts
import { withAuth } from '@sentinel-auth/nextjs/server'

export const GET = withAuth(async (req, user) => {
  return Response.json({ workspace: user.workspaceId })
})
```

## Client components

The default import re-exports all React components with `'use client'`:

```tsx
'use client'
import { AuthzProvider, useAuthz, AuthzGuard, AuthzCallback } from '@sentinel-auth/nextjs'
```

See [React Integration](react.md) for hook and component details.

## Complete example

```typescript
// middleware.ts
import { createSentinelAuthzMiddleware } from '@sentinel-auth/nextjs/authz-middleware'
export default createSentinelAuthzMiddleware({
  sentinelUrl: process.env.SENTINEL_URL!,
  idpJwksUrl: 'https://www.googleapis.com/oauth2/v3/certs',
  idpAudience: process.env.GOOGLE_CLIENT_ID!,
  idpIssuer: 'https://accounts.google.com',
  serviceName: 'my-app',
  publicPaths: ['/login', '/auth/callback'],
})
export const config = { matcher: ['/((?!_next|favicon.ico).*)'] }
```

```tsx
// app/login/page.tsx
'use client'
import { AuthzProvider, useAuthz } from '@sentinel-auth/nextjs'
import { IdpConfigs } from '@sentinel-auth/js'

function LoginButton() {
  const { login } = useAuthz()
  return <button onClick={() => login('google')}>Sign in with Google</button>
}

export default function LoginPage() {
  return (
    <AuthzProvider config={{
      sentinelUrl: process.env.NEXT_PUBLIC_SENTINEL_URL!,
      idps: { google: IdpConfigs.google(process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID!) },
    }}>
      <LoginButton />
    </AuthzProvider>
  )
}
```

```tsx
// app/auth/callback/page.tsx
'use client'
import { AuthzProvider, AuthzCallback } from '@sentinel-auth/nextjs'
import { useRouter } from 'next/navigation'

export default function CallbackPage() {
  const router = useRouter()
  return (
    <AuthzProvider config={{ sentinelUrl: process.env.NEXT_PUBLIC_SENTINEL_URL! }}>
      <AuthzCallback onSuccess={() => router.push('/dashboard')} />
    </AuthzProvider>
  )
}
```

```tsx
// app/dashboard/page.tsx (Server Component)
import { getUser } from '@sentinel-auth/nextjs/server'
export default async function DashboardPage() {
  const user = await getUser()
  return <h1>Welcome, {user?.name}</h1>
}
```
