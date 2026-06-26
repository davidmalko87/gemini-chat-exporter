# tests/test_takeout.py — schema-tolerant Takeout import.
# Author: David Malko

"""Tests that both known Takeout shapes import and that non-Gemini rows drop."""

from gemini_export.takeout import import_takeout


def test_import_myactivity_array(fixtures_dir):
    convs, stats = import_takeout(fixtures_dir / "takeout_myactivity.json")
    assert stats["form"] == "my-activity"
    # Two Gemini rows kept, one "Search" row skipped.
    assert stats["skipped_non_gemini"] == 1
    assert len(convs) == 2
    ids = {c.id for c in convs}
    assert "cccc000000000001" in ids  # extracted from /app/<id>
    # First row had no response -> counted; second row had a subtitles response.
    assert stats["without_response"] == 1
    by_id = {c.id: c for c in convs}
    assert by_id["cccc000000000001"].first_user_prompt().startswith("What is the capital")
    assert any(t.role == "model" for t in by_id["cccc000000000002"].turns)


def test_import_conversations_form(fixtures_dir):
    convs, stats = import_takeout(fixtures_dir / "takeout_conversations.json")
    assert stats["form"] == "conversations"
    assert len(convs) == 2
    first = convs[0]
    assert first.id == "cccc000000000001"
    assert first.turns[0].role == "user"
    assert first.turns[1].role == "model"
    assert "Paris" in first.turns[1].text
    # Second uses author/content keys -> still normalized.
    second = convs[1]
    assert second.turns[0].role == "user"
    assert "calls itself" in second.turns[1].text


def test_takeout_conversations_all_have_responses(fixtures_dir):
    _convs, stats = import_takeout(fixtures_dir / "takeout_conversations.json")
    assert stats["without_response"] == 0
