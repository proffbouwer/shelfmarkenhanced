## Progress

**Session 1 (2026-05-08):** Phase 0 + Phase 1 complete.
- main.py: 3,323 → 391 lines (88% reduction)
- New modules: auth_middleware, auth_routes, static_routes, settings_routes, download_routes, metadata_routes, websocket_handlers
- settings.py: 1,871 lines → settings/ package (6 sub-modules)
- rate_limit.py: persistent SQLite-backed login rate limiting
- api_errors.py: @handle_api_errors decorator
- Docker CI: .github/workflows/build-and-publish-enhanced.yml + compose/docker-compose.enhanced.yml

**Session 2 (2026-05-21):** Phase 2 + Phase 3 + Phase 4 + Phase 6 complete.
- SettingsPage wired as dedicated route `/settings/:tab`
- Magic UI components (AnimatedBackground, ShimmerButton, BlurFade, BorderBeam, NumberTicker, TextReveal)
- Download privacy: public/private visibility, `.private/<user_id>/` storage
- Library screen: full CRUD + visibility filters + send-to-ACW/folder
- Phase 6: SAML2 SSO, OIDC promotion, session invalidation, UsersPage

**Next:** Phase 5 (Gluetun VPN) or Phase 7 (CI/CD Dockerfile.enhanced)

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

- [x] **P3-1** Investigate `authlib <1.8` cap — 1.8 doesn't exist; latest is 1.7.2; widened to `>=1.7.0`
- [x] **P3-2** Upgrade all Python deps (`uv lock --upgrade`) — 20 packages updated
- [x] **P3-3** gevent 26.4→26.5, Flask-SocketIO 5.6.1 already latest; pair is fine
- [x] **P3-4** Install `motion` package (motion/react API, replaces framer-motion branding)
- [x] **P3-5** Copy + adapt Magic UI components to `src/frontend/src/components/ui/magic/`:
  - [x] `AnimatedBackground.tsx` — animated highlight primitive (AnimatedTabs built on this)
  - [x] `ShimmerButton.tsx` — Primary action buttons
  - [x] `BlurFade.tsx` — Page/card load animations
  - [x] `BorderBeam.tsx` — Active download card highlight
  - [x] `NumberTicker.tsx` — Queue/download count stats
  - [x] `TextReveal.tsx` — Onboarding welcome
- [x] **P3-6** Tailwind v4 CSS variable syntax applied; keyframes added to styles.css as `@utility`

---

## Phase 4 — Download Privacy + Library Screen

### Database

- [x] **P4-1** Add migration: `visibility` + `private_storage_path` columns to `download_history`
- [x] **P4-2** Add index on `(visibility, user_id, terminal_at DESC)`

### Backend

- [x] **P4-3** Add `visibility: str = 'public'` field to `DownloadTask` model
- [x] **P4-4** `queue_release()` accepts `visibility` param; stores on task + history row
- [x] **P4-5** Private downloads routed to `<base>/.private/<user_id>/` in `destination.py`
- [x] **P4-6** `POST /api/releases/download` reads `visibility` from request body
- [x] **P4-7** `GET /api/localdownload` returns 403 for private files not owned by caller
- [x] **P4-8** `shelfmark/core/library_routes.py` — all 4 endpoints implemented

### Frontend

- [x] **P4-9** `src/frontend/src/pages/LibraryPage.tsx`
- [x] **P4-10** `src/frontend/src/hooks/useLibrary.ts`
- [x] **P4-11** `src/frontend/src/components/library/`:
  - [x] `LibraryGrid.tsx`
  - [x] `LibraryItem.tsx` (visibility badge, download/ACW/folder/delete actions)
  - [x] `LibraryFilters.tsx` (search, visibility, status filters)
  - [x] `SendToFolderModal.tsx`
- [x] **P4-12** `src/frontend/src/services/libraryApi.ts`
- [x] **P4-13** `/library` route added to `App.tsx`
- [x] **P4-14** "Library" link added to `Header.tsx` dropdown

---

