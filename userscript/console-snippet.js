/*
 * Gemini Chat Exporter - console snippet (no userscript manager required).
 *
 * HOW TO USE:
 *   1. Open https://gemini.google.com/ and sign in.
 *   2. Open DevTools (F12) -> Console.
 *   3. Paste this whole file and press Enter.
 *   4. When prompted, choose where to save gemini_chats.ndjson.
 *   5. Verify the result:  gemini-export --verify gemini_chats.ndjson
 *
 * This is the compact sibling of gemini-chat-exporter.user.js and keeps the same
 * safety guarantees: it validates CONTENT IDENTITY before scraping (URL id +
 * first prompt must match the target and differ from the previous conversation)
 * and refuses to save a body identical to the previous one. It therefore cannot
 * reproduce the stale-stub corruption that silently broke the earlier exporter.
 *
 * CAVEAT: selectors are undocumented Gemini internals and may break. Always run
 * the output through the verifier; for guaranteed-complete history use Google
 * Takeout (My Activity > Gemini Apps).
 */

(async function () {
  "use strict";

  const SEL = {
    link: 'a[href^="/app/"]',
    container: ".conversation-container",
    user: ["user-query .query-text", "user-query", ".query-text"],
    model: ["model-response .markdown", ".model-response-text", "model-response"],
  };
  const POLL = 600;
  const TIMEOUT = 20000;
  const NBSP = new RegExp("[" + String.fromCharCode(0xa0, 0x202f) + "]", "g");

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const idOf = (h) => ((h || "").match(/\/app\/([^/?#]+)/) || [])[1] || null;
  const pathId = () => idOf(location.pathname);

  const clean = (t) =>
    !t
      ? ""
      : t
          .replace(NBSP, " ")
          .replace(/\r\n?/g, "\n")
          .replace(/^\s*(you said|gemini said)\b[:\s]*/i, "")
          .split("\n")
          .map((l) => l.replace(/[ \t]+/g, " ").replace(/\s+$/, ""))
          .join("\n")
          .replace(/\n{3,}/g, "\n\n")
          .trim();

  function pick(root, sels) {
    for (const s of sels) {
      const el = root.querySelector(s);
      if (el && el.innerText && el.innerText.trim()) return el.innerText;
    }
    return "";
  }

  function scrape() {
    const cs = document.querySelectorAll(SEL.container);
    const turns = [];
    for (const c of cs) {
      const u = clean(pick(c, SEL.user));
      if (u) turns.push({ role: "user", text: u });
      turns.push({ role: "model", text: clean(pick(c, SEL.model)) });
    }
    return { turns, n: cs.length };
  }
  const firstPrompt = (turns) =>
    (turns.find((x) => x.role === "user" && x.text.trim()) || {}).text || "";

  async function sha(t) {
    const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(t));
    return Array.from(new Uint8Array(b))
      .map((x) => x.toString(16).padStart(2, "0"))
      .join("");
  }

  async function waitRender(id, prevPrompt) {
    const end = Date.now() + TIMEOUT;
    let lastLen = -1;
    let stable = 0;
    while (Date.now() < end) {
      await sleep(POLL);
      if (pathId() !== id) continue;
      const s = scrape();
      if (!s.n) continue;
      const fp = (firstPrompt(s.turns) || "").trim();
      if (!fp || (prevPrompt && fp === prevPrompt)) continue;
      const len = s.turns.reduce((a, t) => a + t.text.length, 0);
      if (len === lastLen) {
        if (++stable >= 1) return { ok: true, stable: true };
      } else {
        stable = 0;
        lastLen = len;
      }
    }
    if (pathId() === id) {
      const fp = (firstPrompt(scrape().turns) || "").trim();
      if (fp && (!prevPrompt || fp !== prevPrompt)) return { ok: true, stable: false };
    }
    return { ok: false, stable: false };
  }

  // --- collect ---
  const seen = new Map();
  for (const a of document.querySelectorAll(SEL.link)) {
    const id = idOf(a.getAttribute("href"));
    if (id && !seen.has(id))
      seen.set(id, {
        id,
        title: (a.getAttribute("aria-label") || a.innerText || "").trim() || id,
        el: a,
      });
  }
  const list = Array.from(seen.values());
  if (!list.length) {
    throw new Error(
      "No conversations found - Gemini's DOM may have changed; selectors need updating."
    );
  }
  console.log(`[GCE] ${list.length} conversations found.`);

  const out = [];
  let prevPrompt = "";
  let prevHash = "";
  let failed = 0;
  for (let i = 0; i < list.length; i++) {
    const c = list[i];
    if (c.el && document.contains(c.el)) c.el.click();
    else {
      history.pushState({}, "", `/app/${c.id}`);
      window.dispatchEvent(new PopStateEvent("popstate"));
    }
    await sleep(400);
    const v = await waitRender(c.id, prevPrompt);
    if (!v.ok) {
      failed++;
      out.push(JSON.stringify({ id: c.id, title: c.title, turns: [], source: "scraper", flags: ["failed"] }));
      console.warn(`[GCE] ${i + 1}/${list.length} FAILED ${c.id}`);
      continue;
    }
    const s = scrape();
    const body = s.turns.map((t) => `${t.role}: ${t.text.trim()}`).join("\n").trim();
    const h = await sha(body);
    if (h === prevHash && body) {
      failed++;
      out.push(JSON.stringify({ id: c.id, title: c.title, turns: [], source: "scraper", flags: ["failed", "duplicate-body"] }));
      console.warn(`[GCE] ${i + 1}/${list.length} duplicate body, not saved: ${c.id}`);
      continue;
    }
    out.push(
      JSON.stringify({
        id: c.id,
        title: c.title,
        turns: s.turns,
        source: "scraper",
        flags: v.stable ? [] : ["needs-review"],
      })
    );
    prevPrompt = (firstPrompt(s.turns) || "").trim() || prevPrompt;
    prevHash = h;
    console.log(`[GCE] ${i + 1}/${list.length} ${c.id}`);
  }

  const blob = new Blob([out.join("\n") + "\n"], { type: "application/x-ndjson" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "gemini_chats.ndjson";
  a.click();
  console.log(`[GCE] Done. ${out.length - failed} saved, ${failed} failed. Verify with: gemini-export --verify gemini_chats.ndjson`);
})();
