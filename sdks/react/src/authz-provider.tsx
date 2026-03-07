import {
  createContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import {
  SentinelAuthz,
  type SentinelAuthzConfig,
  type SentinelUser,
  type AuthzResolveResponse,
} from '@sentinel-auth/js'

export interface AuthzContextValue {
  client: SentinelAuthz
  user: SentinelUser | null
  isLoading: boolean
  isAuthenticated: boolean
  login(provider: string): void
  resolve(idpToken: string, provider: string): Promise<AuthzResolveResponse>
  selectWorkspace(idpToken: string, provider: string, workspaceId: string): Promise<void>
  logout(): void
  fetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response>
  fetchJson: <T>(input: RequestInfo | URL, init?: RequestInit) => Promise<T>
}

const AuthzContext = createContext<AuthzContextValue | null>(null)

export interface AuthzProviderProps {
  config?: SentinelAuthzConfig
  client?: SentinelAuthz
  children: ReactNode
}

export function AuthzProvider({
  config,
  client: externalClient,
  children,
}: AuthzProviderProps) {
  const clientRef = useRef<SentinelAuthz | null>(externalClient ?? null)
  if (!clientRef.current) {
    if (!config) throw new Error('AuthzProvider requires either config or client prop')
    clientRef.current = new SentinelAuthz(config)
  }
  const client = clientRef.current
  const ownsClient = !externalClient

  const [user, setUser] = useState<SentinelUser | null>(() => client.getUser())
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    setUser(client.getUser())
    setIsLoading(false)

    const unsub = client.onAuthStateChange((u) => {
      setUser(u)
    })

    return () => {
      unsub()
      if (ownsClient) client.destroy()
    }
  }, [client, ownsClient])

  const value: AuthzContextValue = {
    client,
    user,
    isLoading,
    isAuthenticated: user !== null,
    login: (provider) => client.login(provider),
    resolve: (idpToken, provider) => client.resolve(idpToken, provider),
    selectWorkspace: (idpToken, provider, workspaceId) =>
      client.selectWorkspace(idpToken, provider, workspaceId),
    logout: () => client.logout(),
    fetch: (input, init) => client.fetch(input, init),
    fetchJson: <T,>(input: RequestInfo | URL, init?: RequestInit) =>
      client.fetchJson<T>(input, init),
  }

  return (
    <AuthzContext.Provider value={value}>
      {children}
    </AuthzContext.Provider>
  )
}

export { AuthzContext }
