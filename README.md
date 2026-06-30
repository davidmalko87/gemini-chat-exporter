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

## How it works

It is **two steps**, and they use two different tools:

1. **Capture** — a browser userscript adds an **"Export all"** button to Gemini.
   It clicks through every conversation and streams them to one file,
   `gemini_chats.ndjson`. *(This part runs in your browser because Gemini only
   renders chats in the logged-in UI.)*
2. **Process** — a small Python toolkit reads that file, **verifies** it isn't
   corrupt, and **converts** it to readable per-conversation JSON + Markdown.

```
 Browser (userscript)            Your computer (Python)
 ┌──────────────────┐            ┌───────────────────────────────┐
 │ "Export all" btn │ ─────────► │ gemini_chats.ndjson           │
 │  scrapes chats   │   saves    │   → python main.py --verify   │
 └──────────────────┘            │   → python main.py --convert  │
                                 │   → out/*.json + *.md         │
                                 └───────────────────────────────┘
```

> Don't want to scrape? Skip step 1 and feed a **Google Takeout** export into
> step 2 instead (`--import-takeout`). See [Quick Start](#quick-start).

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

You install **two pieces** — the browser userscript (captures chats) and the
Python toolkit (verifies + converts).

### 1. Browser userscript — the capture step

1. Install a userscript manager — **[Tampermonkey](https://www.tampermonkey.net/)**
   (Chrome, Edge, Firefox, Safari) is the easiest.
2. Open this raw file and click **Install** in the dialog Tampermonkey shows:
   **[gemini-chat-exporter.user.js](https://raw.githubusercontent.com/davidmalko87/gemini-chat-exporter/master/userscript/gemini-chat-exporter.user.js)**
3. In the Tampermonkey dashboard, confirm the script header reads
   **`@version 0.1.3`** (or newer). To update later: Tampermonkey ▸ *Check for
   userscript updates*.

> **No userscript manager?** You don't need one. Copy all of
> [`userscript/console-snippet.js`](userscript/console-snippet.js), open
> <https://gemini.google.com/>, press **F12 ▸ Console**, paste it, and press Enter.

### 2. Python toolkit — the verify / convert step

Requires **Python 3.10+**.

```bash
git clone https://github.com/davidmalko87/gemini-chat-exporter.git
cd gemini-chat-exporter
pip install -r requirements.txt
```

Check it works:

```bash
python main.py --help
```

---

## Quick Start

> Install both pieces first (see [Install](#install)).

### Step 1 — Capture your chats from the browser

1. Open **<https://gemini.google.com/>** and make sure you are **signed in**.
2. Click the blue **"GCE: Export all"** button in the **bottom-right** of the page.
3. Watch the button — it walks through these states:
   - **`GCE: loading list... N`** — it opens the sidebar and scrolls your whole
     chat list (can take a minute for hundreds of chats).
   - A **save dialog** appears — choose where to put **`gemini_chats.ndjson`**.
     *(If your browser doesn't support the picker, the file just downloads at the
     end instead.)*
   - **`GCE: 12/542`** — it exports each conversation in turn. **Keep the tab open
     and in front.** A full history takes roughly **30–45 minutes**.
4. When it's done you get an alert: *"Done. N saved, M skipped, K failed..."*.

It is built to be safe and unattended-friendly:

- opens the sidebar if collapsed, and **re-opens it if it collapses mid-run**;
- loads the **full** lazy-paginated list (not just the first page);
- **skips chats already saved**, so you can stop and re-run any time (resume);
- **never saves a stale or duplicate page** — those are marked `failed` and
  retried on the next run, instead of silently corrupting your backup.

> **Prefer not to scrape?** Use Google Takeout as the source instead — it's the
> authoritative route. At [takeout.google.com](https://takeout.google.com/):
> *Deselect all* ▸ select **"My Activity"** ▸ set format to **JSON** ▸ click
> *"All activity data included"* and keep only **"Gemini Apps"** ▸ export.
> (The standalone **"Gemini"** product exports *Gems*, not your chats.) Then go
> to Step 3 and use `--import-takeout`.

### Step 2 — Verify the capture (always do this)

```bash
python main.py --verify gemini_chats.ndjson
```

You want **`RESULT: PASS`**. If it fails, the report names exactly what's wrong
(duplicate bodies, a stale-page run, missing chats) — **don't trust the export
until it passes**. (`--verify` exits non-zero on failure, so it fits cron/CI.)

### Step 3 — Convert to JSON + Markdown

```bash
# from a scraper capture:
python main.py --convert gemini_chats.ndjson --out ./out

# ...or straight from a Google Takeout export:
python main.py --import-takeout "Takeout/My Activity/Gemini Apps/MyActivity.json" --out ./out
```

You get one `.json` and one `.md` per conversation in `./out/`, plus a
`manifest.json` (checksums + a `complete` flag). To recover chats a scrape got
wrong, diff against Takeout:

```bash
python main.py --reconcile gemini_chats.ndjson MyActivity.json
```

### Don't like flags? Use the menu

Run `python main.py` with **no arguments** for an interactive menu:

```
==================================================
  Gemini Chat Exporter v0.1.3
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

## Troubleshooting

| What you see | Why, and what to do |
|---|---|
| **"No conversation links found"** | The left sidebar was collapsed (only an issue on v0.1.1 and earlier). **Update to v0.1.3+** — it opens the sidebar automatically. One-off workaround: open the left sidebar so your chats are visible, then click Export. |
| **Total looks too low** (e.g. `X/333` when you have more chats) | An old version didn't load the lazy-paginated list. **Update to v0.1.2+.** |
| **Looks stuck; `FAIL` keeps climbing** | On a long run the sidebar collapsed and an old version couldn't recover. **Update to v0.1.3+** (it re-opens the sidebar and continues). |
| **A few chats marked `failed`** | Normal for very large conversations that don't finish rendering in time. Click **"Export all"** again — it retries only the failures (resume skips the rest). |
| **Where did the file go?** | Wherever you chose in the save dialog. If your browser lacks that dialog, it's in your **Downloads** as `gemini_chats.ndjson`. |
| **`python: command not found`** | Try `python3`, or install **Python 3.10+**. |
| **Verify says `FAIL`** | That's the safety net doing its job. Read the report, then re-capture or recover the flagged chats from Takeout before trusting the backup. |
| **Selectors broke after a Gemini update** | If a capture suddenly returns nothing, Gemini changed its DOM. Update the `CONFIG` selectors at the top of [`userscript/gemini-chat-exporter.user.js`](userscript/gemini-chat-exporter.user.js) (or open an issue). |

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
│   ├── console-snippet.js             # DevTools-paste fallback
│   └── README.md                      # Browser-capture install + usage
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
