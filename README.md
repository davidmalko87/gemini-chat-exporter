# Gemini Chat Exporter

[![CI](https://github.com/davidmalko87/gemini-chat-exporter/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/davidmalko87/gemini-chat-exporter/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/gemini-chat-exporter.svg)](https://pypi.org/project/gemini-chat-exporter/)
[![PyPI downloads](https://img.shields.io/pypi/dm/gemini-chat-exporter.svg)](https://pypi.org/project/gemini-chat-exporter/)
[![Python](https://img.shields.io/pypi/pyversions/gemini-chat-exporter.svg?logo=python&logoColor=white)](https://pypi.org/project/gemini-chat-exporter/)
[![Userscript](https://img.shields.io/badge/userscript-Tampermonkey-00485B.svg?logo=tampermonkey&logoColor=white)](#install)
[![Sources](https://img.shields.io/badge/sources-userscript%20%7C%20Takeout-success.svg)](#two-ways-to-export--and-why-it-matters)
[![Output](https://img.shields.io/badge/output-JSON%20%7C%20Markdown-success.svg)](#what-gets-exported)
[![Verified](https://img.shields.io/badge/corruption-verified-success.svg)](#-verified)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/davidmalko87/gemini-chat-exporter/blob/master/LICENSE)
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

- **Google Takeout is prompt-centric.** My Activity > Gemini Apps includes your
  prompts, but often no model response, and the schema varies by account and is
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
 │  scrapes chats   │   saves    │   → gemini-export --verify    │
 └──────────────────┘            │   → gemini-export --convert   │
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
| **Verifier** (Python) | — | — | The safety net: catches duplicate-body / stale-page corruption and duplicate ids before you trust an export |

Use the scraper for convenience, Takeout for ground truth, and **always run the
verifier** on whatever you get (`--import-takeout` runs it for you on Takeout files).
`reconcile` diffs the two and lists which corrupt scraper conversations Takeout can
replace.

---

## Features

| Feature | Description |
|---|---|
| **Content-identity validation** | The scraper won't save a conversation until the URL id matches the target and the first prompt is present **and differs from the previous one** — the guard the old tool lacked |
| **Duplicate-body guard** | Each body is SHA-256 hashed; a body identical to the previous one is retried once, then marked `failed` instead of saved |
| **Streaming writes + resume** | Each conversation is written as one NDJSON line to the file you picked (or buffered and downloaded at the end when there is no save dialog); the file is committed when the run finishes. Already-saved ids are skipped on re-run |
| **Fail loudly** | Zero sidebar links aborts with a clear error instead of emitting empty output; a chat whose content never renders is marked `failed`, not saved |
| **Independent verifier** | `--verify` audits any export for duplicate bodies, ratio, contiguous runs and duplicate ids; exits non-zero for cron/CI |
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
> [`userscript/console-snippet.js`](https://raw.githubusercontent.com/davidmalko87/gemini-chat-exporter/master/userscript/console-snippet.js), open
> <https://gemini.google.com/>, press **F12 ▸ Console**, paste it, and press Enter.

### 2. Python toolkit — the verify / convert step

Requires **Python 3.10+**.

**Via PyPI (recommended)** — provides the `gemini-export` command:

```bash
pip install gemini-chat-exporter
```

**Or as an isolated app with [pipx](https://pipx.pypa.io/)** — keeps its dependencies out of your global Python:

```bash
pipx install gemini-chat-exporter
```

**Upgrade:**

```bash
pip install -U gemini-chat-exporter              # pipx: pipx upgrade gemini-chat-exporter
```

**Or clone and run from source** (development):

```bash
git clone https://github.com/davidmalko87/gemini-chat-exporter.git
cd gemini-chat-exporter
pip install -r requirements.txt
python main.py --help           # same flags as gemini-export
```

> **Where files live:** everything is relative to the folder you run `gemini-export`
> from. An optional `.env` is read only from that folder (variables already set in
> your shell win), `--verify` / `--reconcile` write `verify_report.json` /
> `reconcile_report.json` into it (or into `--out DIR`, which must already exist),
> and converted output goes to `./out` (change it with `--out DIR` or `OUTPUT_ROOT`).
> There is no log file and nothing is written to your home or install folder; a
> clone behaves the same way.

Check it works:

```bash
gemini-export --help             # all flags
gemini-export --version          # installed version
```

From a clone, use `python main.py` in place of `gemini-export` — the flags are identical.

---

## Quick Start

> Install both pieces first (see [Install](#install)).

### Step 1 — Capture your chats from the browser

1. Open **<https://gemini.google.com/>** and make sure you are **signed in**.
2. Click the blue **"GCE: Export all"** button in the **bottom-right** of the page.
3. Watch the button — it walks through these states:
   - **`GCE: loading list... N`** — it opens the sidebar and scrolls your whole
     chat list (can take a minute for hundreds of chats).
   - A **save dialog** may appear — choose where to put **`gemini_chats.ndjson`**.
     *(If it doesn't — your browser lacks the picker, or loading a long list took
     too long — the file just downloads at the end instead.)*
   - **`GCE: 12/542`** — it exports each conversation in turn. **Keep the tab open
     and in front.** A full history takes roughly **30–45 minutes**.
4. When it's done you get an alert: *"Done. N saved, M skipped, K failed..."*.

It is built to be safe and unattended-friendly:

- opens the sidebar if collapsed, and **re-opens it if it collapses mid-run**;
- loads the **full** lazy-paginated list (not just the first page);
- **skips chats already saved** when you run it again (resume) — but the file is
  only written when a run finishes, so **keep the tab open until the "Done"
  alert** (see [Troubleshooting](#troubleshooting) if a run was interrupted);
- **refuses stale or duplicate pages it detects** — those are marked `failed` and
  retried on the next run, instead of silently corrupting your backup.

> **Prefer not to scrape?** Use Google Takeout as the source instead — it's the
> authoritative route. At [takeout.google.com](https://takeout.google.com/):
> *Deselect all* ▸ select **"My Activity"** ▸ set format to **JSON** ▸ click
> *"All activity data included"* and keep only **"Gemini Apps"** ▸ export.
> (The standalone **"Gemini"** product exports *Gems*, not your chats.) Then go
> to Step 3 and use `--import-takeout`.

### Step 2 — Verify the capture (always do this)

Run this in the folder that holds `gemini_chats.ndjson`, or pass the file's full
path (e.g. `~/Downloads/gemini_chats.ndjson`):

```bash
gemini-export --verify gemini_chats.ndjson
```

You want **`RESULT: PASS`**. If it fails, the report names exactly what's wrong
(duplicate bodies, a stale-page run, duplicate ids) — **don't trust the export
until it passes**. (`--verify` exits non-zero on failure, so it fits cron/CI. It
also saves the report as `verify_report.json` in the current folder.)

A PASS means no corruption was found, not that every chat was captured: chats the
userscript marked `failed` only show up as a "no model text" warning, so also check
the *K failed* count in the final alert.

### Step 3 — Convert to JSON + Markdown

```bash
# from a scraper capture:
gemini-export --convert gemini_chats.ndjson --out ./out

# ...or straight from a Google Takeout export:
gemini-export --import-takeout "Takeout/My Activity/Gemini Apps/MyActivity.json" --out ./out
```

You get one `.json` and one `.md` per conversation in `./out/`, plus a
`manifest.json` (checksums + a `complete` flag). To see which corrupt chats
Takeout can replace, diff the capture against Takeout:

```bash
gemini-export --reconcile gemini_chats.ndjson MyActivity.json
```

The console shows counts; the ids of the recoverable conversations are listed in
`reconcile_report.json` (written to the current folder). Reconcile only reports —
it does not change or merge either file.

### More examples

**Verify:**

```bash
gemini-export --validate gemini_chats.ndjson                  # same as --verify
gemini-export --verify gemini_chats.ndjson --dup-ratio 0.05   # custom duplicate threshold (0..1)
```

**Convert / import:**

```bash
gemini-export --convert gemini_chats.ndjson --out ./out --md-only   # Markdown only (--json-only: JSON only)
gemini-export --convert gemini_chats.ndjson --dry-run               # verify and count, write no files
gemini-export --import-takeout takeout-export.zip --out ./out       # a Takeout .zip or extracted folder
```

**Accepted inputs:** `--verify` / `--convert` read the scraper's `.ndjson`, a JSON
array (or `{"conversations": [...]}`), or the legacy delimited `.txt` export.
`--import-takeout` takes `MyActivity.json`, a Takeout `.zip`, or the extracted
folder — use the `.zip` / folder only when the export contains just *My Activity ▸
Gemini Apps* (as in the recipe above); otherwise point it at `MyActivity.json`.
Don't run `--verify` on a Takeout file; `--import-takeout` verifies it for you.

### Don't like flags? Use the menu

From a clone, run `python main.py` with **no arguments** for an interactive menu
(the installed `gemini-export` command has no menu — with no arguments it prints
its help):

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
| **A few chats marked `failed`** | Normal for very large conversations that don't finish rendering in time. Click **"Export all"** again — it retries only the failures (resume skips the rest). The re-run's file holds **only** the retried chats: keep it next to the first one (saving over `gemini_chats.ndjson` replaces your first capture), then verify and convert it separately (e.g. `--out ./out-retry`). |
| **A run was interrupted** (tab closed, browser crashed) | The file is only written when a run finishes, but the chats it reached are already remembered as saved, so a re-run would skip them. Before running again, clear the resume state: **F12 ▸ Application ▸ Local Storage ▸ `https://gemini.google.com`** ▸ delete `gce_saved_ids_v1`. |
| **Where did the file go?** | Wherever you chose in the save dialog. If no save dialog appeared, it's in your **Downloads** as `gemini_chats.ndjson`. |
| **`python: command not found`** | Try `python3`, or install **Python 3.10+**. |
| **`gemini-export: command not found`** | pip put the command in a scripts folder that isn't on your `PATH`. Use `pipx install gemini-chat-exporter` (then `pipx ensurepath` and open a new terminal), or activate the virtual environment you installed it into. From a clone, use `python main.py` instead. |
| **`error: externally-managed-environment`** | Your system Python (e.g. Debian/Ubuntu, Homebrew) blocks global `pip install` (PEP 668). Use `pipx install gemini-chat-exporter`, or create a virtual environment first: `python3 -m venv .venv`, activate it, then `pip install gemini-chat-exporter`. |
| **Verify says `FAIL`** | That's the safety net doing its job. Read the report, then re-capture or recover the flagged chats from Takeout before trusting the backup. |
| **Selectors broke after a Gemini update** | If a capture suddenly returns nothing, Gemini changed its DOM. Update the `CONFIG` selectors at the top of [`userscript/gemini-chat-exporter.user.js`](https://github.com/davidmalko87/gemini-chat-exporter/blob/master/userscript/gemini-chat-exporter.user.js) (or open an issue). |

---

## What Gets Exported

| File | Contents |
|---|---|
| `gemini_chats.ndjson` | Scraper output: one JSON conversation per line (`id`, `title`, `turns`, `source`, `flags`) — streaming-friendly and resumable |
| `NNNN_<slug>.json` | One structured JSON file per conversation (ASCII filename slugged from the title, or the conversation id when the title has no Latin letters or digits; UTF-8 content) |
| `NNNN_<slug>.md` | One readable Markdown transcript per conversation (David / Gemini headers) |
| `manifest.json` | Per-file SHA-256 checksums, body hashes, counts, and a `complete` flag that is only `true` when verification passed |
| `verify_report.json` | Full audit from `--verify` / `--validate`, written to the current folder (or `--out DIR`) |
| `reconcile_report.json` | Counts and the recoverable / corrupt conversation ids from `--reconcile`, written to the current folder (or `--out DIR`) |

---

## ✅ Verified

This tool's verifier is **proven against the real corrupt export** that prompted the
project: it correctly flags 285/473 conversations as sharing a duplicated body, names
the dominant stub (281x), and pinpoints the contiguous corruption run (#193-#473) — and
exits non-zero. That file is personal data and is not in the repo, so CI runs a
synthetic regression fixture with the same shape (a duplicated stub in a contiguous run)
on every push to `master` and every pull request, plus a clean synthetic export that
must pass. Both fixtures use the
legacy `.txt` format; there is no NDJSON (scrape-format) fixture yet.

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
| Gemini DOM selectors | Will break over time | Undocumented Angular internals; update `CONFIG` in the userscript when scraping returns nothing. If the sidebar links stop matching, the export aborts with an error; if the conversation content stops matching, chats are marked `failed` (watch the failed count). |
| Takeout "My Activity" | Prompt-centric | Often one record per prompt and frequently **no model response**; counted and reported (`without_response`). Use the scraper for full transcripts, and `reconcile` to cross-check. |
| Images / Canvas / Gems | Not captured | Image-only replies are flagged (empty model text); generated images, Canvas docs, and Gems are out of scope. |
| Already-corrupted dumps | Not recoverable from themselves | Once a body was overwritten by a stub it is gone; `reconcile` lists which of those ids Takeout still has. |
| Re-importing into Gemini | Not possible | There is no write API; this is export/backup only (no "restore"). |

---

## Project Structure

```
gemini-chat-exporter/
├── main.py                       # From a clone: interactive menu (no args) + CLI flags
├── pyproject.toml                # Package metadata; installs the gemini-export command
├── requirements.txt              # Runtime dependency for a clone (python-dotenv)
├── .env.example                  # Optional settings template
├── userscript/
│   ├── gemini-chat-exporter.user.js   # Hardened Tampermonkey scraper
│   ├── console-snippet.js             # DevTools-paste fallback
│   └── README.md                      # Browser-capture install + usage
├── gemini_export/
│   ├── __init__.py               # Package version
│   ├── models.py                 # Conversation/Turn model + body hashing (dup detection)
│   ├── config.py                 # Optional .env loader and validation
│   ├── parsers.py                # NDJSON / legacy-txt / JSON readers
│   ├── verify.py                 # The safety net: corruption + duplicate-id audit
│   ├── takeout.py                # Schema-tolerant Google Takeout importer
│   ├── convert.py                # Per-conversation JSON + Markdown + manifest (SHA-256)
│   ├── reconcile.py              # Diff scraper export vs Takeout
│   ├── cli.py                    # Argparse CLI behind gemini-export (UTF-8-safe console)
│   └── menu.py                   # Interactive menu
├── tests/                        # 40 offline pytest cases (synthetic fixtures only)
├── .github/
│   ├── workflows/ci.yml          # ruff + pytest (3.10-3.13) + node --check userscript
│   ├── workflows/publish.yml     # Publishes to PyPI when a GitHub Release is published
│   └── dependabot.yml            # Monthly dependency update PRs
├── CHANGELOG.md                  # Version history
├── CONTRIBUTING.md               # Ground rules + release steps
├── LICENSE                       # MIT
└── PROMPTS.md                    # Agent-Coding Kit (the workflow that built this)
```

---

## Configuration Reference

The tool needs no credentials. Optional tunables can be set as environment
variables, in a `.env` file in the folder you run `gemini-export` from, or as CLI
flags (flags win over both; variables already set in your shell win over `.env`).
`.env.example` is not included in the PyPI package, so create `.env` yourself:

```ini
OUTPUT_ROOT=./out
DUP_RATIO_FAIL=0.02
MIN_RUN=5
```

…or download the template (from a clone: `cp .env.example .env`):

```bash
curl -o .env https://raw.githubusercontent.com/davidmalko87/gemini-chat-exporter/master/.env.example
```

| Setting | CLI flag | Default | Description |
|---|---|---|---|
| `OUTPUT_ROOT` | `--out DIR` | `./out` | Where converted output is written (`--out` also moves the report files) |
| `DUP_RATIO_FAIL` | `--dup-ratio F` | `0.02` | Fail if more than this fraction (0..1) of conversations share a body |
| `MIN_RUN` | — | `5` | Min consecutive same-body run length to flag |
| — | `--json-only` | off | Write only the per-conversation JSON (skip Markdown) |
| — | `--md-only` | off | Write only the Markdown transcripts (skip JSON) |
| — | `--dry-run` | off | For `--convert` / `--import-takeout`: verify and count, but write no files (`--verify` / `--reconcile` still write their report) |

`WRITE_JSON` / `WRITE_MARKDOWN` from older `.env` files no longer change the output
(and setting both to `false` is rejected as invalid); remove them and use
`--json-only` / `--md-only`.

---

## Requirements

- Python **3.10+**
- [`python-dotenv`](https://pypi.org/project/python-dotenv/) >= 1.0 (the only runtime dependency)
- A browser + userscript manager (for live scraping); the toolkit itself is offline

---

## Changelog

See [CHANGELOG.md](https://github.com/davidmalko87/gemini-chat-exporter/blob/master/CHANGELOG.md) for the full version history.

## Contributing

See [CONTRIBUTING.md](https://github.com/davidmalko87/gemini-chat-exporter/blob/master/CONTRIBUTING.md). In short: no personal data in the repo,
synthetic test fixtures only, ASCII console output, fail loudly, prove it with the
verifier.

## License

[MIT](https://github.com/davidmalko87/gemini-chat-exporter/blob/master/LICENSE)

## Related

- [`jira-project-backup-restore`](https://github.com/davidmalko87/jira-project-backup-restore)
  — backup & restore individual Jira Cloud projects via REST API.

<!--
GitHub repo "About" settings (the SEO layer, set in the repo's About panel):
DESCRIPTION:
  Export & back up your Google Gemini chat history to JSON + Markdown - via browser
  userscript or Google Takeout - with a built-in corruption (duplicate/stale-page)
  verifier. Local & private, no API key.
TOPICS:
  google-gemini, gemini, gemini-ai, chat-export, conversation-export, chat-history,
  backup, data-export, google-takeout, data-portability, userscript, tampermonkey,
  markdown, json, web-scraping, cli, python, archiving, data-integrity
-->
