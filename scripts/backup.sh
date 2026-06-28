#!/usr/bin/env bash
set -euo pipefail

. "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/scripts/lib.sh"

INSTALL_DIR="${INSTALL_DIR:-$PWD}"
BACKUP_DIR="${BACKUP_DIR:-$INSTALL_DIR/backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"

while [ $# -gt 0 ]; do
  case "$1" in
    --dir|--install-dir)
      INSTALL_DIR="$2"
      shift 2
      ;;
    --dir=*|--install-dir=*)
      INSTALL_DIR="${1#*=}"
      shift
      ;;
    --backup-dir)
      BACKUP_DIR="$2"
      shift 2
      ;;
    --backup-dir=*)
      BACKUP_DIR="${1#*=}"
      shift
      ;;
    -h|--help)
      cat <<'EOF'
Usage: bash scripts/backup.sh [options]
  --dir PATH         Project directory
  --backup-dir PATH  Output backup directory
EOF
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

cd "$INSTALL_DIR"
mkdir -p "$BACKUP_DIR"

eval "$(load_env_file .env)"

if [ -d media ]; then
  tar -czf "$BACKUP_DIR/media-$STAMP.tar.gz" media
fi

if command -v docker >/dev/null 2>&1; then
  compose_up exec -T db pg_dump -U "${POSTGRES_USER:-invoicehub}" "${POSTGRES_DB:-invoicehub}" > "$BACKUP_DIR/db-$STAMP.sql"
fi

echo "Backup saved to $BACKUP_DIR"
