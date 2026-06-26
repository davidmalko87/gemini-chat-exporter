# tests/test_convert.py — JSON/Markdown/manifest output.
# Author: David Malko

"""Tests that conversion writes faithful files, an integrity manifest, and that
the ``complete`` flag honestly reflects the verification result."""

import json

from gemini_export.convert import conversation_to_markdown, convert
from gemini_export.models import ROLE_MODEL, ROLE_USER, Conversation, Turn


def _sample():
    return [
        Conversation(
            "id1",
            "Capital of France",
            [Turn(ROLE_USER, "What is the capital?"), Turn(ROLE_MODEL, "Paris.")],
            source="scraper",
        ),
        # Non-Latin title must still produce an ASCII filename.
        Conversation(
            "id2",
            "Привіт світ",
            [Turn(ROLE_USER, "Привіт"), Turn(ROLE_MODEL, "Вітаю")],
            source="scraper",
        ),
    ]


def test_convert_writes_files_and_manifest(tmp_path):
    manifest = convert(_sample(), tmp_path, complete=True)
    assert manifest["conversation_count"] == 2
    assert manifest["complete"] is True
    files = {p.name for p in tmp_path.iterdir()}
    assert "manifest.json" in files
    # Each conversation yields a .json and .md, filenames are ASCII.
    md_files = [p for p in tmp_path.iterdir() if p.suffix == ".md"]
    json_files = [
        p for p in tmp_path.iterdir() if p.suffix == ".json" and p.name != "manifest.json"
    ]
    assert len(md_files) == 2
    assert len(json_files) == 2
    for p in tmp_path.iterdir():
        assert p.name.isascii(), f"non-ascii filename: {p.name}"


def test_manifest_has_checksums(tmp_path):
    convert(_sample(), tmp_path, complete=True)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["conversations"]:
        assert len(entry["body_sha256"]) == 64
        assert len(entry["json_sha256"]) == 64
        assert len(entry["md_sha256"]) == 64


def test_complete_flag_reflects_verification(tmp_path):
    manifest = convert(_sample(), tmp_path, complete=False)
    assert manifest["complete"] is False


def test_dry_run_writes_nothing(tmp_path):
    manifest = convert(_sample(), tmp_path, complete=True, dry_run=True)
    assert manifest["conversation_count"] == 2
    assert list(tmp_path.iterdir()) == []  # nothing on disk


def test_markdown_structure_and_image_placeholder():
    conv = Conversation(
        "id3",
        "Image",
        [Turn(ROLE_USER, "draw a cat"), Turn(ROLE_MODEL, "")],
    )
    md = conversation_to_markdown(conv)
    assert md.startswith("# Image")
    assert "## David" in md
    assert "## Gemini" in md
    assert "image or no text response" in md
