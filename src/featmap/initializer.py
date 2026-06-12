"""featmap init: create MAP.md, write assistant rules, install the hook.

Every step is idempotent: re-running init never duplicates content.
"""

from __future__ import annotations

import os
import re
import sys
from importlib import resources
from pathlib import Path

RULES_START = "<!-- featmap:rules:start -->"
RULES_END = "<!-- featmap:rules:end -->"

# Files that do not count as "existing code" when deciding whether
# to print the bootstrap prompt.
_NON_CODE_NAMES = {"MAP.md", "AGENTS.md", "CLAUDE.md"}
_NON_CODE_PREFIXES = ("README", "LICENSE", "LICENCE", "CHANGELOG", "CONTRIBUTING", "NOTICE")


def read_template(name: str) -> str:
    return (resources.files("featmap") / "templates" / name).read_text(encoding="utf-8")


def init_project(
    root: Path,
    *,
    hook: bool = False,
    target: str | None = None,
    interactive: bool | None = None,
) -> int:
    """Run all init steps in `root`; returns a process exit code."""
    if interactive is None:
        interactive = sys.stdin.isatty()

    map_path = root / "MAP.md"
    if map_path.exists():
        print("MAP.md already exists, leaving it untouched")
    else:
        map_path.write_text(read_template("MAP.template.md"), encoding="utf-8")
        print("created MAP.md")

    rules_path = root / _choose_rules_file(root, target, interactive)
    status = upsert_rules(rules_path)
    print(f"{status} {rules_path.name}")

    if hook:
        install_hook(root)
    else:
        print("hint: run 'featmap init --hook' to install the pre-commit reminder hook")

    if _has_existing_code(root):
        print()
        print("This project already contains code. Copy the prompt below to your")
        print("AI assistant — it will scan the project and fill in MAP.md:")
        print()
        print("-" * 72)
        print(read_template("bootstrap_prompt.md"), end="")
        print("-" * 72)
    return 0


def _choose_rules_file(root: Path, target: str | None, interactive: bool) -> str:
    if target == "agents":
        return "AGENTS.md"
    if target == "claude":
        return "CLAUDE.md"
    if (root / "AGENTS.md").exists() or not (root / "CLAUDE.md").exists():
        return "AGENTS.md"
    # CLAUDE.md exists and AGENTS.md does not: ask, or default to AGENTS.md.
    if interactive:
        answer = input("Found CLAUDE.md. Write assistant rules to [agents/claude]? ")
        if answer.strip().lower().startswith("c"):
            return "CLAUDE.md"
        return "AGENTS.md"
    print("note: found CLAUDE.md; writing rules to AGENTS.md (override with --target claude)")
    return "AGENTS.md"


def upsert_rules(path: Path) -> str:
    """Create or update the featmap rules block; returns what happened."""
    block = read_template("agents_rules.md").strip("\n")
    if not path.exists():
        path.write_text(block + "\n", encoding="utf-8")
        return "created"
    text = path.read_text(encoding="utf-8")
    has_start, has_end = RULES_START in text, RULES_END in text
    if has_start and has_end:
        pattern = re.compile(re.escape(RULES_START) + r".*?" + re.escape(RULES_END), re.DOTALL)
        new_text = pattern.sub(lambda _: block, text, count=1)
        if new_text == text:
            return "featmap rules already up to date in"
        path.write_text(new_text, encoding="utf-8")
        return "updated featmap rules block in"
    if has_start or has_end:
        raise SystemExit(
            f"featmap: {path.name} contains only one of the featmap rules markers; "
            "fix the file manually"
        )
    path.write_text(text.rstrip("\n") + "\n\n" + block + "\n", encoding="utf-8")
    return "added featmap rules block to"


def install_hook(root: Path) -> None:
    hooks_dir = root / ".git" / "hooks"
    if not hooks_dir.is_dir():
        print("warning: .git/hooks not found, skipping hook install", file=sys.stderr)
        return
    hook_path = hooks_dir / "pre-commit"
    content = read_template("pre-commit")
    if hook_path.exists():
        if hook_path.read_text(encoding="utf-8") == content:
            print("pre-commit hook already installed")
        else:
            print("a pre-commit hook already exists; not overwriting it.")
            print("Add this line to .git/hooks/pre-commit manually:")
            print("  featmap check --staged")
        return
    hook_path.write_text(content, encoding="utf-8")
    hook_path.chmod(hook_path.stat().st_mode | 0o755)
    print("installed .git/hooks/pre-commit")


def _has_existing_code(root: Path) -> bool:
    for _dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in filenames:
            if name.startswith("."):
                continue
            if name in _NON_CODE_NAMES:
                continue
            if name.upper().startswith(_NON_CODE_PREFIXES):
                continue
            return True
    return False
