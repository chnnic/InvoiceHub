#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

. "$ROOT_DIR/scripts/lib.sh"

if ! command -v git >/dev/null 2>&1; then
  echo "git is required." >&2
  exit 1
fi

git pull origin main
git rev-parse --short HEAD > .github-version
compose_up up -d --build
