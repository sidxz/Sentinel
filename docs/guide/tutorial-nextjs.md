# Tutorial: Next.js Frontend

This tutorial shows how to build the **Team Notes** frontend using Next.js App Router and `@sentinel-auth/nextjs`. It covers the same app as the [main tutorial](tutorial.md) but replaces the Vite + React frontend with Next.js.

!!! tip "Backend first"
    Complete [Steps 1--10 of the main tutorial](tutorial.md) before starting here. This page only covers the Next.js frontend.

## Prerequisites

- Sentinel running locally with the backend from the main tutorial
- Node.js 18+
- Familiarity with Next.js App Router

## What's Different from React + Vite?

| Concern | React + Vite | Next.js |
|---------|-------------|---------|
| Auth enforcement | `AuthzGuard` component | Edge Middleware (server-side) |
| Token validation | Client-side only | Dual-token validation at Edge |
| User in server code | N/A | `getUser()` / `requireUser()` from headers |
| Route handlers | Separate FastAPI backend | Can use Next.js Route Handlers alongside FastAPI |
| Client components | Everything is client | Explicit `'use client'` where needed |
| Imports | `@sentinel-auth/react` | `@sentinel-auth/nextjs` (re-exports with `'use client'`) |

---

## Step 1: Create the Next.js App

```bash
npx create-next-app@latest team-notes-nextjs --typescript --tailwind --app --src-dir
cd team-notes-nextjs
npm install @sentinel-auth/js @sentinel-auth/nextjs @react-oauth/google @tanstack/react-query
```

Add the environment variables to `.env.local`:

```dotenv
NEXT_PUBLIC_SENTINEL_URL=http://localhost:9003
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
IDP_JWKS_URL=https://www.googleapis.com/oauth2/v3/certs
```

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_SENTINEL_URL` | Sentinel base URL (used by `AuthzProvider` on the client) |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | Google OAuth Client ID for `@react-oauth/google` |
| `IDP_JWKS_URL` | Google's JWKS endpoint for Edge Middleware token verification |

## Step 2: Edge Middleware (Dual-Token)

Create `middleware.ts` in the project root. This validates **both** tokens at the edge before any page or API route runs:

```typescript
// middleware.ts
import { createSentinelAuthzMiddleware } from '@sentinel-auth/nextjs/authz-middleware'

export default createSentinelAuthzMiddleware({
  sentinelUrl: process.env.NEXT_PUBLIC_SENTINEL_URL || 'http://localhost:9003',
  idpJwksUrl: process.env.IDP_JWKS_URL || 'https://www.googleapis.com/oauth2/v3/certs',
  publicPaths: ['/login'],
})

export const config = {
  matcher: ['/((?!_next|favicon.ico).*)'],
}
```

Every non-public request must carry two tokens:

| Header | Token | Verified against |
|--------|-------|------------------|
| `Authorization: Bearer <token>` | Google ID token | Google's JWKS (`idpJwksUrl`) |
| `X-Authz-Token: <token>` | Sentinel authz token | Sentinel's JWKS (derived from `sentinelUrl`) |

The middleware verifies both signatures, then checks that the `sub` claim in the Google token matches the `idp_sub` claim in the Sentinel authz token. This binding ensures the two tokens belong to the same user.

After verification, the middleware:

- **Strips** any incoming `x-sentinel-*` headers (prevents spoofing).
- **Sets** `x-sentinel-user-id`, `x-sentinel-email`, `x-sentinel-name`, `x-sentinel-workspace-id`, `x-sentinel-workspace-slug`, and `x-sentinel-workspace-role` from the authz token claims.
- **Redirects** unauthenticated page requests to `/login`.
- **Returns 401** for unauthenticated API route requests.

## Step 3: Auth Provider Layout

The auth provider wraps all pages with `GoogleOAuthProvider` (for the sign-in button) and `AuthzProvider` (for token management and authenticated fetches).

First, create the Sentinel client instance:

```typescript
// src/lib/sentinel.ts
import { SentinelAuthz } from '@sentinel-auth/js'

export const authzClient = new SentinelAuthz({
  sentinelUrl: process.env.NEXT_PUBLIC_SENTINEL_URL || 'http://localhost:9003',
})
```

Then the providers wrapper:

```tsx
// src/app/providers.tsx
'use client'

