import { useAuthz } from '@sentinel-auth/react'
import type { AuthzWorkspaceOption } from '@sentinel-auth/js'

interface WorkspacePickerProps {
  workspaces: AuthzWorkspaceOption[]
  idpToken: string
  onBack: () => void
}

export function WorkspacePicker({ workspaces, idpToken, onBack }: WorkspacePickerProps) {
  const { selectWorkspace } = useAuthz()

  const handleSelect = async (ws: AuthzWorkspaceOption) => {
    await selectWorkspace(idpToken, 'google', ws.id)
  }

  return (
    <div style={{ maxWidth: 400, margin: '4rem auto', fontFamily: 'system-ui' }}>
      <h2>Select Workspace</h2>
      <ul style={{ listStyle: 'none', padding: 0 }}>
        {workspaces.map((ws) => (
          <li key={ws.id} style={{ marginBottom: '0.5rem' }}>
            <button
              onClick={() => handleSelect(ws)}
              style={{ width: '100%', padding: '0.75rem', textAlign: 'left', cursor: 'pointer' }}
            >
              <strong>{ws.name}</strong> <span style={{ color: '#666' }}>({ws.role})</span>
            </button>
          </li>
        ))}
      </ul>
      <button onClick={onBack} style={{ marginTop: '1rem' }}>Back</button>
    </div>
  )
}
