# PROMPTS.md — Agent-Coding Kit

Reusable, paste-once prompts for building and hardening real CLI/automation tools
with a coding agent. This file travels with the repo so the workflow stays with
the project.

## The one discipline that matters

> **Make the agent prove the round-trip empirically — never trust that "it ran"
> means "it works."**

Every real bug in these tools came from proving an assumption against reality
(live round-trip, a real user host, real API responses) — *not* from re-reading the
code. Structural validity is necessary but **not** sufficient: a backup is only
proven once it has been restored (or, here, re-verified) end-to-end and diffed.

For *this* repo specifically, the round-trip is **export -> verify -> convert ->
reconcile**, and "verified" means the verifier catches the real corruption in an
actual export — which it does against the file that prompted this project.

**How to use:** keep §0 (Guardrails) as a saved snippet and paste it into §1/§2/§4
wherever they say `[paste §0]`. Each prompt below is self-contained.

---

## §0 — Data-safety guardrails

*Prepend to ANY session that touches a real instance / real data.*

```
GUARDRAILS — data safety (this tool handles real, possibly-confidential data):
- Test only on a NON-PROD site. Trust observed API behavior over docs.
- I will NEVER enter credentials into a browser/login field on your behalf, even
  with your authorization — that's a fixed boundary. For REST/Basic-auth tools,
  write the token into a gitignored .env yourself; I'll read it via the config
  loader. (An API token authenticates REST calls; it does NOT create a browser
  UI session — UI-gated screens always need your own login.)
- The tool's OUTPUT is sensitive: gitignore the backup dir, *.log, .env, csv
  exports, and any captured cURL from the first commit. Run `git status` and
  confirm nothing sensitive is staged before every commit.
- Redact cookies/tokens/domain in any cURL or output shown.
- PAUSE before anything irreversible (publish, delete, restore-overwrite) and
  before the final commit. Feature branch + PR; never push/release without my OK.
```

---

## §1 — Harden an existing tool via live round-trip

*The prompt that found every real bug. Use when a tool "works" but hasn't been proven.*

```
You are hardening an existing tool: <REPO/PACKAGE> — <one-line description>.
Work empirically and autonomously against a NON-PROD environment, but PAUSE
before anything irreversible (publish/delete) and before the final commit.
PHASE 1 — Live round-trip (the point). Create a scratch source with RICH content
(every feature: hierarchy/parent-child, rich-text bodies, comments, attachments,
links, varied statuses), back it up -> restore into a NEW scratch target -> diff
EVERY dimension via the API (counts, types, hierarchy, body fidelity, metadata,
attachments by SHA-256, no-duplicate links). Record pass/fail per dimension.
Structural validity is NOT proof — only a verified restore counts.
PHASE 2 — Fix every bug the diff surfaces. Also audit the HTTP client: does it
tolerate a non-JSON 2xx body (vs crashing on .json())? Is 202 Accepted treated as
success? Is a phase marked complete only when zero items failed (so re-runs retry)?
Do uploads still work with the right anti-XSRF header + non-browser UA?
PHASE 3 — Add an OFFLINE pytest suite (pure-logic units: body flatten/convert,
key mapping, phase ordering, retry/backoff via a fake session, config validation).
Extract nested helpers to module level if needed for testability. Add pytest to
the CI matrix; set [tool.pytest.ini_options] pythonpath=["."] if imports fail.
PHASE 4 (optional) — Investigate any documented "cannot restore X" limitation as a
best-effort opt-in phase. Be honest about what's actually possible via the API.
OUTPUT — Report the round-trip table + bugs found/fixed. Open a PR with fixes +
tests, bump version + CHANGELOG, update the README limitations table honestly,
and add a "round-trip verified" badge + section. PAUSE before merge/release.
GUARDRAILS: [paste §0]
```

---

## §2 — Cross-pollinate features between sibling tools

*When a sibling repo grew hardening features this one likely lacks. Audit before building.*

