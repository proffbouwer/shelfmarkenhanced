#!/usr/bin/env bash
# publish_image.sh — tag a release and push to GitHub, triggering GitHub Actions
# to build and publish ghcr.io/proffbouwer/enhanced-shelfmark to GHCR.
#
# Usage:
#   ./publish_image.sh              # prompts for version
#   ./publish_image.sh v1.0.0       # tag and push v1.0.0  → latest + 1.0.0 + 1.0
#   ./publish_image.sh dev          # push current branch  → dev tag only
#   ./publish_image.sh --list       # list existing tags
#   ./publish_image.sh --status     # check GitHub Actions status of latest build

set -euo pipefail

# ── config ────────────────────────────────────────────────────────────────────
REPO="proffbouwer/shelfmarkenhanced"
IMAGE="ghcr.io/proffbouwer/enhanced-shelfmark"
REGISTRY="ghcr.io"
REMOTE="origin"
# ──────────────────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

info()    { echo -e "${CYAN}▸ $*${RESET}"; }
success() { echo -e "${GREEN}✓ $*${RESET}"; }
warn()    { echo -e "${YELLOW}⚠ $*${RESET}"; }
error()   { echo -e "${RED}✗ $*${RESET}" >&2; exit 1; }
header()  { echo -e "\n${BOLD}$*${RESET}"; }

# ── helpers ───────────────────────────────────────────────────────────────────

require() {
  command -v "$1" &>/dev/null || error "'$1' is required but not installed. Install it and retry."
}

check_deps() {
  require git
}

check_gh() {
  command -v gh &>/dev/null
}

current_branch() {
  git rev-parse --abbrev-ref HEAD
}

ensure_clean() {
  if [[ -n "$(git status --porcelain)" ]]; then
    warn "You have uncommitted changes:"
    git status --short
    echo ""
    read -rp "Continue anyway? [y/N] " yn
    [[ "${yn,,}" == "y" ]] || { info "Aborted."; exit 0; }
  fi
}

list_tags() {
  header "Existing release tags:"
  git tag --sort=-version:refname | grep -E '^v[0-9]' | head -20 || echo "  (none yet)"
}

show_status() {
  if ! check_gh; then
    warn "'gh' CLI not installed — cannot query Actions status."
    info "View builds at: https://github.com/${REPO}/actions"
    return
  fi
  header "Latest GitHub Actions runs:"
  gh run list --repo "${REPO}" --workflow "build-and-publish-enhanced.yml" --limit 5
}

push_dev() {
  local branch
  branch=$(current_branch)
  header "Dev push — branch: ${branch}"
  ensure_clean
  info "Pushing branch '${branch}' → triggers 'dev' image tag on GHCR…"
  git push "${REMOTE}" "${branch}"
  success "Pushed. GitHub Actions will build:"
  echo "  ${IMAGE}:dev"
  echo "  ${IMAGE}:sha-$(git rev-parse --short HEAD)"
  echo ""
  info "Track progress: https://github.com/${REPO}/actions"
}

release_tag() {
  local version="$1"

  # Normalise: ensure leading 'v'
  [[ "${version}" == v* ]] || version="v${version}"

  # Validate semver-ish: v1, v1.2, v1.2.3, v1.2.3.4
  if ! [[ "${version}" =~ ^v[0-9]+(\.[0-9]+)*$ ]]; then
    error "Invalid version '${version}'. Use format: v1.0.0"
  fi

  header "Release: ${version}"
  ensure_clean

  # Check tag doesn't already exist
  if git tag | grep -qx "${version}"; then
    error "Tag '${version}' already exists locally. Delete it first: git tag -d ${version}"
  fi

  local branch sha
  branch=$(current_branch)
  sha=$(git rev-parse --short HEAD)

  echo ""
  echo -e "  Branch : ${CYAN}${branch}${RESET}"
  echo -e "  Commit : ${CYAN}${sha}${RESET}"
  echo -e "  Tag    : ${CYAN}${version}${RESET}"
  echo ""
  echo -e "  This will push to GitHub and trigger a build of:"
  echo -e "    ${IMAGE}:latest"
  echo -e "    ${IMAGE}:${version#v}"

  # Derive minor (1.0 from 1.0.0 or 1.0.0.0)
  local ver_no_v="${version#v}"
  local parts
  IFS='.' read -ra parts <<< "${ver_no_v}"
  if [[ ${#parts[@]} -ge 2 ]]; then
    echo -e "    ${IMAGE}:${parts[0]}.${parts[1]}"
  fi
  echo -e "    ${IMAGE}:${parts[0]}"
  echo -e "    ${IMAGE}:sha-${sha}"
  echo -e "    ${IMAGE}-lite:latest  (and same semver tags)"
  echo ""

  read -rp "Proceed? [y/N] " yn
  [[ "${yn,,}" == "y" ]] || { info "Aborted."; exit 0; }

  # Push branch first (in case it's ahead of remote)
  info "Pushing branch '${branch}'…"
  git push "${REMOTE}" "${branch}"

  # Create and push tag
  info "Creating tag '${version}'…"
  git tag "${version}"
  info "Pushing tag '${version}'…"
  git push "${REMOTE}" "${version}"

  success "Tag pushed! GitHub Actions is now building the release."
  echo ""
  echo -e "  ${BOLD}Track progress:${RESET}"
  echo -e "    https://github.com/${REPO}/actions"
  echo ""
  echo -e "  ${BOLD}Image will be available at:${RESET}"
  echo -e "    docker pull ${IMAGE}:latest"
  echo -e "    docker pull ${IMAGE}:${version#v}"
}

interactive_version() {
  header "enhanced-shelfmark — Release Publisher"
  list_tags
  echo ""
  read -rp "Enter version to release (e.g. v1.0.0), or 'dev' to push branch: " input
  [[ -z "${input}" ]] && { info "Aborted."; exit 0; }
  echo ""

  if [[ "${input}" == "dev" ]]; then
    push_dev
  else
    release_tag "${input}"
  fi
}

# ── main ─────────────────────────────────────────────────────────────────────

check_deps

case "${1:-}" in
  --list|-l)
    list_tags
    ;;
  --status|-s)
    show_status
    ;;
  dev)
    push_dev
    ;;
  v*|[0-9]*)
    release_tag "${1}"
    ;;
  "")
    interactive_version
    ;;
  *)
    echo "Usage: $0 [VERSION | dev | --list | --status]"
    echo ""
    echo "  $0               — interactive prompt"
    echo "  $0 v1.0.0        — tag and release v1.0.0"
    echo "  $0 dev           — push branch → builds :dev image"
    echo "  $0 --list        — show existing tags"
    echo "  $0 --status      — show recent GitHub Actions runs (needs gh CLI)"
    exit 1
    ;;
esac
