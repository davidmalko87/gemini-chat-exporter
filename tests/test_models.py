# tests/test_models.py — clean_text + Conversation behavior.
# Author: David Malko

"""Offline unit tests for the core data model and text normalization."""

from gemini_export.models import (
    ROLE_MODEL,
    ROLE_USER,
    Conversation,
    Turn,
    clean_text,
)


def test_clean_text_strips_screen_reader_labels():
    assert clean_text("You said\nhello there") == "hello there"
    assert clean_text("Gemini said: hi") == "hi"


def test_clean_text_normalizes_nbsp_and_blank_runs():
    assert clean_text("a" + chr(0xA0) + "b" + chr(0x202F) + "c") == "a b c"
    assert clean_text("x\n\n\n\ny") == "x\n\ny"
    assert clean_text("  trailing   spaces  ") == "trailing spaces"


def test_clean_text_empty():
    assert clean_text("") == ""
    assert clean_text(None) == ""  # type: ignore[arg-type]


def test_body_hash_groups_identical_content():
    a = Conversation("1", "t", [Turn(ROLE_USER, "hi"), Turn(ROLE_MODEL, "yo")])
    b = Conversation("2", "t", [Turn(ROLE_USER, "hi"), Turn(ROLE_MODEL, "yo")])
    c = Conversation("3", "t", [Turn(ROLE_USER, "hi"), Turn(ROLE_MODEL, "different")])
    # Identical transcripts hash the same -> this is the duplicate fingerprint.
    assert a.body_hash() == b.body_hash()
    assert a.body_hash() != c.body_hash()


def test_first_user_prompt_skips_empty_and_model():
    c = Conversation(
        "1", "t", [Turn(ROLE_MODEL, "intro"), Turn(ROLE_USER, "  real prompt ")]
    )
    assert c.first_user_prompt() == "real prompt"


def test_is_body_empty_for_image_only():
    img = Conversation("1", "t", [Turn(ROLE_USER, "draw"), Turn(ROLE_MODEL, "")])
    full = Conversation("2", "t", [Turn(ROLE_USER, "q"), Turn(ROLE_MODEL, "a")])
    assert img.is_body_empty()
    assert not full.is_body_empty()


def test_dict_roundtrip():
    c = Conversation(
        "1",
        "t",
        [Turn(ROLE_USER, "q"), Turn(ROLE_MODEL, "a")],
        created="2025-01-01",
        source="scraper",
        flags=["needs-review"],
    )
    assert Conversation.from_dict(c.to_dict()).to_dict() == c.to_dict()
