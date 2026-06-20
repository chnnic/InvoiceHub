#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required."
  exit 1
fi

read -r -p "Domain (e.g. invoice.yourdomain.com): " DOMAIN
read -r -p "Email for HTTPS certs (optional): " CADDY_EMAIL

if [ -z "${DOMAIN}" ]; then
  echo "Domain is required."
  exit 1
fi

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
data['DOMAIN'] = ${DOMAIN@Q}
if ${CADDY_EMAIL@Q}:
    data['CADDY_EMAIL'] = ${CADDY_EMAIL@Q}
path.write_text('\\n'.join(f'{k}={v}' for k,v in data.items()) + '\\n')
PY

docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d --build
echo "Deployed to https://${DOMAIN}"
