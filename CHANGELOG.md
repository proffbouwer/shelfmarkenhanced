# Changelog

All notable changes to Shelfmark Enhanced are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] — 2026-05-26

Initial public release of Shelfmark Enhanced.

### Added

#### Authentication & Users
- **SAML2 SSO** — single sign-on support for Authentik, Keycloak, Okta, Azure AD, and any SAML2-compliant identity provider
- **Session invalidation** — active sessions are invalidated on auth config changes, forcing re-authentication
- **Users admin page** — full user management UI at `/users`; create, edit, enable/disable users without touching config files

#### VPN Integration
- **Gluetun VPN overlay** — Docker Compose overlay (`docker-compose.gluetun.yml`) that routes all Shelfmark traffic through a VPN with kill-switch protection
- **VPN status indicator** — live connected/disconnected pill in the header, polling the Gluetun HTTP control API
- **VPN settings widget** — status display in the Settings page

#### UI Enhancements
- **Floating book-cover parallax** — animated Canvas 2D background on the home screen; 25 book covers float across 5 depth layers with subtle mouse-parallax
- **Library shelf redesign** — completed downloads shown as an animated book grid; clicking a book morphs it into a 3D open-book detail modal using Framer Motion `layoutId`
- **Download visibility toggle** — Public / Private selector in the header dropdown, persisted per user in `localStorage`; wired into all download and request submission paths

#### Infrastructure
- **Multi-platform Docker images** — `linux/amd64` and `linux/arm64` builds published to GHCR on every release
- **Pre-built images** — no local build required; pull `ghcr.io/shelfmark-enhanced/enhanced-shelfmark:latest`
- **`publish_image.sh`** — interactive release script for tagging and pushing new versions
- **OCI image labels** — `org.opencontainers.image.*` labels on all published images
- **GitHub Actions CI/CD** — automated build and publish pipeline with GHA cache for faster builds

#### Code Quality
- **Refactored `main.py`** — split from a single 3,300-line file into focused route modules
- **Refactored `settings.py`** — split into a per-group package under `shelfmark/config/settings/`
- **Persistent rate limiting** — login lockouts survive container restarts (SQLite-backed)

### Inherited from upstream Shelfmark

All original Shelfmark features are fully preserved — source plugins, metadata providers (Hardcover, Open Library, Google Books), the request system, download queue, Calibre-Web integration, audiobook support, OIDC, proxy auth, Prowlarr, IRC, and more.

See the [upstream changelog](https://github.com/calibrain/shelfmark) for the history of the base project.

---

<!-- 
Template for future releases:

## [X.Y.Z] — YYYY-MM-DD

### Added
- 

### Changed
- 

### Fixed
- 

### Removed
- 

### Security
- 
-->
