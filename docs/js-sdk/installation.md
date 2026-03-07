# Installation

## Install from npm

=== "React App"

    ```bash
    npm install @sentinel-auth/js @sentinel-auth/react
    ```

=== "Next.js App"

    ```bash
    npm install @sentinel-auth/js @sentinel-auth/react @sentinel-auth/nextjs
    ```

=== "Node.js Server Only"

    ```bash
    npm install @sentinel-auth/js
    ```

`@sentinel-auth/js` is the core package. The `react` and `nextjs` packages are thin wrappers that depend on it.

## Peer Dependencies

| Package | Peer Dependencies |
|---------|-------------------|
| `@sentinel-auth/js` | None |
| `@sentinel-auth/react` | `react` ^18 or ^19, `@sentinel-auth/js` ^0.7.1 |
| `@sentinel-auth/nextjs` | `next` ^14 or ^15, `react` ^18 or ^19, `@sentinel-auth/js` ^0.7.1, `@sentinel-auth/react` ^0.7.1 |

## Local Development

If you are developing against a local checkout of the Sentinel monorepo, reference the packages via `file:` paths in your `package.json`:

```json
{
  "dependencies": {
    "@sentinel-auth/js": "file:../../sdks/js",
    "@sentinel-auth/react": "file:../../sdks/react"
  }
}
```

Build the SDK packages first:

```bash
cd sdks && npm install && npm run build
```

Then install in your app:

```bash
cd your-app && npm install
```

## Package Exports

### `@sentinel-auth/js`

| Entry Point | Import | Contents |
|-------------|--------|----------|
| `.` (default) | `import { SentinelAuth } from '@sentinel-auth/js'` | Browser auth client, PKCE, storage, JWT utils, types |
| `./server` | `import { verifyToken } from '@sentinel-auth/js/server'` | JWT verifier, PermissionClient, RoleClient |

### `@sentinel-auth/react`

| Entry Point | Import | Contents |
|-------------|--------|----------|
| `.` (default) | `import { useAuth } from '@sentinel-auth/react'` | Provider, hooks, AuthGuard, AuthCallback |

### `@sentinel-auth/nextjs`

| Entry Point | Import | Contents |
|-------------|--------|----------|
| `.` (default) | `import { useAuth } from '@sentinel-auth/nextjs'` | Client-side re-exports from `@sentinel-auth/react` |
| `./middleware` | `import { createSentinelMiddleware } from '@sentinel-auth/nextjs/middleware'` | Edge Middleware factory |
| `./server` | `import { getUser } from '@sentinel-auth/nextjs/server'` | Server Component / Route Handler helpers |

## Requirements

- **Node.js** >= 18 (for `fetch` and Web Crypto API)
- **TypeScript** >= 5.0 (optional but recommended)
- **Sentinel Auth service** running and accessible

## Next Steps

- [Auth Client](auth-client.md) -- configure the browser auth client
- [React Integration](react.md) -- set up the React provider
