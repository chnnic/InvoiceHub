#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required."
  exit 1
fi

read -r -p "VPS port [10081]: " APP_PORT
APP_PORT="${APP_PORT:-10081}"
find_free_port() {
  python3 - <<'PY'
import os
import socket

start = int(os.environ.get("APP_PORT", "10081"))
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
APP_PORT="$(find_free_port)"
read -r -p "Superuser username [admin]: " SUPERUSER_USERNAME
SUPERUSER_USERNAME="${SUPERUSER_USERNAME:-admin}"
read -r -p "Superuser email [admin@example.com]: " SUPERUSER_EMAIL
SUPERUSER_EMAIL="${SUPERUSER_EMAIL:-admin@example.com}"

if [ ! -f .env ]; then
  cp .env.example .env
fi

export APP_PORT SUPERUSER_USERNAME SUPERUSER_EMAIL

python3 - <<'PY'
from pathlib import Path
import os
path = Path('.env')
lines = path.read_text().splitlines()
data = {}
for line in lines:
    if '=' in line and not line.startswith('#'):
        k,v = line.split('=',1)
        data[k]=v
data['APP_PORT'] = os.environ['APP_PORT']
data['ALLOWED_HOSTS'] = '*'
data['SUPERUSER_USERNAME'] = os.environ['SUPERUSER_USERNAME']
data['SUPERUSER_EMAIL'] = os.environ['SUPERUSER_EMAIL']
path.write_text('\n'.join(f'{k}={v}' for k,v in data.items()) + '\n')
PY

docker compose up -d --build
echo "Deployed to http://<your-vps-ip>:${APP_PORT}"