import { GoogleOAuthProvider } from '@react-oauth/google'
import { AuthzProvider } from '@sentinel-auth/nextjs'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { authzClient } from '@/lib/sentinel'

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () => new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1 } } }),
  )

  return (
    <GoogleOAuthProvider clientId={process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID!}>
      <AuthzProvider client={authzClient}>
        <QueryClientProvider client={queryClient}>
          {children}
        </QueryClientProvider>
      </AuthzProvider>
    </GoogleOAuthProvider>
  )
}
```

Wire it into the root layout:

```tsx
// src/app/layout.tsx
import { Providers } from './providers'

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
```

!!! note "Why two providers?"
    `GoogleOAuthProvider` renders Google's Sign-In button and handles the credential response. `AuthzProvider` manages the dual-token lifecycle -- resolving workspaces, storing tokens, attaching them to fetch calls, and auto-refreshing the authz token before it expires.

## Step 4: Login Page

The login page uses Google's Sign-In button directly. There is no OAuth redirect and no callback route -- Google Sign-In runs entirely in the browser and returns a credential (an ID token) to your `onSuccess` handler.

```tsx
// src/app/login/page.tsx
'use client'

import { GoogleLogin } from '@react-oauth/google'
import { useAuthz } from '@sentinel-auth/nextjs'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import type { AuthzResolveResponse } from '@sentinel-auth/nextjs'

