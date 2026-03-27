#!/usr/bin/env bash
set -euo pipefail

# PlatformForge configuration script
# Checks dependencies, validates the Git repo, and updates all manifests.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLACEHOLDER="YOUR_ORG"

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
RESET='\033[0m'

info()  { echo -e "${GREEN}[✓]${RESET} $1"; }
warn()  { echo -e "${YELLOW}[!]${RESET} $1"; }
error() { echo -e "${RED}[✗]${RESET} $1"; }

# --- Dependency checks ---

echo ""
echo -e "${BOLD}PlatformForge Configuration${RESET}"
echo "=========================================="
echo ""
echo "Checking dependencies..."
echo ""

MISSING=0

for cmd in kubectl helm ansible-playbook git; do
  if command -v "$cmd" &>/dev/null; then
    version=$("$cmd" version --short 2>/dev/null || "$cmd" --version 2>/dev/null | head -1)
    info "$cmd found: $version"
  else
    error "$cmd is not installed"
    MISSING=1
  fi
done

echo ""

if [[ "$MISSING" -eq 1 ]]; then
  error "Missing required dependencies. Please install them and re-run this script."
  exit 1
fi

info "All dependencies satisfied."
echo ""

# --- Check if already configured ---

if ! grep -rq "$PLACEHOLDER" "$SCRIPT_DIR/ansible" "$SCRIPT_DIR/argocd" 2>/dev/null; then
  warn "It looks like YOUR_ORG has already been replaced in this repo."
  read -rp "Do you want to re-configure anyway? (y/N): " RECONF
  if [[ ! "$RECONF" =~ ^[Yy]$ ]]; then
    echo "Exiting."
    exit 0
  fi
fi

# --- Prompt for repo ---

echo "=========================================="
echo ""
echo "Enter your PlatformForge Git repository URL."
echo "This is the repo that Argo CD will watch for changes."
echo ""
echo "Examples:"
echo "  https://github.com/myorg/PlatformForge.git"
echo "  git@github.com:myorg/PlatformForge.git"
echo ""

while true; do
  read -rp "Repository URL: " REPO_URL

  # Trim whitespace
  REPO_URL="$(echo "$REPO_URL" | xargs)"

  if [[ -z "$REPO_URL" ]]; then
    error "Repository URL cannot be empty."
    continue
  fi

  # Validate the repo is reachable
  echo ""
  echo "Verifying repository..."

  if git ls-remote "$REPO_URL" &>/dev/null; then
    info "Repository verified: $REPO_URL"
    break
  else
    error "Could not reach repository: $REPO_URL"
    echo "  Make sure the URL is correct and you have access."
    echo "  If using SSH, ensure your SSH key is configured."
    echo ""
  fi
done

echo ""

# --- Normalize URL for HTTPS references in manifests ---
# Argo CD typically uses HTTPS URLs in Application manifests.
# If user provided SSH URL, derive the HTTPS equivalent for manifests.

if [[ "$REPO_URL" =~ ^git@github\.com:(.+)$ ]]; then
  HTTPS_URL="https://github.com/${BASH_REMATCH[1]}"
  warn "SSH URL detected. Argo CD manifests will use the HTTPS equivalent:"
  echo "  $HTTPS_URL"
  echo ""
  echo "  If your repo is private and you want Argo CD to use SSH,"
  echo "  you can change this later in the argocd/ manifests and"
  echo "  configure an SSH credential secret in Argo CD."
  echo ""
  MANIFEST_URL="$HTTPS_URL"
elif [[ "$REPO_URL" =~ ^https?:// ]]; then
  # Ensure it ends with .git
  if [[ ! "$REPO_URL" =~ \.git$ ]]; then
    MANIFEST_URL="${REPO_URL}.git"
  else
    MANIFEST_URL="$REPO_URL"
  fi
else
  # Non-GitHub URL, use as-is
  MANIFEST_URL="$REPO_URL"
fi

# --- Replace placeholder in all files ---

echo "Updating manifests..."
echo ""

# Build the old pattern to replace
OLD_URL="https://github.com/${PLACEHOLDER}/PlatformForge.git"
FILES_UPDATED=0

while IFS= read -r -d '' file; do
  if grep -q "$OLD_URL" "$file" 2>/dev/null; then
    if [[ "$(uname)" == "Darwin" ]]; then
      sed -i '' "s|${OLD_URL}|${MANIFEST_URL}|g" "$file"
    else
      sed -i "s|${OLD_URL}|${MANIFEST_URL}|g" "$file"
    fi
    info "Updated: ${file#"$SCRIPT_DIR"/}"
    FILES_UPDATED=$((FILES_UPDATED + 1))
  fi
done < <(find "$SCRIPT_DIR" -type f \( -name '*.yml' -o -name '*.yaml' -o -name '*.md' \) -not -path '*/.git/*' -print0)

echo ""

if [[ "$FILES_UPDATED" -eq 0 ]]; then
  warn "No files needed updating (placeholder not found)."
else
  info "$FILES_UPDATED file(s) updated."
fi

# --- Summary ---

echo ""
echo "=========================================="
echo -e "${BOLD}Configuration complete!${RESET}"
echo "=========================================="
echo ""
echo "  Repository: $MANIFEST_URL"
echo ""
echo "  Next step -- run the bootstrap playbook:"
echo ""
echo -e "    ${BOLD}cd ansible && ansible-playbook playbooks/bootstrap.yml${RESET}"
echo ""
echo "  This will:"
echo "    1. Ask which environment model you're using (A or B)"
echo "    2. Discover and verify your kubectl contexts"
echo "    3. Install Argo CD"
echo "    4. Deploy Falco and OPA Gatekeeper Applications"
echo ""
