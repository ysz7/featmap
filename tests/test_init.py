from __future__ import annotations

import os
from pathlib import Path

from featmap.initializer import RULES_END, RULES_START, init_project, read_template
from featmap.parser import parse


def run_init(root: Path, **kwargs):
    kwargs.setdefault("interactive", False)
    return init_project(root, **kwargs)


def test_init_creates_map_and_agents(git_repo: Path, capsys):
    assert run_init(git_repo) == 0
    out = capsys.readouterr().out
    assert "created MAP.md" in out
    assert "AGENTS.md" in out

    map_text = (git_repo / "MAP.md").read_text(encoding="utf-8")
    result = parse(map_text)
    assert not any(v.is_error for v in result.violations)

    agents = (git_repo / "AGENTS.md").read_text(encoding="utf-8")
    assert RULES_START in agents and RULES_END in agents
    assert "Read first" in agents


def test_init_is_idempotent(git_repo: Path, capsys):
    run_init(git_repo)
    before = {
        name: (git_repo / name).read_text(encoding="utf-8") for name in ("MAP.md", "AGENTS.md")
    }
    capsys.readouterr()
    assert run_init(git_repo) == 0
    after = {
        name: (git_repo / name).read_text(encoding="utf-8") for name in ("MAP.md", "AGENTS.md")
    }
    assert before == after


def test_init_appends_block_to_existing_agents(git_repo: Path):
    (git_repo / "AGENTS.md").write_text("# My rules\n\nBe nice.\n", encoding="utf-8")
    run_init(git_repo)
    agents = (git_repo / "AGENTS.md").read_text(encoding="utf-8")
    assert agents.startswith("# My rules")
    assert "Be nice." in agents
    assert agents.count(RULES_START) == 1
    run_init(git_repo)
    agents_again = (git_repo / "AGENTS.md").read_text(encoding="utf-8")
    assert agents_again == agents


def test_init_replaces_stale_block(git_repo: Path):
    (git_repo / "AGENTS.md").write_text(
        f"intro\n\n{RULES_START}\nold rules\n{RULES_END}\n\noutro\n", encoding="utf-8"
    )
    run_init(git_repo)
    agents = (git_repo / "AGENTS.md").read_text(encoding="utf-8")
    assert "old rules" not in agents
    assert "Read first" in agents
    assert agents.startswith("intro")
    assert agents.rstrip().endswith("outro")


def test_init_prefers_agents_when_claude_exists(git_repo: Path, capsys):
    (git_repo / "CLAUDE.md").write_text("# Claude notes\n", encoding="utf-8")
    run_init(git_repo)
    assert (git_repo / "AGENTS.md").exists()
    assert RULES_START not in (git_repo / "CLAUDE.md").read_text(encoding="utf-8")
    assert "--target claude" in capsys.readouterr().out


def test_init_target_claude(git_repo: Path):
    (git_repo / "CLAUDE.md").write_text("# Claude notes\n", encoding="utf-8")
    run_init(git_repo, target="claude")
    assert not (git_repo / "AGENTS.md").exists()
    claude = (git_repo / "CLAUDE.md").read_text(encoding="utf-8")
    assert claude.startswith("# Claude notes")
    assert RULES_START in claude


def test_init_prints_bootstrap_prompt_for_existing_code(git_repo: Path, capsys):
    (git_repo / "src").mkdir()
    (git_repo / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    run_init(git_repo)
    out = capsys.readouterr().out
    assert "Просканируй этот проект" in out
    assert "<!-- featmap v1 -->" in out


def test_init_no_bootstrap_prompt_in_empty_repo(git_repo: Path, capsys):
    (git_repo / "README.md").write_text("# x\n", encoding="utf-8")
    run_init(git_repo)
    assert "Просканируй" not in capsys.readouterr().out


def test_init_hook_installs_pre_commit(git_repo: Path, capsys):
    run_init(git_repo, hook=True)
    hook = git_repo / ".git" / "hooks" / "pre-commit"
    assert hook.is_file()
    assert os.access(hook, os.X_OK)
    content = hook.read_text(encoding="utf-8")
    assert content == read_template("pre-commit")
    assert "featmap check --staged" in content
    # Re-running must not complain about the existing identical hook.
    capsys.readouterr()
    run_init(git_repo, hook=True)
    assert "already installed" in capsys.readouterr().out


def test_init_hook_keeps_foreign_hook(git_repo: Path, capsys):
    hook = git_repo / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/bin/sh\necho custom\n", encoding="utf-8")
    run_init(git_repo, hook=True)
    assert hook.read_text(encoding="utf-8") == "#!/bin/sh\necho custom\n"
    assert "featmap check --staged" in capsys.readouterr().out


def test_init_without_hook_prints_hint(git_repo: Path, capsys):
    run_init(git_repo)
    assert "--hook" in capsys.readouterr().out
    assert not (git_repo / ".git" / "hooks" / "pre-commit").exists()


def test_hook_template_never_blocks_commit():
    content = read_template("pre-commit")
    assert content.startswith("#!/bin/sh")
    assert content.rstrip().splitlines()[-1].startswith("exit 0")
