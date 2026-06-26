#!/usr/bin/env python3
# main.py — Entry point: interactive menu (no args) or CLI flags.
# Author: David Malko

"""Run the Gemini export toolkit.

    python main.py                       # interactive menu
    python main.py --verify export.txt   # CLI mode (non-zero exit on failure)

See ``python main.py --help`` for all flags.
"""

from __future__ import annotations

import sys

from gemini_export.cli import main as cli_main
from gemini_export.menu import run_menu


def main() -> int:
    if len(sys.argv) > 1:
        return cli_main(sys.argv[1:])
    return run_menu()


if __name__ == "__main__":
    raise SystemExit(main())
