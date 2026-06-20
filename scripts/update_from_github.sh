#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

git pull origin main
docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d --build