export default function LoginPage() {
  const { resolve, selectWorkspace } = useAuthz()
  const router = useRouter()
  const [workspaces, setWorkspaces] = useState<AuthzResolveResponse['workspaces'] | null>(null)
  const [idpToken, setIdpToken] = useState('')

  const handleLogin = async (credential: string) => {
    setIdpToken(credential)
    const result = await resolve(credential, 'google')

    // Single workspace — select automatically
    if (result.workspaces?.length === 1) {
      await selectWorkspace(credential, 'google', result.workspaces[0].id)
      router.replace('/notes')
      return
    }

    // Multiple workspaces — let the user pick
    setWorkspaces(result.workspaces ?? null)
  }

  if (workspaces) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="w-full max-w-sm space-y-2">
          <h2 className="text-center text-lg font-semibold">Select Workspace</h2>
          {workspaces.map((ws) => (
            <button
              key={ws.id}
              onClick={async () => {
                await selectWorkspace(idpToken, 'google', ws.id)
                router.replace('/notes')
              }}
              className="w-full rounded-lg border p-4 text-left hover:bg-gray-50"
            >
              <div className="font-medium">{ws.name}</div>
              <div className="text-xs text-gray-500">{ws.slug} -- {ws.role}</div>
            </button>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen items-center justify-center">
      <div className="text-center space-y-6">
        <h1 className="text-2xl font-bold">Team Notes</h1>
        <GoogleLogin
          onSuccess={(response) => handleLogin(response.credential!)}
          onError={() => console.error('Google Sign-In failed')}
        />
      </div>
    </div>
  )
}
```

The auth flow works in three steps:

1. **Google Sign-In** -- the user clicks the button, Google returns an ID token.
2. **`resolve(idpToken, 'google')`** -- sends the ID token to Sentinel's `/authz/resolve` endpoint, which returns the user's available workspaces.
3. **`selectWorkspace(idpToken, 'google', wsId)`** -- exchanges the ID token for a Sentinel authz token scoped to the chosen workspace. Both tokens are stored in `localStorage` and attached to all subsequent requests.

## Step 5: Server Component -- User Context

Behind the middleware, every request has verified `x-sentinel-*` headers. Use `getUser()` to read them in Server Components:

```tsx
// src/app/notes/layout.tsx
import { getUser } from '@sentinel-auth/nextjs/server'
import { LogoutButton } from './logout-button'

export default async function NotesLayout({ children }: { children: React.ReactNode }) {
  const user = await getUser()

  return (
    <div>
      <nav className="flex items-center justify-between border-b px-6 py-3">
        <span className="text-sm">
          {user?.name} -- {user?.workspaceSlug} ({user?.workspaceRole})
        </span>
        <LogoutButton />
      </nav>
      {children}
    </div>
  )
}
```

The logout button is a Client Component that clears the stored tokens:

```tsx
// src/app/notes/logout-button.tsx
'use client'

import { useAuthz } from '@sentinel-auth/nextjs'
import { useRouter } from 'next/navigation'

export function LogoutButton() {
  const { logout } = useAuthz()
  const router = useRouter()

  return (
    <button
      onClick={() => { logout(); router.replace('/login') }}
      className="text-sm text-gray-500 hover:text-gray-800"
    >
      Logout
    </button>
  )
}
```

## Step 6: Client Component -- Fetch Notes

Use `fetchJson` from `useAuthz()` with React Query. The `fetchJson` helper automatically attaches both the `Authorization` and `X-Authz-Token` headers to every request:

```tsx
// src/app/notes/page.tsx
'use client'

import { useQuery } from '@tanstack/react-query'
import { useAuthz, useAuthzHasRole } from '@sentinel-auth/nextjs'

interface Note {
  id: string
  title: string
  content: string
}

export default function NotesPage() {
  const { fetchJson } = useAuthz()
  const canCreate = useAuthzHasRole('editor')

  const { data: notes } = useQuery({
    queryKey: ['notes'],
    queryFn: () => fetchJson<Note[]>('/api/notes'),
  })

  return (
    <div className="mx-auto max-w-2xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-bold">Notes</h1>
        {canCreate && (
          <button className="rounded bg-blue-600 px-4 py-2 text-sm text-white">
            New Note
          </button>
        )}
      </div>
      <ul className="space-y-2">
        {notes?.map((note) => (
          <li key={note.id} className="rounded border p-4">
            <div className="font-medium">{note.title}</div>
            <div className="text-sm text-gray-500">{note.content}</div>
          </li>
        ))}
      </ul>
    </div>
  )
}
```

`useAuthzHasRole('editor')` checks the workspace role from the authz token against a hierarchy (`viewer` < `editor` < `admin` < `owner`). A user with the `admin` role satisfies a check for `editor`.

## Step 7: Route Handler with `withAuth`

You can add Next.js Route Handlers that proxy or augment your FastAPI backend. Use `withAuth` to enforce authentication -- it reads the `x-sentinel-*` headers set by the middleware and passes the user to your handler:

```typescript
// src/app/api/me/route.ts
import { withAuth } from '@sentinel-auth/nextjs/server'

export const GET = withAuth(async (req, user) => {
  return Response.json({
    userId: user.userId,
    email: user.email,
    workspace: user.workspaceSlug,
    role: user.workspaceRole,
  })
})
```

If the middleware did not set user headers (which only happens if the route was not matched or was public), `withAuth` throws a 401 error.

## Step 8: Configure and Run

### Register the service app

In the Sentinel admin panel, go to **Service Apps** and register:

- **Name**: `team-notes-nextjs`
- **Allowed Origins**: `http://localhost:3000`

### Environment

Confirm `.env.local` has:

```dotenv
NEXT_PUBLIC_SENTINEL_URL=http://localhost:9003
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
IDP_JWKS_URL=https://www.googleapis.com/oauth2/v3/certs
```

### Start

```bash
# Terminal 1: Sentinel
make start

# Terminal 2: Demo backend (from main tutorial)
cd demo/backend && uv run python -m src.main

# Terminal 3: Next.js frontend
cd team-notes-nextjs && npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Click the Google Sign-In button, pick a workspace, and you will be redirected to the notes page.

## Summary

| What | How | SDK API |
|------|-----|---------|
| Route protection | Edge Middleware | `createSentinelAuthzMiddleware()` |
| Token validation | Dual-token at Edge | Validates IdP + authz + `idp_sub` binding |
| Google Sign-In | Native button | `GoogleLogin` from `@react-oauth/google` |
| Workspace selection | Resolve + select | `resolve()`, `selectWorkspace()` from `useAuthz()` |
| User in Server Components | Headers from middleware | `getUser()`, `requireUser()` |
| User in Client Components | React context | `useAuthz()`, `useAuthzUser()` |
| Authenticated fetch | Dual-header + JSON parsing | `fetchJson()` from `useAuthz()` |
| Role checks | Hook | `useAuthzHasRole("editor")` |
| Route Handlers | HOC wrapper | `withAuth()` |

## Next Steps

- [Main Tutorial](tutorial.md) -- FastAPI backend setup
- [Next.js SDK Reference](../js-sdk/nextjs.md) -- full middleware, server, and client API docs
- [React Integration](../js-sdk/react.md) -- hooks and components reference
- [Auth Client](../js-sdk/auth-client.md) -- `SentinelAuthz` class reference
