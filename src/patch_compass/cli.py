from __future__ import annotations

import argparse
import sys
from pathlib import Path

from patch_compass import __version__
from patch_compass.analysis import analyze
from patch_compass.git_ops import GitError, collect_changes
from patch_compass.report import render_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="patch-compass",
        description="Turn Git changes into a deterministic, path-based review checklist.",
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="repository path (default: current directory)")
    parser.add_argument("--base", help="base ref; defaults to origin/HEAD, then local main/master")
    parser.add_argument("--format", choices=("text", "markdown", "json"), default="text", help="report format")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _configure_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="backslashreplace")


def main(argv: list[str] | None = None) -> int:
    _configure_output()
    args = build_parser().parse_args(argv)
    try:
        changes = collect_changes(args.repo, args.base)
        report = analyze(changes)
        print(render_report(report, args.format))
    except (GitError, OSError, ValueError) as exc:
        print(f"patch-compass: {exc}", file=sys.stderr)
        return 1
    return 0
