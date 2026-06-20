#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

git pull origin main
if command -v caddy >/dev/null 2>&1 && [ -f /etc/caddy/Caddyfile ]; then
  docker compose -f docker-compose.yml -f docker-compose.host-caddy.yml up -d --build
  if sudo grep -q 'import /etc/caddy/conf.d/\*\.caddy' /etc/caddy/Caddyfile 2>/dev/null; then
    sudo systemctl reload caddy || sudo service caddy reload || sudo caddy reload --config /etc/caddy/Caddyfile || true
  fi
else
  docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d --build
fi
