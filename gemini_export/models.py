# models.py — Core data model for Gemini conversations.
# Author: David Malko

"""Data model shared by every parser, the verifier, and the converters.

A :class:`Conversation` is the normalized in-memory shape that every input
source (live scraper NDJSON, legacy plaintext, Google Takeout JSON) is mapped
to. Keeping one model means the verifier and converters never need to know
where the data came from.

The body hash (see :meth:`Conversation.body_hash`) is the single most important
thing in this whole tool: it is how we detect the silent duplicate-stub
corruption that wrecked the previous export. Two *different* conversations that
share an identical, non-empty body hash are the fingerprint of a scraper that
re-saved a stale page instead of the conversation it claimed to.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

# Roles are normalized to these two values everywhere.
ROLE_USER = "user"
ROLE_MODEL = "model"

_WS_RUN = re.compile(r"[ \t]+")
_NL_RUN = re.compile(r"\n{3,}")
# Screen-reader / a11y labels Gemini injects that are not real content.
_SR_LABELS = re.compile(r"^(you said|gemini said)\b[:\s]*", re.IGNORECASE)

# No-break spaces Gemini's DOM sometimes emits, normalized to plain spaces.
# Built from code points so the source file stays pure ASCII.
_NBSP = chr(0xA0)  # U+00A0 no-break space
_NARROW_NBSP = chr(0x202F)  # U+202F narrow no-break space


def clean_text(text: str) -> str:
    """Normalize scraped text without altering meaningful content.

    - Strips leading "You said" / "Gemini said" screen-reader labels.
    - Replaces no-break spaces (U+00A0 / U+202F) with normal spaces.
    - Collapses runs of spaces/tabs and 3+ newlines.
    - Trims trailing whitespace on each line and the ends.

    Pure and deterministic so it can be unit-tested offline.
    """
    if not text:
        return ""
    text = text.replace(_NBSP, " ").replace(_NARROW_NBSP, " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _SR_LABELS.sub("", text.lstrip())
    # Trim trailing spaces per line, collapse inner space runs.
    lines = [_WS_RUN.sub(" ", ln).rstrip() for ln in text.split("\n")]
    text = "\n".join(lines)
    text = _NL_RUN.sub("\n\n", text)
    return text.strip()


@dataclass
class Turn:
    """One message in a conversation."""

    role: str  # ROLE_USER or ROLE_MODEL
    text: str

    def is_empty(self) -> bool:
        return not self.text.strip()


@dataclass
class Conversation:
    """A single Gemini conversation, normalized across all sources."""

    id: str
    title: str
    turns: list[Turn] = field(default_factory=list)
    created: str | None = None  # ISO-8601 string if known
    source: str = ""  # "scraper" | "takeout" | "legacy-txt"
    flags: list[str] = field(default_factory=list)  # e.g. "needs-review"

    # -- derived views -----------------------------------------------------

    def body_text(self) -> str:
        """Canonical body used for duplicate detection and hashing.

        Includes every turn (role + text) so that two conversations are
        considered identical only when their *entire* exchange matches. This
        is deliberately strict: it is what catches the stale-stub bug.
        """
        return "\n".join(f"{t.role}: {t.text.strip()}" for t in self.turns).strip()

    def body_hash(self) -> str:
        """SHA-256 of the canonical body (full hex digest)."""
        return hashlib.sha256(self.body_text().encode("utf-8")).hexdigest()

    def first_user_prompt(self) -> str:
        """First user turn text — used by the scraper's content-identity check."""
        for t in self.turns:
            if t.role == ROLE_USER and t.text.strip():
                return t.text.strip()
        return ""

    def is_body_empty(self) -> bool:
        """True when there is no model text at all (e.g. image-only replies)."""
        return all(t.role != ROLE_MODEL or t.is_empty() for t in self.turns)

    def to_dict(self) -> dict:
        """Plain-dict form for JSON output."""
        d: dict = {
            "id": self.id,
            "title": self.title,
            "turns": [{"role": t.role, "text": t.text} for t in self.turns],
        }
        if self.created:
            d["created"] = self.created
        if self.source:
            d["source"] = self.source
        if self.flags:
            d["flags"] = list(self.flags)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Conversation:
        """Inverse of :meth:`to_dict`; tolerant of missing optional fields."""
        turns = [
            Turn(role=str(t.get("role", "")), text=str(t.get("text", "")))
            for t in (d.get("turns") or [])
        ]
        return cls(
            id=str(d.get("id", "")),
            title=str(d.get("title", "")),
            turns=turns,
            created=d.get("created"),
            source=str(d.get("source", "")),
            flags=list(d.get("flags") or []),
        )
