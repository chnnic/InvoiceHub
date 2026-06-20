#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

find_free_port() {
  python3 - <<'PY'
import socket
for port in range(18081, 28081):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            continue
        print(port)
        raise SystemExit(0)
raise SystemExit("no free port found")
PY
}

git pull origin main
if command -v caddy >/dev/null 2>&1 && [ -f /etc/caddy/Caddyfile ]; then
  APP_PORT=""
  if [ -f .env ]; then
    APP_PORT="$(python3 - <<'PY'
from pathlib import Path
data = {}
for line in Path('.env').read_text().splitlines():
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        data[k] = v
print(data.get('APP_PORT', ''))
PY
)"
  fi
  if [ -z "${APP_PORT}" ]; then
    APP_PORT="$(find_free_port)"
    python3 - <<PY
from pathlib import Path
path = Path('.env')
data = {}
if path.exists():
    for line in path.read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            data[k] = v
data['APP_PORT'] = ${APP_PORT@Q}
path.write_text('\\n'.join(f'{k}={v}' for k,v in data.items()) + '\\n')
PY
  fi
  export APP_PORT
  docker compose -f docker-compose.yml -f docker-compose.host-caddy.yml up -d --build
  if sudo grep -q 'import /etc/caddy/conf.d/\*\.caddy' /etc/caddy/Caddyfile 2>/dev/null; then
    sudo systemctl reload caddy || sudo service caddy reload || sudo caddy reload --config /etc/caddy/Caddyfile || true
  fi
else
  docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d --build
fi
