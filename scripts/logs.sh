#!/usr/bin/env bash
set -euo pipefail

. "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/scripts/lib.sh"

SERVICE="web"
TAIL_LINES=120

while [ $# -gt 0 ]; do
  case "$1" in
    --service)
      SERVICE="$2"
      shift 2
      ;;
    --service=*)
      SERVICE="${1#*=}"
      shift
      ;;
    --tail)
      TAIL_LINES="$2"
      shift 2
      ;;
    --tail=*)
      TAIL_LINES="${1#*=}"
      shift
      ;;
    -h|--help)
      cat <<'EOF'
Usage: bash scripts/logs.sh [options]
  --service NAME   Service name (web/db)
  --tail N         Number of lines to show
EOF
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

compose_up logs --no-color --tail "$TAIL_LINES" "$SERVICE"
