"""featmap command-line interface: init / check / links / version."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from featmap import FORMAT_VERSION, __version__, gitutils
from featmap.initializer import init_project
from featmap.links import update_used_by
from featmap.parser import Violation, parse
from featmap.validator import MAP_FILENAME, check_staged, validate


def _find_root() -> Path:
    return gitutils.repo_root() or Path.cwd()


def _read_map(path: Path) -> tuple[str, str]:
    """Read the map as LF-normalized text, remembering the original EOL style."""
    text = path.read_bytes().decode("utf-8")
    eol = "\r\n" if "\r\n" in text else "\n"
    if eol == "\r\n":
        text = text.replace("\r\n", "\n")
    return text, eol


def _print_violations(violations: list[Violation]) -> None:
    for violation in sorted(violations, key=lambda v: (v.line, v.code, v.message)):
        print(f"{MAP_FILENAME}:{violation.line}: {violation.code} {violation.message}")


def cmd_init(args: argparse.Namespace) -> int:
    return init_project(_find_root(), hook=args.hook, target=args.target)


def cmd_check(args: argparse.Namespace) -> int:
    root = _find_root()
    map_path = root / MAP_FILENAME
    if not map_path.is_file():
        print(f"featmap: {MAP_FILENAME} not found in {root} (run 'featmap init')", file=sys.stderr)
        return 1
    text, _ = _read_map(map_path)
    result = parse(text)
    violations = list(result.violations)
    violations.extend(validate(result, repo_root=root))
    if args.staged:
        violations.extend(check_staged(result, root))
    _print_violations(violations)
    has_errors = any(v.is_error for v in violations)
    has_warnings = any(not v.is_error for v in violations)
    if has_errors or (args.strict and has_warnings):
        return 1
    return 0


def cmd_links(_args: argparse.Namespace) -> int:
    root = _find_root()
    map_path = root / MAP_FILENAME
    if not map_path.is_file():
        print(f"featmap: {MAP_FILENAME} not found in {root} (run 'featmap init')", file=sys.stderr)
        return 1
    text, eol = _read_map(map_path)
    result = parse(text)
    errors = [v for v in result.violations if v.is_error]
    errors.extend(v for v in validate(result, repo_root=root) if v.is_error)
    if errors:
        _print_violations(errors)
        print("featmap: fix the errors above before running 'featmap links'", file=sys.stderr)
        return 1
    new_text, changed = update_used_by(text)
    if changed:
        if eol == "\r\n":
            new_text = new_text.replace("\n", "\r\n")
        map_path.write_bytes(new_text.encode("utf-8"))
        print(f"updated '**Used by:**' for {changed} feature(s)")
    else:
        print("'**Used by:**' lines already in sync")
    return 0


def cmd_version(_args: argparse.Namespace) -> int:
    print(f"featmap {__version__} (map format v{FORMAT_VERSION})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="featmap",
        description="AI-maintained feature map (MAP.md): init, validate, cross-link.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="create MAP.md, assistant rules and optionally a hook")
    p_init.add_argument(
        "--hook", action="store_true", help="also install the pre-commit reminder hook"
    )
    p_init.add_argument(
        "--target",
        choices=("agents", "claude"),
        help="where to write assistant rules when both AGENTS.md and CLAUDE.md are options",
    )
    p_init.set_defaults(func=cmd_init)

    p_check = sub.add_parser("check", help="validate MAP.md and print violations")
    p_check.add_argument(
        "--staged",
        action="store_true",
        help="also warn about staged files whose MAP.md section is not updated (V10)",
    )
    p_check.add_argument(
        "--strict", action="store_true", help="treat warnings as errors (exit code 1)"
    )
    p_check.set_defaults(func=cmd_check)

    p_links = sub.add_parser(
        "links", help="regenerate '**Used by:**' reverse links in MAP.md"
    )
    p_links.set_defaults(func=cmd_links)

    p_version = sub.add_parser("version", help="print tool and map format versions")
    p_version.set_defaults(func=cmd_version)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
