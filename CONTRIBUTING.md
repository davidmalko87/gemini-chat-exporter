# Contributing

Thanks for helping keep this tool trustworthy. The whole point of the project is
that it **never silently produces a corrupt or incomplete backup**, so the bar for
changes is "prove it, don't assume it".

## Ground rules

- **Never commit personal data.** No real conversation exports, `.env` files,
  logs, Takeout archives, or output directories. They are gitignored; run
  `git status` before every commit and confirm nothing sensitive is staged.
- **Test fixtures are synthetic.** Anything under `tests/fixtures/` must be made-up
  content, never a real chat.
- **ASCII-only console output.** Conversation data is UTF-8 in files, but anything
  printed to the terminal must survive a Windows code page (the CLI reconfigures
  stdout to UTF-8 defensively; keep report text ASCII regardless).
- **Keep it local.** No servers, credentials, API tokens, or telemetry.

## Development

```bash
pip install -r requirements.txt
pip install ruff pytest
ruff check .
pytest -q
python main.py --verify tests/fixtures/corrupted_sample.txt   # should FAIL (exit 1)
```

If you touch the userscript, syntax-check it the way CI does:

```bash
node --check userscript/gemini-chat-exporter.user.js
node --check userscript/console-snippet.js
```

## Selectors break - that's expected

Gemini is an undocumented Angular SPA. When Google changes the DOM, update the
selectors in `userscript/gemini-chat-exporter.user.js` (the `CONFIG` block) and
the console snippet. The tool is designed to **fail loudly** when selectors stop
matching rather than emit empty output - keep that behavior.

## Versioning policy

Semantic Versioning. To release:

1. Bump the version in **both** `gemini_export/__init__.py` and `pyproject.toml`
   (they must match).
2. Add a `## [X.Y.Z]` section to `CHANGELOG.md`.
3. Open a PR; once merged, draft a GitHub Release with tag `vX.Y.Z` (the leading
   `v` matters) targeting `master`, body = the changelog section. Publishing the
   release triggers `publish.yml` (PyPI trusted publishing).

Do not bump the version again after tagging.
