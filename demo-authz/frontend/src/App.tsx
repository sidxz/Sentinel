import { useState } from 'react'
import { useAuthz } from '@sentinel-auth/react'
import type { AuthzWorkspaceOption } from '@sentinel-auth/js'
import { Login } from './components/Login'
import { WorkspacePicker } from './components/WorkspacePicker'
import { Notes } from './components/Notes'

export function App() {
  const { isAuthenticated, user, logout } = useAuthz()
  const [workspaces, setWorkspaces] = useState<AuthzWorkspaceOption[] | null>(null)
  const [idpToken, setIdpToken] = useState<string | null>(null)

  if (isAuthenticated && user) {
    return (
      <div style={{ maxWidth: 600, margin: '2rem auto', fontFamily: 'system-ui' }}>
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <div>
            <strong>{user.name}</strong> — {user.workspaceSlug} ({user.workspaceRole})
          </div>
          <button onClick={logout}>Logout</button>
        </header>
        <Notes />
      </div>
    )
  }

  if (workspaces && idpToken) {
    return (
      <WorkspacePicker
        workspaces={workspaces}
        idpToken={idpToken}
        onBack={() => { setWorkspaces(null); setIdpToken(null) }}
      />
    )
  }

  return (
    <Login
      onResolved={(token, ws) => {
        setIdpToken(token)
        setWorkspaces(ws)
      }}
    />
  )
}
