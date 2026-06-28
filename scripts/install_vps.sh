#!/usr/bin/env bash
set -euo pipefail

# This installer is intentionally self-contained because the documented
# one-line install runs it directly from GitHub raw before the repository
# exists on the VPS.
compose_up() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
    return 0
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
    return 0
  fi
  echo "Docker Compose is required but was not found." >&2
  return 1
}

find_free_port() {
  local start="${1:-${APP_PORT:-18081}}"
  python3 - "$start" <<'PY'
import socket
import sys

start = int(sys.argv[1])
for port in [start, *range(start + 1, start + 1000)]:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", port))
        except OSError:
            continue
        print(port)
        raise SystemExit(0)
raise SystemExit("no free port found")
PY
}

write_env_file() {
  local file="${1:-.env}"
  shift || true
  python3 - "$file" "$@" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
updates = {}
for item in sys.argv[2:]:
    if "=" not in item:
        raise SystemExit(f"invalid env pair: {item}")
    k, v = item.split("=", 1)
    updates[k] = v

data = {}
if path.exists():
    for line in path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            data[k] = v

data.update(updates)
path.write_text("\n".join(f"{k}={v}" for k, v in data.items()) + "\n")
PY
}

read_env_value() {
  local key="$1"
  local file="${2:-.env}"
  python3 - "$key" "$file" <<'PY'
from pathlib import Path
import sys

key, file = sys.argv[1:3]
path = Path(file)
if not path.exists():
    raise SystemExit(0)
for line in path.read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        if k == key:
            print(v)
            break
PY
}

prompt_input() {
  local prompt="$1"
  local default_value="${2:-}"
  local var_name="$3"
  local value=""
  if [ -t 0 ]; then
    if [ -n "$default_value" ]; then
      read -r -p "${prompt} [${default_value}]: " value
      value="${value:-$default_value}"
    else
      read -r -p "${prompt}: " value
    fi
  else
    value="$default_value"
  fi
  printf -v "$var_name" '%s' "$value"
}

prompt_secret() {
  local prompt="$1"
  local var_name="$2"
  local value=""
  if [ -t 0 ]; then
    read -r -s -p "${prompt}: " value
    echo
  fi
  printf -v "$var_name" '%s' "$value"
}

REPO_URL="${REPO_URL:-https://github.com/chnnic/InvoiceHub.git}"
BRANCH="${BRANCH:-main}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/invoicehub}"
APP_PORT="${APP_PORT:-18081}"
SUPERUSER_USERNAME="${SUPERUSER_USERNAME:-admin}"
SUPERUSER_EMAIL="${SUPERUSER_EMAIL:-admin@example.com}"
SUPERUSER_PASSWORD="${SUPERUSER_PASSWORD:-}"
NON_INTERACTIVE="${NON_INTERACTIVE:-0}"
APP_PORT_PROVIDED=0
SUPERUSER_PASSWORD_PROVIDED=0

while [ $# -gt 0 ]; do
  case "$1" in
    --repo)
      REPO_URL="$2"
      shift 2
      ;;
    --repo=*)
      REPO_URL="${1#*=}"
      shift
      ;;
    --branch)
      BRANCH="$2"
      shift 2
      ;;
    --branch=*)
      BRANCH="${1#*=}"
      shift
      ;;
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
      APP_PORT_PROVIDED=1
      shift 2
      ;;
    --port=*)
      APP_PORT="${1#*=}"
      APP_PORT_PROVIDED=1
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
    --password)
      SUPERUSER_PASSWORD="$2"
      SUPERUSER_PASSWORD_PROVIDED=1
      shift 2
      ;;
    --password=*)
      SUPERUSER_PASSWORD="${1#*=}"
      SUPERUSER_PASSWORD_PROVIDED=1
      shift
      ;;
    --non-interactive|--yes)
      NON_INTERACTIVE=1
      shift
      ;;
    -h|--help)
      cat <<'EOF'
Usage: bash scripts/install_vps.sh [options]
  --repo URL          GitHub repo URL
  --branch NAME       Git branch to install
  --dir PATH          Install directory
  --port PORT         App port
  --username NAME     Superuser username
  --email EMAIL       Superuser email
  --password PASS     Superuser password
  --non-interactive    Skip prompts and use provided/default values
