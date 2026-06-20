#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required."
  exit 1
fi

read -r -p "VPS port [10081]: " APP_PORT
APP_PORT="${APP_PORT:-10081}"
read -r -p "Superuser username [admin]: " SUPERUSER_USERNAME
SUPERUSER_USERNAME="${SUPERUSER_USERNAME:-admin}"
read -r -p "Superuser email [admin@example.com]: " SUPERUSER_EMAIL
SUPERUSER_EMAIL="${SUPERUSER_EMAIL:-admin@example.com}"

if [ ! -f .env ]; then
  cp .env.example .env
fi

python3 - <<PY
from pathlib import Path
path = Path('.env')
lines = path.read_text().splitlines()
data = {}
for line in lines:
    if '=' in line and not line.startswith('#'):
        k,v = line.split('=',1)
        data[k]=v
data['APP_PORT'] = ${APP_PORT@Q}
data['ALLOWED_HOSTS'] = '*'
data['SUPERUSER_USERNAME'] = ${SUPERUSER_USERNAME@Q}
data['SUPERUSER_EMAIL'] = ${SUPERUSER_EMAIL@Q}
path.write_text('\\n'.join(f'{k}={v}' for k,v in data.items()) + '\\n')
PY

docker compose up -d --build
echo "Deployed to http://<your-vps-ip>:${APP_PORT}"
