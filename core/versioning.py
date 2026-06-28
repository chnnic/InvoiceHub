from pathlib import Path

from .version import VERSION


def get_git_version():
    root = Path(__file__).resolve().parent.parent
    marker = root / ".github-version"
    if marker.exists():
        value = marker.read_text().strip()
        if value:
            return value
    try:
        import subprocess

        result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root, capture_output=True, text=True, timeout=3, check=True)
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def version_context(request):
    return {
        "local_version": VERSION,
        "github_version": get_git_version(),
    }
