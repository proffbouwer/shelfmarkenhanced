# Contributing to Shelfmark Enhanced

## Branch Structure

| Branch | Purpose | Direct push |
|---|---|---|
| `development` | All active work — features, fixes, experiments | ✅ Yes |
| `production` | Stable, released code only — merged from `development` | ❌ Never |

**The golden rule: `production` is never committed to directly. Everything goes through `development` first.**

---

## Release Workflow

```
feature/fix work
      │
      ▼
 development  ◄── all commits land here first
      │
      │  (validate / UAT on development build)
      │
      ▼
  production  ◄── merge from development only (never direct commits)
      │
      ▼
  vX.Y.Z tag  ◄── triggers Docker image build and GHCR publish
```

### Step by step

**1. Do all work on `development`**
```bash
git checkout development
# make changes, commit as normal
git push origin development
```

**2. Validate on the `dev` image**

The CI builds `ghcr.io/proffbouwer/enhanced-shelfmark:dev` on every push to `development`. Pull and test it before releasing.

**3. Merge to `production` via PR (recommended) or fast-forward merge**
```bash
# Option A — PR (preferred, gives a clean audit trail)
gh pr create --base production --head development --title "Release vX.Y.Z"

# Option B — local merge
git checkout production
git merge --ff-only development
git push origin production
```

**4. Tag the release**
```bash
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

This triggers CI to build and publish:
- `ghcr.io/proffbouwer/enhanced-shelfmark:latest`
- `ghcr.io/proffbouwer/enhanced-shelfmark:X.Y.Z`
- `ghcr.io/proffbouwer/enhanced-shelfmark:X.Y`
- `ghcr.io/proffbouwer/enhanced-shelfmark:X`

---

## Versioning

This project follows [Semantic Versioning](https://semver.org/):

| Change type | Version bump | Example |
|---|---|---|
| Validation fixes, minor tweaks during UAT | patch | `v1.0.0 → v1.0.1` |
| New features, non-breaking changes | minor | `v1.0.1 → v1.1.0` |
| Breaking changes, major rework | major | `v1.x.x → v2.0.0` |

Update `CHANGELOG.md` before tagging each release.

---

## What NOT to do

- ❌ `git push origin production` — direct push to production
- ❌ `git push --force origin development` — rewriting development history
- ❌ Cherry-picking between branches — use merge instead to keep histories in sync
- ❌ Tagging on `development` — tags should always be on `production`
- ❌ Committing `.env` files or credentials

---

## External contributions

1. Fork the repo
2. Create a branch off `development` (`git checkout -b feat/my-feature`)
3. Open a PR targeting `development`
4. Once merged, it will flow to `production` in the next release
