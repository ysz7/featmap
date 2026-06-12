from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

# Reference valid map used across tests. References src/parser.py,
# src/validator.py and src/rules.py, which fixtures create on disk.
VALID_MAP = """\
<!-- featmap v1 -->
# Project: demo

Demo project for featmap tests.
Second line of the description.

<!--
Format cheat sheet: the parser ignores comments.
-->

## Layer: Core

Core logic.

### Parser {#parser}

**What:** Parses MAP.md into a data model.
**Files:** `src/parser.py`
**Depends:** —
**Status:** active
**Used by:** <!-- autogen --> [Validator](#validator)

### Validator {#validator}

**What:** Checks format and semantic rules.
**Files:** `src/validator.py`, `src/rules.py:10`
**Depends:** [Parser](#parser)
**Status:** active
"""

VALID_MAP_FILES = ["src/parser.py", "src/validator.py", "src/rules.py"]


def git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )
    return result.stdout


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    git(["init", "-q"], tmp_path)
    git(["config", "user.email", "test@example.com"], tmp_path)
    git(["config", "user.name", "Test"], tmp_path)
    git(["config", "commit.gpgsign", "false"], tmp_path)
    return tmp_path


@pytest.fixture
def valid_repo(git_repo: Path) -> Path:
    """A git repo containing the reference MAP.md and all files it mentions."""
    (git_repo / "MAP.md").write_text(VALID_MAP, encoding="utf-8")
    for rel in VALID_MAP_FILES:
        path = git_repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# stub\n", encoding="utf-8")
    return git_repo
