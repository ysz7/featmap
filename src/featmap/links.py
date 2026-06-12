"""Reverse dependency links: compute and regenerate '**Используется:**' lines."""

from __future__ import annotations

from featmap.parser import AUTOGEN_MARK, FIELD_USED_BY, Feature, parse


def compute_used_by(features: list[Feature]) -> dict[str, list[tuple[str, str]]]:
    """Map feature anchor -> [(dependent title, dependent anchor)] in document order."""
    incoming: dict[str, list[tuple[str, str]]] = {}
    for feature in features:
        if not feature.anchor:
            continue
        for dep in feature.depends:
            entries = incoming.setdefault(dep, [])
            if (feature.title, feature.anchor) not in entries:
                entries.append((feature.title, feature.anchor))
    return incoming


def render_used_by(entries: list[tuple[str, str]]) -> str:
    links = ", ".join(f"[{title}](#{anchor})" for title, anchor in entries)
    return f"**{FIELD_USED_BY}:** {AUTOGEN_MARK} {links}"


def update_used_by(text: str) -> tuple[str, int]:
    """Rewrite only the '**Используется:**' lines; return (new text, changed features).

    Features with incoming dependencies get the line (inserted after the last
    field if absent); features without incoming dependencies get it removed.
    All other lines are left untouched.
    """
    result = parse(text)
    lines = list(result.lines)
    incoming = compute_used_by(result.features)
    changed = 0
    # Bottom-up so that edits do not shift line numbers of features above.
    for feature in sorted(result.features, key=lambda f: f.line_start, reverse=True):
        if not feature.anchor:
            continue
        entries = incoming.get(feature.anchor, [])
        desired = render_used_by(entries) if entries else None
        if feature.used_by_line is not None:
            idx = feature.used_by_line - 1
            if desired is None:
                del lines[idx]
                changed += 1
            elif lines[idx] != desired:
                lines[idx] = desired
                changed += 1
        elif desired is not None:
            insert_after = max(
                ln
                for ln in (
                    feature.status_line,
                    feature.depends_line,
                    feature.files_line,
                    feature.what_line,
                    feature.line_start,
                )
                if ln is not None
            )
            lines.insert(insert_after, desired)
            changed += 1
    return "\n".join(lines), changed
