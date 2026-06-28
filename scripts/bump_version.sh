#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION_FILE="$ROOT_DIR/VERSION"

if [ ! -f "$VERSION_FILE" ]; then
  echo "VERSION file not found: $VERSION_FILE" >&2
  exit 1
fi

CURRENT_VERSION="$(tr -d '[:space:]' < "$VERSION_FILE")"

if [ $# -gt 0 ]; then
  NEW_VERSION="$1"
else
  NEW_VERSION="$(python3 - "$CURRENT_VERSION" <<'PY'
import re
import sys

version = sys.argv[1]
match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
if not match:
    raise SystemExit(f"Unsupported version format: {version}")
major, minor, patch = map(int, match.groups())
print(f"{major}.{minor}.{patch + 1}")
PY
)"
fi

python3 - "$NEW_VERSION" "$VERSION_FILE" <<'PY'
from pathlib import Path
import re
import sys

new_version = sys.argv[1]
version_file = Path(sys.argv[2])
if not re.fullmatch(r"\d+\.\d+\.\d+", new_version):
    raise SystemExit(f"Unsupported version format: {new_version}")
version_file.write_text(new_version + "\n")
print(new_version)
PY
