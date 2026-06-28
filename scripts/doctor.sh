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
Usage: bash scripts/doctor.sh [options]
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
eval "$(load_env_file .env)"

echo "InvoiceHub doctor"
echo "Project: $INSTALL_DIR"
echo "Port: ${APP_PORT}"
echo

check_item() {
  local label="$1"
  shift
  if "$@"; then
    printf '[OK] %s\n' "$label"
  else
    printf '[FAIL] %s\n' "$label"
  fi
}

check_item "Docker" command -v docker >/dev/null 2>&1
check_item "Git" command -v git >/dev/null 2>&1

if command -v docker >/dev/null 2>&1; then
  check_item "Docker daemon" docker info >/dev/null 2>&1
  if docker compose version >/dev/null 2>&1 || command -v docker-compose >/dev/null 2>&1; then
    echo "[OK] Docker Compose"
  else
    echo "[FAIL] Docker Compose"
  fi
fi

check_item ".env" test -f .env
check_item "VERSION" test -f VERSION

if [ -n "${DATABASE_URL:-}" ]; then
  echo "[OK] DATABASE_URL set"
else
  echo "[WARN] DATABASE_URL missing"
fi

if [ -n "${APP_PORT:-}" ]; then
  echo "[OK] APP_PORT=${APP_PORT}"
else
  echo "[WARN] APP_PORT missing"
fi

if [ -f .github-version ]; then
  echo "[OK] GitHub version marker: $(cat .github-version)"
else
  echo "[WARN] .github-version missing"
fi

if command -v docker >/dev/null 2>&1 && (docker compose version >/dev/null 2>&1 || command -v docker-compose >/dev/null 2>&1); then
  echo
  compose_up ps || true
fi
