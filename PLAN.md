## Progress

**Session 1 (2026-05-08):** Phase 0 + Phase 1 complete.
- main.py: 3,323 → 391 lines (88% reduction)
- New modules: auth_middleware, auth_routes, static_routes, settings_routes, download_routes, metadata_routes, websocket_handlers
- settings.py: 1,871 lines → settings/ package (6 sub-modules)
- rate_limit.py: persistent SQLite-backed login rate limiting
- api_errors.py: @handle_api_errors decorator
- Docker CI: .github/workflows/build-and-publish-enhanced.yml + compose/docker-compose.enhanced.yml

**Next:** Phase 2 (Settings screen route), Phase 3 (deps + Magic UI), Phase 4 (download privacy + library)

---

# Enhanced Shelfmark — Implementation Plan & Progress Checklist

> Image name: `enhanced_shelfmark` | Repo: proffbouwer/enhanced-shelfmark
> Branch strategy: `main` branch = upstream tracking, `enhanced/` branches = our work

---

## Top 6 Code Quality Improvements (Phase 0)

- [x] **P0-1** Persist rate limiting to SQLite — remove `failed_login_attempts` dict, add `login_attempts` table in `users.db`, create `shelfmark/core/rate_limit.py`
- [x] **P0-2** Global API error handler — create `shelfmark/core/api_errors.py` with `@handle_api_errors` decorator, eliminate ~40 duplicate try/except blocks
- [x] **P0-3** Startup-time settings registration — call `_register_all_settings()` once in app factory, remove per-route `import_module()` calls
- [x] **P0-4** Split `settings.py` into group files — each group gets `shelfmark/config/settings/<group>_settings.py`, main becomes importer shim
- [ ] **P0-5** Typed config accessor — Pydantic or `@dataclass` layer over `app_config.get()` calls
- [ ] **P0-6** Complete route extraction pattern — extract all remaining routes from `main.py` following existing `register_*_routes()` pattern

---

## Phase 1 — Refactor main.py + settings.py

### main.py extraction (target: < 200 lines, app factory only)

- [x] **P1-1** Extract `auth_middleware.py` — `login_required` decorator, `_resolve_status_scope` (shared by all modules, must go first)
- [x] **P1-2** Extract `static_routes.py` — `index.html` + asset serving
- [x] **P1-3** Extract `auth_routes.py` — `/api/auth/login`, `/api/auth/logout`, `/api/auth/check`, proxy auth middleware
- [x] **P1-4** Extract `settings_routes.py` — `/api/settings/*`, `/api/onboarding/*`
- [x] **P1-5** Extract `download_routes.py` — `/api/releases/download`, queue management, retry, local download
- [x] **P1-6** Extract `metadata_routes.py` — `/api/metadata/*`, `/api/releases`, `/api/release-sources`
- [x] **P1-7** Extract `websocket_handlers.py` — `@socketio.on` connect/disconnect/status events
- [x] **P1-8** Slim `main.py` to app factory only (< 200 lines)

### settings.py split (target: one file per group)

- [x] **P1-9** Create `shelfmark/config/settings/` package with `__init__.py`
- [x] **P1-10** Extract `general_settings.py` (general, search_mode groups)
- [x] **P1-11** Extract `network_settings.py` (network, proxy groups)
- [x] **P1-12** Extract `download_settings.py` (direct_download, output groups)
- [x] **P1-13** Extract `metadata_settings.py` (metadata_providers group)
- [x] **P1-14** Extract `advanced_settings.py` (advanced group + `_on_save_advanced`)
- [x] **P1-15** Keep `security.py` + `users_settings.py` as-is (already separate)
- [x] **P1-16** Replace `shelfmark/config/settings.py` with importer shim

---

## Phase 2 — Dedicated Settings Screen (Frontend)

- [x] **P2-1** Create `src/frontend/src/pages/SettingsPage.tsx`
- [x] **P2-2** Add routes `/settings` → redirect, `/settings/:tab` in `App.tsx`
- [x] **P2-3** Update `App.tsx` — admin settings click navigates to `/settings/general` instead of opening modal
- [ ] **P2-4** Keep modal accessible via keyboard shortcut
- [ ] **P2-5** Add "Settings" to navigation

---

## Phase 3 — Dependency Upgrades + Magic UI

- [ ] **P3-1** Investigate `authlib <1.8` cap — read changelog, widen if safe
- [ ] **P3-2** Upgrade all Python deps (`uv lock --upgrade`), run tests
- [ ] **P3-3** Upgrade `gevent` + `Flask-SocketIO` as a pair, verify WebSocket
- [ ] **P3-4** Install `framer-motion` for Magic UI
- [ ] **P3-5** Copy + adapt Magic UI components to `src/frontend/src/components/ui/magic/`:
  - [ ] `AnimatedTabs.tsx` — Settings tab navigation
  - [ ] `ShimmerButton.tsx` — Primary action buttons
  - [ ] `BlurFade.tsx` — Page/card load animations
  - [ ] `BorderBeam.tsx` — Active download card highlight
  - [ ] `NumberTicker.tsx` — Queue/download count stats
  - [ ] `TextReveal.tsx` — Onboarding welcome
- [ ] **P3-6** Adapt Tailwind v3 class syntax → v4 CSS variable syntax in all copied components

---

## Phase 4 — Download Privacy + Library Screen

### Database

- [ ] **P4-1** Add migration: `visibility` + `private_storage_path` columns to `download_history`
- [ ] **P4-2** Add index on `(visibility, user_id, terminal_at DESC)`

