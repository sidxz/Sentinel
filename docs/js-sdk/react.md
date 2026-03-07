# React Integration

The `@sentinel-auth/react` package provides React context providers, hooks, and components for integrating Sentinel Auth into React applications. It supports both **authz mode** (recommended) and **proxy mode**.

## AuthZ Mode (Recommended)

For apps that use direct IdP sign-in (Google Sign-In, MSAL, etc.) with Sentinel authorization tokens.

### AuthzProvider

Wrap your app with `AuthzProvider` for authz mode:

```tsx
import { AuthzProvider } from '@sentinel-auth/react'

function App() {
  return (
    <AuthzProvider config={{ sentinelUrl: 'http://localhost:9003' }}>
      <YourApp />
    </AuthzProvider>
  )
}
```

| Prop | Type | Description |
|------|------|-------------|
| `config` | `SentinelAuthzConfig` | Config (sentinelUrl, storage, etc.) |
| `client` | `SentinelAuthz` | Pre-created client (takes precedence) |
| `children` | `ReactNode` | Child components |

!!! tip "Shared client"
    If you need access to the `SentinelAuthz` instance outside of React (e.g., for API modules), create it yourself and pass it via the `client` prop:

    ```tsx
    import { SentinelAuthz } from '@sentinel-auth/js'
    import { AuthzProvider } from '@sentinel-auth/react'

    const authzClient = new SentinelAuthz({
      sentinelUrl: 'http://localhost:9003',
    })

    function App() {
      return (
        <AuthzProvider client={authzClient}>
          <YourApp />
        </AuthzProvider>
      )
    }
    ```

### useAuthz

Access the full authz context. Throws if used outside `AuthzProvider`.

```tsx
import { useAuthz } from '@sentinel-auth/react'

function MyComponent() {
  const {
    resolve,          // (idpToken, provider) => Promise<AuthzResolveResponse>
    selectWorkspace,  // (idpToken, provider, wsId) => Promise<void>
    user,             // SentinelUser | null
    isAuthenticated,  // boolean
    isLoading,        // boolean
    fetch,            // dual-header fetch
    fetchJson,        // <T>(input, init?) => Promise<T>
    logout,           // () => void
  } = useAuthz()
}
```

### useAuthzUser

Get the current user from the authz token. Throws if not authenticated -- use inside `AuthzGuard` or after checking `isAuthenticated`.

```tsx
import { useAuthzUser } from '@sentinel-auth/react'

function Profile() {
  const user = useAuthzUser()
  return <p>{user.email} -- {user.workspaceRole}</p>
}
```

The returned `SentinelUser` has these fields:

| Field | Type | Description |
|-------|------|-------------|
| `userId` | `string` | User ID |
| `email` | `string` | User email |
| `name` | `string` | Display name |
| `workspaceId` | `string` | Current workspace ID |
| `workspaceSlug` | `string` | Current workspace slug |
| `workspaceRole` | `WorkspaceRole` | Role in workspace (`owner`, `admin`, `editor`, `viewer`) |
| `groups` | `string[]` | Group memberships |

### useAuthzHasRole

Check if the current user has at least the given workspace role. Uses hierarchy: `viewer` < `editor` < `admin` < `owner`.

```tsx
import { useAuthzHasRole } from '@sentinel-auth/react'

function AdminPanel() {
  const isAdmin = useAuthzHasRole('admin')
  if (!isAdmin) return <p>Access denied</p>
  return <AdminDashboard />
}
```

### useAuthzFetch

Shortcut to the dual-header fetch wrapper.

```tsx
import { useAuthzFetch } from '@sentinel-auth/react'

function DataLoader() {
  const authzFetch = useAuthzFetch()

  async function loadData() {
    const res = await authzFetch('/api/data')
    return res.json()
  }
}
```

### AuthzGuard

Conditionally renders children based on authz authentication state.

