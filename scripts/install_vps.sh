#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/chnnic/InvoiceHub.git}"
BRANCH="${BRANCH:-main}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/invoicehub}"

install_caddy() {
  if command -v caddy >/dev/null 2>&1; then
    echo "Caddy already installed."
    return
  fi

  if command -v apt-get >/dev/null 2>&1; then
    echo "Installing Caddy..."
    sudo apt-get update
    sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
    sudo apt-get update
    sudo apt-get install -y caddy
    return
  fi

  echo "Caddy is not installed and automatic installation is only implemented for apt-based systems."
  exit 1
}

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required."
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "git is required for the one-click installer."
  exit 1
fi

install_caddy

read -r -p "Domain (e.g. invoice.yourdomain.com): " DOMAIN
read -r -p "HTTPS email (optional): " CADDY_EMAIL

if [ -z "${DOMAIN}" ]; then
  echo "Domain is required."
  exit 1
fi

mkdir -p "$(dirname "$INSTALL_DIR")"
if [ ! -d "$INSTALL_DIR/.git" ]; then
  git clone --branch "$BRANCH" --depth 1 "$REPO_URL" "$INSTALL_DIR"
else
  git -C "$INSTALL_DIR" pull origin "$BRANCH"
fi

cd "$INSTALL_DIR"

export DOMAIN CADDY_EMAIL

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
data["DOMAIN"] = os.environ["DOMAIN"]
data["APP_PORT"] = "80"
data["DEBUG"] = "0"

email = os.environ.get("CADDY_EMAIL", "").strip()
if email:
    data["CADDY_EMAIL"] = email

env_path.write_text("\n".join(f"{k}={v}" for k, v in data.items()) + "\n")
PY

docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d --build

sleep 8
docker compose -f docker-compose.yml -f docker-compose.vps.yml logs --no-color web --tail=80 || true

echo
echo "Installed to https://${DOMAIN}"
