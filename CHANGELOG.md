# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-27

Initial release. Born out of a real incident: a previous DOM-scraper run silently
overwrote ~280 of 473 conversations with a single duplicated stub and reported
"zero errors". This release is built so that can never happen unnoticed again.

### Added

- **Hardened userscript** (`userscript/gemini-chat-exporter.user.js`) and a
  **console-snippet** fallback that export all Gemini conversations to NDJSON with:
  - content-identity validation (URL id + first prompt must match the target and
    differ from the previous conversation before scraping);
  - a post-scrape duplicate-body guard that marks a conversation FAILED instead of
    saving a stale stub;
  - streaming writes (File System Access API) instead of one giant in-memory string;
  - resume via `localStorage`; fail-loud on missing selectors.
- **Python verifier** (`gemini-export --verify` / `--validate`) that audits any
  export for duplicate bodies, duplicate ratio over threshold, contiguous
  same-body runs, duplicate/missing ids, and empty/image-only bodies; exits
  non-zero on failure for cron/CI.
- **Schema-tolerant Google Takeout importer** (`--import-takeout`) handling both the
  My Activity array form and the conversations object form.
- **Converters** (`--convert`) to per-conversation JSON + Markdown plus a
  `manifest.json` with SHA-256 checksums and a `complete` flag tied to verification.
- **Reconcile** (`--reconcile`) to diff a scraper export against Takeout and flag
  which corrupt conversations are recoverable.
- Interactive menu and CLI sharing one codebase; UTF-8-safe console.
- Offline pytest suite (40 tests) including a regression that proves the verifier
  flags the exact corruption that broke the previous run; ruff lint; CI matrix on
  Python 3.10-3.13 plus a `node --check` of the userscript.

[0.1.0]: https://github.com/davidmalko87/gemini-chat-exporter/releases/tag/v0.1.0
