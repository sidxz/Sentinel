# Public /authz/resolve — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow browser frontends to call `/authz/resolve` directly using CORS origin validation, eliminating the backend proxy.

**Architecture:** Add `allowed_origins` to `ServiceApp`. The `/authz/resolve` endpoint accepts either `X-Service-Key` (backends) or `Origin` header match (browsers). CORS middleware includes ServiceApp origins. JS SDK calls Sentinel directly.

**Tech Stack:** SQLAlchemy 2.0, Alembic, FastAPI, React (admin UI), TypeScript (JS SDK)

---

## Task 1: Add `allowed_origins` to ServiceApp Model

**Files:**
- Modify: `service/src/models/service_app.py`

**Step 1: Add the column**

Add after the `key_prefix` column (line 21):

```python
from sqlalchemy.dialects.postgresql import ARRAY

allowed_origins: Mapped[list[str]] = mapped_column(
    ARRAY(Text), server_default="{}", nullable=False
)
```

The import for `ARRAY` goes with the existing `UUID` import from `sqlalchemy.dialects.postgresql`.

**Step 2: Verify import compiles**

Run: `cd /Users/sidx/workspace/identity-service/service && uv run python -c "from src.models.service_app import ServiceApp; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add service/src/models/service_app.py
git commit -m "feat: add allowed_origins column to ServiceApp model"
```

---

## Task 2: Alembic Migration

**Files:**
- Create: `service/migrations/versions/f1a2b3c4d5e6_add_allowed_origins_to_service_apps.py`

**Step 1: Generate the migration**

```bash
cd /Users/sidx/workspace/identity-service/service && uv run alembic revision --autogenerate -m "add allowed_origins to service_apps"
```

Verify the generated migration adds the `allowed_origins` column as `ARRAY(sa.Text)` with `server_default='{}'`.

**Step 2: Run the migration**

```bash
cd /Users/sidx/workspace/identity-service/service && uv run alembic upgrade head
```

**Step 3: Commit**

```bash
git add service/migrations/versions/
git commit -m "feat: migration for allowed_origins on service_apps"
```

---

## Task 3: Origin Validation in Service Layer

**Files:**
- Modify: `service/src/services/service_app_service.py`

**Step 1: Add origin cache key and validate_origin function**

Add after `_CACHE_TTL = 300` (line 15):

```python
_ORIGIN_CACHE_KEY = "svc:origin_cache"
```

Add after the `has_active_apps` function (after line 132):

```python
async def validate_origin(origin: str, db: AsyncSession) -> tuple[str, uuid.UUID] | None:
    """Validate a request origin against service app allowed_origins.

    Returns (service_name, app_id) or None.
    """
    r = await get_redis()

    # Try cache first
    cached = await r.hget(_ORIGIN_CACHE_KEY, origin)
    if cached:
        svc, app_id_str = cached.split(":", 1)
        return svc, uuid.UUID(app_id_str)

    # Cache miss — rebuild origin cache from DB
    await _rebuild_origin_cache(db)

    # Retry from cache
    cached = await r.hget(_ORIGIN_CACHE_KEY, origin)
    if cached:
        svc, app_id_str = cached.split(":", 1)
        return svc, uuid.UUID(app_id_str)

    return None
```

**Step 2: Add `_rebuild_origin_cache` helper**

Add after `_rebuild_cache` (after line 150):

```python
async def _rebuild_origin_cache(db: AsyncSession) -> None:
    """Load all active apps' allowed_origins into a Redis hash."""
    r = await get_redis()
    result = await db.execute(
        select(ServiceApp).where(ServiceApp.is_active == True)  # noqa: E712
    )
    apps = result.scalars().all()
    pipe = r.pipeline()
    pipe.delete(_ORIGIN_CACHE_KEY)
    for app in apps:
        for origin in (app.allowed_origins or []):
            pipe.hset(_ORIGIN_CACHE_KEY, origin, f"{app.service_name}:{app.id}")
    pipe.expire(_ORIGIN_CACHE_KEY, _CACHE_TTL)
    await pipe.execute()
```

**Step 3: Invalidate origin cache alongside key cache**

In `_invalidate_cache()`, add the origin cache deletion:

```python
async def _invalidate_cache() -> None:
    r = await get_redis()
    await r.delete(_CACHE_KEY, _ORIGIN_CACHE_KEY)
```

