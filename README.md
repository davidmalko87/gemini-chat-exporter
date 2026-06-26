# Gemini Chat Exporter

[![CI](https://github.com/davidmalko87/gemini-chat-exporter/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/davidmalko87/gemini-chat-exporter/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Userscript](https://img.shields.io/badge/userscript-Tampermonkey-00485B.svg?logo=tampermonkey&logoColor=white)](#install)
[![Sources](https://img.shields.io/badge/sources-userscript%20%7C%20Takeout-success.svg)](#two-ways-to-export--and-why-it-matters)
[![Output](https://img.shields.io/badge/output-JSON%20%7C%20Markdown-success.svg)](#what-gets-exported)
[![Verified](https://img.shields.io/badge/corruption-verified-success.svg)](#-verified)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](#)
[![Last commit](https://img.shields.io/github/last-commit/davidmalko87/gemini-chat-exporter.svg)](https://github.com/davidmalko87/gemini-chat-exporter/commits/master)
[![GitHub issues](https://img.shields.io/github/issues/davidmalko87/gemini-chat-exporter.svg)](https://github.com/davidmalko87/gemini-chat-exporter/issues)

**Export & back up your Google Gemini chat history** to **JSON + Markdown** — from a
hardened **browser userscript** or from **Google Takeout** — with a built-in
**verifier** that refuses to let a silently corrupt export pass for a good one.
Fully local, no API key, no servers, no telemetry.

---

## Why?

Getting your own Gemini conversations out, completely and faithfully, is harder than it
should be:

- **Google Takeout used to omit full transcripts.** It now includes prompts *and*
  responses (My Activity > Gemini Apps), but the schema varies by account and is
  under-documented — you have to verify what you actually got.
- **The page HTML has no conversation content.** Gemini is an Angular SPA; transcripts
  are rendered client-side after load, and `gemini.google.com` blocks iframing and
  background fetches. So a scraper has to drive the real, logged-in UI.
- **A naive scraper fails silently — and that is worse than failing loudly.** A prior
  run of an earlier exporter scraped 473 conversations but only the first ~190 had real
  bodies. The rest were overwritten with one duplicated stub, while it reported *zero
  errors*. "Zero exceptions" is not "zero wrong content":

```
[FAIL] 285/473 conversations (60.3%) share a body with another conversation
       - exceeds the 2.0% threshold. This is the duplicate-stub corruption fingerprint.
[FAIL] contiguous duplicate run: conversations #193-#473 (281 in a row) all share
       one body ("Spheres for Self-Realization") - classic stale-page corruption
RESULT: FAIL
```

That report is this tool's verifier running on the actual corrupt file. The whole
project is built so that failure mode can never go unnoticed again.

For backing up other platforms, see the sibling project
[`jira-project-backup-restore`](https://github.com/davidmalko87/jira-project-backup-restore).

---

## Two ways to export — and why it matters

| Route | Fidelity | Cost / risk | Role |
|---|---|---|---|
| **Userscript / console scraper** (JS) | Full multi-turn transcripts | Undocumented selectors; fragile; *can* lag the UI | Convenient live capture — hardened |
| **Google Takeout** (Python importer) | Authoritative — Google generates it | Manual export; schema varies; My Activity is prompt-centric | Trustworthy / recovery route |
| **Verifier** (Python) | — | — | The safety net: proves an export is distinct & complete before you trust it |

Use the scraper for convenience, Takeout for ground truth, and **always run the
verifier** on whatever you get. `reconcile` can diff the two and recover conversations
the scraper got wrong from Takeout.

---

## Features

| Feature | Description |
|---|---|
| **Content-identity validation** | The scraper won't save a conversation until the URL id + first prompt match the target **and differ from the previous one** — the guard the old tool lacked |
| **Duplicate-body guard** | Each body is SHA-256 hashed; a body identical to the previous one is retried once, then marked `failed` instead of saved |
| **Streaming writes + resume** | Conversations stream to disk one at a time (no giant in-memory string); already-saved ids are skipped on re-run |
| **Fail loudly** | Zero links or zero conversation containers throws a clear "DOM may have changed" error instead of emitting empty output |
| **Independent verifier** | `--verify` audits any export for duplicate bodies, ratio, contiguous runs, duplicate/missing ids; exits non-zero for cron/CI |
| **Schema-tolerant Takeout import** | Handles both the My Activity array form and the conversations object form |
| **JSON + Markdown + manifest** | Per-conversation files plus `manifest.json` with checksums and a `complete` flag tied to verification |
| **Reconcile** | Diffs a scraper export against Takeout and flags which corrupt conversations are recoverable |

---

## Install

**The exporter (browser side)** — install a userscript manager
([Tampermonkey](https://www.tampermonkey.net/) / Greasemonkey), then add
[`userscript/gemini-chat-exporter.user.js`](userscript/gemini-chat-exporter.user.js).
No userscript manager? Paste
[`userscript/console-snippet.js`](userscript/console-snippet.js) into the DevTools
console instead.

**The toolkit (verify / import / convert)** — clone and run with Python **3.10+**:

```bash
git clone https://github.com/davidmalko87/gemini-chat-exporter.git
cd gemini-chat-exporter
pip install -r requirements.txt
```

---

## Quick Start

### 1. Capture your conversations

- **Userscript:** open <https://gemini.google.com/>, sign in, click **"GCE: Export
  all"** (bottom-right), and choose where to save `gemini_chats.ndjson`.
- **Takeout (authoritative):** [Google Takeout](https://takeout.google.com/) >
  **My Activity** > **Gemini Apps** > JSON. (The standalone "Gemini" option exports
  Gems, not your chats.)

### 2. Verify (do this every time)

```bash
python main.py --verify gemini_chats.ndjson        # exits non-zero if corrupt
```

### 3. Convert to JSON + Markdown

```bash
python main.py --convert gemini_chats.ndjson --out ./out
python main.py --import-takeout "Takeout/My Activity/Gemini Apps/MyActivity.json" --out ./out
python main.py --reconcile gemini_chats.ndjson MyActivity.json   # recover corrupt rows
```

### Or use the interactive menu

```bash
python main.py
```

```
==================================================
  Gemini Chat Exporter v0.1.0
==================================================
  --- Verify ---
  1) Verify / audit an export for corruption
  --- Import & convert ---
  2) Import a Google Takeout export
  3) Convert an export to JSON + Markdown
  --- Reconcile ---
  4) Reconcile a scraper export against Takeout
  0) Exit
```

---

## What Gets Exported

| File | Contents |
|---|---|
| `gemini_chats.ndjson` | Scraper output: one JSON conversation per line (`id`, `title`, `turns`, `source`, `flags`) — streaming-friendly and resumable |
| `NNNN_<slug>_<id>.json` | One structured JSON file per conversation (ASCII filename; UTF-8 content) |
| `NNNN_<slug>_<id>.md` | One readable Markdown transcript per conversation (David / Gemini headers) |
| `manifest.json` | Per-file SHA-256 checksums, body hashes, counts, and a `complete` flag that is only `true` when verification passed |

---

## ✅ Verified

This tool's verifier is **proven against the real corrupt export** that prompted the
project: it correctly flags 285/473 conversations as sharing a duplicated body, names
the dominant stub (281x), and pinpoints the contiguous corruption run (#193-#473) — and
exits non-zero. A clean synthetic export passes end-to-end (scrape format -> verify ->
JSON/Markdown -> manifest with `complete: true`). The regression test that asserts this
runs in CI on every push.

Honest framing: the **scraper is best-effort** and depends on undocumented Gemini
internals; **Google Takeout is the authoritative route** for guaranteed-complete
history. The verifier exists precisely so you never have to take either source on faith.
An export is only "verified" once the verifier passes it — structural validity alone is
not enough.

---

## Known Limitations

These are platform/source constraints, stated honestly — not all of them are fixable:

| Area | Status | Notes |
|---|---|---|
| Gemini DOM selectors | Will break over time | Undocumented Angular internals; update `CONFIG` in the userscript when scraping returns nothing. The tool fails loudly when this happens. |
| Takeout "My Activity" | Prompt-centric | Often one record per prompt and frequently **no model response**; counted and reported. Prefer the per-conversation Takeout form or the scraper for full transcripts, then `reconcile`. |
| Images / Canvas / Gems | Not captured | Image-only replies are flagged (empty model text); generated images, Canvas docs, and Gems are out of scope. |
| Already-corrupted dumps | Not recoverable from themselves | Once a body was overwritten by a stub it is gone; recover those ids from Takeout via `reconcile`. |
| Re-importing into Gemini | Not possible | There is no write API; this is export/backup only (no "restore"). |

---

## Project Structure

```
gemini-chat-exporter/
├── main.py                       # Entry point - interactive menu + CLI flags
├── userscript/
│   ├── gemini-chat-exporter.user.js   # Hardened Tampermonkey scraper
│   └── console-snippet.js             # DevTools-paste fallback
├── gemini_export/
│   ├── models.py                 # Conversation/Turn model + body hashing (dup detection)
│   ├── config.py                 # Optional .env loader and validation
│   ├── parsers.py                # NDJSON / legacy-txt / JSON readers
│   ├── verify.py                 # The safety net: corruption + completeness audit
│   ├── takeout.py                # Schema-tolerant Google Takeout importer
│   ├── convert.py                # Per-conversation JSON + Markdown + manifest (SHA-256)
│   ├── reconcile.py              # Diff scraper export vs Takeout
│   ├── cli.py                    # Argparse CLI (UTF-8-safe console)
│   └── menu.py                   # Interactive menu
├── tests/                        # 40 offline pytest cases (synthetic fixtures only)
├── .github/workflows/ci.yml      # ruff + pytest (3.10-3.13) + node --check userscript
└── PROMPTS.md                    # Agent-Coding Kit (the workflow that built this)
```

---

## Configuration Reference

The tool needs no credentials. Optional tunables live in `.env` (copy from
`.env.example`) or as CLI flags:

| Setting | CLI flag | Default | Description |
|---|---|---|---|
| `OUTPUT_ROOT` | `--out DIR` | `./out` | Where converted output is written |
| `DUP_RATIO_FAIL` | `--dup-ratio F` | `0.02` | Fail if more than this fraction of conversations share a body |
| `MIN_RUN` | — | `5` | Min consecutive same-body run length to flag |
| `WRITE_JSON` | `--md-only` disables | `true` | Emit per-conversation JSON |
| `WRITE_MARKDOWN` | `--json-only` disables | `true` | Emit per-conversation Markdown |
| — | `--dry-run` | off | Compute everything, write nothing |

---

## Requirements

- Python **3.10+**
- [`python-dotenv`](https://pypi.org/project/python-dotenv/) >= 1.0 (the only runtime dependency)
- A browser + userscript manager (for live scraping); the toolkit itself is offline

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full version history.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: no personal data in the repo,
synthetic test fixtures only, ASCII console output, fail loudly, prove it with the
verifier.

## License

[MIT](LICENSE)

## Related

- [`jira-project-backup-restore`](https://github.com/davidmalko87/jira-project-backup-restore)
  — backup & restore individual Jira Cloud projects via REST API.

<!--
GitHub repo "About" settings (the SEO layer, set in the repo's About panel):
DESCRIPTION:
  Export & back up your Google Gemini chat history to JSON + Markdown - via browser
  userscript or Google Takeout - with a built-in completeness/corruption verifier.
  Local & private, no API key.
TOPICS:
  google-gemini, gemini, gemini-ai, chat-export, conversation-export, chat-history,
  backup, data-export, google-takeout, data-portability, userscript, tampermonkey,
  markdown, json, web-scraping, cli, python, archiving
-->