### Backend

- [ ] **P4-3** Add `visibility` field to `DownloadTask` model
- [ ] **P4-4** Update `orchestrator.py` `queue_release()` to accept + store `visibility`
- [ ] **P4-5** Branch destination path in post-process: public → `/books/`, private → `/books/.private/{user_id}/`
- [ ] **P4-6** Update `POST /api/releases/download` to accept `visibility` field
- [ ] **P4-7** Update `GET /api/localdownload` — enforce ownership for private files
- [ ] **P4-8** Create `shelfmark/core/library_routes.py` with new endpoints:
  - [ ] `GET /api/library` — paginated, filtered, visibility-scoped
  - [ ] `POST /api/library/<task_id>/send-to-acw`
  - [ ] `POST /api/library/<task_id>/send-to-folder`
  - [ ] `DELETE /api/library/<task_id>`

### Frontend

- [ ] **P4-9** Create `src/frontend/src/pages/LibraryPage.tsx`
- [ ] **P4-10** Create `src/frontend/src/hooks/useLibrary.ts`
- [ ] **P4-11** Create `src/frontend/src/components/library/` components:
  - [ ] `LibraryGrid.tsx`
  - [ ] `LibraryItem.tsx` (privacy badge, action buttons)
  - [ ] `LibraryFilters.tsx` (search, sort, visibility filter)
  - [ ] `SendToAcwModal.tsx`
- [ ] **P4-12** Create `src/frontend/src/services/libraryApi.ts`
- [ ] **P4-13** Add `/library` route to `App.tsx`
- [ ] **P4-14** Add "Library" link to `Header.tsx`

---

## Phase 5 — Gluetun VPN Integration

### Docker

- [ ] **P5-1** Create `compose/docker-compose.gluetun.yml` overlay
- [ ] **P5-2** Move port mapping from `shelfmark` → `gluetun` in the overlay
- [ ] **P5-3** Add `network_mode: "service:gluetun"` to shelfmark in overlay
- [ ] **P5-4** Document usage: `docker compose -f ... -f compose/docker-compose.gluetun.yml up`

### Backend

- [ ] **P5-5** Create `shelfmark/config/settings/vpn_settings.py` — provider, type, credentials, regions, kill switch fields
- [ ] **P5-6** Add `GET /api/vpn/status` endpoint → calls Gluetun control API at `http://gluetun:8000/v1/publicip/ip`
- [ ] **P5-7** VPN settings write to `.env.vpn` file; show "restart required" banner on change

### Frontend

- [ ] **P5-8** Add VPN settings tab to Settings page
- [ ] **P5-9** VPN status indicator in Header (connected / disconnected)

---

## Phase 6 — User Management + SSO (OIDC + SAML2)

### Database

- [ ] **P6-1** Migration: add `saml_subject`, `last_login_at`, `session_invalidated_at` columns to `users`
- [ ] **P6-2** Add unique index on `saml_subject`

### OIDC Completion

- [ ] **P6-3** Promote `HIDE_LOCAL_AUTH` + `OIDC_AUTO_REDIRECT` from env-only to settings fields
- [ ] **P6-4** Add `OIDC_EMAIL_CLAIM` + `OIDC_USERNAME_CLAIM` settings fields
- [ ] **P6-5** Add "Force re-login" admin action per user

### SAML2

- [ ] **P6-6** Add `python3-saml` (or `pysaml2`) dependency
- [ ] **P6-7** Add `libxmlsec1-dev` to Dockerfile (if using `python3-saml`)
- [ ] **P6-8** Create `shelfmark/core/saml_auth.py` — metadata parsing, assertion validation, user provisioning
- [ ] **P6-9** Create `shelfmark/core/saml_routes.py` — `/api/auth/saml/login`, `/api/auth/saml/callback`, `/api/auth/saml/metadata`
- [ ] **P6-10** Add SAML settings fields to `shelfmark/config/security.py`
- [ ] **P6-11** Wire `register_saml_routes()` in app factory

### User Management Enhancements

- [ ] **P6-12** Add `GET /api/admin/users/<id>/stats` endpoint
- [ ] **P6-13** Add `GET/DELETE /api/admin/users/<id>/sessions` endpoints
- [ ] **P6-14** Add `session_invalidated_at` check in `login_required`
- [ ] **P6-15** Create `src/frontend/src/pages/UsersPage.tsx`
- [ ] **P6-16** Add bulk actions to `UserListView.tsx` (role change, bulk delete)
- [ ] **P6-17** Add user activity cards (last login, stats)
- [ ] **P6-18** Add `/users` route to `App.tsx`

---

## Docker / CI

- [ ] **CI-1** Create `Dockerfile.enhanced` (or add `LABEL` to existing + rename image in compose)
- [ ] **CI-2** Update `compose/docker-compose.yml` image name → `enhanced_shelfmark`
- [ ] **CI-3** Add GitHub Actions workflow to push `enhanced_shelfmark` image to GHCR under `proffbouwer/enhanced-shelfmark`

---

## Notes

- SAML library choice: `python3-saml` (needs C lib, better IdP compat) vs `pysaml2` (pure Python)
- `authlib <1.8` cap: investigate changelog before widening
- Magic UI + Tailwind v4: translate v3 class syntax to CSS variable syntax when copying components
- Gluetun VPN settings write to `.env.vpn`; changing provider requires container restart
- SQLite migrations: always use `ALTER TABLE ... ADD COLUMN` (safe, non-destructive); never `DROP COLUMN`
