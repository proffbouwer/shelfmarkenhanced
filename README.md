# 📚 Shelfmark & Shelfmark Enhanced

> **Shelfmark Enhanced** is a community fork of [Shelfmark](https://github.com/calibrain/shelfmark) by CaliBrain — with added SSO, VPN integration, UI enhancements, and a refactored codebase. It is fully open source, free to use, and no commercial version exists.

---

## Table of Contents

- [Shelfmark (upstream)](#-shelfmark-upstream)
  - [Features](#-features)
  - [Screenshots](#-screenshots)
  - [Quick Start](#-quick-start)
  - [Configuration](#-configuration)
  - [Docker Variants](#-docker-variants)
  - [Authentication](#-authentication-upstream)
  - [Project Scope](#project-scope)
  - [Health Monitoring](#health-monitoring)
  - [Logging](#logging)
  - [Development](#development)
- [Shelfmark Enhanced](#-shelfmark-enhanced-1)
  - [What's Different](#-whats-different)
  - [Quick Start (Enhanced)](#-quick-start-enhanced)
  - [With VPN (Gluetun)](#with-vpn-gluetun-overlay)
  - [Authentication (Enhanced)](#-authentication-enhanced)
  - [Pre-built Docker Images](#-pre-built-docker-images)
  - [Building Locally](#-building-locally)
  - [Contributing](#-contributing)
- [Licence & Legal](#-licence--legal)

---

# 📖 Shelfmark (upstream)

<img src="src/frontend/public/logo.png" alt="Shelfmark" width="200">

Shelfmark is a self-hosted web interface for searching and requesting books and audiobooks across multiple sources. Bring your own sources, metadata providers, and download clients to build a single hub for your digital library. Supports multiple users with a built-in request system, so you can share your instance with others and let them browse and request books on their own.

Works great alongside the following library tools, with support for automatic imports:
- [Calibre](https://calibre-ebook.com/)
- [Calibre-Web](https://github.com/janeczku/calibre-web)
- [Calibre-Web-Automated](https://github.com/crocodilestick/Calibre-Web-Automated)
- [Grimmory](https://github.com/grimmory-tools/grimmory)
- [Audiobookshelf](https://github.com/advplyr/audiobookshelf)

## ✨ Features

- **One-Stop Interface** - A clean, modern UI to search, browse, and download from multiple configured sources in one place
- **Multiple Sources** - Configurable web, torrent, usenet, and IRC source support
- **Audiobook Support** - Full audiobook search and download with dedicated processing
- **Flexible Search** - Search metadata providers (Hardcover, Open Library, Google Books) for rich book and audiobook discovery, or query configured sources directly
- **Multi-User & Requests** - Share your instance with others, let users browse and request books, and manage approvals with configurable notifications
- **Authentication** - Built-in login, OIDC single sign-on, proxy auth, and Calibre-Web database support
- **Real-Time Progress** - Unified download queue with live status updates across all sources
- **Network Flexibility** - Configurable proxy support, DNS settings, and optional Cloudflare handling for protected sources

## 🖼️ Screenshots

**Home screen**
![Home screen](README_images/homescreen.png 'Home screen')

**Search results**
![Search results](README_images/search-results.png 'Search results')

**Multi-source downloads**
![Multi-source downloads](README_images/multi-source.png 'Multi-source downloads')

**Download queue**
![Download queue](README_images/downloads.png 'Download queue')

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose

### Installation

1. Download the [docker-compose file](compose/docker-compose.yml):
   ```bash
   curl -O https://raw.githubusercontent.com/calibrain/shelfmark/main/compose/docker-compose.yml
   ```

2. Start the service:
   ```bash
   docker compose up -d
   ```

3. Open `http://localhost:8084`

Open the web interface, then configure the sources and settings you want to use.

### Volume Setup

```yaml
volumes:
  - /your/config/path:/config   # Config, database, and artwork cache directory
  - /your/download/path:/books  # Downloaded books
  - /client/path:/client/path   # Optional: For Torrent/Usenet downloads, match your client directory exactly.
```

> **Tip**: Point the download volume to your CWA or Grimmory ingest folder for automatic import.

> **Note**: CIFS shares require `nobrl` mount option to avoid database lock errors.

### Non-root container mode

- Start the container as `1000:1000` with Docker `user: "1000:1000"` or `docker run --user 1000:1000`.
- For Kubernetes, set `runAsUser: 1000`, `runAsGroup: 1000`, and `runAsNonRoot: true` together.
- `PUID`/`PGID` keep the default root startup flow.
- Mounted paths must already be writable by `1000:1000`.
- `USING_TOR=true` requires root startup.

## ⚙️ Configuration

### Search Modes

**Direct**
- Queries configured sources directly

**Universal** (recommended)
- Search via metadata providers (Hardcover, Open Library, Google Books) for richer results
- Aggregates releases from multiple configured sources
- Full audiobook support

### Environment Variables

Environment variables work for initial setup and Docker deployments. They serve as defaults that can be overridden in the web interface.

| Variable | Description | Default |
|---|---|---|
| `FLASK_PORT` | Web interface port | `8084` |
| `INGEST_DIR` | Book download directory | `/books` |
| `TZ` | Container timezone | `UTC` |
| `PUID` / `PGID` | Runtime user/group for the default root-startup flow | `1000` / `1000` |
| `SEARCH_MODE` | `direct` or `universal` | `universal` |
| `USING_TOR` | Enable Tor routing (requires root startup) | `false` |

See the full [Environment Variables Reference](docs/environment-variables.md) for all available options.

Some of the additional options available in Settings:
- **Prowlarr** - Configure indexers and download clients to download books and audiobooks
- **Additional audiobook sources** - Configure additional sources for audiobook discovery
- **IRC** - Add details for IRC book sources and download directly from the UI
- **Library Link** - Add a link to your Calibre-Web or Grimmory instance in the UI header
- **File processing** - Customiseable download paths, file renaming and directory creation with template-based renaming
- **Network Settings** - Custom proxy support (SOCKS5 + HTTP/S) and configurable DNS
- **Format & Language** - Filter downloads by preferred formats, languages and sorting order
- **Metadata Providers** - Configure API keys for Hardcover, Open Library, etc.

## 🐳 Docker Variants

### Standard
```bash
docker compose up -d
```

The full-featured image with all network capabilities included.

#### Tor Routing
Optional Tor support for network privacy:
```bash
curl -O https://raw.githubusercontent.com/calibrain/shelfmark/main/compose/docker-compose.tor.yml
docker compose -f docker-compose.tor.yml up -d
```

**Notes:**
- Requires root startup
- Requires `NET_ADMIN` and `NET_RAW` capabilities
- Timezone is auto-detected from Tor exit node
- Custom DNS/proxy settings are ignored when Tor is active

### Lite
A lighter image without the built-in browser automation. Ideal for:

- **External services** - Already running FlareSolverr or similar for other applications
- **Alternative sources** - Using Prowlarr, IRC, or other configured sources
- **Audiobooks** - Using Shelfmark primarily for audiobooks

```bash
curl -O https://raw.githubusercontent.com/calibrain/shelfmark/main/compose/docker-compose.lite.yml
docker compose -f docker-compose.lite.yml up -d
```

If you need browser-based access with the Lite image, configure an external resolver in Settings.

## 🔐 Authentication (upstream)

Authentication is optional but recommended for shared or exposed instances. Multiple authentication methods are available in Settings:

**1. Single Username/Password**

**2. Proxy (Forward) Authentication**

Proxy auth trusts headers set by your reverse proxy (e.g. `X-Auth-User`). Ensure Shelfmark is not directly exposed, and configure your proxy to strip/overwrite these headers for all inbound requests.

**3. OIDC (OpenID Connect)**

Integrate with your identity provider (Authelia, Authentik, Keycloak, etc.) for single sign-on. Supports PKCE flow, auto-discovery, group-based admin mapping, and auto-provisioning of new users.

**4. Calibre-Web Database**

If you're running Calibre-Web, you can reuse its user database by mounting it:

```yaml
volumes:
  - /path/to/calibre-web/app.db:/auth/app.db:ro
```

### Multi-User Support

With any authentication method enabled, Shelfmark supports multi-user management with admin/user roles. Users can have per-user settings for download destinations, email recipients, and notification preferences. Non-admin users only see their own downloads and can submit book requests for admin review. Admins can configure request policies per source to control whether users can download directly, must submit a request, or are blocked entirely.

## Project Scope

Shelfmark is a manual search and download tool, the entry point to your book library, not a library manager. It finds books, downloads them, and sends them to a configured destination. That's the full scope.

Shelfmark intentionally does not:

- **Track or manage your library** - it doesn't know or care what you already own
- **Integrate with library software** - what happens after delivery is up to your library tool
- **Monitor authors, series, or new releases** - there is no background automation
- **Queue future downloads** - if a book isn't available now, Shelfmark won't watch for it

These are non-goals, not missing features.

## Health Monitoring

The application exposes a health endpoint at `/api/health` (no authentication required). Add a health check to your compose:

```yaml
healthcheck:
  test: ["CMD", "curl", "-sf", "http://localhost:8084/api/health"]
  interval: 30s
  timeout: 30s
  retries: 3
```

## Logging

Logs are available via:
- `docker logs <container-name>`
- `/var/log/shelfmark/` inside the container (when `ENABLE_LOGGING=true`)

Log level is configurable via Settings or `LOG_LEVEL` environment variable.

## Development

```bash
# Quality checks
make checks              # Run ALL static analysis (frontend + Python)
make python-checks       # Run Ruff, BasedPyright, and Vulture
make install-python-dev  # Sync Python runtime + dev tools with uv

# Frontend development
make install     # Install dependencies
make dev         # Start Vite dev server (localhost:5173)
make build       # Production build
make frontend-typecheck  # TypeScript checks

# Backend (Docker)
make up          # Start backend via docker-compose.dev.yml
make down        # Stop services
make refresh     # Rebuild and restart
make restart     # Restart container
```

The frontend dev server proxies to the backend on port 8084.

---

# 🚀 Shelfmark Enhanced

> A community fork — all original Shelfmark features are fully preserved. The project scope is unchanged.

## ✨ What's Different

| Feature | Shelfmark (upstream) | Shelfmark Enhanced |
|---|---|---|
| Authentication | Local login, OIDC, proxy auth | **+ SAML2 SSO** (Authentik, Keycloak, Okta, Azure AD) |
| Session management | Basic sessions | Session invalidation, forced re-auth on config change |
| User management | Config file | **Users admin page** — create, edit, disable users in the UI |
| VPN integration | None | **Gluetun status** — live VPN indicator in the header; kill-switch routing via compose overlay |
| Home screen | Plain search bar | **Floating book-cover parallax** animation in the background |
| Library view | Simple download list | **Book shelf grid** with animated 3D open-book detail modal |
| Download visibility | Private only | **Public / Private toggle** per download, persisted per user |
| Code quality | Original structure | Refactored `main.py` and `settings.py`; cleaned module layout |
| Docker image | Build-only | **Pre-built multi-platform image** (amd64 + arm64) published to GHCR |

## 🚀 Quick Start (Enhanced)

### Prerequisites

- Docker & Docker Compose

### Basic install (no VPN)

**`docker-compose.yml`**
```yaml
services:
  shelfmark:
    image: ghcr.io/shelfmark-enhanced/enhanced-shelfmark:latest
    container_name: shelfmark
    environment:
      PUID: 1000
      PGID: 1000
    ports:
      - "6060:8084"
    volumes:
      - /path/to/books:/books
      - /path/to/config:/config
    restart: unless-stopped
```

```bash
docker compose up -d
```

Open `http://localhost:6060` and complete the setup wizard.

### With VPN (Gluetun overlay)

Route all Shelfmark traffic through a VPN using [Gluetun](https://github.com/qdm12/gluetun). The overlay moves the port binding onto the Gluetun container so all outbound traffic is VPN-routed. The header will display a live VPN connected/disconnected pill.

**`docker-compose.yml`** (base — no `ports:` block needed here)
```yaml
services:
  shelfmark:
    image: ghcr.io/shelfmark-enhanced/enhanced-shelfmark:latest
    container_name: shelfmark
    environment:
      PUID: 1000
      PGID: 1000
    volumes:
      - /path/to/books:/books
      - /path/to/config:/config
    restart: unless-stopped
```

**`docker-compose.gluetun.yml`** (overlay — applied on top with `-f`)
```yaml
services:
  gluetun:
    image: qmcgaw/gluetun:latest
    container_name: gluetun
    cap_add:
      - NET_ADMIN
    devices:
      - /dev/net/tun:/dev/net/tun
    ports:
      - "6060:8084"               # Shelfmark UI (port moved here from shelfmark service)
      - "127.0.0.1:8000:8000"    # Gluetun HTTP control API (for VPN status indicator)
    environment:
      VPN_SERVICE_PROVIDER: "${VPN_SERVICE_PROVIDER}"   # e.g. mullvad, nordvpn, expressvpn
      VPN_TYPE: "${VPN_TYPE}"                           # wireguard or openvpn
      WIREGUARD_PRIVATE_KEY: "${WIREGUARD_PRIVATE_KEY}" # WireGuard only
      WIREGUARD_ADDRESSES: "${WIREGUARD_ADDRESSES}"     # WireGuard only
      OPENVPN_USER: "${OPENVPN_USER}"                   # OpenVPN only
      OPENVPN_PASSWORD: "${OPENVPN_PASSWORD}"           # OpenVPN only
      SERVER_COUNTRIES: "${SERVER_COUNTRIES:-}"         # Optional server selection
      HTTP_CONTROL_SERVER_ADDRESS: ":8000"
      HTTP_CONTROL_SERVER_AUTH_DEFAULT_ROLE: >-
        {"routes":[
          {"path":"/v1/publicip/ip","methods":["GET"]},
          {"path":"/v1/vpn/status","methods":["GET"]}
        ]}
    restart: unless-stopped
    volumes:
      - gluetun_data:/gluetun

  shelfmark:
    network_mode: "service:gluetun"
    depends_on:
      - gluetun
    ports: !reset []

volumes:
  gluetun_data:
```

**`.env`** (never commit this file — add it to `.gitignore`)
```env
VPN_SERVICE_PROVIDER=mullvad
VPN_TYPE=wireguard
WIREGUARD_PRIVATE_KEY=your-private-key-here
WIREGUARD_ADDRESSES=10.x.x.x/32
SERVER_COUNTRIES=Netherlands
```

Start with both compose files:
```bash
docker compose -f docker-compose.yml -f docker-compose.gluetun.yml up -d
```

Full Gluetun provider docs and credential setup: https://github.com/qdm12/gluetun/wiki

## 🔐 Authentication (Enhanced)

All upstream authentication methods are available. Shelfmark Enhanced adds:

### SAML2 SSO (Authentik, Keycloak, Okta, Azure AD)

```yaml
auth:
  mode: saml2
  saml2:
    idp_metadata_url: "https://auth.example.com/api/v3/sso/saml/metadata/"
    sp_entity_id: "shelfmark"
    sp_acs_url: "https://shelfmark.example.com/auth/saml/acs"
    attribute_mapping:
      username: "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name"
      email: "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"
```

### OIDC (same as upstream, shown for reference)

```yaml
auth:
  mode: oidc
  oidc:
    issuer_url: "https://auth.example.com/application/o/shelfmark/"
    client_id: "your-client-id"
    client_secret: "your-client-secret"
    redirect_uri: "https://shelfmark.example.com/auth/callback"
```

### Proxy auth

```yaml
auth:
  mode: proxy
  proxy:
    username_header: "Remote-User"
    email_header: "Remote-Email"
```

## 🖼️ Pre-built Docker Images

Images are published to the GitHub Container Registry on every release:

| Tag | Description |
|---|---|
| `latest` | Latest stable release |
| `1.0.0`, `1.0`, `1` | Pinned semantic version (recommended for production) |
| `dev` | Latest build from `production` / `development` branch |

**Full image** (all features including SAML2):
```
ghcr.io/shelfmark-enhanced/enhanced-shelfmark:latest
```

**Lite image** (smaller footprint, no SAML2):
```
ghcr.io/shelfmark-enhanced/enhanced-shelfmark-lite:latest
```

Both images are built for `linux/amd64` and `linux/arm64`.

## 🔧 Building Locally

```bash
git clone https://github.com/shelfmark-enhanced/shelfmarkenhanced.git
cd shelfmarkenhanced

docker compose -f compose/docker-compose.enhanced.yml up --build -d
```

## 🤝 Contributing

Pull requests are welcome. For significant changes please open an issue first to discuss what you'd like to change.

1. Fork the repo
2. Create a feature branch off `development` (`git checkout -b feat/my-feature`)
3. Commit your changes
4. Push and open a PR against `development`

Production releases are merged from `development` → `production` and tagged with a semver version (e.g. `v1.0.0`).

---

# ⚖️ Licence & Legal

### Upstream Shelfmark

MIT License — Copyright (c) 2024 CaliBrain.
See [LICENSE](LICENSE) for the full text.

### Shelfmark Enhanced (this fork)

Also released under the **MIT License** — Copyright (c) 2025 Shelfmark Enhanced Contributors.

**Open source, free to use.** No commercial version of Shelfmark Enhanced exists or is planned. If you encounter anyone selling this software, they are not affiliated with this project.

**Fork attribution.** Shelfmark Enhanced is an independent community project. It is not affiliated with, endorsed by, or supported by CaliBrain or the original Shelfmark project.

**No warranty.** This software is provided "as is", without warranty of any kind. Use it at your own risk.

**Your responsibility.** You are solely responsible for ensuring your use complies with the laws of your jurisdiction and the terms of service of any sources you configure.

---

## ⚠️ Disclaimer

Shelfmark (upstream and Enhanced) is a search interface that displays results from external metadata providers and sources. It does not host, store, or distribute any content. The developers are not responsible for how the tool is used or what is accessed through it.

Users are solely responsible for:
- Ensuring they have the legal right to download any material they access
- Complying with copyright laws and intellectual property rights in their jurisdiction
- Understanding and accepting the terms of any sources they configure

Use of this tool is entirely at your own risk.

---

For upstream Shelfmark support: [github.com/calibrain/shelfmark/issues](https://github.com/calibrain/shelfmark/issues)
