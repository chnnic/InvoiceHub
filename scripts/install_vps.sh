#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/chnnic/InvoiceHub.git}"
BRANCH="${BRANCH:-main}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/invoicehub}"
APP_PORT="${APP_PORT:-18081}"

find_free_port() {
  python3 - <<'PY'
import os
import socket

start = int(os.environ.get("APP_PORT", "18081"))
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

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required."
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "git is required."
  exit 1
fi

read -r -p "Install directory [${INSTALL_DIR}]: " INPUT_INSTALL_DIR
INSTALL_DIR="${INPUT_INSTALL_DIR:-$INSTALL_DIR}"

mkdir -p "$(dirname "$INSTALL_DIR")"
if [ ! -d "$INSTALL_DIR/.git" ]; then
  git clone --branch "$BRANCH" --depth 1 "$REPO_URL" "$INSTALL_DIR"
else
  git -C "$INSTALL_DIR" pull origin "$BRANCH"
fi

cd "$INSTALL_DIR"

read -r -p "VPS port [${APP_PORT}]: " INPUT_APP_PORT
APP_PORT="${INPUT_APP_PORT:-$APP_PORT}"
APP_PORT="$(find_free_port)"

read -r -p "Superuser username [admin]: " SUPERUSER_USERNAME
SUPERUSER_USERNAME="${SUPERUSER_USERNAME:-admin}"
read -r -p "Superuser email [admin@example.com]: " SUPERUSER_EMAIL
SUPERUSER_EMAIL="${SUPERUSER_EMAIL:-admin@example.com}"
read -r -s -p "Superuser password (blank = auto-generate): " SUPERUSER_PASSWORD
echo

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

python3 - <<'PY'
from pathlib import Path
import os
import secrets

env_path = Path(".env")
example_path = Path(".env.example")
data = {}

if example_path.exists():
    for line in example_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            data[k] = v

data["SECRET_KEY"] = secrets.token_urlsafe(48)
data["POSTGRES_PASSWORD"] = secrets.token_urlsafe(24)
data["DATABASE_URL"] = f"postgresql://invoicehub:{data['POSTGRES_PASSWORD']}@db:5432/invoicehub"
data["DEBUG"] = "0"
data["ALLOWED_HOSTS"] = "*"
data["CSRF_TRUSTED_ORIGINS"] = ""
data["APP_PORT"] = os.environ["APP_PORT"]
data["SUPERUSER_USERNAME"] = os.environ["SUPERUSER_USERNAME"]
data["SUPERUSER_EMAIL"] = os.environ["SUPERUSER_EMAIL"]
data["SUPERUSER_PASSWORD"] = os.environ["SUPERUSER_PASSWORD"]

env_path.write_text("\n".join(f"{k}={v}" for k, v in data.items()) + "\n")
PY

printf '%s\n' "${GITHUB_VERSION}" > .github-version

docker compose up -d --build
sleep 8
docker compose logs --no-color web --tail=80 || true

echo
echo "Installed."
echo "Open: http://<your-vps-ip>:${APP_PORT}"
echo "Superuser: ${SUPERUSER_USERNAME}"
if [ -n "${AUTO_PASSWORD_NOTE}" ]; then
  echo "Password: ${SUPERUSER_PASSWORD} ${AUTO_PASSWORD_NOTE}"
else
  echo "Password: ${SUPERUSER_PASSWORD}"
fi
