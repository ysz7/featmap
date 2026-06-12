from __future__ import annotations

from conftest import VALID_MAP

from featmap.parser import FileRef, parse


def messages(result):
    return [(v.code, v.line, v.message) for v in result.violations]


def test_valid_map_has_no_violations():
    result = parse(VALID_MAP)
    assert result.violations == []


def test_valid_map_model():
    result = parse(VALID_MAP)
    project = result.project
    assert project is not None
    assert project.name == "Project: demo"
    assert len(project.description) == 2
    assert [layer.name for layer in result.layers] == ["Core"]
    assert [f.anchor for f in result.features] == ["parser", "validator"]

    parser_feature, validator_feature = result.features
    assert parser_feature.title == "Parser"
    assert parser_feature.what.startswith("Parses")
    assert parser_feature.files == [FileRef("src/parser.py")]
    assert parser_feature.depends == []
    assert parser_feature.status == "active"
    assert parser_feature.used_by == ["validator"]

    assert validator_feature.files == [
        FileRef("src/validator.py"),
        FileRef("src/rules.py", 10),
    ]
    assert validator_feature.depends == ["parser"]
    assert validator_feature.used_by is None


def test_line_tracking():
    result = parse(VALID_MAP)
    parser_feature = result.features[0]
    assert parser_feature.line_start == 15
    assert parser_feature.line_end == 21
    assert parser_feature.status_line == 20
    assert parser_feature.used_by_line == 21


def test_f1_missing_marker():
    result = parse("# Project: x\n\nDescription.\n")
    assert any(v.code == "E1" and v.line == 1 and "F1" in v.message for v in result.violations)


def test_f2_multiple_h1():
    text = VALID_MAP + "\n# Second project\n"
    result = parse(text)
    assert any(v.code == "E1" and "F2" in v.message for v in result.violations)


def test_f2_missing_project_heading():
    result = parse("<!-- featmap v1 -->\n\nJust some text.\n")
    assert any(v.code == "E1" and "F2" in v.message for v in result.violations)


def test_f2_missing_description():
    text = "<!-- featmap v1 -->\n# Project: x\n\n## Layer: A\n"
    result = parse(text)
    assert any(v.code == "E1" and v.line == 2 and "F2" in v.message for v in result.violations)


def test_f2_description_too_long():
    text = "<!-- featmap v1 -->\n# Project: x\n\none\ntwo\nthree\nfour\n"
    result = parse(text)
    assert any(v.code == "E1" and "F2" in v.message for v in result.violations)


def test_f3_bad_layer_heading():
    text = VALID_MAP.replace("## Layer: Core", "## Core")
    result = parse(text)
    assert any(v.code == "E1" and v.line == 11 and "F3" in v.message for v in result.violations)


def test_f4_missing_anchor():
    text = VALID_MAP.replace("### Parser {#parser}", "### Parser")
    result = parse(text)
    assert any(v.code == "E1" and v.line == 15 and "F4" in v.message for v in result.violations)


def test_f4_anchor_not_kebab_case():
    text = VALID_MAP.replace("{#parser}", "{#Parser_One}")
    result = parse(text)
    assert any(v.code == "E1" and "F4" in v.message for v in result.violations)


def test_f4_feature_outside_layer():
    text = (
        "<!-- featmap v1 -->\n# Project: x\n\nDescription.\n\n"
        "### Feature {#feature}\n\n**What:** Something.\n**Files:** `a.py`\n"
        "**Depends:** —\n**Status:** active\n"
    )
    result = parse(text)
    assert any(v.code == "E1" and "F4" in v.message and v.line == 6 for v in result.violations)


def test_f5_deep_heading():
    text = VALID_MAP + "\n#### Too deep\n"
    result = parse(text)
    assert any(v.code == "E1" and "F5" in v.message for v in result.violations)


def test_f6_body_too_long():
    text = VALID_MAP.replace(
        "**Status:** active\n**Used by:**",
        "**Status:** active\nextra line 1\nextra line 2\nextra line 3\n**Used by:**",
    )
    result = parse(text)
    assert any(v.code == "E1" and "F6" in v.message and v.line == 15 for v in result.violations)


def test_f6_used_by_and_blanks_not_counted():
    # The reference map has 4 fields + a used-by line: must not trigger F6.
    result = parse(VALID_MAP)
    assert not any("F6" in v.message for v in result.violations)


def test_f7_missing_field():
    text = VALID_MAP.replace("**Depends:** —\n", "")
    result = parse(text)
    assert any(
        v.code == "E1" and "F7" in v.message and "Depends" in v.message
        for v in result.violations
    )


def test_f7_wrong_order():
    text = VALID_MAP.replace(
        "**What:** Parses MAP.md into a data model.\n**Files:** `src/parser.py`\n",
        "**Files:** `src/parser.py`\n**What:** Parses MAP.md into a data model.\n",
    )
    result = parse(text)
    assert any(v.code == "E1" and "F7" in v.message for v in result.violations)


def test_f7_duplicate_field():
    text = VALID_MAP.replace(
        "**Status:** active\n**Used", "**Status:** active\n**Status:** active\n**Used"
    )
    result = parse(text)
    assert any(v.code == "E1" and "F7" in v.message and "duplicate" in v.message
               for v in result.violations)


def test_f8_files_without_backticks():
    text = VALID_MAP.replace("**Files:** `src/parser.py`", "**Files:** src/parser.py")
    result = parse(text)
    assert any(v.code == "E1" and "F8" in v.message and v.line == 18 for v in result.violations)


def test_f9_bad_dependency():
    text = VALID_MAP.replace("**Depends:** [Parser](#parser)", "**Depends:** parser")
    result = parse(text)
    assert any(v.code == "E1" and "F9" in v.message for v in result.violations)


def test_f10_bad_status():
    text = VALID_MAP.replace("**Status:** active\n**Used", "**Status:** done\n**Used")
    result = parse(text)
    assert any(v.code == "E1" and "F10" in v.message and v.line == 20 for v in result.violations)


def test_html_comments_are_ignored():
    # The cheat-sheet comment spans lines 7-9; none of its lines may produce
    # violations or leak into the project description.
    result = parse(VALID_MAP)
    assert result.project is not None
    assert all("cheat sheet" not in line for line in result.project.description)