**Step 4: Add `allowed_origins` to `update_service_app`**

Update the function signature and body:

```python
async def update_service_app(
    db: AsyncSession,
    app_id: uuid.UUID,
    name: str | None = None,
    is_active: bool | None = None,
    allowed_origins: list[str] | None = None,
) -> ServiceApp:
    app = await db.get(ServiceApp, app_id)
    if not app:
        raise ValueError("Service app not found")
    if name is not None:
        app.name = name
    if is_active is not None:
        app.is_active = is_active
    if allowed_origins is not None:
        app.allowed_origins = allowed_origins
    await db.flush()
    await _invalidate_cache()
    return app
```

**Step 5: Add `allowed_origins` to `create_service_app`**

Update the function signature:

```python
async def create_service_app(
    db: AsyncSession,
    name: str,
    service_name: str,
    created_by: uuid.UUID | None = None,
    allowed_origins: list[str] | None = None,
) -> tuple[ServiceApp, str]:
    plaintext, sha, prefix = _generate_key()
    app = ServiceApp(
        id=uuid.uuid4(),
        name=name,
        service_name=service_name,
        key_hash=sha,
        key_prefix=prefix,
        created_by=created_by,
        allowed_origins=allowed_origins or [],
    )
    db.add(app)
    await db.flush()
    await _invalidate_cache()
    return app, plaintext
```

**Step 6: Verify it compiles**

Run: `cd /Users/sidx/workspace/identity-service/service && uv run python -c "from src.services.service_app_service import validate_origin; print('OK')"`

**Step 7: Commit**

```bash
git add service/src/services/service_app_service.py
git commit -m "feat: add origin-based service app validation with Redis cache"
```

---

## Task 4: `require_service_context` Dependency

**Files:**
- Modify: `service/src/api/dependencies.py`

**Step 1: Add `require_service_context` function**

Add after `verify_service_scope` (after line 112):

```python
async def require_service_context(
    request: Request, db: AsyncSession = Depends(get_db)
) -> ServiceKeyContext:
    """Resolve service identity from X-Service-Key header OR Origin header.

    Backends send X-Service-Key. Browser frontends are identified by
    matching the Origin header against ServiceApp.allowed_origins.
    """
    from src.services import service_app_service

    # 1. Try service key (backends)
    key = request.headers.get("X-Service-Key")
    if key:
        result = await service_app_service.validate_key(key, db)
        if not result:
            raise HTTPException(
                status_code=401, detail="Invalid or missing service API key"
            )
        service_name, _app_id = result
        return ServiceKeyContext(service_name=service_name)

    # 2. Try origin (browser frontends)
    origin = request.headers.get("Origin")
    if origin:
        result = await service_app_service.validate_origin(origin, db)
        if result:
            service_name, _app_id = result
            return ServiceKeyContext(service_name=service_name)

    raise HTTPException(
        status_code=401,
        detail="Missing service API key or unregistered origin",
    )
```

**Step 2: Verify it compiles**

Run: `cd /Users/sidx/workspace/identity-service/service && uv run python -c "from src.api.dependencies import require_service_context; print('OK')"`

**Step 3: Commit**

```bash
git add service/src/api/dependencies.py
git commit -m "feat: add require_service_context dependency (key OR origin)"
```

---

## Task 5: Update `/authz/resolve` to Use New Dependency

**Files:**
- Modify: `service/src/api/authz_routes.py`

**Step 1: Change the dependency**

Replace the import (line 8):

```python
from src.api.dependencies import ServiceKeyContext, require_service_context
```

Replace the function parameter (line 32):

```python
service_ctx: ServiceKeyContext = Depends(require_service_context),
```

**Step 2: Run service tests**

Run: `cd /Users/sidx/workspace/identity-service/service && uv run pytest tests/ -x -q`
Expected: All tests pass

**Step 3: Commit**

```bash
git add service/src/api/authz_routes.py
git commit -m "feat: /authz/resolve accepts service key or origin auth"
```

---

## Task 6: Include ServiceApp Origins in CORS Middleware

**Files:**
- Modify: `service/src/middleware/cors.py`

**Step 1: Update `refresh_origins` to include ServiceApp origins**

Add import at top:

