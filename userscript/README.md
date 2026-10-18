# Userscript — the capture step

This folder holds the browser side of [Gemini Chat Exporter](../README.md): it adds
an **"Export all"** button to Gemini and saves every conversation to a single
`gemini_chats.ndjson` file. You then verify and convert that file with the Python
toolkit in the repo root.

Two options — pick one. The Tampermonkey script is the full tool; the console
snippet is a minimal fallback with **no resume, no save dialog and no duplicate
retry** — it keeps everything in memory and downloads one file at the end, so
closing the tab loses the run.

## Option A: Tampermonkey (recommended)

1. Install **[Tampermonkey](https://www.tampermonkey.net/)** (Chrome, Edge, Firefox, Safari).
2. Open this raw file and click **Install** in the dialog:
   [`gemini-chat-exporter.user.js`](https://raw.githubusercontent.com/davidmalko87/gemini-chat-exporter/master/userscript/gemini-chat-exporter.user.js)
3. Confirm the header says **`@version 0.1.3`** or newer.

## Option B: Console snippet (no extension)

1. Open <https://gemini.google.com/> (signed in).
2. Press **F12 ▸ Console**.
3. Paste all of [`console-snippet.js`](console-snippet.js) and press Enter.

## Run it

1. On <https://gemini.google.com/>, click **"GCE: Export all"** (bottom-right; with
   the console snippet it starts immediately).
2. It shows `loading list... N`, may ask where to save `gemini_chats.ndjson`
   (Tampermonkey only — otherwise the file downloads at the end), then shows
   `X/542` as it works. Keep the tab open and in front until it finishes; a big
   history takes ~30–45 min.
3. Verify it with the Python toolkit (`pip install gemini-chat-exporter`):
   ```bash
   gemini-export --verify gemini_chats.ndjson
   ```
   From a clone, use `python main.py --verify gemini_chats.ndjson`.

## What it does for you

- Opens the sidebar (and re-opens it if it collapses mid-run) so the chat list is loaded.
- Loads the **full** lazy-paginated list, not just the first page.
- **Resume** (Tampermonkey): skips chats already saved (stored in `localStorage`). A
  re-run's file holds only the newly captured chats, so don't save it over the first
  one — see the main [Troubleshooting](../README.md#troubleshooting) table.
- **Refuses stale/duplicate pages it detects** — those are marked `failed` (the
  Tampermonkey script retries them on the next run).

## Output format

One JSON object per line (NDJSON):

```json
{"id":"d5ff…","title":"…","turns":[{"role":"user","text":"…"},{"role":"model","text":"…"}],"source":"scraper","flags":[]}
```

## When it breaks

Gemini's DOM is undocumented and changes over time. If a capture suddenly finds
nothing, update the selectors in the `CONFIG` block at the top of
[`gemini-chat-exporter.user.js`](gemini-chat-exporter.user.js), or open an issue.
See the main [Troubleshooting](../README.md#troubleshooting) table for common fixes.
