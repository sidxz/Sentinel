import {
  createContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import {
  SentinelAuth,
  type SentinelConfig,
  type SentinelUser,
  type WorkspaceOption,
} from '@sentinel-auth/js'

export interface SentinelAuthContextValue {
  client: SentinelAuth
  user: SentinelUser | null
  isLoading: boolean
  isAuthenticated: boolean
  login(provider: string): Promise<void>
  logout(): void
  getProviders(): Promise<string[]>
  getWorkspaces(code: string): Promise<WorkspaceOption[]>
  selectWorkspace(code: string, workspaceId: string): Promise<void>
  fetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response>
}

const SentinelAuthContext = createContext<SentinelAuthContextValue | null>(null)

export interface SentinelAuthProviderProps {
  /** Provide config to let the provider create a SentinelAuth instance, or provide a pre-created client. */
  config?: SentinelConfig
  /** Pre-created SentinelAuth client. Takes precedence over config. */
  client?: SentinelAuth
  children: ReactNode
}

export function SentinelAuthProvider({
  config,
  client: externalClient,
  children,
}: SentinelAuthProviderProps) {
  const clientRef = useRef<SentinelAuth | null>(externalClient ?? null)
  if (!clientRef.current) {
    if (!config) throw new Error('SentinelAuthProvider requires either config or client prop')
    clientRef.current = new SentinelAuth(config)
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

  const value: SentinelAuthContextValue = {
    client,
    user,
    isLoading,
    isAuthenticated: user !== null,
    login: (provider) => client.login(provider),
    logout: () => client.logout(),
    getProviders: () => client.getProviders(),
    getWorkspaces: (code) => client.getWorkspaces(code),
    selectWorkspace: async (code, workspaceId) => {
      await client.selectWorkspace(code, workspaceId)
    },
    fetch: (input, init) => client.fetch(input, init),
  }

  return (
    <SentinelAuthContext.Provider value={value}>
      {children}
    </SentinelAuthContext.Provider>
  )
}

export { SentinelAuthContext }
