# 📚 Shelfmark Enhanced

> A community fork of [Shelfmark](https://github.com/calibrain/shelfmark) by CaliBrain.

Shelfmark Enhanced is a self-hosted book and audiobook search tool that builds on the original Shelfmark project with additional authentication options, UI improvements, VPN integration, and several quality-of-life features. It is fully open source, free to use, and no commercial version exists.

---

## ✨ What's Different from Upstream Shelfmark

| Feature | Shelfmark (upstream) | Shelfmark Enhanced |
|---|---|---|
| Authentication | Local login, OIDC, proxy auth | **+ SAML2 SSO** (e.g. Authentik, Keycloak) |
| Session management | Basic sessions | Session invalidation, forced re-auth |
| User management | Config file | **Users admin page** — create, edit, disable users in the UI |
| VPN integration | None | **Gluetun status** — live VPN pill in the header; automatic kill-switch routing |
| Home screen | Plain search bar | **Floating book-cover parallax** animation in the background |
| Library view | Simple download list | **Book shelf grid** with animated 3D open-book detail modal |
| Download visibility | Private only | **Public / Private toggle** per download, persisted per user |
| Code quality | Original structure | Refactored `main.py` and `settings.py`; cleaned module layout |
| Docker image | Build-only | **Pre-built multi-platform image** (amd64 + arm64) on GHCR |

All original Shelfmark features are preserved — sources, metadata providers, request system, download queue, Calibre-Web integration, audiobooks, etc.

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose

### Basic install (no VPN)

1. Create a `docker-compose.yml`:

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

2. Start it:

```bash
docker compose up -d
```

3. Open `http://localhost:6060` and complete the setup wizard.

---

### With VPN (Gluetun overlay)

Route all Shelfmark traffic through a VPN using [Gluetun](https://github.com/qdm12/gluetun).

**`docker-compose.yml`**
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
      - "6060:8084"          # Shelfmark UI (port moved here from shelfmark service)
      - "127.0.0.1:8000:8000" # Gluetun HTTP control API (for VPN status)
    environment:
      VPN_SERVICE_PROVIDER: "${VPN_SERVICE_PROVIDER}"   # e.g. mullvad, nordvpn
      VPN_TYPE: "${VPN_TYPE}"                           # wireguard or openvpn
      WIREGUARD_PRIVATE_KEY: "${WIREGUARD_PRIVATE_KEY}" # WireGuard only
      WIREGUARD_ADDRESSES: "${WIREGUARD_ADDRESSES}"     # WireGuard only
      OPENVPN_USER: "${OPENVPN_USER}"                   # OpenVPN only
      OPENVPN_PASSWORD: "${OPENVPN_PASSWORD}"           # OpenVPN only
      SERVER_COUNTRIES: "${SERVER_COUNTRIES:-}"
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

**.env** (never commit this file)
```env
VPN_SERVICE_PROVIDER=mullvad
VPN_TYPE=wireguard
WIREGUARD_PRIVATE_KEY=your-private-key-here
WIREGUARD_ADDRESSES=10.x.x.x/32
SERVER_COUNTRIES=Netherlands
```

Start with both files:
```bash
docker compose -f docker-compose.yml -f docker-compose.gluetun.yml up -d
```

Full Gluetun provider docs: https://github.com/qdm12/gluetun/wiki

---

## 🔐 Authentication Options

Shelfmark Enhanced supports multiple authentication methods, configured in the UI or `config/settings.yml`.

### Local login (default)
No extra config needed — create users through the Users admin page after first run.

### OIDC (e.g. Authentik, Keycloak, Auth0)
```yaml
auth:
  mode: oidc
  oidc:
    issuer_url: "https://auth.example.com/application/o/shelfmark/"
    client_id: "your-client-id"
    client_secret: "your-client-secret"
    redirect_uri: "https://shelfmark.example.com/auth/callback"
```

### SAML2 SSO (e.g. Authentik, Okta, Azure AD)
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

### Proxy auth (e.g. Authelia, Traefik Forward Auth)
```yaml
auth:
  mode: proxy
  proxy:
    username_header: "Remote-User"
    email_header: "Remote-Email"
```

---

## 🖼️ Pre-built Docker Images

Images are published to the GitHub Container Registry on every release:

| Tag | Description |
|---|---|
| `latest` | Latest stable release |
| `1.0.0`, `1.0`, `1` | Pinned semantic version |
| `dev` | Latest build from the `production` / `development` branch |

**Full image** (includes all features including SAML2):
```
ghcr.io/shelfmark-enhanced/enhanced-shelfmark:latest
```

**Lite image** (smaller footprint, no SAML2):
```
ghcr.io/shelfmark-enhanced/enhanced-shelfmark-lite:latest
```

Images are built for `linux/amd64` and `linux/arm64`.

---

## 🔧 Building Locally

```bash
git clone https://github.com/shelfmark-enhanced/shelfmarkenhanced.git
cd shelfmarkenhanced

# Build and run
docker compose -f compose/docker-compose.enhanced.yml up --build -d
```

---

## 📖 Original Shelfmark

This project is a fork of **Shelfmark** by [CaliBrain](https://github.com/calibrain/shelfmark). All core functionality — source plugins, metadata providers, the request system, download queue, Calibre-Web integration — originates from the upstream project and is maintained under the original MIT licence.

Please also consider ⭐ starring the [original repository](https://github.com/calibrain/shelfmark).

---

## ⚖️ Licence & Legal

### Fork attribution

Shelfmark Enhanced is a community fork. It is **not affiliated with, endorsed by, or supported by** the original Shelfmark project or CaliBrain.

### Open source — free to use

This software is released under the **MIT Licence** (see [`LICENSE`](LICENSE)). You are free to use, copy, modify, merge, publish, distribute, and sublicense it for any purpose, including personal and commercial use, subject to the licence terms.

**No commercial version of Shelfmark Enhanced exists.** There is no paid tier, no premium plan, and no company behind this fork. If you encounter anyone selling this software, they are not affiliated with this project.

### No warranty

This software is provided "as is", without warranty of any kind. Use it at your own risk. The authors are not responsible for any data loss, legal issues arising from your use of configured sources, or any other damages.

### Your responsibility

Shelfmark Enhanced is a tool that helps you download books from sources you configure. You are solely responsible for ensuring that your use complies with the laws of your jurisdiction and the terms of service of any sources you connect.

---

## 🤝 Contributing

Pull requests are welcome. For significant changes please open an issue first to discuss what you'd like to change.

1. Fork the repo
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Commit your changes
4. Push and open a PR against `development`

Production releases are merged from `development` → `production` and tagged with a semver version.
