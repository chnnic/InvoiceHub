#!/usr/bin/env bash
set -euo pipefail

. "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/scripts/lib.sh"

INSTALL_DIR="${INSTALL_DIR:-$PWD}"
APP_PORT="${APP_PORT:-18081}"

while [ $# -gt 0 ]; do
  case "$1" in
    --dir|--install-dir)
      INSTALL_DIR="$2"
      shift 2
      ;;
    --dir=*|--install-dir=*)
      INSTALL_DIR="${1#*=}"
      shift
      ;;
    --port)
      APP_PORT="$2"
      shift 2
      ;;
    --port=*)
      APP_PORT="${1#*=}"
      shift
      ;;
    -h|--help)
      cat <<'EOF'
Usage: bash scripts/status.sh [options]
  --dir PATH     Project directory
  --port PORT    App port
EOF
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

cd "$INSTALL_DIR"

echo "Project: $INSTALL_DIR"
echo "Port: ${APP_PORT}"
echo "Version: $(cat VERSION 2>/dev/null || echo unknown)"
echo "GitHub version: $(cat .github-version 2>/dev/null || echo unknown)"
echo

if command -v docker >/dev/null 2>&1; then
  if docker compose version >/dev/null 2>&1 || command -v docker-compose >/dev/null 2>&1; then
    compose_up ps
  else
    echo "Docker Compose not found."
  fi
else
  echo "Docker not found."
fi
