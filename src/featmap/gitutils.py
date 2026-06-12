"""Thin git wrappers via subprocess; no third-party git libraries."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

_RE_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)


def _git(args: list[str], cwd: Path | None = None) -> str | None:
    """Run git and return stdout, or None when git is missing or the call fails."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def repo_root(cwd: Path | None = None) -> Path | None:
    out = _git(["rev-parse", "--show-toplevel"], cwd=cwd)
    if out is None:
        return None
    path = out.strip()
    return Path(path) if path else None


def staged_files(root: Path) -> list[str]:
    """Paths (relative to the repo root) of files staged for commit."""
    out = _git(["diff", "--cached", "--name-only"], cwd=root)
    if out is None:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def staged_changed_lines(root: Path, relpath: str) -> list[tuple[int, int]]:
    """Inclusive (start, end) line ranges changed in the staged version of relpath."""
    out = _git(["diff", "--cached", "-U0", "--", relpath], cwd=root)
    if not out:
        return []
    ranges: list[tuple[int, int]] = []
    for match in _RE_HUNK.finditer(out):
        start = int(match.group(1))
        count = int(match.group(2)) if match.group(2) is not None else 1
        if count == 0:
            # Pure deletion: it touches the boundary between start and start+1.
            ranges.append((max(start, 1), start + 1))
        else:
            ranges.append((start, start + count - 1))
    return ranges
