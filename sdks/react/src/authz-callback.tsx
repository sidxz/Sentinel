import { useEffect, useRef, useState, type ReactNode } from 'react'
import type { AuthzWorkspaceOption, SentinelUser } from '@sentinel-auth/js'
import { useAuthz } from './authz-hooks'

export interface AuthzWorkspaceSelectorProps {
  workspaces: AuthzWorkspaceOption[]
  onSelect: (workspaceId: string) => void
  isLoading: boolean
}

export interface AuthzCallbackProps {
  /** Called after successful authentication. */
  onSuccess: (user: SentinelUser) => void
  /** Called on error. */
  onError?: (error: Error) => void
  /** Shown while loading. */
  loadingComponent?: ReactNode
  /** Shown on error. */
  errorComponent?: (error: Error) => ReactNode
  /** Custom workspace selector UI. */
  workspaceSelector?: (props: AuthzWorkspaceSelectorProps) => ReactNode
}

// Capture hash at module load — must survive React StrictMode double-mount.
// The hash contains the IdP token and is only present once (on redirect back).
const capturedCallback =
  typeof window !== 'undefined'
    ? (() => {
        const hash = window.location.hash.substring(1)
        if (hash) window.history.replaceState({}, '', window.location.pathname)
        return hash
      })()
    : ''

/**
 * AuthZ mode OAuth callback component. Reads `id_token` from URL hash,
 * resolves workspaces, auto-selects if one, shows picker if multiple.
 *
 * Drop-in equivalent of proxy mode's `AuthCallback`.
 */
export function AuthzCallback({
  onSuccess,
  onError,
  loadingComponent,
  errorComponent,
  workspaceSelector,
}: AuthzCallbackProps) {
  const { resolve, selectWorkspace, client } = useAuthz()
  const [workspaces, setWorkspaces] = useState<AuthzWorkspaceOption[]>([])
  const [idpToken, setIdpToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [selecting, setSelecting] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const resolvedRef = useRef(false)

  // Determine provider from sessionStorage (set by login()) or default to google
  const provider = sessionStorage.getItem('sentinel_authz_provider') || 'google'

  useEffect(() => {
    if (resolvedRef.current) return
    resolvedRef.current = true

    if (!capturedCallback) {
      const err = new Error('No IdP response in callback URL')
      setError(err)
      setLoading(false)
      onError?.(err)
      return
    }

    const params = new URLSearchParams(capturedCallback)
    const idToken = params.get('id_token')
    const oauthError = params.get('error')

    if (oauthError) {
      const err = new Error(params.get('error_description') || oauthError)
      setError(err)
      setLoading(false)
      onError?.(err)
      return
    }

    if (!idToken) {
      const err = new Error('No ID token in IdP response')
      setError(err)
      setLoading(false)
      onError?.(err)
      return
    }

    // Clean up session storage
    sessionStorage.removeItem('sentinel_authz_nonce')
    sessionStorage.removeItem('sentinel_authz_provider')

    setIdpToken(idToken)

    resolve(idToken, provider)
      .then(async (result) => {
        if (!result.workspaces || result.workspaces.length === 0) {
          throw new Error('No workspaces available. Ask an admin to add you to a workspace.')
        }
        if (result.workspaces.length === 1) {
          await selectWorkspace(idToken, provider, result.workspaces[0].id)
          onSuccess(client.getUser()!)
          return
        }
        setWorkspaces(result.workspaces)
        setLoading(false)
      })
      .catch((e: unknown) => {
        const err = e instanceof Error ? e : new Error('Authentication failed')
        setError(err)
        setLoading(false)
        onError?.(err)
      })
  }, [])

  async function handleSelectWorkspace(workspaceId: string) {
    if (!idpToken) return
    setSelecting(true)
    try {
      await selectWorkspace(idpToken, provider, workspaceId)
      onSuccess(client.getUser()!)
    } catch (e: unknown) {
      const err = e instanceof Error ? e : new Error('Workspace selection failed')
      setError(err)
      setSelecting(false)
      onError?.(err)
    }
  }

  if (error) {
    if (errorComponent) return <>{errorComponent(error)}</>
    return <div>{error.message}</div>
  }

  if (loading) {
    if (loadingComponent) return <>{loadingComponent}</>
    return <div>Signing you in...</div>
  }

  if (workspaces.length > 0) {
    if (workspaceSelector) {
      return (
        <>
          {workspaceSelector({
            workspaces,
            onSelect: handleSelectWorkspace,
            isLoading: selecting,
          })}
        </>
      )
    }

    // Default workspace picker
    return (
      <div>
        <h2>Select Workspace</h2>
        {workspaces.map((ws) => (
          <button
            key={ws.id}
            onClick={() => handleSelectWorkspace(ws.id)}
            disabled={selecting}
          >
            {ws.name} ({ws.slug}) — {ws.role}
          </button>
        ))}
      </div>
    )
  }

  return null
}
