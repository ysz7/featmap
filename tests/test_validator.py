from __future__ import annotations

from pathlib import Path

from conftest import VALID_MAP, git

from featmap import cli
from featmap.parser import parse
from featmap.validator import check_staged, validate

HEADER = """\
<!-- featmap v1 -->
# Project: demo

Project description.

## Layer: Core

Layer description.

"""


def feature(title: str, anchor: str, depends: str = "—", status: str = "active",
            files: str = "`src/a.py`") -> str:
    return (
        f"### {title} {{#{anchor}}}\n\n"
        f"**What:** Does something.\n"
        f"**Files:** {files}\n"
        f"**Depends:** {depends}\n"
        f"**Status:** {status}\n\n"
    )


def run_validate(text: str, repo_root: Path | None = None):
    result = parse(text)
    assert not any(v.is_error for v in result.violations), result.violations
    return validate(result, repo_root=repo_root)


def test_valid_map_is_clean(valid_repo: Path):
    result = parse(VALID_MAP)
    assert result.violations == []
    assert validate(result, repo_root=valid_repo) == []


def test_e2_duplicate_anchor():
    text = HEADER + feature("Alpha", "same") + feature("Beta", "same")
    violations = run_validate(text)
    assert any(v.code == "E2" and "#same" in v.message for v in violations)


def test_e3_unknown_dependency():
    text = HEADER + feature("Alpha", "a", depends="[Ghost](#ghost)")
    violations = run_validate(text)
    assert any(v.code == "E3" and "#ghost" in v.message for v in violations)


def test_e4_dependency_cycle():
    text = (
        HEADER
        + feature("Alpha", "a", depends="[Beta](#b)")
        + feature("Beta", "b", depends="[Alpha](#a)")
    )
    violations = run_validate(text)
    cycles = [v for v in violations if v.code == "E4"]
    assert len(cycles) == 1
    assert "->" in cycles[0].message
    assert "#a" in cycles[0].message and "#b" in cycles[0].message


def test_e4_self_cycle():
    text = HEADER + feature("Alpha", "a", depends="[Alpha](#a)")
    violations = run_validate(text)
    assert any(v.code == "E4" for v in violations)


def test_w1_missing_file(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    text = HEADER + feature("Alpha", "a", files="`src/a.py`, `src/missing.py`")
    violations = run_validate(text, repo_root=tmp_path)
    w1 = [v for v in violations if v.code == "W1"]
    assert len(w1) == 1
    assert "src/missing.py" in w1[0].message


def test_w2_depends_on_deprecated():
    text = (
        HEADER
        + feature("Old", "old", status="deprecated")
        + feature("New", "new", depends="[Old](#old)")
    )
    violations = run_validate(text)
    assert any(v.code == "W2" and "#old" in v.message for v in violations)


def test_w3_used_by_out_of_sync():
    # 'b' depends on 'a', but 'a' has no '**Used by:**' line.
    text = HEADER + feature("Alpha", "a") + feature("Beta", "b", depends="[Alpha](#a)")
    violations = run_validate(text)
    assert any(v.code == "W3" and "#a" in v.message for v in violations)


def test_w3_stale_used_by_line():
    text = HEADER + feature("Alpha", "a").replace(
        "**Status:** active\n",
        "**Status:** active\n**Used by:** <!-- autogen --> [Ghost](#ghost)\n",
    )
    violations = run_validate(text)
    assert any(v.code == "W3" for v in violations)


def test_w4_layer_without_features():
    text = HEADER + feature("Alpha", "a") + "## Layer: Empty\n\nNothing here.\n"
    violations = run_validate(text)
    assert any(v.code == "W4" and "Empty" in v.message for v in violations)


def test_w4_feature_without_files():
    text = HEADER + feature("Alpha", "a", files="—")
    violations = run_validate(text)
    assert any(v.code == "W4" and "#a" in v.message for v in violations)


def test_check_cli_clean_map(valid_repo: Path, monkeypatch, capsys):
    monkeypatch.chdir(valid_repo)
    assert cli.main(["check"]) == 0
    assert capsys.readouterr().out == ""


def test_check_cli_reports_line_numbers(valid_repo: Path, monkeypatch, capsys):
    (valid_repo / "MAP.md").write_text(
        VALID_MAP.replace("**Status:** active\n**Used", "**Status:** done\n**Used"),
        encoding="utf-8",
    )
    monkeypatch.chdir(valid_repo)
    assert cli.main(["check"]) == 1
    out = capsys.readouterr().out
    assert "MAP.md:20: E1" in out


def test_check_cli_warnings_exit_zero_unless_strict(valid_repo: Path, monkeypatch, capsys):
    (valid_repo / "src" / "rules.py").unlink()  # triggers W1 only
    monkeypatch.chdir(valid_repo)
    assert cli.main(["check"]) == 0
    assert "W1" in capsys.readouterr().out
    assert cli.main(["check", "--strict"]) == 1


def test_v10_staged_file_without_map_update(valid_repo: Path):
    git(["add", "."], valid_repo)
    git(["commit", "-q", "-m", "base"], valid_repo)
    # Change a file of feature #parser, stage it, leave MAP.md untouched.
    (valid_repo / "src" / "parser.py").write_text("changed = True\n", encoding="utf-8")
    git(["add", "src/parser.py"], valid_repo)
    result = parse((valid_repo / "MAP.md").read_text(encoding="utf-8"))
    violations = check_staged(result, valid_repo)
    assert len(violations) == 1
    assert violations[0].code == "V10"
    assert "src/parser.py" in violations[0].message
    assert "#parser" in violations[0].message
    assert not violations[0].is_error


def test_v10_quiet_when_map_section_staged(valid_repo: Path):
    git(["add", "."], valid_repo)
    git(["commit", "-q", "-m", "base"], valid_repo)
    (valid_repo / "src" / "parser.py").write_text("changed = True\n", encoding="utf-8")
    map_text = (valid_repo / "MAP.md").read_text(encoding="utf-8")
    map_text = map_text.replace(
        "**What:** Parses MAP.md into a data model.",
        "**What:** Parses MAP.md into a data model line by line.",
    )
    (valid_repo / "MAP.md").write_text(map_text, encoding="utf-8")
    git(["add", "src/parser.py", "MAP.md"], valid_repo)
    result = parse(map_text)
    assert check_staged(result, valid_repo) == []


def test_v10_quiet_when_nothing_staged(valid_repo: Path):
    result = parse(VALID_MAP)
    assert check_staged(result, valid_repo) == []
