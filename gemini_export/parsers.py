# parsers.py — Read exports from every supported on-disk format.
# Author: David Malko

"""Parsers that turn an on-disk export into a list of :class:`Conversation`.

Three input shapes are supported:

* **NDJSON** (`.ndjson`) — what the hardened userscript streams to disk: one
  JSON conversation object per line. Streaming-friendly and resumable.
* **Legacy plaintext** (`.txt`) — the delimited format produced by the original
  (buggy) exporter:  ``CONVERSATION N: <title>`` / ``[id: ...]`` blocks with
  ``[DAVID]:`` / ``[GEMINI]:`` turn markers. Parsing it lets the verifier audit
  old dumps and prove the corruption.
* **JSON** (`.json`) — an array of conversation dicts, or ``{"conversations": [...]}``.

`load_conversations` dispatches on file extension with a content sniff fallback.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .models import ROLE_MODEL, ROLE_USER, Conversation, Turn, clean_text

# A run of 6+ '=' then a CONVERSATION header line then an [id: ...] line.
_LEGACY_HEADER = re.compile(
    r"={6,}\s*\nCONVERSATION\s+\d+:\s*(?P<title>.*?)\n"
    r"\[id:\s*(?P<id>[^\]]+)\]\s*\n={6,}\s*\n",
)
# Turn markers like "[DAVID]:" / "[GEMINI]:" each on their own line.
_LEGACY_TURN = re.compile(r"(?m)^\[(DAVID|GEMINI)\]:[ \t]*\n?")


def parse_legacy_txt(path: str | Path) -> list[Conversation]:
    """Parse the original exporter's delimited plaintext format."""
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    # split() with capturing groups yields: [pre, title, id, body, title, id, body, ...]
    parts = _LEGACY_HEADER.split(raw)
    convs: list[Conversation] = []
    for i in range(1, len(parts), 3):
        title, cid, body = parts[i], parts[i + 1], parts[i + 2]
        convs.append(_legacy_body_to_conversation(cid.strip(), title, body))
    return convs


def _legacy_body_to_conversation(cid: str, title: str, body: str) -> Conversation:
    chunks = _LEGACY_TURN.split(body)
    # chunks: [preamble, role, text, role, text, ...]
    turns: list[Turn] = []
    for j in range(1, len(chunks), 2):
        role_raw = chunks[j]
        text = clean_text(chunks[j + 1]) if j + 1 < len(chunks) else ""
        role = ROLE_USER if role_raw == "DAVID" else ROLE_MODEL
        turns.append(Turn(role=role, text=text))
    return Conversation(
        id=cid, title=clean_text(title), turns=turns, source="legacy-txt"
    )


def parse_ndjson(path: str | Path) -> list[Conversation]:
    """Parse one-JSON-object-per-line NDJSON (skips blank lines)."""
    convs: list[Conversation] = []
    for lineno, line in enumerate(
        Path(path).read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = line.strip()
        if not line:
            continue
        try:
            convs.append(Conversation.from_dict(json.loads(line)))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed NDJSON on line {lineno}: {exc}") from exc
    return convs


def parse_json(path: str | Path) -> list[Conversation]:
    """Parse a JSON array of conversations or a ``{"conversations": [...]}`` wrapper."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "conversations" in data:
        data = data["conversations"]
    if isinstance(data, dict):  # a single conversation object
        data = [data]
    if not isinstance(data, list):
        raise ValueError("JSON export must be a list or a {'conversations': [...]} object")
    return [Conversation.from_dict(d) for d in data]


def load_conversations(path: str | Path) -> list[Conversation]:
    """Dispatch to the right parser by extension, with a content-sniff fallback."""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".ndjson":
        return parse_ndjson(p)
    if suffix == ".json":
        return parse_json(p)
    if suffix == ".txt":
        return parse_legacy_txt(p)

    # Unknown extension: sniff the first non-space character.
    head = p.read_text(encoding="utf-8", errors="replace").lstrip()[:1]
    if head in ("[", "{"):
        # Could be a JSON document or NDJSON; try JSON first, then NDJSON.
        try:
            return parse_json(p)
        except (json.JSONDecodeError, ValueError):
            return parse_ndjson(p)
    return parse_legacy_txt(p)
