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

deploy_host_caddy() {
  local tries=0
  while [ "${tries}" -lt 10 ]; do
    APP_PORT="$(find_free_port)"
    export APP_PORT
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
path.write_text('\\n'.join(f'{k}={v}' for k, v in data.items()) + '\\n')
PY
    docker compose -f docker-compose.yml -f docker-compose.host-caddy.yml up -d --build && return 0
    docker compose -f docker-compose.yml -f docker-compose.host-caddy.yml down || true
    tries=$((tries + 1))
  done
  echo "Failed to find a free internal port for host Caddy mode."
  exit 1
}

git pull origin main
if command -v caddy >/dev/null 2>&1 && [ -f /etc/caddy/Caddyfile ]; then
  deploy_host_caddy
  if sudo grep -q 'import /etc/caddy/conf.d/\*\.caddy' /etc/caddy/Caddyfile 2>/dev/null; then
    sudo systemctl reload caddy || sudo service caddy reload || sudo caddy reload --config /etc/caddy/Caddyfile || true
  fi
else
  docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d --build
fi
