"""Semantic validation of a parsed MAP.md: rules E2-E4, W1-W4 and V10 (staged)."""

from __future__ import annotations

from pathlib import Path

from featmap import gitutils
from featmap.links import compute_used_by
from featmap.parser import Feature, ParseResult, Violation

MAP_FILENAME = "MAP.md"


def validate(result: ParseResult, repo_root: Path | None = None) -> list[Violation]:
    """Run semantic checks; pass repo_root to enable file existence checks (W1)."""
    out: list[Violation] = []
    anchors: dict[str, Feature] = {}
    for feature in result.features:
        if not feature.anchor:
            continue
        if feature.anchor in anchors:
            out.append(
                Violation(
                    "E2",
                    feature.line_start,
                    f"duplicate anchor '#{feature.anchor}' "
                    f"(first defined at line {anchors[feature.anchor].line_start})",
                )
            )
        else:
            anchors[feature.anchor] = feature

    for feature in result.features:
        line = feature.depends_line or feature.line_start
        for dep in feature.depends:
            if dep not in anchors:
                out.append(
                    Violation("E3", line, f"'**Depends:**' references unknown anchor '#{dep}'")
                )
            elif anchors[dep].status == "deprecated":
                out.append(
                    Violation(
                        "W2",
                        line,
                        f"depends on deprecated feature '{anchors[dep].title}' (#{dep})",
                    )
                )

    graph = {
        anchor: [dep for dep in feature.depends if dep in anchors]
        for anchor, feature in anchors.items()
    }
    for cycle in _find_cycles(graph):
        path = " -> ".join(f"#{anchor}" for anchor in cycle)
        out.append(Violation("E4", anchors[cycle[0]].line_start, f"dependency cycle: {path}"))

    if repo_root is not None:
        for feature in result.features:
            for ref in feature.files:
                if not (repo_root / ref.path).exists():
                    out.append(
                        Violation(
                            "W1",
                            feature.files_line or feature.line_start,
                            f"file '{ref.path}' does not exist in the repository",
                        )
                    )

    incoming = compute_used_by(result.features)
    for feature in result.features:
        if not feature.anchor:
            continue
        expected = [anchor for _, anchor in incoming.get(feature.anchor, [])]
        actual = feature.used_by if feature.used_by is not None else []
        if expected != actual:
            out.append(
                Violation(
                    "W3",
                    feature.used_by_line or feature.line_start,
                    f"'**Used by:**' is out of sync for '#{feature.anchor}'; "
                    "run 'featmap links'",
                )
            )

    for layer in result.layers:
        if not layer.features:
            out.append(Violation("W4", layer.line, f"layer '{layer.name}' has no features"))
    for feature in result.features:
        if not feature.files:
            out.append(
                Violation(
                    "W4",
                    feature.files_line or feature.line_start,
                    f"feature '{feature.title}' (#{feature.anchor}) lists no files",
                )
            )
    return out


def check_staged(result: ParseResult, repo_root: Path) -> list[Violation]:
    """V10: a staged file belongs to a feature whose MAP.md section is not staged."""
    staged = gitutils.staged_files(repo_root)
    if not staged:
        return []
    staged_set = set(staged)
    ranges = gitutils.staged_changed_lines(repo_root, MAP_FILENAME)
    out: list[Violation] = []
    for feature in result.features:
        touched = sorted({ref.path for ref in feature.files if ref.path in staged_set})
        if not touched:
            continue
        if any(lo <= feature.line_end and hi >= feature.line_start for lo, hi in ranges):
            continue
        out.append(
            Violation(
                "V10",
                feature.line_start,
                f"staged file(s) {', '.join(touched)} belong to feature "
                f"'{feature.title}' (#{feature.anchor}), but its MAP.md section has no "
                "staged changes — did you forget to update the map?",
            )
        )
    return out


def _find_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    """Return dependency cycles (each as [a, b, ..., a]), each reported once."""
    white, gray, black = 0, 1, 2
    color = dict.fromkeys(graph, white)
    stack: list[str] = []
    cycles: list[list[str]] = []
    seen: set[frozenset[str]] = set()

    def dfs(node: str) -> None:
        color[node] = gray
        stack.append(node)
        for neighbor in graph.get(node, ()):  # noqa: B023 - bound per call
            if color.get(neighbor, black) == gray:
                start = stack.index(neighbor)
                cycle = stack[start:] + [neighbor]
                key = frozenset(cycle)
                if key not in seen:
                    seen.add(key)
                    cycles.append(cycle)
            elif color.get(neighbor) == white:
                dfs(neighbor)
        stack.pop()
        color[node] = black

    for node in graph:
        if color[node] == white:
            dfs(node)
    return cycles
