"""Command line entry point. Exit 0 = passed policy; 1 = review needed; 2 = error."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .core import SkillDiffError, compare, load, scan
from .render import render, safe_text


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="skill-diff", description="See what changed behind SKILL.md. Offline. No API key.")
    p.add_argument("--version", action="version", version=f"SkillDiff {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    snap = sub.add_parser("snapshot", help="Record a skill directory as a portable baseline")
    snap.add_argument("directory", type=Path)
    snap.add_argument("-o", "--output", type=Path, required=True)
    snap.add_argument("--force", action="store_true", help="Replace an existing snapshot after review")
    for command, help_text in [("diff", "Compare two skill directories or snapshots"), ("check", "Gate any content drift from a reviewed snapshot")]:
        cmd = sub.add_parser(command, help=help_text)
        cmd.add_argument("before", type=Path, help="Skill directory or snapshot JSON")
        cmd.add_argument("after", type=Path, help="Skill directory or snapshot JSON")
        cmd.add_argument("--format", choices=["text", "json", "markdown", "html"], default="text")
        cmd.add_argument("-o", "--output", type=Path, help="Write a report (otherwise stdout)")
        cmd.add_argument("--fail-on", choices=["change", "signals", "high", "none"], default="change" if command == "check" else "none",
                         help="Exit 1 for any change, added signals, added high-priority signals, or never")
    return p


def output_allowed(path: Path, sources: list[Path]) -> None:
    target = path.expanduser().resolve()
    for source in sources:
        source = source.expanduser().resolve()
        if target == source or (source.is_dir() and source in target.parents):
            raise SkillDiffError("Write reports and snapshots outside the input skill directory and never over an input snapshot")


def write(path: Path | None, text: str, *, exclusive: bool = False) -> None:
    if path is None:
        sys.stdout.write(text)
    else:
        with path.expanduser().open("x" if exclusive else "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    # Consistent Unicode output across Windows terminals and CI redirection.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    try:
        if args.command == "snapshot":
            output_allowed(args.output, [args.directory])
            snapshot = scan(args.directory)
            write(args.output, json.dumps(snapshot, ensure_ascii=True, indent=2) + "\n", exclusive=not args.force)
            print(f"Recorded {len(snapshot['files'])} files / {snapshot['digest'][:12]} -> {safe_text(str(args.output))}")
            return 0
        if args.output:
            output_allowed(args.output, [args.before, args.after])
        report = compare(load(args.before), load(args.after))
        write(args.output, render(report, args.format))
        if args.output:
            print(f"Report written to {safe_text(str(args.output))}", file=sys.stderr)
        added = [x for x in report["signals"] if x["change"] == "added"]
        return int({"none": False, "change": report["changed"], "signals": bool(added),
                    "high": any(x["priority"] == "high" for x in added)}[args.fail_on])
    except BrokenPipeError:
        return 0
    except (OSError, SkillDiffError, RecursionError) as exc:
        print(f"skill-diff: {safe_text(str(exc))}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
