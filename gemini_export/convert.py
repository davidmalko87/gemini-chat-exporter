# convert.py — Write conversations to per-file JSON + Markdown + a manifest.
# Author: David Malko

"""Convert normalized conversations into durable, human-readable output.

For each conversation we emit (toggleable):

* a **JSON** file — structured ``{id, title, turns:[{role,text}], ...}``;
* a **Markdown** file — readable transcript with David / Gemini headers.

Plus one **manifest.json** for the whole run: per-file SHA-256 checksums, body
hashes, counts, and a ``complete`` flag that is only true when an accompanying
verification passed. Tying ``complete`` to the verifier means the manifest can
never claim an export is sound while it is actually corrupt.

Output filenames are ASCII-safe (titles are slugified; non-Latin titles fall
back to the conversation id) so they are portable across Windows/macOS/Linux.
File *contents* are UTF-8 and preserve the original text verbatim.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import __version__
from .models import ROLE_USER, Conversation

_SLUG_STRIP = re.compile(r"[^A-Za-z0-9]+")


def _slug(title: str, fallback: str) -> str:
    s = _SLUG_STRIP.sub("-", title).strip("-").lower()
    return s[:40] or fallback


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def conversation_to_markdown(conv: Conversation) -> str:
    """Render one conversation as a Markdown transcript."""
    lines: list[str] = [f"# {conv.title}".rstrip(), ""]
    meta = [f"id: `{conv.id}`"]
    if conv.created:
        meta.append(f"created: {conv.created}")
    if conv.source:
        meta.append(f"source: {conv.source}")
    if conv.flags:
        meta.append(f"flags: {', '.join(conv.flags)}")
    lines.append("> " + " | ".join(meta))
    lines.append("")
    for turn in conv.turns:
        speaker = "David" if turn.role == ROLE_USER else "Gemini"
        body = turn.text.strip() or "_(image or no text response)_"
        lines.append(f"## {speaker}")
        lines.append("")
        lines.append(body)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def convert(
    convs: list[Conversation],
    out_dir: str | Path,
    *,
    write_json: bool = True,
    write_markdown: bool = True,
    complete: bool | None = None,
    verification: dict | None = None,
    dry_run: bool = False,
) -> dict:
    """Write conversations to ``out_dir`` and return the manifest dict.

    Args:
        convs: conversations to write, in order.
        out_dir: destination directory (created if needed, unless dry_run).
        write_json / write_markdown: which per-conversation formats to emit.
        complete: value for the manifest ``complete`` flag. Pass the verifier's
            ``passed`` result; defaults to None ("unknown / not verified").
        verification: optional verifier summary embedded in the manifest.
        dry_run: compute the manifest but write nothing to disk.

    Returns:
        The manifest as a dict (also written to ``out_dir/manifest.json``).
    """
    out = Path(out_dir)
    if not dry_run:
        out.mkdir(parents=True, exist_ok=True)

    entries: list[dict] = []
    seen_names: set[str] = set()
    for idx, conv in enumerate(convs, start=1):
        base = f"{idx:04d}_{_slug(conv.title, conv.id or f'chat-{idx}')}"
        # Guarantee unique base names even when slugs collide.
        candidate, n = base, 1
        while candidate in seen_names:
            n += 1
            candidate = f"{base}-{n}"
        seen_names.add(candidate)

        entry: dict = {
            "index": idx,
            "id": conv.id,
            "title": conv.title,
            "turns": len(conv.turns),
            "body_sha256": conv.body_hash(),
            "flags": list(conv.flags),
        }
        if write_json:
            json_name = f"{candidate}.json"
            json_text = json.dumps(conv.to_dict(), ensure_ascii=False, indent=2)
            entry["json_file"] = json_name
            entry["json_sha256"] = _sha256_text(json_text)
            if not dry_run:
                (out / json_name).write_text(json_text, encoding="utf-8")
        if write_markdown:
            md_name = f"{candidate}.md"
            md_text = conversation_to_markdown(conv)
            entry["md_file"] = md_name
            entry["md_sha256"] = _sha256_text(md_text)
            if not dry_run:
                (out / md_name).write_text(md_text, encoding="utf-8")
        entries.append(entry)

    manifest = {
        "generated_by": f"gemini-chat-exporter {__version__}",
        "conversation_count": len(convs),
        "complete": complete,
        "verification": verification,
        "conversations": entries,
    }
    if not dry_run:
        (out / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return manifest
