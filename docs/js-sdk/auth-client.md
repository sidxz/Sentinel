# Auth Client

The `SentinelAuth` class is the core browser auth client. It handles the full OAuth2 + PKCE + workspace-selection flow, token storage, automatic refresh, and provides an auth-aware `fetch` wrapper.

## Setup

```typescript
import { SentinelAuth } from '@sentinel-auth/js'

const auth = new SentinelAuth({
  sentinelUrl: 'http://localhost:9003',
})
```

### Configuration Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sentinelUrl` | `string` | *required* | Base URL of the Sentinel Auth service |
| `redirectUri` | `string` | `${window.location.origin}/auth/callback` | OAuth redirect URI |
| `storage` | `TokenStore` | `LocalStorageStore` | Token storage backend |
| `autoRefresh` | `boolean` | `true` | Automatically refresh tokens before expiry |
| `refreshBuffer` | `number` | `60` | Seconds before expiry to trigger refresh |

## Auth Flow

The Sentinel auth flow is a non-standard OAuth2 + PKCE flow with an extra workspace-selection step:

```
1. login('google')        →  Generate PKCE, redirect to /auth/login/google
2. [User signs in]        →  OAuth provider redirects to /auth/callback/google
3. [Sentinel generates code] → Redirects to your app's /auth/callback?code=...
4. getWorkspaces(code)    →  GET /auth/workspaces?code=...
5. selectWorkspace(code, workspaceId) → POST /auth/token (with PKCE verifier)
6. [Tokens stored]        →  Access + refresh tokens in localStorage
```

### Login

Initiates OAuth login with PKCE. Redirects the browser to the identity provider.

```typescript
await auth.login('google')
// Browser redirects to Google → Sentinel → your /auth/callback
```

### Get Workspaces

After the OAuth callback, fetch the user's available workspaces using the auth code.

```typescript
const workspaces = await auth.getWorkspaces(code)
// [{ id: '...', name: 'My Workspace', slug: 'my-ws', role: 'admin' }]
```

### Select Workspace

Complete the token exchange by selecting a workspace. This validates the PKCE verifier and stores the tokens.

```typescript
await auth.selectWorkspace(code, workspaceId)
// Tokens are now stored, user is authenticated
```

### Refresh

Manually refresh the access token. Called automatically when `autoRefresh` is enabled.

```typescript
const success = await auth.refresh()
```

### Logout

Clear stored tokens and notify listeners.

```typescript
auth.logout()
```

## Token Access

```typescript
// Get the raw access token (may be expired)
const token = auth.getToken()

// Get the current user (parsed from JWT, null if expired or missing)
const user = auth.getUser()
// { userId, email, name, workspaceId, workspaceSlug, workspaceRole, groups }

// Check if authenticated (has non-expired token)
if (auth.isAuthenticated) {
  // ...
}
```

## Auth-Aware Fetch

The `fetch` method wraps the native `fetch` API with automatic Bearer token injection and 401 retry:

```typescript
const res = await auth.fetch('/api/notes')
const notes = await res.json()
```

Behavior:

1. Injects `Authorization: Bearer <token>` header
2. If the response is 401, attempts a token refresh
3. If refresh succeeds, retries the original request with the new token

## Events

Subscribe to auth state changes:

```typescript
const unsubscribe = auth.onAuthStateChange((user) => {
  if (user) {
    console.log('Logged in:', user.email)
  } else {
    console.log('Logged out')
  }
})

// Later: unsubscribe()
```

## Token Storage

The SDK provides three storage backends:

| Backend | Use Case | XSS Exposure |
|---------|----------|--------------|
| `LocalStorageStore` (default) | Browser apps -- persists across tabs and sessions | Tokens accessible until explicitly cleared |
| `SessionStorageStore` | Browser apps -- cleared when the tab closes | Limited to current tab lifetime |
| `MemoryStore` | SSR, testing, or when localStorage is unavailable | Tokens lost on page refresh |

!!! warning "XSS and token storage"
    All browser-side storage is accessible to JavaScript. If your app is vulnerable to XSS, an attacker can steal tokens regardless of which store you use. `SessionStorageStore` limits the blast radius (tokens are cleared when the tab closes), while `LocalStorageStore` persists tokens across sessions. Choose based on your security posture vs. user experience needs.

```typescript
import { SentinelAuth, SessionStorageStore } from '@sentinel-auth/js'

// Use sessionStorage for reduced XSS exposure
const auth = new SentinelAuth({
  sentinelUrl: 'http://localhost:9003',
  storage: new SessionStorageStore(),
})
```

Tokens are stored with the `sentinel_` prefix (`sentinel_access_token`, `sentinel_refresh_token`). The PKCE verifier is always stored in `sessionStorage` (must survive the OAuth redirect but not persist).

## Cleanup

Call `destroy()` when the client is no longer needed (e.g., on component unmount):

```typescript
auth.destroy() // Clears refresh timer, removes listeners
```

## Next Steps

- [React Integration](react.md) -- use the auth client with React
- [Server Utilities](server.md) -- verify JWTs and check permissions on the server
