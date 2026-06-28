#!/usr/bin/env bash
set -euo pipefail

. "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/scripts/lib.sh"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required."
  exit 1
fi

APP_PORT="${APP_PORT:-18081}"
SUPERUSER_USERNAME="${SUPERUSER_USERNAME:-admin}"
SUPERUSER_EMAIL="${SUPERUSER_EMAIL:-admin@example.com}"
NON_INTERACTIVE="${NON_INTERACTIVE:-0}"

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
    --username)
      SUPERUSER_USERNAME="$2"
      shift 2
      ;;
    --username=*)
      SUPERUSER_USERNAME="${1#*=}"
      shift
      ;;
    --email)
      SUPERUSER_EMAIL="$2"
      shift 2
      ;;
    --email=*)
      SUPERUSER_EMAIL="${1#*=}"
      shift
      ;;
    --non-interactive|--yes)
      NON_INTERACTIVE=1
      shift
      ;;
    -h|--help)
      cat <<'EOF'
Usage: bash scripts/deploy_vps.sh [options]
  --port PORT         App port
  --username NAME     Superuser username
  --email EMAIL       Superuser email
  --non-interactive   Skip prompts and use provided/default values
EOF
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [ "$NON_INTERACTIVE" = "0" ]; then
  prompt_input "VPS port" "$APP_PORT" APP_PORT
  prompt_input "Superuser username" "$SUPERUSER_USERNAME" SUPERUSER_USERNAME
  prompt_input "Superuser email" "$SUPERUSER_EMAIL" SUPERUSER_EMAIL
fi

APP_PORT="$(find_free_port "$APP_PORT")"

if [ ! -f .env ]; then
  cp .env.example .env
fi

export APP_PORT SUPERUSER_USERNAME SUPERUSER_EMAIL
write_env_file .env \
  "APP_PORT=${APP_PORT}" \
  "ALLOWED_HOSTS=*" \
  "SUPERUSER_USERNAME=${SUPERUSER_USERNAME}" \
  "SUPERUSER_EMAIL=${SUPERUSER_EMAIL}"

compose_up up -d --build
echo "Deployed to http://<your-vps-ip>:${APP_PORT}"
