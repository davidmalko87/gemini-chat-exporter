# takeout.py — Import the authoritative Google Takeout "Gemini Apps" export.
# Author: David Malko

"""Schema-tolerant importer for Google Takeout's Gemini Apps activity.

Takeout is the *authoritative* route: Google generates it, so it cannot silently
re-save a stale page the way a DOM scraper can. The catch is that its schema
varies by account age and which surfaces you used, and it is under-documented.
So this importer is deliberately defensive and handles the two shapes seen in
the wild rather than assuming one fixed layout:

1. **My Activity array** — ``[ {header, title, titleUrl, time, ...}, ... ]``.
   Activity-log granularity: typically one record per prompt. The prompt is in
   ``title`` (often prefixed "Prompted "); the model response is frequently NOT
   present (My Activity is prompt-centric). Records are grouped into a
   conversation by the ``/app/<id>`` id in ``titleUrl`` when available.

2. **Conversations object** — ``{"conversations": [ {title, create_time,
   entries|messages: [ {role|author, text|content}, ... ]}, ... ]}``. Richer:
   full multi-turn transcripts.

Accepts a ``.json`` file, a ``.zip`` Takeout archive, or an extracted directory.
Returns ``(conversations, stats)`` where ``stats`` honestly reports what Takeout
did and did not include (e.g. how many records had no response).
"""

from __future__ import annotations

import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path

from .models import ROLE_MODEL, ROLE_USER, Conversation, Turn, clean_text

_APP_ID = re.compile(r"/app/([0-9a-fA-F]+)")
_PROMPTED_PREFIX = re.compile(r"^(prompted|asked)\b[:\s]+", re.IGNORECASE)
_GEMINI_HEADERS = {"gemini apps", "bard", "gemini"}


def _norm_role(value: str | None) -> str:
    v = (value or "").strip().lower()
    if v in ("user", "you", "human", "david"):
        return ROLE_USER
    return ROLE_MODEL


def _extract_app_id(url: str) -> str | None:
    m = _APP_ID.search(url or "")
    return m.group(1) if m else None


def _load_takeout_json(path: str | Path):
    """Return the parsed JSON from a file, a .zip archive, or a directory."""
    p = Path(path)
    if p.is_dir():
        candidates = sorted(p.rglob("*.json"))
        gemini = [c for c in candidates if "gemini" in str(c).lower()]
        target = (gemini or candidates or [None])[0]
        if target is None:
            raise FileNotFoundError(f"No .json found under {p}")
        return json.loads(target.read_text(encoding="utf-8"))
    if p.suffix.lower() == ".zip":
        with zipfile.ZipFile(p) as zf:
            names = [n for n in zf.namelist() if n.lower().endswith(".json")]
            gemini = [n for n in names if "gemini" in n.lower()]
            target = (gemini or names or [None])[0]
            if target is None:
                raise FileNotFoundError(f"No .json inside {p}")
            with zf.open(target) as fh:
                return json.loads(fh.read().decode("utf-8"))
    return json.loads(p.read_text(encoding="utf-8"))


def import_takeout(path: str | Path) -> tuple[list[Conversation], dict]:
    """Import a Takeout export into normalized conversations + honest stats."""
    data = _load_takeout_json(path)
    if isinstance(data, dict) and "conversations" in data:
        return _from_conversations_form(data["conversations"])
    if isinstance(data, dict):
        # Some exports wrap a single conversation or use a different top key.
        for key in ("items", "activities", "data"):
            if isinstance(data.get(key), list):
                return _from_myactivity_form(data[key])
        return _from_conversations_form([data])
    if isinstance(data, list):
        return _from_myactivity_form(data)
    raise ValueError("Unrecognized Takeout JSON shape")


def _from_conversations_form(items: list) -> tuple[list[Conversation], dict]:
    convs: list[Conversation] = []
    without_response = 0
    for idx, it in enumerate(items):
        entries = it.get("entries") or it.get("messages") or it.get("turns") or []
        turns: list[Turn] = []
        for e in entries:
            role = _norm_role(e.get("role") or e.get("author"))
            text = clean_text(str(e.get("text") or e.get("content") or ""))
            turns.append(Turn(role=role, text=text))
        if not any(t.role == ROLE_MODEL and t.text.strip() for t in turns):
            without_response += 1
        cid = str(it.get("id") or it.get("conversation_id") or f"takeout-{idx}")
        convs.append(
            Conversation(
                id=cid,
                title=clean_text(str(it.get("title") or "(untitled)")),
                turns=turns,
                created=it.get("create_time") or it.get("created") or it.get("time"),
                source="takeout",
            )
        )
    stats = {
        "form": "conversations",
        "records": len(items),
        "conversations": len(convs),
        "without_response": without_response,
    }
    return convs, stats


def _from_myactivity_form(records: list) -> tuple[list[Conversation], dict]:
    groups: defaultdict[str, list] = defaultdict(list)
    kept = 0
    skipped_non_gemini = 0
    for r in records:
        header = str(r.get("header") or "").strip().lower()
        if header and header not in _GEMINI_HEADERS:
            skipped_non_gemini += 1
            continue
        kept += 1
        cid = _extract_app_id(r.get("titleUrl", "")) or f"activity-{len(groups)}-{kept}"
        groups[cid].append(r)

    convs: list[Conversation] = []
    without_response = 0
    for cid, recs in groups.items():
        turns: list[Turn] = []
        first_prompt = ""
        for r in recs:
            prompt = _PROMPTED_PREFIX.sub("", str(r.get("title") or "")).strip()
            if prompt:
                turns.append(Turn(role=ROLE_USER, text=clean_text(prompt)))
                first_prompt = first_prompt or prompt
            response = _extract_activity_response(r)
            if response:
                turns.append(Turn(role=ROLE_MODEL, text=clean_text(response)))
        if not any(t.role == ROLE_MODEL and t.text.strip() for t in turns):
            without_response += 1
        title = first_prompt[:80] if first_prompt else "(untitled)"
        created = recs[0].get("time")
        flags = ["no-response"] if not any(t.role == ROLE_MODEL for t in turns) else []
        convs.append(
            Conversation(
                id=cid,
                title=clean_text(title),
                turns=turns,
                created=created,
                source="takeout",
                flags=flags,
            )
        )
    stats = {
        "form": "my-activity",
        "records": len(records),
        "kept": kept,
        "skipped_non_gemini": skipped_non_gemini,
        "conversations": len(convs),
        "without_response": without_response,
        "note": (
            "My Activity is prompt-centric; many records carry no model response. "
            "For full transcripts prefer the per-conversation Takeout export or the "
            "live userscript, and reconcile."
        ),
    }
    return convs, stats


def _extract_activity_response(record: dict) -> str:
    """Best-effort pull of a model response from a My Activity record.

    My Activity rarely stores the response, but when present it tends to live in
    ``subtitles`` (list of {name}) or a free-form ``details``/``description``.
    """
    subs = record.get("subtitles")
    if isinstance(subs, list):
        texts = [str(s.get("name", "")) for s in subs if isinstance(s, dict)]
        joined = "\n".join(t for t in texts if t).strip()
        if joined:
            return joined
    for key in ("response", "answer", "description"):
        val = record.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return ""
