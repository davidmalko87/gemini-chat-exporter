# cli.py — Command-line interface for the Gemini export toolkit.
# Author: David Malko

"""Argparse CLI: verify / validate / import-takeout / convert / reconcile.

Every verb is a flag (mirrors the sibling jira tool's ``--<verb> <arg>`` UX).
``--verify`` / ``--validate`` exit non-zero when the audit fails, so they drop
straight into cron or CI. Console output is reconfigured to UTF-8 up front so a
Cyrillic (or any non-ASCII) conversation title never crashes a Windows console.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .config import load_config
from .convert import convert
from .parsers import load_conversations
from .reconcile import format_reconcile, reconcile
from .takeout import import_takeout
from .verify import VerifyReport, format_report, verify_conversations


def configure_console() -> None:
    """Make stdout/stderr tolerate non-ASCII text on any platform/code page."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):  # pragma: no cover - stream not reconfigurable
                pass


def _verify_summary(report: VerifyReport) -> dict:
    return {
        "passed": report.passed,
        "total": report.total,
        "distinct_body_hashes": report.distinct_body_hashes,
        "duplicated_conversation_count": report.duplicated_conversation_count,
        "duplicate_ratio": report.duplicate_ratio,
        "failures": report.failures,
        "warnings": report.warnings,
    }


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def cmd_verify(args, cfg) -> int:
    convs = load_conversations(args.path)
    report = verify_conversations(
        convs, dup_ratio_fail=cfg.dup_ratio_fail, min_run=cfg.min_run
    )
    print(format_report(report))
    out_path = Path(args.out or ".") / "verify_report.json"
    _write_json(out_path, report.to_dict())
    print(f"\nReport written to {out_path}")
    return 0 if report.passed else 1


def cmd_import_takeout(args, cfg) -> int:
    convs, stats = import_takeout(args.path)
    print("Takeout import:")
    for key, val in stats.items():
        print(f"  {key}: {val}")
    report = verify_conversations(
        convs, dup_ratio_fail=cfg.dup_ratio_fail, min_run=cfg.min_run
    )
    print()
    print(format_report(report))
    out_dir = Path(args.out or cfg.output_root)
    manifest = convert(
        convs,
        out_dir,
        write_json=not args.md_only,
        write_markdown=not args.json_only,
        complete=report.passed,
        verification=_verify_summary(report),
        dry_run=args.dry_run,
    )
    print(f"\n{manifest['conversation_count']} conversations -> {out_dir} "
          f"(dry-run={args.dry_run})")
    return 0


def cmd_convert(args, cfg) -> int:
    convs = load_conversations(args.path)
    report = verify_conversations(
        convs, dup_ratio_fail=cfg.dup_ratio_fail, min_run=cfg.min_run
    )
    print(format_report(report))
    if not report.passed:
        print("\n[!] Export FAILED verification - manifest will mark complete=false.")
        print("    Converting anyway so you can inspect, but do NOT trust as a backup.")
    out_dir = Path(args.out or cfg.output_root)
    manifest = convert(
        convs,
        out_dir,
        write_json=not args.md_only,
        write_markdown=not args.json_only,
        complete=report.passed,
        verification=_verify_summary(report),
        dry_run=args.dry_run,
    )
    print(f"\n{manifest['conversation_count']} conversations -> {out_dir} "
          f"(complete={manifest['complete']}, dry-run={args.dry_run})")
    return 0


def cmd_reconcile(args, cfg) -> int:
    scraper_convs = load_conversations(args.reconcile[0])
    takeout_convs, _stats = import_takeout(args.reconcile[1])
    report = reconcile(scraper_convs, takeout_convs)
    print(format_reconcile(report))
    out_path = Path(args.out or ".") / "reconcile_report.json"
    _write_json(out_path, report)
    print(f"\nReport written to {out_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gemini-export",
        description="Verify, import, convert and reconcile Gemini chat exports.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--verify", metavar="PATH", help="audit an export for corruption")
    group.add_argument("--validate", metavar="PATH",
                       help="alias for --verify (non-zero exit on failure, for cron/CI)")
    group.add_argument("--import-takeout", dest="import_takeout", metavar="PATH",
                       help="import a Google Takeout Gemini Apps export")
    group.add_argument("--convert", metavar="PATH",
                       help="convert an export to per-conversation JSON + Markdown")
    group.add_argument("--reconcile", nargs=2, metavar=("SCRAPER", "TAKEOUT"),
                       help="diff a scraper export against a Takeout export")

    p.add_argument("--out", metavar="DIR", help="output directory")
    p.add_argument("--dry-run", action="store_true", help="compute but write nothing")
    p.add_argument("--dup-ratio", type=float, metavar="F",
                   help="override the duplicate-body fail threshold (0..1)")
    p.add_argument("--json-only", action="store_true", help="write JSON, skip Markdown")
    p.add_argument("--md-only", action="store_true", help="write Markdown, skip JSON")
    return p


def main(argv: list[str] | None = None) -> int:
    configure_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    cfg = load_config()
    if args.dup_ratio is not None:
        cfg.dup_ratio_fail = args.dup_ratio

    if args.verify or args.validate:
        args.path = args.verify or args.validate
        return cmd_verify(args, cfg)
    if args.import_takeout:
        args.path = args.import_takeout
        return cmd_import_takeout(args, cfg)
    if args.convert:
        args.path = args.convert
        return cmd_convert(args, cfg)
    if args.reconcile:
        return cmd_reconcile(args, cfg)

    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
