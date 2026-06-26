# tests/test_parsers.py — legacy txt / ndjson / json parsing.
# Author: David Malko

"""Offline tests for the on-disk parsers and format dispatch."""

from gemini_export.parsers import (
    load_conversations,
    parse_legacy_txt,
)


def test_parse_legacy_corrupted(fixtures_dir):
    convs = parse_legacy_txt(fixtures_dir / "corrupted_sample.txt")
    assert len(convs) == 8
    assert convs[0].id == "aaaa000000000001"
    assert convs[0].title == "Capital of France"
    assert convs[0].turns[0].role == "user"
    assert convs[0].turns[1].role == "model"
    assert "Paris" in convs[0].turns[1].text


def test_parse_legacy_clean_with_image_only(fixtures_dir):
    convs = parse_legacy_txt(fixtures_dir / "clean_sample.txt")
    assert len(convs) == 4
    # Last conversation is an image-only response (empty model text).
    assert convs[3].is_body_empty()


def test_load_dispatch_ndjson(tmp_path):
    p = tmp_path / "x.ndjson"
    p.write_text(
        '{"id":"1","title":"t","turns":[{"role":"user","text":"q"}]}\n'
        "\n"  # blank line should be skipped
        '{"id":"2","title":"t2","turns":[]}\n',
        encoding="utf-8",
    )
    convs = load_conversations(p)
    assert [c.id for c in convs] == ["1", "2"]


def test_load_dispatch_json_array(tmp_path):
    p = tmp_path / "x.json"
    p.write_text('[{"id":"1","title":"t","turns":[]}]', encoding="utf-8")
    assert len(load_conversations(p)) == 1


def test_load_dispatch_json_wrapped(tmp_path):
    p = tmp_path / "x.json"
    p.write_text('{"conversations":[{"id":"1","title":"t","turns":[]}]}', encoding="utf-8")
    assert len(load_conversations(p)) == 1
