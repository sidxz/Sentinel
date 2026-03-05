# Concepts

This section covers the core concepts and design decisions behind the Daikon Identity Service. Each page dives deep into a specific area of the system.

## Tutorial

A step-by-step guide to building a "Team Notes" app that demonstrates authentication, workspace isolation, role enforcement, custom RBAC, and entity-level permissions. Start here if you want to integrate the SDK into your own app.

[Read more](tutorial.md)

## Architecture

How the service is structured, why we chose each technology, and how the major components fit together. Includes the full entity-relationship diagram and system topology.

[Read more](architecture.md)

## Authentication

The OAuth2/OIDC login flow from browser redirect through provider callback to JWT issuance. Covers all three supported identity providers (Google, GitHub, Microsoft Entra ID) and how Authlib handles the heavy lifting.

[Read more](authentication.md)

## JWT Tokens

Access and refresh token structure, RS256 signing, claim contents, token lifecycle, and the refresh rotation mechanism with reuse detection. Explains how revocation works via the Redis-backed `jti` denylist.

[Read more](jwt.md)

## Workspaces

The tenant isolation boundary. Covers workspace CRUD, slug constraints, member management, and the four-tier role hierarchy (Owner, Admin, Editor, Viewer) with a full permissions matrix.

[Read more](workspaces.md)

## Groups

Named collections of users within a workspace. Groups simplify permission grants by letting you share resources with an entire team instead of individual users. Group IDs are embedded in JWT claims for fast resolution.

[Read more](groups.md)

## Permissions

The Zanzibar-style permission system with its three-tier architecture: workspace roles (stateless, from JWT), custom RBAC roles (action-based, service call), and entity-level ACLs (service call). Covers the 7-step `check_permission` resolution algorithm, visibility modes, and share types.

[Read more](permissions.md)

## Custom Roles (RBAC)

NIST Core RBAC as a third authorization layer between workspace roles and entity ACLs. Services register actions, admins organize them into named roles within workspaces, and users are assigned to roles. Action checks are real-time database queries -- revoking a role takes effect immediately.

[Read more](roles.md)

## Service-to-Service Auth

How consuming applications authenticate with the Identity Service using `X-Service-Key` headers. Covers the dual-auth and service-only auth tiers, dev mode bypass, and key generation.

[Read more](service-auth.md)

## Admin Panel

The administrative interface for platform operators. Covers the dashboard, user and workspace management, activity logs, CSV import, and the admin authentication flow.

[Read more](admin.md)
