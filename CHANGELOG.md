# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.3] - 2026-06-27

### Fixed

- **Exports stalled partway with a runaway FAIL count** (e.g. "233/542 (FAIL 50)").
  Diagnosed live: on a long run the left sidebar can collapse mid-export (a very
  large conversation spikes memory and the SPA sheds the list), dropping every
  `a[href^="/app/"]` anchor. Navigation then fell back to a URL change, which
  Gemini renders as a blank shell, so each remaining chat burned the full ~20s
  timeout and was marked FAIL. Now `navigateTo()` calls `ensureSidebarOpen()`
  first (re-opens the rail if it collapsed) and falls back to scrolling the list
  to bring the target anchor into view; if no clickable anchor can be found the
  chat is marked failed immediately instead of grinding for 20s on a blank shell.
  Verified live: recovered from a forced collapse and navigated to conversation
  #500 of 542.

## [0.1.2] - 2026-06-27

### Fixed

- **Userscript collected only a partial list (e.g. 333 of 540+ chats).** Confirmed
  live: Gemini's chat list is **lazy-paginated** - only the first few hundred
  conversations load initially, and scrolling to the bottom fetches the next page.
  The previous scroll-then-snapshot stopped early (during a pagination pause) and
  captured a single incomplete snapshot. The exporter now harvests with
  `harvestConversations()`: it repeatedly jumps to the bottom and **accumulates
  ids across scroll steps** until no new ones appear for several rounds.
- Navigation now re-finds a live sidebar anchor by id at click time (a stored
  element can go stale after scrolling, and a direct `/app/{id}` load renders only
  the shell, so clicking a live anchor is required).

## [0.1.1] - 2026-06-27

### Fixed

- **Userscript "No conversation links found" on a collapsed sidebar.** Verified
  empirically against a live account: when Gemini's left sidebar is collapsed it
  renders **zero** `a[href^="/app/"]` anchors, so the exporter found nothing and
  (correctly) failed loud. The selectors were never broken. The exporter now runs
  `ensureListLoaded()` first - it opens the sidebar, expands the "Recent" section,
  and scrolls the virtualized list to materialize every conversation before
  collecting. The error message now tells the user to open the sidebar.
- **Harden the render-wait against transient DOM accumulation.** During SPA
  navigation Gemini briefly leaves stale conversation containers in the DOM; the
  stability check now requires the container *count* (not just text length) to be
  stable across reads, so a conversation is never scraped mid-transition.

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

[0.1.3]: https://github.com/davidmalko87/gemini-chat-exporter/releases/tag/v0.1.3
[0.1.2]: https://github.com/davidmalko87/gemini-chat-exporter/releases/tag/v0.1.2
[0.1.1]: https://github.com/davidmalko87/gemini-chat-exporter/releases/tag/v0.1.1
[0.1.0]: https://github.com/davidmalko87/gemini-chat-exporter/releases/tag/v0.1.0
