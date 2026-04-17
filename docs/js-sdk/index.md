# JavaScript / TypeScript SDK

Three npm packages for browser auth, React bindings, and Next.js integration.

## Packages

```bash
# Core — browser client + server utilities
npm install @sentinel-auth/js

# React — provider, hooks, components
npm install @sentinel-auth/react

# Next.js — Edge Middleware, server helpers, client re-exports
npm install @sentinel-auth/nextjs
```

## Which package do I need?

| I'm building...                    | Install                                      |
|------------------------------------|----------------------------------------------|
| React SPA (Vite, CRA)             | `@sentinel-auth/js` + `@sentinel-auth/react` |
| Next.js app                        | `@sentinel-auth/js` + `@sentinel-auth/nextjs` |
| Node.js / Express API              | `@sentinel-auth/js` (server entry point)     |
| Vanilla JS / any framework         | `@sentinel-auth/js`                          |

## Two modes

**AuthZ mode** (recommended) -- your app handles IdP sign-in directly (Google, EntraID). Sentinel issues short-lived authorization tokens. Uses `SentinelAuthz`, `AuthzProvider`.

**Proxy mode** -- Sentinel manages the full OAuth2 + PKCE redirect flow. Uses `SentinelAuth`, `SentinelAuthProvider`.

## Quick start (AuthZ mode)

```tsx
import { SentinelAuthz, IdpConfigs } from '@sentinel-auth/js'

const authz = new SentinelAuthz({
  sentinelUrl: 'http://localhost:9003',
  mintEndpoint: '/api/auth/mint', // YOUR backend route — holds the service key
  idps: { google: IdpConfigs.google('your-google-client-id') },
})

// Login redirects to Google
authz.login('google')

// After callback, resolve + select workspace
const result = await authz.resolve(idpToken, 'google')
await authz.selectWorkspace(idpToken, 'google', result.workspaces![0].id)

// Authenticated fetch with dual-token headers
const notes = await authz.fetchJson<Note[]>('/api/notes')
```

## Sections

- [AuthZ Client](authz-client.md) -- browser auth for authz mode (recommended)
- [Proxy Client](proxy-client.md) -- browser auth for proxy mode
- [React Integration](react.md) -- provider, hooks, guard, callback
- [Next.js Integration](nextjs.md) -- Edge Middleware + server helpers
- [Server Utilities](server.md) -- JWT verification, permissions, RBAC