```tsx
import { AuthzGuard } from '@sentinel-auth/react'

function App() {
  return (
    <AuthzGuard fallback={<LoginPage />} loading={<Spinner />}>
      <Dashboard />
    </AuthzGuard>
  )
}
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `children` | `ReactNode` | *required* | Rendered when authenticated |
| `fallback` | `ReactNode` | *required* | Rendered when not authenticated (e.g., login page) |
| `loading` | `ReactNode` | `null` | Rendered while checking auth state |

### Full AuthZ Mode Example

```tsx
import { GoogleOAuthProvider, GoogleLogin } from '@react-oauth/google'
import { AuthzProvider, AuthzGuard, useAuthz, useAuthzUser } from '@sentinel-auth/react'

function App() {
  return (
    <GoogleOAuthProvider clientId="your-google-client-id">
      <AuthzProvider config={{ sentinelUrl: 'http://localhost:9003' }}>
        <AuthzGuard fallback={<Login />} loading={<p>Loading...</p>}>
          <Dashboard />
        </AuthzGuard>
      </AuthzProvider>
    </GoogleOAuthProvider>
  )
}

function Login() {
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

function Dashboard() {
  const user = useAuthzUser()
  const { logout } = useAuthz()
  return (
    <div>
      <p>Welcome, {user.name}!</p>
      <button onClick={logout}>Logout</button>
    </div>
  )
}
```

---

## Full Proxy Mode

For apps that use Sentinel's OAuth redirect flow instead of direct IdP sign-in.

### SentinelAuthProvider

Wrap your app with `SentinelAuthProvider`:

```tsx
import { SentinelAuthProvider } from '@sentinel-auth/react'

function App() {
  return (
    <SentinelAuthProvider config={{ sentinelUrl: 'http://localhost:9003' }}>
      <YourApp />
    </SentinelAuthProvider>
  )
}
```

#### Provider Props

| Prop | Type | Description |
|------|------|-------------|
| `config` | `SentinelConfig` | Config to create a new `SentinelAuth` instance |
| `client` | `SentinelAuth` | Pre-created client (takes precedence over `config`) |
| `children` | `ReactNode` | Child components |

!!! tip "Shared client"
    If you need access to the `SentinelAuth` instance outside of React (e.g., for API modules), create it yourself and pass it via the `client` prop:

    ```tsx
    import { SentinelAuth } from '@sentinel-auth/js'
    import { SentinelAuthProvider } from '@sentinel-auth/react'

    const sentinelClient = new SentinelAuth({
      sentinelUrl: 'http://localhost:9003',
    })

    function App() {
      return (
        <SentinelAuthProvider client={sentinelClient}>
          <YourApp />
        </SentinelAuthProvider>
      )
    }
    ```

### Hooks

#### `useAuth`

Access the full auth context. Throws if used outside `SentinelAuthProvider`.

```tsx
import { useAuth } from '@sentinel-auth/react'

function MyComponent() {
  const {
    client,         // SentinelAuth -- the underlying client instance
    user,           // SentinelUser | null
    isAuthenticated,// boolean
    isLoading,      // boolean
    login,          // (provider: string) => Promise<void>
    logout,         // () => void
    getProviders,   // () => Promise<string[]> -- fetch available OAuth providers
    getWorkspaces,  // (code: string) => Promise<WorkspaceOption[]> -- get workspace options after OAuth callback
    selectWorkspace,// (code: string, workspaceId: string) => Promise<void> -- complete auth by selecting a workspace
    fetch,          // auth-aware fetch wrapper
    fetchJson,      // <T>(input, init?) => Promise<T> -- auth-aware fetch that returns parsed JSON
  } = useAuth()
}
```

#### `useUser`

Get the current authenticated user. Throws if not authenticated -- use inside `AuthGuard` or after checking `isAuthenticated`.

```tsx
import { useUser } from '@sentinel-auth/react'

function Profile() {
  const user = useUser()
  return <p>{user.email} -- {user.workspaceRole}</p>
}
```

The returned `SentinelUser` has these fields:

| Field | Type | Description |
|-------|------|-------------|
| `userId` | `string` | User ID (JWT `sub` claim) |
| `email` | `string` | User email |
| `name` | `string` | Display name |
| `workspaceId` | `string` | Current workspace ID |
| `workspaceSlug` | `string` | Current workspace slug |
| `workspaceRole` | `WorkspaceRole` | Role in workspace (`owner`, `admin`, `editor`, `viewer`) |
| `groups` | `string[]` | Group memberships |

#### `useHasRole`

Check if the current user has at least the given workspace role. Uses hierarchy: `viewer` < `editor` < `admin` < `owner`.

```tsx
import { useHasRole } from '@sentinel-auth/react'

function AdminPanel() {
  const isAdmin = useHasRole('admin')
  if (!isAdmin) return <p>Access denied</p>
  return <AdminDashboard />
}
```

#### `useAuthFetch`

Shortcut to the auth-aware `fetch` wrapper.

```tsx
import { useAuthFetch } from '@sentinel-auth/react'

function DataLoader() {
  const authFetch = useAuthFetch()

  async function loadData() {
    const res = await authFetch('/api/data')
    return res.json()
  }
}
```

### Components

#### `AuthGuard`

Conditionally renders children based on authentication state.

```tsx
import { AuthGuard } from '@sentinel-auth/react'

function App() {
  return (
    <AuthGuard
      fallback={<LoginPage />}
      loading={<div>Loading...</div>}
    >
      <Dashboard />
    </AuthGuard>
  )
}
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `children` | `ReactNode` | *required* | Rendered when authenticated |
| `fallback` | `ReactNode` | *required* | Rendered when not authenticated (e.g., login page) |
| `loading` | `ReactNode` | `null` | Rendered while checking auth state |

#### `AuthCallback`

OAuth callback route component. Reads `?code=` from the URL, fetches available workspaces, auto-selects if there's only one, and shows a picker if multiple. Router-agnostic.

```tsx
import { AuthCallback } from '@sentinel-auth/react'
import { useNavigate } from 'react-router-dom'

function CallbackPage() {
  const navigate = useNavigate()

  return (
    <AuthCallback
      onSuccess={() => navigate('/dashboard', { replace: true })}
      onError={(err) => console.error(err)}
    />
  )
}
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `onSuccess` | `(user: SentinelUser) => void` | *required* | Called after successful authentication |
| `onError` | `(error: Error) => void` | -- | Called on error |
| `loadingComponent` | `ReactNode` | `"Signing you in..."` | Loading UI |
| `errorComponent` | `(error: Error) => ReactNode` | Error message `<div>` | Error UI |
| `workspaceSelector` | `(props) => ReactNode` | Built-in button list | Custom workspace picker |

##### Custom Workspace Selector

Override the default workspace picker with your own UI:

```tsx
<AuthCallback
  onSuccess={(user) => navigate('/dashboard')}
  workspaceSelector={({ workspaces, onSelect, isLoading }) => (
    <div className="workspace-picker">
      <h2>Choose a workspace</h2>
      {workspaces.map((ws) => (
        <button
          key={ws.id}
          onClick={() => onSelect(ws.id)}
          disabled={isLoading}
        >
          {ws.name} ({ws.role})
        </button>
      ))}
    </div>
  )}
/>
```

### Full Proxy Mode Example

```tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { SentinelAuthProvider, AuthGuard, AuthCallback, useAuth, useUser } from '@sentinel-auth/react'

function App() {
  return (
    <SentinelAuthProvider config={{ sentinelUrl: 'http://localhost:9003' }}>
      <BrowserRouter>
        <Routes>
          <Route path="/auth/callback" element={<Callback />} />
          <Route path="/*" element={
            <AuthGuard fallback={<Login />}>
              <Dashboard />
            </AuthGuard>
          } />
        </Routes>
      </BrowserRouter>
    </SentinelAuthProvider>
  )
}

function Login() {
  const { login } = useAuth()
  return <button onClick={() => login('google')}>Sign in with Google</button>
}

function Callback() {
  const navigate = useNavigate()
  return <AuthCallback onSuccess={() => navigate('/', { replace: true })} />
}

function Dashboard() {
  const user = useUser()
  const { logout } = useAuth()
  return (
    <div>
      <p>Welcome, {user.name}!</p>
      <button onClick={logout}>Logout</button>
    </div>
  )
}
```

## Next Steps

- [AuthZ Client](authz-client.md) -- configure the authz-mode browser client
- [Auth Client](auth-client.md) -- configure the proxy-mode browser client
- [Next.js Integration](nextjs.md) -- Edge Middleware and server helpers
- [Server Utilities](server.md) -- JWT verification and permission checks