```
You maintain <TOOL A>. Its sibling <TOOL B URL> grew hardening features A likely
lacks. Do NOT build yet — AUDIT first, then propose, then implement only what I
approve.
PHASE 1 — For each capability below, report what THIS repo already has vs. a real
gap. Don't duplicate what exists.
PHASE 2 — Evaluate porting, but KEEP THIS TOOL'S CHARACTER (don't turn an
interactive/migration tool into an unattended daemon, or vice-versa). For each,
give fit + priority + plan: [list the sibling's features].
PHASE 3 — Implement the approved subset, reusing the sibling's module shapes.
Minimal deps; each capability independently toggleable and OFF by default where it
needs new config so existing usage is unchanged.
Bias: prioritize anything that's actually a latent BUG (e.g. "we log progress but
never ASSERT completeness") over net-new features. Start with the audit; no code
until I approve.
GUARDRAILS: [paste §0]
```

---

## §3 — Release to PyPI (for envs that can't push tags)

*Triggers the publish workflow via a GitHub Release when the local env can't push tags.*

```
In repo <OWNER/REPO>, create a GitHub Release to trigger the PyPI publish workflow.
1. Confirm master HEAD has version <X.Y.Z> in __init__.py AND pyproject.toml — STOP
   if they differ.
2. Releases -> "Draft a new release". Tag: v<X.Y.Z> (leading "v" matters), created
   on publish targeting master. Title: v<X.Y.Z>.
3. Body: paste the [X.Y.Z] section from CHANGELOG.md verbatim.
4. Publish (NOT draft, NOT pre-release). Confirm the publish.yml workflow starts and
   succeeds (trusted publishing, id-token: write).
DO NOT skip the "v", mark pre-release, or bump the version again.
```

---

## §4 — New tool kickoff — research before building

*Forces the strategic decision + empirical auth check before any production code.*

```
New project: <TOOL>. Research the real platform behavior FIRST; no production code
until Phase 1 is done and I approve.
PHASE 1 — STRATEGIC DECISION before anything else: evaluate the 2+ viable approaches
(e.g. native export/import vs REST dump+reconstruct) and recommend one, weighing
FIDELITY vs OPERATIONAL COST (e.g. UI-gated = recurring cookie-refresh toil; API
token = lossier but zero-maintenance). Verify auth EMPIRICALLY with redacted cURL —
don't trust docs. Map the data model and produce an honest CANNOT-restore list.
PHASE 2 — Design mirroring <SIBLING REPO> (same file layout, UX, config). Decide
restore-target SAFETY: default to a NEW target, never silently clobber; --overwrite
+ confirmation otherwise.
PHASE 3 — Build the approved design. Streaming writes, resumable, dry-run, 3.10+,
ASCII-safe console.
PHASE 4 — VALIDATE THE RESTORE: real round-trip -> diff -> README limitations table.
A backup is only proven once restored end-to-end and verified.
GUARDRAILS: [paste §0]
```

---

## Appendix — What one hardening session produced (example)

Evidence that the round-trip discipline works. Each release below came from proving
an assumption empirically, never from re-reading code (from the sibling
`jira-project-backup-restore`).

| Version | What | How it was found |
|---|---|---|
| 1.3.0 | Interactive menu redesign: CSV export, backup inspection, connection test, config viewer | Feature request |
| 1.3.1 | Streaming issue writes (OOM fix on 18k issues / 1GB host) | Live user issue |
| 1.3.2 | Python 3.10/3.11 compat, SSL-warning suppression, worklog progress | Issue follow-up |
| 1.4.0 | Backup completeness verification (`approximate-count`), SHA-256 manifests, `--validate` | Cross-pollination from sibling tool |
| 1.5.0 | ADF comment/worklog corruption fix, HTTP client hardening (non-JSON 2xx, 202), 34 pytest tests in CI, opt-in status restore | Live round-trip testing |
