#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACTION="${1:-help}"
shift || true

case "$ACTION" in
  install)
    exec bash "$ROOT_DIR/scripts/install_vps.sh" "$@"
    ;;
  update)
    exec bash "$ROOT_DIR/scripts/update_from_github.sh" "$@"
    ;;
  deploy)
    exec bash "$ROOT_DIR/scripts/deploy_vps.sh" "$@"
    ;;
  status)
    exec bash "$ROOT_DIR/scripts/status.sh" "$@"
    ;;
  doctor)
    exec bash "$ROOT_DIR/scripts/doctor.sh" "$@"
    ;;
  logs)
    exec bash "$ROOT_DIR/scripts/logs.sh" "$@"
    ;;
  backup)
    exec bash "$ROOT_DIR/scripts/backup.sh" "$@"
    ;;
  restore)
    exec bash "$ROOT_DIR/scripts/restore.sh" "$@"
    ;;
  bump-version|version)
    exec bash "$ROOT_DIR/scripts/bump_version.sh" "$@"
    ;;
  preview)
    exec bash "$ROOT_DIR/scripts/run_local_preview.sh" "$@"
    ;;
  help|-h|--help|"")
    cat <<'EOF'
InvoiceHub command center

Usage:
  bash scripts/ih.sh <command> [options]

Commands:
  install   One-click VPS install
  update    Pull latest code and rebuild
  deploy    Deploy to a VPS-like environment
  status    Show version and container status
  doctor    Check environment health
  logs      Tail container logs
  backup    Backup database and media
  restore   Restore from backup files
  version   Bump patch version or set a specific version
  preview   Start local preview
EOF
    ;;
  *)
    echo "Unknown command: $ACTION" >&2
    exit 1
    ;;
esac