```python
from src.models.service_app import ServiceApp
```

Update `refresh_origins`:

```python
async def refresh_origins(db: AsyncSession) -> None:
    """Rebuild allowed origins from active client apps, service apps, and static config."""
    global _allowed_origins
    origins: set[str] = set(settings.cors_origin_list)

    # Client app redirect URIs
    stmt = select(ClientApp.redirect_uris).where(ClientApp.is_active.is_(True))
    result = await db.execute(stmt)
    for (uris,) in result.all():
        for uri in uris:
            origin = _extract_origin(uri)
            if origin:
                origins.add(origin)

    # Service app allowed origins
    svc_stmt = select(ServiceApp.allowed_origins).where(ServiceApp.is_active.is_(True))
    svc_result = await db.execute(svc_stmt)
    for (svc_origins,) in svc_result.all():
        for origin in (svc_origins or []):
            origins.add(origin)

    _allowed_origins = origins
    logger.info("cors_origins_refreshed", count=len(origins))
```

**Step 2: Verify it compiles**

Run: `cd /Users/sidx/workspace/identity-service/service && uv run python -c "from src.middleware.cors import refresh_origins; print('OK')"`

**Step 3: Commit**

```bash
git add service/src/middleware/cors.py
git commit -m "feat: include ServiceApp allowed_origins in CORS middleware"
```

---

## Task 7: Update Admin Schemas

**Files:**
- Modify: `service/src/schemas/service_app.py`

**Step 1: Add `allowed_origins` to schemas**

Update `ServiceAppCreateRequest`:

```python
class ServiceAppCreateRequest(BaseModel):
    name: SafeStr = Field(min_length=1, max_length=255)
    service_name: str = Field(
        pattern=r"^[a-z][a-z0-9-]*[a-z0-9]$", min_length=2, max_length=255
    )
    allowed_origins: list[str] = Field(default_factory=list)
```

Update `ServiceAppUpdateRequest`:

```python
class ServiceAppUpdateRequest(BaseModel):
    name: SafeStrOptional = None
    is_active: bool | None = None
    allowed_origins: list[str] | None = None
```

Update `ServiceAppResponse`:

```python
class ServiceAppResponse(BaseModel):
    id: uuid.UUID
    name: str
    service_name: str
    key_prefix: str
    is_active: bool
    allowed_origins: list[str]
    last_used_at: datetime | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

**Step 2: Commit**

```bash
git add service/src/schemas/service_app.py
git commit -m "feat: add allowed_origins to service app schemas"
```

---

## Task 8: Update Admin Routes

**Files:**
- Modify: `service/src/api/admin_routes.py`

**Step 1: Pass `allowed_origins` through create route**

In `create_service_app` (line 1221), add `allowed_origins`:

```python
app, plaintext_key = await service_app_service.create_service_app(
    db,
    name=body.name,
    service_name=body.service_name,
    created_by=actor_id,
    allowed_origins=body.allowed_origins,
)
```

**Step 2: Pass `allowed_origins` through update route**

In `update_service_app` (line 1271), add `allowed_origins`:

```python
app = await service_app_service.update_service_app(
    db,
    app_id,
    name=body.name,
    is_active=body.is_active,
    allowed_origins=body.allowed_origins,
)
```

**Step 3: Run all service tests**

Run: `cd /Users/sidx/workspace/identity-service/service && uv run pytest tests/ -x -q`

**Step 4: Commit**

```bash
git add service/src/api/admin_routes.py
git commit -m "feat: pass allowed_origins through admin service app routes"
```

---

## Task 9: Update Admin UI — TypeScript Types + API Client

**Files:**
- Modify: `admin/src/types/api.ts`
- Modify: `admin/src/api/client.ts`

**Step 1: Add `allowed_origins` to TypeScript interface**

In `admin/src/types/api.ts`, update the `ServiceApp` interface (line 213):

```typescript
export interface ServiceApp {
  id: string;
  name: string;
  service_name: string;
  key_prefix: string;
  is_active: boolean;
  allowed_origins: string[];
  last_used_at: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}
```

**Step 2: Update `createServiceApp` call signature**

In `admin/src/api/client.ts` (line 348):

```typescript
export const createServiceApp = (body: {
  name: string;
  service_name: string;
  allowed_origins?: string[];
}) =>
  request<ServiceAppCreateResponse>("/admin/service-apps", {
    method: "POST",
    body: JSON.stringify(body),
  });
