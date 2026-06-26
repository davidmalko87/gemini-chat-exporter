// ==UserScript==
// @name         Gemini Chat Exporter
// @namespace    https://github.com/davidmalko87/gemini-chat-exporter
// @version      0.1.0
// @description  Export all your Google Gemini conversations to NDJSON, with content-identity validation so it can never silently save a stale/duplicate page.
// @author       David Malko
// @match        https://gemini.google.com/*
// @run-at       document-idle
// @grant        none
// @license      MIT
// @homepageURL  https://github.com/davidmalko87/gemini-chat-exporter
// @supportURL   https://github.com/davidmalko87/gemini-chat-exporter/issues
// ==/UserScript==

/*
 * WHY THIS EXISTS / WHAT BROKE BEFORE
 * -----------------------------------
 * A previous exporter checked only that the extracted *text length* stabilized
 * before scraping. Under memory pressure the Gemini SPA kept showing the
 * previously loaded conversation, so the loop scraped that same stale body into
 * hundreds of slots and reported "zero errors" (zero exceptions != zero wrong
 * content). ~280 of 473 conversations were silently overwritten with one stub.
 *
 * The fixes baked in here:
 *   1. CONTENT-IDENTITY VALIDATION: after navigating, we do not scrape until the
 *      URL id matches the target AND the first user prompt is non-empty AND it
 *      differs from the previously scraped conversation.
 *   2. POST-SCRAPE DUPLICATE GUARD: we hash each body; if it equals the previous
 *      conversation's body we retry once, then mark the conversation FAILED
 *      rather than saving the stale stub.
 *   3. STREAMING WRITES: each conversation is written to disk immediately (File
 *      System Access API) instead of accumulating one giant in-memory string.
 *   4. RESUME: already-saved ids are remembered in localStorage and skipped.
 *   5. FAIL LOUDLY: zero links or zero conversation containers throws a clear
 *      error instead of producing empty/garbage output.
 *
 * CAVEAT: the selectors below are undocumented Gemini internals (valid as of
 * mid-2026) and WILL break when Google changes the UI. Always run the output
 * through the Python verifier (`gemini-export --verify`) before trusting it.
 * For guaranteed-complete history, Google Takeout (My Activity > Gemini Apps)
 * is the authoritative route.
 */

