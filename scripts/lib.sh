#!/usr/bin/env bash
set -euo pipefail

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

ensure_env_value() {
  local key="$1"
  local value="$2"
  local file="${3:-.env}"
  python3 - "$key" "$value" "$file" <<'PY'
from pathlib import Path
import sys

key, value, file = sys.argv[1:4]
path = Path(file)
data = {}
if path.exists():
    for line in path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            data[k] = v
data[key] = value
path.write_text("\n".join(f"{k}={v}" for k, v in data.items()) + "\n")
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

load_env_file() {
  local file="${1:-.env}"
  python3 - "$file" <<'PY'
from pathlib import Path
import shlex
import sys

path = Path(sys.argv[1])
if not path.exists():
    raise SystemExit(0)

for line in path.read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        print(f"export {k}={shlex.quote(v)}")
PY
}
