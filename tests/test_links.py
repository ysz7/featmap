from __future__ import annotations

from pathlib import Path

from conftest import VALID_MAP

from featmap import cli
from featmap.links import compute_used_by, update_used_by
from featmap.parser import parse
from featmap.validator import validate

MAP_A_DEPENDS_B = """\
<!-- featmap v1 -->
# Проект: demo

Описание проекта.

## Слой: Ядро

Описание слоя.

### А {#a}

**Что:** Использует Б.
**Файлы:** `src/a.py`
**Зависит:** [Б](#b)
**Статус:** active

### Б {#b}

**Что:** Базовый механизм.
**Файлы:** `src/b.py`
**Зависит:** —
**Статус:** active
"""


def test_compute_used_by():
    result = parse(MAP_A_DEPENDS_B)
    incoming = compute_used_by(result.features)
    assert incoming == {"b": [("А", "a")]}


def test_links_adds_reverse_link():
    new_text, changed = update_used_by(MAP_A_DEPENDS_B)
    assert changed == 1
    lines = new_text.split("\n")
    assert "**Используется:** <!-- autogen --> [А](#a)" in lines
    # The line is appended to feature 'b', right after its status line.
    idx = lines.index("**Статус:** active", lines.index("### Б {#b}"))
    assert lines[idx + 1] == "**Используется:** <!-- autogen --> [А](#a)"


def test_links_touches_nothing_else():
    new_text, _ = update_used_by(MAP_A_DEPENDS_B)
    old_lines = set(MAP_A_DEPENDS_B.split("\n"))
    extra = [line for line in new_text.split("\n") if line not in old_lines]
    assert extra == ["**Используется:** <!-- autogen --> [А](#a)"]


def test_links_is_idempotent():
    once, _ = update_used_by(MAP_A_DEPENDS_B)
    twice, changed = update_used_by(once)
    assert changed == 0
    assert twice == once


def test_links_removes_stale_line():
    text, _ = update_used_by(MAP_A_DEPENDS_B)
    text = text.replace("**Зависит:** [Б](#b)", "**Зависит:** —")
    new_text, changed = update_used_by(text)
    assert changed == 1
    assert "Используется" not in new_text


def test_links_result_passes_w3():
    new_text, _ = update_used_by(MAP_A_DEPENDS_B)
    result = parse(new_text)
    assert result.violations == []
    assert not any(v.code == "W3" for v in validate(result))


def test_links_cli_roundtrip(valid_repo: Path, monkeypatch, capsys):
    # Break the sync: drop the autogen line from the reference map.
    broken = "\n".join(
        line for line in VALID_MAP.split("\n") if not line.startswith("**Используется:**")
    )
    (valid_repo / "MAP.md").write_text(broken, encoding="utf-8")
    monkeypatch.chdir(valid_repo)
    assert cli.main(["check"]) == 0  # W3 is a warning
    assert "W3" in capsys.readouterr().out
    assert cli.main(["links"]) == 0
    capsys.readouterr()
    assert cli.main(["check"]) == 0
    assert capsys.readouterr().out == ""
    assert (valid_repo / "MAP.md").read_text(encoding="utf-8") == VALID_MAP


def test_links_cli_refuses_on_errors(valid_repo: Path, monkeypatch, capsys):
    broken = VALID_MAP.replace("**Зависит:** [Парсер](#parser)", "**Зависит:** [X](#ghost)")
    (valid_repo / "MAP.md").write_text(broken, encoding="utf-8")
    monkeypatch.chdir(valid_repo)
    assert cli.main(["links"]) == 1
    assert "E3" in capsys.readouterr().out
    assert (valid_repo / "MAP.md").read_text(encoding="utf-8") == broken


def test_links_preserves_crlf(valid_repo: Path, monkeypatch):
    broken = "\n".join(
        line for line in VALID_MAP.split("\n") if not line.startswith("**Используется:**")
    )
    (valid_repo / "MAP.md").write_bytes(broken.replace("\n", "\r\n").encode("utf-8"))
    monkeypatch.chdir(valid_repo)
    assert cli.main(["links"]) == 0
    data = (valid_repo / "MAP.md").read_bytes()
    assert b"\r\n" in data
    assert data == VALID_MAP.replace("\n", "\r\n").encode("utf-8")
