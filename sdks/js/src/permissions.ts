import type {
  AccessibleResult,
  PermissionCheck,
  PermissionResult,
  RegisterResourceRequest,
  ShareRequest,
} from './types'
import { warnIfInsecure } from './warn-insecure'

/**
 * Server-side client for the Sentinel permission API.
 * Mirrors the Python SDK's `PermissionClient`.
 */
export class PermissionClient {
  private readonly baseUrl: string
  private readonly serviceName: string
  private readonly serviceKey: string | undefined

  constructor(baseUrl: string, serviceName: string, serviceKey?: string) {
    this.baseUrl = baseUrl.replace(/\/+$/, '')
    this.serviceName = serviceName
    this.serviceKey = serviceKey
    warnIfInsecure(this.baseUrl, 'PermissionClient')
  }

  /** Batch check permissions. */
  async check(
    token: string,
    checks: PermissionCheck[],
  ): Promise<PermissionResult[]> {
    const res = await fetch(`${this.baseUrl}/permissions/check`, {
      method: 'POST',
      headers: this.headers(token),
      body: JSON.stringify({ checks }),
    })
    if (!res.ok) throw new Error(`Permission check failed: ${res.status}`)
    const data = await res.json()
    return data.results as PermissionResult[]
  }

  /** Convenience: check a single permission. */
  async can(
    token: string,
    resourceType: string,
    resourceId: string,
    action: string,
  ): Promise<boolean> {
    const results = await this.check(token, [
      {
        service_name: this.serviceName,
        resource_type: resourceType,
        resource_id: resourceId,
        action,
      },
    ])
    return results.length > 0 && results[0].allowed
  }

  /** Register a new resource (service-key only, no user JWT needed). */
  async registerResource(
    request: RegisterResourceRequest,
  ): Promise<Record<string, unknown>> {
    const res = await fetch(`${this.baseUrl}/permissions/register`, {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify(request),
    })
    if (!res.ok) throw new Error(`Register resource failed: ${res.status}`)
    return res.json()
  }

  /** Share a resource with a user or group. */
  async share(
    token: string,
    resourceType: string,
    resourceId: string,
    share: ShareRequest,
  ): Promise<void> {
    // Resolve resource coordinates to permission ID
    const lookup = await fetch(
      `${this.baseUrl}/permissions/resource/${this.serviceName}/${resourceType}/${resourceId}`,
      { headers: this.headers() },
    )
    if (!lookup.ok) throw new Error(`Resource lookup failed: ${lookup.status}`)
    const { id: permissionId } = await lookup.json()

    const res = await fetch(
      `${this.baseUrl}/permissions/${permissionId}/share`,
      {
        method: 'POST',
        headers: this.headers(token),
        body: JSON.stringify(share),
      },
    )
    if (!res.ok) throw new Error(`Share failed: ${res.status}`)
  }

  /** List accessible resource IDs for the current user. */
  async accessible(
    token: string,
    resourceType: string,
    action: string,
    workspaceId: string,
    limit?: number,
  ): Promise<AccessibleResult> {
    const payload: Record<string, unknown> = {
      service_name: this.serviceName,
      resource_type: resourceType,
      action,
      workspace_id: workspaceId,
    }
    if (limit !== undefined) payload.limit = limit

    const res = await fetch(`${this.baseUrl}/permissions/accessible`, {
      method: 'POST',
      headers: this.headers(token),
      body: JSON.stringify(payload),
    })
    if (!res.ok) throw new Error(`Accessible query failed: ${res.status}`)
    return res.json() as Promise<AccessibleResult>
  }

  private headers(token?: string): Record<string, string> {
    const h: Record<string, string> = { 'Content-Type': 'application/json' }
    if (this.serviceKey) h['X-Service-Key'] = this.serviceKey
    if (token) h['Authorization'] = `Bearer ${token}`
    return h
  }
}
