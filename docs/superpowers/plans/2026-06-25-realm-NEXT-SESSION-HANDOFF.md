# Realms — Next-Session Handoff (Plans 2–6)

**Read this first in a fresh session, then resume. Do NOT re-brainstorm — the design is approved.**

## Resume in one line
`git checkout realm-trusted-app-group` → read the spec (below) → for **each** plan: `superpowers:writing-plans` to author it, then `superpowers:subagent-driven-development` to execute it. One plan per cycle; review between.

## Authority documents
- **Spec (source of truth):** `docs/superpowers/specs/2026-06-25-realm-trusted-app-group-design.md`
- **Plan 1 (done, reference style):** `docs/superpowers/plans/2026-06-25-realm-scope-core.md`
- **Memory:** `realm-trusted-app-groups.md` (auto-loaded via MEMORY.md)

## State
- **Plan 1 of 6 = DONE** on branch `realm-trusted-app-group` (commits `041249c..90251e8`). Full suite **273 green**; Opus final review = ready-to-merge, no Critical/Important. Branch **kept as-is, not merged**.
- ⚠️ Branch is **stacked on the unmerged `ratelimit-consolidation`** (created off `551c0ce`, not `main`) — merge/PR to main would carry rate-limit too. Realm-only range = `551c0ce..HEAD`.
- The working tree holds the **user's unrelated uncommitted work** (`role_service.py`, `test_register_actions.py`, session-start rate-limit edits to `config.py`/`main.py`/`middleware/rate_limit.py`/`permission_routes.py`/`test_rate_limit_*`). **Never commit, format, or discard these.**

## Plans 2–6 (scope only — author details in writing-plans)
2. **Token flows** — `GET /realm/whoami` (SDK self-discovers `effective_scope`); `_AUD_M2M = "sentinel:m2m"` + `create_m2m_token()` in `jwt.py`; `POST /realm/m2m-token` (`require_service_key`, rate-limited via `service_or_ip_key`, server-stamps `caller`+`svc` from the key, `actions:["*"]`, optional `aud_target` reserved-off); SDK accept (`type=m2m` → `SystemAuth`) + cached mint helper. (Authz-token `svc=effective_scope` minting was ALREADY done in Plan 1.)
3. **Network split** — `create_app(tier)` factory in `main.py`; `TIER` env → public listener (admin, proxy `/auth/*`, jwks) vs **unpublished** internal listener (`/realm/*`, `/permissions/*`, `/authz/*`, roles); router audit (user/workspace/group routers → audit, default public).
4. **Admin** — `/admin/realms` CRUD + membership (`admin_routes.py`, admin cookie + `X-Requested-With`); audit events `realm_*`; React Realms page; Service App detail shows realm. **Must add** realm-`slug` schema validation `^[a-z][a-z0-9-]*[a-z0-9]$` (deferred from Plan 1).
5. **SDKs** — Python `whoami`/`mint_m2m_token()`/`SystemAuth`; JS m2m mint+accept in the **server** entry only (`@sentinel-auth/js` server, nextjs server helpers) — never browser.
6. **Docs** — guide/api/sdk for realms + m2m + the internal-listener deployment posture.

## Interfaces Plan 1 already provides (build on these)
- `ServiceKeyContext.realm_slug` + `.effective_scope` property (`service/src/api/dependencies.py`).
- `validate_key(...) -> (service_name, app_id, realm_slug)` 3-tuple + `_encode_cache`/`_decode_cache` (`service/src/services/service_app_service.py`).
- `realm_service`: `create_realm/get_realm/list_realms/add_member/remove_member` (`service/src/services/realm_service.py`).
- `Realm` model + `service_apps.realm_id` FK (`service/src/models/realm.py`).
- Audiences in `service/src/auth/jwt.py`: `_AUD_ACCESS/_AUD_ADMIN/_AUD_REFRESH/_AUD_AUTHZ` (add `_AUD_M2M`).

## MANDATORY conventions for every subagent dispatch (these bit us / kept us safe)
- **Format/stage ONLY changed files** (`uv run ruff format <files>` + `ruff check --fix <files>` from `service/`). NEVER `ruff format .` / whole-tree `--fix` / `make fmt`. NEVER `git add -A`/`.`.
- **Never touch** `service/src/services/role_service.py` or `service/tests/test_register_actions.py`.
- **Tests** = pure-unit with fakes (no `conftest.py`); `@pytest.mark.asyncio` for async. For handler-level behavior, the **behavioral TestClient + dependency_overrides + monkeypatch** pattern (`test_authz_org_gate.py`, `test_realm_authz_minting.py`) is the house style. Gate on the **task's own test file**; broad-suite **IdP/JWKS connection failures are a known network-sandbox artifact**, not task failures.
- **Regenerate `task-brief` per plan** from the correct plan file. The `.superpowers/sdd/task-*-brief.md` slots may hold STALE briefs (rate-limit + Plan-1) — overwrite or verify before dispatching. (In Plan 1, `task-5-brief.md` was a stale rate-limit brief; only the self-contained dispatch saved it.)
- **SDD ledger**: `.superpowers/sdd/progress.md` (currently Plan 1; archive it before starting a new plan's SDD run). Rate-limit history archived at `progress-ratelimit-archive.md`.

## Known repo gotcha (from memory, relevant to Plan 3 network split)
- `service/Dockerfile` does NOT `COPY uv.lock` before `uv sync` → container installs latest-within-pyproject, not the pinned lock. Keep in mind when wiring two listeners into the deploy.
