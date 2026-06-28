#!/usr/bin/env bash
set -euo pipefail

. "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/scripts/lib.sh"

INSTALL_DIR="${INSTALL_DIR:-$PWD}"
BACKUP_DIR="${BACKUP_DIR:-$INSTALL_DIR/backups}"
DB_BACKUP=""
MEDIA_BACKUP=""

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
    --db)
      DB_BACKUP="$2"
      shift 2
      ;;
    --db=*)
      DB_BACKUP="${1#*=}"
      shift
      ;;
    --media)
      MEDIA_BACKUP="$2"
      shift 2
      ;;
    --media=*)
      MEDIA_BACKUP="${1#*=}"
      shift
      ;;
    -h|--help)
      cat <<'EOF'
Usage: bash scripts/restore.sh [options]
  --dir PATH         Project directory
  --backup-dir PATH  Backup directory
  --db FILE          Database sql backup file
  --media FILE       Media tar.gz backup file
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
eval "$(load_env_file .env)"

if [ -z "$DB_BACKUP" ]; then
  DB_BACKUP="$(ls -1t "$BACKUP_DIR"/db-*.sql 2>/dev/null | head -n 1 || true)"
fi
if [ -z "$MEDIA_BACKUP" ]; then
  MEDIA_BACKUP="$(ls -1t "$BACKUP_DIR"/media-*.tar.gz 2>/dev/null | head -n 1 || true)"
fi

if [ -n "$MEDIA_BACKUP" ] && [ -f "$MEDIA_BACKUP" ]; then
  tar -xzf "$MEDIA_BACKUP" -C "$INSTALL_DIR"
fi

if [ -n "$DB_BACKUP" ] && [ -f "$DB_BACKUP" ]; then
  if command -v docker >/dev/null 2>&1; then
    compose_up exec -T db psql -U "${POSTGRES_USER:-invoicehub}" -d "${POSTGRES_DB:-invoicehub}" < "$DB_BACKUP"
  fi
fi

echo "Restore completed."
