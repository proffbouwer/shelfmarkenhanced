# Security Policy

## Supported Versions

Only the latest release of Shelfmark Enhanced receives security fixes.

| Version | Supported |
|---|---|
| Latest (`production` branch) | ✅ |
| Older releases | ❌ |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.** A public issue exposes the flaw to everyone before it can be fixed.

Instead, use one of the following:

### Option 1 — GitHub Private Vulnerability Reporting (preferred)

GitHub has a built-in private disclosure flow:

1. Go to the **Security** tab of this repository
2. Click **"Report a vulnerability"**
3. Fill in the details — this is only visible to repository maintainers

### Option 2 — What to include

Whether you use GitHub's private reporting or another channel, please include as much of the following as possible:

- **Description** of the vulnerability and its potential impact
- **Steps to reproduce** — the more specific the better
- **Affected version(s)** — Docker image tag or git commit
- **Proof of concept** — code, screenshots, or a description of the exploit
- **Suggested fix** — if you have one

## What to Expect

- **Acknowledgement** within 3–5 days
- **Assessment** of severity and impact
- **Fix and release** — timeline depends on severity; critical issues are prioritised
- **Credit** — reporters will be credited in the release notes unless they prefer to remain anonymous

## Scope

The following are **in scope**:

- Authentication bypass or privilege escalation
- Remote code execution
- Sensitive data exposure (credentials, API keys, user data)
- Server-side request forgery (SSRF)
- Injection vulnerabilities (SQL, command, etc.)

The following are **out of scope**:

- Vulnerabilities in third-party services or sources you have configured
- Issues requiring physical access to the host machine
- Denial of service via resource exhaustion (unless trivially exploitable)
- Missing security headers on self-hosted instances (user's responsibility to configure reverse proxy)

## Disclaimer

Shelfmark Enhanced is a community project maintained in spare time. There is no SLA or guaranteed response time. We will do our best to address reported issues promptly.
