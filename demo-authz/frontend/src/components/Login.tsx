import { GoogleLogin } from '@react-oauth/google'
import { useAuthz } from '@sentinel-auth/react'
import type { AuthzWorkspaceOption } from '@sentinel-auth/js'

interface LoginProps {
  onResolved: (idpToken: string, workspaces: AuthzWorkspaceOption[]) => void
}

export function Login({ onResolved }: LoginProps) {
  const { resolve, selectWorkspace } = useAuthz()

  const handleGoogleSignIn = async (credential: string) => {
    try {
      const result = await resolve(credential, 'google')

      if (result.workspaces && result.workspaces.length > 0) {
        if (result.workspaces.length === 1) {
          await selectWorkspace(credential, 'google', result.workspaces[0].id)
        } else {
          onResolved(credential, result.workspaces)
        }
      }
    } catch (err) {
      console.error('Auth resolve failed:', err)
    }
  }

  return (
    <div style={{ maxWidth: 400, margin: '4rem auto', textAlign: 'center', fontFamily: 'system-ui' }}>
      <h1>Team Notes</h1>
      <p style={{ color: '#666' }}>AuthZ Mode Demo — Sign in with Google</p>
      <div style={{ display: 'inline-block', marginTop: '1rem' }}>
        <GoogleLogin
          onSuccess={(response) => {
            if (response.credential) {
              handleGoogleSignIn(response.credential)
            }
          }}
          onError={() => console.error('Google Sign-In failed')}
        />
      </div>
    </div>
  )
}
