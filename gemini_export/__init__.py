# gemini_export — Hardened backup/export toolkit for Google Gemini chats.
# Author: David Malko
# License: MIT

"""Offline toolkit that imports, verifies, and converts Gemini chat exports.

Public API surface kept small and import-cheap so the CI smoke test can do
`from gemini_export import __version__` without pulling heavy dependencies.
"""

__version__ = "0.1.1"
