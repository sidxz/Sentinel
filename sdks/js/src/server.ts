// Server (Node.js / Edge) entry point
export { verifyToken, payloadToUser } from './jwt-verifier'
export { PermissionClient } from './permissions'
export { RoleClient } from './roles'

export type {
  SentinelUser,
  WorkspaceRole,
  JWTPayload,
  VerifyOptions,
  PermissionCheck,
  PermissionResult,
  RegisterResourceRequest,
  ShareRequest,
  AccessibleResult,
  ActionDefinition,
} from './types'
