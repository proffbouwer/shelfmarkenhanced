# Enhanced Shelfmark

A fork of [Shelfmark](https://github.com/calibrain/shelfmark) with extended functionality, UI improvements, and new integrations.

> Docker image: `ghcr.io/proffbouwer/enhanced-shelfmark`

---

## What's different from upstream

- **Refactored architecture** — `main.py` split from 3,323 into focused route modules; `settings.py` split into a per-group package
- **Persistent rate limiting** — login lockouts survive container restarts (SQLite-backed)
- **Dedicated Settings screen** — `/settings/:tab` as a full page route *(in progress)*
- **Gluetun VPN integration** — optional Docker overlay with kill switch *(planned)*
- **Download privacy** — public/private downloads with per-user storage *(planned)*
- **Library screen** — browse and re-deliver completed downloads *(planned)*
- **User management UI** — full CRUD, bulk actions, session management *(planned)*
- **SAML2 SSO** — in addition to existing OIDC support *(planned)*

---

## Quick start

```yaml
# compose/docker-compose.enhanced.yml
services:
  enhanced-shelfmark:
    image: ghcr.io/proffbouwer/enhanced-shelfmark:latest
    container_name: enhanced-shelfmark
    environment:
      PUID: 1000
      PGID: 1000
    ports:
      - 8084:8084
    restart: unless-stopped
    volumes:
      - /path/to/books:/books
      - /path/to/config:/config
```

---

## Development

See [PLAN.md](PLAN.md) for the full implementation checklist and progress.

### Running locally

```bash
# Backend
uv sync
uv run gunicorn ...

# Frontend
cd src/frontend
npm install
npm run dev
```

---

## Upstream

Tracking [calibrain/shelfmark](https://github.com/calibrain/shelfmark). Upstream changes can be merged into the `main` branch and then merged into `development`.
