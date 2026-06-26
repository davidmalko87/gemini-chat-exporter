# menu.py — Interactive menu for the Gemini export toolkit.
# Author: David Malko

"""A small interactive menu for users who would rather not type CLI flags.

It is intentionally thin: it just gathers a path or two and delegates to the same
functions the CLI uses, so behavior can never diverge between the two front ends.
All prompts and output are ASCII-only.
"""

from __future__ import annotations

from pathlib import Path

from . import __version__
from .cli import configure_console
from .config import load_config
from .convert import convert
from .parsers import load_conversations
from .reconcile import format_reconcile, reconcile
from .takeout import import_takeout
from .verify import format_report, verify_conversations

_MENU = f"""
==================================================
  Gemini Chat Exporter v{__version__}
==================================================
  --- Verify ---
  1) Verify / audit an export for corruption
  --- Import & convert ---
  2) Import a Google Takeout export
  3) Convert an export to JSON + Markdown
  --- Reconcile ---
  4) Reconcile a scraper export against Takeout
  0) Exit
"""


def _ask(prompt: str) -> str:
    try:
        return input(prompt).strip().strip('"').strip("'")
    except (EOFError, KeyboardInterrupt):
        return ""


def run_menu() -> int:
    """Run the interactive menu loop. Returns a process exit code."""
    configure_console()
    cfg = load_config()
    while True:
        print(_MENU)
        choice = _ask("  Select> ")
        if choice in ("0", "", "q", "exit"):
            print("Bye.")
            return 0
        if choice == "1":
            path = _ask("  Path to export: ")
            if not _exists(path):
                continue
            convs = load_conversations(path)
            report = verify_conversations(
                convs, dup_ratio_fail=cfg.dup_ratio_fail, min_run=cfg.min_run
            )
            print(format_report(report))
        elif choice == "2":
            path = _ask("  Path to Takeout (.json/.zip/dir): ")
            if not _exists(path):
                continue
            convs, stats = import_takeout(path)
            for key, val in stats.items():
                print(f"  {key}: {val}")
            out = _ask(f"  Output dir [{cfg.output_root}]: ") or cfg.output_root
            report = verify_conversations(convs, dup_ratio_fail=cfg.dup_ratio_fail)
            convert(convs, out, complete=report.passed)
            print(f"  Wrote {len(convs)} conversations to {out}")
        elif choice == "3":
            path = _ask("  Path to export: ")
            if not _exists(path):
                continue
            convs = load_conversations(path)
            report = verify_conversations(
                convs, dup_ratio_fail=cfg.dup_ratio_fail, min_run=cfg.min_run
            )
            print(format_report(report))
            out = _ask(f"  Output dir [{cfg.output_root}]: ") or cfg.output_root
            convert(convs, out, complete=report.passed,
                    verification={"passed": report.passed})
            print(f"  Wrote {len(convs)} conversations to {out} "
                  f"(complete={report.passed})")
        elif choice == "4":
            scraper = _ask("  Path to scraper export: ")
            takeout = _ask("  Path to Takeout export: ")
            if not _exists(scraper) or not _exists(takeout):
                continue
            convs = load_conversations(scraper)
            tconvs, _ = import_takeout(takeout)
            print(format_reconcile(reconcile(convs, tconvs)))
        else:
            print("  Unknown choice.")


def _exists(path: str) -> bool:
    if path and Path(path).exists():
        return True
    print(f"  [!] Not found: {path!r}")
    return False