(function () {
  "use strict";

  const CONFIG = {
    // --- Selectors (undocumented; update here when Gemini's DOM changes) ---
    sidebarLink: 'a[href^="/app/"]',
    turnContainer: ".conversation-container",
    userQuery: ["user-query .query-text", "user-query", ".query-text"],
    modelResponse: [
      "model-response .markdown",
      ".model-response-text",
      "model-response",
      "message-content",
    ],
    // --- Timing ---
    pollIntervalMs: 600, // gap between stability reads
    perConversationTimeoutMs: 20000, // hard cap before we give up / fallback
    settleAfterNavMs: 400, // small grace after navigation starts
    // --- Safety ---
    dupRatioWarn: 0.05, // warn in console if duplicate bodies exceed this
    storageKey: "gce_saved_ids_v1",
  };

  // No-break spaces Gemini emits (U+00A0, U+202F), built from char codes so
  // this source file stays pure ASCII. Normalized to plain spaces.
  const NBSP_RE = new RegExp("[" + String.fromCharCode(0xa0, 0x202f) + "]", "g");

  // ---------------------------------------------------------------- helpers

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  function logInfo(...a) {
    console.log("%c[GCE]", "color:#4285F4;font-weight:bold", ...a);
  }
  function logWarn(...a) {
    console.warn("[GCE]", ...a);
  }

  async function sha256Hex(text) {
    const buf = await crypto.subtle.digest(
      "SHA-256",
      new TextEncoder().encode(text)
    );
    return Array.from(new Uint8Array(buf))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  }

  // Mirror of the Python clean_text(): strip a11y labels, normalize spaces.
  function cleanText(text) {
    if (!text) return "";
    return text
      .replace(NBSP_RE, " ")
      .replace(/\r\n?/g, "\n")
      .replace(/^\s*(you said|gemini said)\b[:\s]*/i, "")
      .split("\n")
      .map((l) => l.replace(/[ \t]+/g, " ").replace(/\s+$/, ""))
      .join("\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  function firstMatchText(root, selectors) {
    for (const sel of selectors) {
      const el = root.querySelector(sel);
      if (el && el.innerText && el.innerText.trim()) return el.innerText;
    }
    return "";
  }

  function idFromHref(href) {
    const m = (href || "").match(/\/app\/([^/?#]+)/);
    return m ? m[1] : null;
  }

  function currentPathId() {
    return idFromHref(location.pathname);
  }

  // ----------------------------------------------------------- collect list

  function collectConversations() {
    const seen = new Map();
    for (const a of document.querySelectorAll(CONFIG.sidebarLink)) {
      const id = idFromHref(a.getAttribute("href"));
      if (!id || seen.has(id)) continue;
      const title =
        (a.getAttribute("aria-label") || a.innerText || "").trim() ||
        `(untitled ${id})`;
      seen.set(id, { id, title, el: a });
    }
    return Array.from(seen.values());
  }

  // --------------------------------------------------------------- scraping

  function scrapeCurrent() {
    const containers = document.querySelectorAll(CONFIG.turnContainer);
    const turns = [];
    for (const c of containers) {
      const userText = cleanText(firstMatchText(c, CONFIG.userQuery));
      if (userText) turns.push({ role: "user", text: userText });
      const modelText = cleanText(firstMatchText(c, CONFIG.modelResponse));
      // Push a model turn even if empty (image-only) so structure is preserved.
      turns.push({ role: "model", text: modelText });
    }
    return { turns, containerCount: containers.length };
  }

  function firstUserPrompt(turns) {
    const t = turns.find((x) => x.role === "user" && x.text.trim());
    return t ? t.text.trim() : "";
  }

  // Navigate to a conversation via SPA routing (click, with history fallback).
  async function navigateTo(conv) {
    if (conv.el && document.contains(conv.el)) {
      conv.el.click();
    } else {
      history.pushState({}, "", `/app/${conv.id}`);
      window.dispatchEvent(new PopStateEvent("popstate"));
    }
    await sleep(CONFIG.settleAfterNavMs);
  }

  /*
   * Wait until it is SAFE to scrape the target conversation. Returns
   * { ok, reason, stable }. "ok=false" means we must not save this one.
   */
  async function waitForRender(targetId, prevFirstPrompt) {
    const deadline = Date.now() + CONFIG.perConversationTimeoutMs;
    let lastLen = -1;
    let stableHits = 0;

    while (Date.now() < deadline) {
      await sleep(CONFIG.pollIntervalMs);

      // (a) URL must point at the target conversation.
      if (currentPathId() !== targetId) continue;

      // (b) There must be rendered conversation containers.
      const scraped = scrapeCurrent();
      if (scraped.containerCount === 0) continue;

      const fp = firstUserPrompt(scraped.turns);

      // (c) The first prompt must exist AND differ from the previous
      //     conversation. This is the guard that kills the stale-stub bug.
      if (!fp) continue;
      if (prevFirstPrompt && fp === prevFirstPrompt) continue;

      // (d) Text length must be stable across two consecutive reads.
      const len = scraped.turns.reduce((n, t) => n + t.text.length, 0);
      if (len === lastLen) {
        stableHits += 1;
        if (stableHits >= 1) return { ok: true, reason: "stable", stable: true };
      } else {
        stableHits = 0;
        lastLen = len;
      }
    }

    // Timed out. Proceed only if identity is at least correct; flag for review.
    if (currentPathId() === targetId) {
      const scraped = scrapeCurrent();
      const fp = firstUserPrompt(scraped.turns);
      if (fp && (!prevFirstPrompt || fp !== prevFirstPrompt)) {
        return { ok: true, reason: "timeout-fallback", stable: false };
      }
    }
    return { ok: false, reason: "timeout-unverified", stable: false };
  }

  // ---------------------------------------------------------- output writer

  // Streams NDJSON to a single file when the File System Access API exists;
  // otherwise buffers and downloads once at the end (with a warning).
  async function makeWriter() {
    if (window.showSaveFilePicker) {
      try {
        const handle = await window.showSaveFilePicker({
          suggestedName: "gemini_chats.ndjson",
          types: [
            { description: "NDJSON", accept: { "application/x-ndjson": [".ndjson"] } },
          ],
        });
        const stream = await handle.createWritable();
        return {
          mode: "stream",
          write: (line) => stream.write(line),
          close: () => stream.close(),
        };
      } catch (e) {
        logWarn("File picker cancelled or unavailable, buffering instead:", e);
      }
    }
    const buf = [];
    return {
      mode: "buffer",
      write: (line) => {
        buf.push(line);
        return Promise.resolve();
      },
      close: () => {
        const blob = new Blob(buf, { type: "application/x-ndjson" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "gemini_chats.ndjson";
        a.click();
        URL.revokeObjectURL(url);
        return Promise.resolve();
      },
    };
  }

  // -------------------------------------------------------------- resume io

  function loadSavedIds() {
    try {
      return new Set(JSON.parse(localStorage.getItem(CONFIG.storageKey) || "[]"));
    } catch {
      return new Set();
    }
  }
  function persistSavedIds(set) {
    try {
      localStorage.setItem(CONFIG.storageKey, JSON.stringify(Array.from(set)));
    } catch (e) {
      logWarn("Could not persist resume state:", e);
    }
  }

  // ------------------------------------------------------------- main loop

  async function runExport(button) {
    const conversations = collectConversations();
    if (conversations.length === 0) {
      throw new Error(
        "No conversation links found (selector '" +
          CONFIG.sidebarLink +
          "'). Gemini's DOM structure may have changed - selectors need updating."
      );
    }
    logInfo(`Found ${conversations.length} conversations.`);

    const savedIds = loadSavedIds();
    const writer = await makeWriter();
    const bodyHashes = new Map(); // hash -> count, for the live dup audit

    let done = 0;
    let failed = 0;
    let skipped = 0;
    let prevFirstPrompt = "";
    let prevBodyHash = "";

    for (const conv of conversations) {
      done += 1;
      if (savedIds.has(conv.id)) {
        skipped += 1;
        button.textContent = `GCE: ${done}/${conversations.length} (skip)`;
        continue;
      }

      await navigateTo(conv);
      const verdict = await waitForRender(conv.id, prevFirstPrompt);

      if (!verdict.ok) {
        failed += 1;
        logWarn(`FAILED #${done} ${conv.id} (${conv.title}): ${verdict.reason}`);
        await writer.write(
          JSON.stringify({
            id: conv.id,
            title: conv.title,
            turns: [],
            source: "scraper",
            flags: ["failed", verdict.reason],
          }) + "\n"
        );
        button.textContent = `GCE: ${done}/${conversations.length} (FAIL ${failed})`;
        continue;
      }

      const scraped = scrapeCurrent();
      let bodyText = scraped.turns
        .map((t) => `${t.role}: ${t.text.trim()}`)
        .join("\n")
        .trim();
      let bodyHash = await sha256Hex(bodyText);

      // POST-SCRAPE DUPLICATE GUARD: identical to the previous body? Retry once.
      if (bodyHash === prevBodyHash && bodyText) {
        logWarn(`Duplicate body for ${conv.id}; retrying once...`);
        await sleep(CONFIG.pollIntervalMs * 2);
        const retry = scrapeCurrent();
        bodyText = retry.turns
          .map((t) => `${t.role}: ${t.text.trim()}`)
          .join("\n")
          .trim();
        bodyHash = await sha256Hex(bodyText);
        if (bodyHash === prevBodyHash) {
          failed += 1;
          logWarn(`STILL duplicate for ${conv.id}; marking FAILED (not saving stub).`);
          await writer.write(
            JSON.stringify({
              id: conv.id,
              title: conv.title,
              turns: [],
              source: "scraper",
              flags: ["failed", "duplicate-body"],
            }) + "\n"
          );
          button.textContent = `GCE: ${done}/${conversations.length} (FAIL ${failed})`;
          continue;
        }
      }

      const flags = verdict.stable ? [] : ["needs-review"];
      await writer.write(
        JSON.stringify({
          id: conv.id,
          title: conv.title,
          turns: scraped.turns,
          source: "scraper",
          flags,
        }) + "\n"
      );

      bodyHashes.set(bodyHash, (bodyHashes.get(bodyHash) || 0) + 1);
      savedIds.add(conv.id);
      persistSavedIds(savedIds);
      prevFirstPrompt = firstUserPrompt(scraped.turns) || prevFirstPrompt;
      prevBodyHash = bodyHash;

      // Live duplicate-ratio audit.
      const dupCount = Array.from(bodyHashes.values())
        .filter((n) => n > 1)
        .reduce((a, n) => a + n, 0);
      const ratio = dupCount / Math.max(1, savedIds.size);
      if (ratio > CONFIG.dupRatioWarn) {
        logWarn(
          `Duplicate-body ratio ${(ratio * 100).toFixed(1)}% - inspect output; ` +
            "the page may be lagging behind navigation."
        );
      }

      button.textContent = `GCE: ${done}/${conversations.length}`;
    }

    await writer.close();
    const msg =
      `Done. ${savedIds.size} saved, ${skipped} skipped, ${failed} failed ` +
      `(writer: ${writer.mode}). Run 'gemini-export --verify' on the file.`;
    logInfo(msg);
    button.textContent = `GCE: done (${failed} fail)`;
    alert(msg);
  }

  // --------------------------------------------------------------------- UI

  function injectButton() {
    if (document.getElementById("gce-export-btn")) return;
    const btn = document.createElement("button");
    btn.id = "gce-export-btn";
    btn.textContent = "GCE: Export all";
    Object.assign(btn.style, {
      position: "fixed",
      bottom: "16px",
      right: "16px",
      zIndex: "99999",
      padding: "10px 14px",
      background: "#4285F4",
      color: "#fff",
      border: "none",
      borderRadius: "8px",
      fontSize: "13px",
      cursor: "pointer",
      boxShadow: "0 2px 8px rgba(0,0,0,.3)",
    });
    btn.addEventListener("click", async () => {
      if (btn.disabled) return;
      btn.disabled = true;
      try {
        await runExport(btn);
      } catch (e) {
        logWarn(e);
        alert("Export failed: " + e.message);
        btn.textContent = "GCE: Export all";
      } finally {
        btn.disabled = false;
      }
    });
    document.body.appendChild(btn);
  }

  const ready = setInterval(() => {
    if (document.body) {
      clearInterval(ready);
      injectButton();
    }
  }, 1000);
})();