## Phase 5 — Gluetun VPN Integration

### Docker

- [x] **P5-1** Create `compose/docker-compose.gluetun.yml` overlay
- [x] **P5-2** Move port mapping from `shelfmark` → `gluetun` in the overlay
- [x] **P5-3** Add `network_mode: "service:gluetun"` to shelfmark in overlay
- [x] **P5-4** Document usage: `docker compose -f ... -f compose/docker-compose.gluetun.yml up`

### Backend

- [x] **P5-5** Create `shelfmark/config/settings/vpn_settings.py` — provider, type, credentials, regions, kill switch fields
- [x] **P5-6** Add `GET /api/vpn/status` endpoint → calls Gluetun control API at `http://gluetun:8000/v1/publicip/ip`
- [x] **P5-7** VPN provider fields are reference-only (Gluetun manages them via env vars); restart note shown in field descriptions

### Frontend

- [x] **P5-8** Add VPN settings tab to Settings page
- [x] **P5-9** VPN status indicator in Header (connected / disconnected)

---

## Phase 6 — User Management + SSO (OIDC + SAML2)

### Database

- [x] **P6-1** Migration: add `saml_subject`, `last_login_at`, `session_invalidated_at` columns to `users`
- [x] **P6-2** Add unique index on `saml_subject`

### OIDC Completion

- [x] **P6-3** Promote `HIDE_LOCAL_AUTH` + `OIDC_AUTO_REDIRECT` from env-only to settings fields
- [x] **P6-4** Add `OIDC_EMAIL_CLAIM` + `OIDC_USERNAME_CLAIM` settings fields
- [x] **P6-5** Add "Force re-login" admin action per user — `POST /api/admin/users/<id>/force-logout`

### SAML2

- [x] **P6-6** Add `python3-saml` dependency
- [x] **P6-7** Add `libxmlsec1-dev xmlsec1 libssl-dev pkg-config` to Dockerfile
- [x] **P6-8** Create `shelfmark/core/saml_auth.py` — metadata parsing, assertion validation, user provisioning
- [x] **P6-9** Create `shelfmark/core/saml_routes.py` — `/api/auth/saml/login`, `/api/auth/saml/callback`, `/api/auth/saml/metadata`
- [x] **P6-10** Add SAML settings fields to `shelfmark/config/security.py`
- [x] **P6-11** Wire `register_saml_routes()` in app factory

### User Management Enhancements

- [x] **P6-12** Add `GET /api/admin/users/<id>/stats` endpoint
- [x] **P6-13** Add `DELETE /api/admin/users/<id>/sessions` endpoint (alias for force-logout)
- [x] **P6-14** Add `session_invalidated_at` check in `login_required`
- [x] **P6-15** Create `src/frontend/src/pages/UsersPage.tsx`
- [x] **P6-16** Add "Force Re-Login" per-user action to `UserListView.tsx`
- [x] **P6-17** Add `last_login_at` / download stats to user model + API
- [x] **P6-18** Add `/users` route to `App.tsx` + "Users" link in `Header.tsx` (admin-only)

---

## Docker / CI

- [x] **CI-1** Add OCI `LABEL` to `shelfmark` stage in Dockerfile identifying it as enhanced-shelfmark
- [x] **CI-2** Update `compose/docker-compose.enhanced.yml` to reference `ghcr.io/proffbouwer/enhanced-shelfmark:latest`
- [x] **CI-3** GitHub Actions workflow `.github/workflows/build-and-publish-enhanced.yml` builds + pushes to GHCR on push to main/development/tags

---

## Notes

- SAML library choice: `python3-saml` (needs C lib, better IdP compat) vs `pysaml2` (pure Python)
- `authlib <1.8` cap: investigate changelog before widening
- Magic UI + Tailwind v4: translate v3 class syntax to CSS variable syntax when copying components
- Gluetun VPN settings write to `.env.vpn`; changing provider requires container restart
- SQLite migrations: always use `ALTER TABLE ... ADD COLUMN` (safe, non-destructive); never `DROP COLUMN`