```

**Step 3: Update `updateServiceApp` call signature**

In `admin/src/api/client.ts` (line 357):

```typescript
export const updateServiceApp = (
  id: string,
  body: { name?: string; is_active?: boolean; allowed_origins?: string[] },
) =>
  request<ServiceApp>(`/admin/service-apps/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
```

**Step 4: Commit**

```bash
git add admin/src/types/api.ts admin/src/api/client.ts
git commit -m "feat(admin): add allowed_origins to service app types and API client"
```

---

## Task 10: Update Admin UI — Service App Forms

**Files:**
- Modify: `admin/src/pages/ServiceApps.tsx`
- Modify: `admin/src/pages/ServiceAppDetail.tsx`

**Step 1: Update create form in `ServiceApps.tsx`**

Update the form state (line 62):

```typescript
const [form, setForm] = useState({ name: "", service_name: "", allowed_origins: "" });
```

Update the mutationFn (line 71-72):

```typescript
mutationFn: () =>
  createServiceApp({
    name: form.name,
    service_name: form.service_name,
    allowed_origins: form.allowed_origins
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean),
  }),
```

Reset form (line 76):

```typescript
setForm({ name: "", service_name: "", allowed_origins: "" });
```

Add the origins textarea in the modal, after the Service Name field (after line 164):

```tsx
<div>
  <label className="text-xs text-zinc-500">Allowed Origins (one per line)</label>
  <textarea
    value={form.allowed_origins}
    onChange={(e) => setForm((f) => ({ ...f, allowed_origins: e.target.value }))}
    placeholder={"http://localhost:5174\nhttps://app.example.com"}
    rows={3}
    className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 font-mono placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
  />
  <p className="mt-1 text-xs text-zinc-600">Browser frontends that can call /authz/resolve directly</p>
</div>
```

**Step 2: Update edit form in `ServiceAppDetail.tsx`**

Update editForm state (line 71):

```typescript
const [editForm, setEditForm] = useState({ name: "", is_active: true, allowed_origins: "" });
```

Update openEdit (line 119-121):

```typescript
const openEdit = () => {
  if (app) {
    setEditForm({
      name: app.name,
      is_active: app.is_active,
      allowed_origins: (app.allowed_origins || []).join("\n"),
    });
  }
  setShowEdit(true);
};
```

Update mutationFn in `update` (line 81-84):

```typescript
mutationFn: () =>
  updateServiceApp(id!, {
    name: editForm.name || undefined,
    is_active: editForm.is_active,
    allowed_origins: editForm.allowed_origins
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean),
  }),
```

Add origins textarea in the edit modal, after the Active checkbox (after line 200):

```tsx
<div>
  <label className="text-xs text-zinc-500">Allowed Origins (one per line)</label>
  <textarea
    value={editForm.allowed_origins}
    onChange={(e) => setEditForm((f) => ({ ...f, allowed_origins: e.target.value }))}
    placeholder={"http://localhost:5174\nhttps://app.example.com"}
    rows={3}
    className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 font-mono placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
  />
  <p className="mt-1 text-xs text-zinc-600">Browser frontends that can call /authz/resolve directly</p>
</div>
```

Also add origins display in the detail header card, after the Key line (after line 149):

```tsx
{app.allowed_origins.length > 0 && (
  <div className="text-xs text-zinc-500">
    Origins: {app.allowed_origins.map((o, i) => (
      <code key={i} className="text-zinc-400 font-mono">{o}{i < app.allowed_origins.length - 1 ? ", " : ""}</code>
    ))}
  </div>
)}
```

**Step 3: Commit**

```bash
git add admin/src/pages/ServiceApps.tsx admin/src/pages/ServiceAppDetail.tsx
git commit -m "feat(admin): add allowed_origins field to service app forms"
```

---

## Task 11: Update JS SDK — `sentinelUrl` Config

**Files:**
- Modify: `sdks/js/src/authz-types.ts`
- Modify: `sdks/js/src/authz-client.ts`
- Modify: `sdks/js/src/__tests__/authz-client.test.ts`

**Step 1: Update config type**

In `sdks/js/src/authz-types.ts`, change `SentinelAuthzConfig`:

```typescript
export interface SentinelAuthzConfig {
  /** Base URL of the Sentinel service (e.g. "http://localhost:9003").
   *  Derives /authz/resolve for token exchange. */
  sentinelUrl: string
  /** Token storage backend. Defaults to AuthzLocalStorageStore. */
  storage?: AuthzTokenStore
  /** Automatically refresh authz token before expiry. Defaults to true. */
  autoRefresh?: boolean
  /** Seconds before authz token expiry to trigger refresh. Defaults to 30. */
  refreshBuffer?: number
}
```

**Step 2: Update client**

In `sdks/js/src/authz-client.ts`:

- Rename `backendUrl` to `sentinelUrl` in constructor and field
- Change resolve URL from `${this.sentinelUrl}/auth/resolve` to `${this.sentinelUrl}/authz/resolve`

Key changes:

```typescript
private readonly sentinelUrl: string

constructor(config: SentinelAuthzConfig) {
  this.sentinelUrl = config.sentinelUrl.replace(/\/+$/, '')
  // ... rest same
  warnIfInsecure(this.sentinelUrl, 'SentinelAuthz')
  // ...
}

async resolve(idpToken: string, provider: string): Promise<AuthzResolveResponse> {
  const res = await fetch(`${this.sentinelUrl}/authz/resolve`, {
    // ... same body
  })
  // ...
}

async selectWorkspace(idpToken: string, provider: string, workspaceId: string): Promise<void> {
  const res = await fetch(`${this.sentinelUrl}/authz/resolve`, {
    // ... same body with workspace_id
  })
  // ...
}
```

**Step 3: Update tests**

In `sdks/js/src/__tests__/authz-client.test.ts`:

- Change config from `backendUrl: 'http://localhost:9200'` to `sentinelUrl: 'http://localhost:9003'`
- Change all URL assertions from `http://localhost:9200/auth/resolve` to `http://localhost:9003/authz/resolve`

**Step 4: Run tests**

Run: `cd /Users/sidx/workspace/identity-service/sdks/js && npx vitest run`
Expected: All 61 tests pass

**Step 5: Build**

Run: `cd /Users/sidx/workspace/identity-service/sdks/js && npx tsup`

**Step 6: Commit**

```bash
git add sdks/js/src/authz-types.ts sdks/js/src/authz-client.ts sdks/js/src/__tests__/authz-client.test.ts
git commit -m "feat(js-sdk): SentinelAuthz calls Sentinel directly (sentinelUrl)"
```

---

## Task 12: Update Demo Frontend

**Files:**
- Modify: `demo-authz/frontend/src/main.tsx`

**Step 1: Change config to use sentinelUrl**

```tsx
const SENTINEL_URL = import.meta.env.VITE_SENTINEL_URL || 'http://localhost:9003'

// In the render:
<AuthzProvider config={{ sentinelUrl: SENTINEL_URL }}>
```

**Step 2: Update `.env.example`**

In `demo-authz/frontend/.env.example`:

```
VITE_GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
VITE_SENTINEL_URL=http://localhost:9003
VITE_BACKEND_URL=http://localhost:9200
```

**Step 3: Rebuild React SDK (since types changed)**

```bash
cd /Users/sidx/workspace/identity-service/sdks/react && npx tsup
```

**Step 4: Commit**

```bash
git add demo-authz/frontend/src/main.tsx demo-authz/frontend/.env.example
git commit -m "feat(demo-authz): frontend calls Sentinel directly for authz resolve"
```

---

## Task 13: Final Verification

**Step 1: Run all JS SDK tests**

```bash
cd /Users/sidx/workspace/identity-service/sdks/js && npx vitest run
```

**Step 2: Build all SDK packages**

```bash
cd /Users/sidx/workspace/identity-service/sdks/js && npx tsup
cd /Users/sidx/workspace/identity-service/sdks/react && npx tsup
cd /Users/sidx/workspace/identity-service/sdks/nextjs && npx tsup
```

**Step 3: Run Python service tests**

```bash
cd /Users/sidx/workspace/identity-service/service && uv run pytest tests/ -x -q
```

**Step 4: Verify service starts**

```bash
cd /Users/sidx/workspace/identity-service && make lint
```
