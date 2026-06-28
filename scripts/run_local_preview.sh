#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

. "$ROOT_DIR/scripts/lib.sh"

APP_PORT="${APP_PORT:-18081}"
while [ $# -gt 0 ]; do
  case "$1" in
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
Usage: bash scripts/run_local_preview.sh [options]
  --port PORT    Local preview port
EOF
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done
APP_PORT="$(find_free_port "$APP_PORT")"

if [ ! -f .env ]; then
  cp .env.example .env
fi

write_env_file .env \
  "DEBUG=1" \
  "ALLOWED_HOSTS=localhost,127.0.0.1" \
  "CSRF_TRUSTED_ORIGINS=http://localhost:${APP_PORT}" \
  "APP_PORT=${APP_PORT}"

if [ -d .venv ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

export DATABASE_URL="${DATABASE_URL:-sqlite:///work/preview.sqlite3}"
python3 manage.py migrate --noinput
python3 manage.py runserver 0.0.0.0:"${APP_PORT}"
