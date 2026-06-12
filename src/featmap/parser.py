"""Line-based parser for MAP.md (featmap format v1).

Builds a data model with line tracking and reports format violations
(rules F1-F10 of the spec) as E1 violations. Semantic checks (E2-E4,
W1-W4) live in validator.py. No markdown libraries, stdlib only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MARKER = "<!-- featmap v1 -->"
AUTOGEN_MARK = "<!-- autogen -->"
STATUSES = ("active", "wip", "deprecated")

FIELD_WHAT = "Что"
FIELD_FILES = "Файлы"
FIELD_DEPENDS = "Зависит"
FIELD_STATUS = "Статус"
FIELD_USED_BY = "Используется"
REQUIRED_FIELDS = (FIELD_WHAT, FIELD_FILES, FIELD_DEPENDS, FIELD_STATUS)

_RE_FIELD = re.compile(r"^\*\*(Что|Файлы|Зависит|Статус|Используется):\*\*\s*(.*)$")
_RE_LAYER = re.compile(r"^##\s+Слой:\s*(\S.*?)\s*$")
_RE_FEATURE = re.compile(r"^###\s+(.+?)\s*\{#([^}]*)\}\s*$")
_RE_FEATURE_LOOSE = re.compile(r"^###\s+(.+?)\s*$")
_RE_KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_RE_FILE_ITEM = re.compile(r"^`([^`]+)`$")
_RE_DEP_LINK = re.compile(r"^\[([^\]]+)\]\(#([^)\s]+)\)$")
_RE_LINKS = re.compile(r"\[([^\]]+)\]\(#([^)\s]+)\)")
_RE_DEEP_HEADING = re.compile(r"^#{4,}\s")

MAX_BODY_LINES = 6
MAX_PROJECT_DESC_LINES = 3


@dataclass
class Violation:
    """A single check finding; codes starting with 'E' are errors."""

    code: str
    line: int  # 1-based line in MAP.md
    message: str

    @property
    def is_error(self) -> bool:
        return self.code.startswith("E")


@dataclass
class FileRef:
    path: str  # relative to the repo root
    line: int | None = None


@dataclass
class Feature:
    title: str
    anchor: str
    line_start: int
    line_end: int = 0
    what: str = ""
    files: list[FileRef] = field(default_factory=list)
    depends: list[str] = field(default_factory=list)  # anchors
    status: str = ""
    used_by: list[str] | None = None  # None means the line is absent
    what_line: int | None = None
    files_line: int | None = None
    depends_line: int | None = None
    status_line: int | None = None
    used_by_line: int | None = None


@dataclass
class Layer:
    name: str
    line: int
    description: list[str] = field(default_factory=list)
    features: list[Feature] = field(default_factory=list)


@dataclass
class Project:
    name: str
    line: int
    description: list[str] = field(default_factory=list)
    layers: list[Layer] = field(default_factory=list)


@dataclass
class ParseResult:
    project: Project | None
    layers: list[Layer]
    features: list[Feature]
    violations: list[Violation]
    lines: list[str]


def _comment_mask(lines: list[str]) -> list[bool]:
    """Mark lines that are entirely inside HTML comments (cheat sheets etc.)."""
    mask = [False] * len(lines)
    in_comment = False
    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if in_comment:
            mask[i] = True
            if stripped.endswith("-->"):
                in_comment = False
        elif stripped.startswith("<!--"):
            mask[i] = True
            if not stripped.endswith("-->"):
                in_comment = True
    return mask


class _Parser:
    def __init__(self, text: str):
        self.lines = text.split("\n")
        self.violations: list[Violation] = []
        self.project: Project | None = None
        self.layers: list[Layer] = []
        self.features: list[Feature] = []
        self.layer: Layer | None = None
        self.feature: Feature | None = None
        self.field_seq: list[tuple[str, int]] = []
        self.body_count = 0
        self.last_content_line = 0

    def error(self, code: str, line: int, message: str) -> None:
        self.violations.append(Violation(code, line, message))

    def run(self) -> ParseResult:
        if not self.lines or self.lines[0].strip() != MARKER:
            self.error("E1", 1, f"F1: first line must be exactly '{MARKER}'")
        mask = _comment_mask(self.lines)
        for idx, raw in enumerate(self.lines):
            if mask[idx]:
                continue
            ln = idx + 1
            stripped = raw.strip()
            if not stripped:
                continue
            if _RE_DEEP_HEADING.match(stripped):
                self.error("E1", ln, "F5: headings deeper than '###' are not allowed")
                continue
            if stripped.startswith("### "):
                self._on_feature(stripped, ln)
            elif stripped.startswith("## "):
                self._on_layer(stripped, ln)
            elif stripped.startswith("# "):
                self._on_project(stripped, ln)
            else:
                self._on_content(stripped, ln)
        self._close_feature()
        self._check_project()
        return ParseResult(
            project=self.project,
            layers=self.layers,
            features=self.features,
            violations=self.violations,
            lines=self.lines,
        )

    def _on_project(self, stripped: str, ln: int) -> None:
        self._close_feature()
        if self.project is not None:
            self.error("E1", ln, "F2: exactly one top-level '#' heading is allowed")
            return
        self.project = Project(name=stripped[2:].strip(), line=ln)

    def _on_layer(self, stripped: str, ln: int) -> None:
        self._close_feature()
        m = _RE_LAYER.match(stripped)
        if m:
            name = m.group(1)
        else:
            self.error("E1", ln, "F3: '##' headings must be layers: '## Слой: <имя>'")
            name = stripped[3:].strip()
        layer = Layer(name=name, line=ln)
        self.layers.append(layer)
        if self.project is not None:
            self.project.layers.append(layer)
        self.layer = layer

    def _on_feature(self, stripped: str, ln: int) -> None:
        self._close_feature()
        m = _RE_FEATURE.match(stripped)
        if m:
            title, anchor = m.group(1), m.group(2)
            if not _RE_KEBAB.match(anchor):
                self.error(
                    "E1", ln, f"F4: anchor '#{anchor}' must be kebab-case ([a-z0-9] and '-')"
                )
        else:
            self.error("E1", ln, "F4: feature heading must carry an anchor: '### Имя {#kebab-id}'")
            loose = _RE_FEATURE_LOOSE.match(stripped)
            title = loose.group(1) if loose else stripped[4:].strip()
            anchor = ""
        feature = Feature(title=title, anchor=anchor, line_start=ln)
        self.features.append(feature)
        if self.layer is not None:
            self.layer.features.append(feature)
        else:
            self.error("E1", ln, "F4: feature defined outside of any '## Слой:' layer")
        self.feature = feature
        self.last_content_line = ln

    def _on_content(self, stripped: str, ln: int) -> None:
        if self.feature is not None:
            self.last_content_line = ln
            m = _RE_FIELD.match(stripped)
            if m:
                name, value = m.group(1), m.group(2)
                if name != FIELD_USED_BY:
                    self.body_count += 1
                self._handle_field(name, value, ln)
            else:
                self.body_count += 1
        elif self.layer is not None:
            self.layer.description.append(stripped)
        elif self.project is not None:
            self.project.description.append(stripped)

    def _handle_field(self, name: str, value: str, ln: int) -> None:
        f = self.feature
        assert f is not None
        self.field_seq.append((name, ln))
        if name == FIELD_WHAT:
            f.what = value.strip()
            f.what_line = ln
        elif name == FIELD_FILES:
            f.files_line = ln
            f.files = self._parse_files(value, ln)
        elif name == FIELD_DEPENDS:
            f.depends_line = ln
            f.depends = self._parse_depends(value, ln)
        elif name == FIELD_STATUS:
            f.status_line = ln
            status = value.strip()
            if status not in STATUSES:
                self.error(
                    "E1", ln, f"F10: status '{status}' must be one of: {', '.join(STATUSES)}"
                )
            f.status = status
        elif name == FIELD_USED_BY:
            f.used_by_line = ln
            cleaned = value.replace(AUTOGEN_MARK, "").strip()
            f.used_by = [anchor for _, anchor in _RE_LINKS.findall(cleaned)]

    def _parse_files(self, value: str, ln: int) -> list[FileRef]:
        value = value.strip()
        if value in ("", "—", "-"):
            return []
        refs: list[FileRef] = []
        for item in value.split(","):
            item = item.strip()
            if not item:
                continue
            m = _RE_FILE_ITEM.match(item)
            if not m:
                self.error(
                    "E1",
                    ln,
                    f"F8: file entry {item!r} must be a backtick path like "
                    "`path/to/file.py` or `path/to/file.py:42`",
                )
                continue
            inner = m.group(1)
            path, lineno = inner, None
            head, sep, tail = inner.rpartition(":")
            if sep and tail.isdigit():
                path, lineno = head, int(tail)
            refs.append(FileRef(path=path, line=lineno))
        return refs

    def _parse_depends(self, value: str, ln: int) -> list[str]:
        value = value.strip()
        if value in ("—", "-"):
            return []
        if not value:
            self.error("E1", ln, "F9: '**Зависит:**' must list [Имя](#id) links or be '—'")
            return []
        anchors: list[str] = []
        for item in value.split(","):
            item = item.strip()
            if not item:
                continue
            m = _RE_DEP_LINK.match(item)
            if not m:
                self.error(
                    "E1", ln, f"F9: dependency {item!r} must be an anchor link like [Имя](#id)"
                )
                continue
            anchors.append(m.group(2))
        return anchors

    def _close_feature(self) -> None:
        f = self.feature
        if f is None:
            return
        f.line_end = max(self.last_content_line, f.line_start)
        if self.body_count > MAX_BODY_LINES:
            self.error(
                "E1",
                f.line_start,
                f"F6: feature body has {self.body_count} lines (max {MAX_BODY_LINES}; "
                "blank lines and '**Используется:**' are not counted)",
            )
        seen: dict[str, int] = {}
        for name, ln in self.field_seq:
            if name == FIELD_USED_BY:
                continue
            if name in seen:
                self.error("E1", ln, f"F7: duplicate field '**{name}:**'")
            else:
                seen[name] = ln
        for name in REQUIRED_FIELDS:
            if name not in seen:
                self.error("E1", f.line_start, f"F7: missing required field '**{name}:**'")
        expected = [name for name in REQUIRED_FIELDS if name in seen]
        actual = [name for _, name in sorted((seen[n], n) for n in expected)]
        if actual != expected:
            self.error(
                "E1",
                f.line_start,
                "F7: fields must appear in order "
                "'**Что:**', '**Файлы:**', '**Зависит:**', '**Статус:**'",
            )
        self.feature = None
        self.field_seq = []
        self.body_count = 0

    def _check_project(self) -> None:
        if self.project is None:
            self.error("E1", 1, "F2: missing top-level '# <project>' heading")
            return
        desc = self.project.description
        if not desc:
            self.error(
                "E1",
                self.project.line,
                "F2: project heading must be followed by a 2-3 line description",
            )
        elif len(desc) > MAX_PROJECT_DESC_LINES:
            self.error(
                "E1",
                self.project.line,
                f"F2: project description has {len(desc)} lines "
                f"(max {MAX_PROJECT_DESC_LINES})",
            )


def parse(text: str) -> ParseResult:
    """Parse MAP.md text (LF-normalized) into a model plus format violations."""
    return _Parser(text).run()