EOF
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required."
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "git is required."
  exit 1
fi

mkdir -p "$(dirname "$INSTALL_DIR")"
if [ "$NON_INTERACTIVE" = "0" ]; then
  prompt_input "Install directory" "$INSTALL_DIR" INSTALL_DIR
fi

if [ ! -d "$INSTALL_DIR/.git" ]; then
  git clone --branch "$BRANCH" --depth 1 "$REPO_URL" "$INSTALL_DIR"
else
  git -C "$INSTALL_DIR" pull origin "$BRANCH"
fi

cd "$INSTALL_DIR"

if [ "$NON_INTERACTIVE" = "0" ]; then
  prompt_input "VPS port" "$APP_PORT" APP_PORT
  prompt_input "Superuser username" "$SUPERUSER_USERNAME" SUPERUSER_USERNAME
  prompt_input "Superuser email" "$SUPERUSER_EMAIL" SUPERUSER_EMAIL
  prompt_secret "Superuser password (blank = auto-generate)" SUPERUSER_PASSWORD
  if [ -n "$SUPERUSER_PASSWORD" ]; then
    SUPERUSER_PASSWORD_PROVIDED=1
  fi
fi

if [ "$APP_PORT_PROVIDED" = "0" ]; then
  EXISTING_APP_PORT="$(read_env_value APP_PORT .env)"
  if [ -n "$EXISTING_APP_PORT" ]; then
    APP_PORT="$EXISTING_APP_PORT"
  fi
fi
APP_PORT="$(find_free_port "$APP_PORT")"

if [ -z "${SUPERUSER_PASSWORD}" ] && [ "$SUPERUSER_PASSWORD_PROVIDED" = "0" ]; then
  SUPERUSER_PASSWORD="$(read_env_value SUPERUSER_PASSWORD .env)"
fi

if [ -z "${SUPERUSER_PASSWORD}" ]; then
  SUPERUSER_PASSWORD="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(16))
PY
)"
  AUTO_PASSWORD_NOTE="(auto-generated)"
else
  AUTO_PASSWORD_NOTE=""
fi

export APP_PORT SUPERUSER_USERNAME SUPERUSER_EMAIL SUPERUSER_PASSWORD
GITHUB_VERSION="$(git -C "$INSTALL_DIR" rev-parse --short HEAD)"
export GITHUB_VERSION

SECRET_KEY="$(read_env_value SECRET_KEY .env)"
if [ -z "$SECRET_KEY" ]; then
  SECRET_KEY="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
)"
fi

POSTGRES_PASSWORD="$(read_env_value POSTGRES_PASSWORD .env)"
if [ -z "$POSTGRES_PASSWORD" ]; then
  POSTGRES_PASSWORD="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(24))
PY
)"
fi

write_env_file .env \
  "SECRET_KEY=${SECRET_KEY}" \
  "DEBUG=0" \
  "ALLOWED_HOSTS=*" \
  "CSRF_TRUSTED_ORIGINS=" \
  "POSTGRES_DB=invoicehub" \
  "POSTGRES_USER=invoicehub" \
  "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}" \
  "DATABASE_URL=postgresql://invoicehub:${POSTGRES_PASSWORD}@db:5432/invoicehub" \
  "APP_PORT=${APP_PORT}" \
  "SUPERUSER_USERNAME=${SUPERUSER_USERNAME}" \
  "SUPERUSER_EMAIL=${SUPERUSER_EMAIL}" \
  "SUPERUSER_PASSWORD=${SUPERUSER_PASSWORD}"

printf '%s\n' "${GITHUB_VERSION}" > .github-version

compose_up up -d --build
sleep 8
compose_up logs --no-color web --tail=80 || true

FINAL_PASSWORD="${SUPERUSER_PASSWORD}"
if grep -q '^SUPERUSER_PASSWORD=$' .env 2>/dev/null; then
  FINAL_PASSWORD="(auto-generated in container logs)"
fi

echo
echo "Installed."
echo "Open: http://<your-vps-ip>:${APP_PORT}"
echo "Superuser: ${SUPERUSER_USERNAME}"
echo "Password: ${FINAL_PASSWORD} ${AUTO_PASSWORD_NOTE}"
