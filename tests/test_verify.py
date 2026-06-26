# tests/test_verify.py — the corruption-detection regression suite.
# Author: David Malko

"""These tests are the heart of the project.

They assert that the verifier flags the exact failure that silently corrupted the
previous export (duplicate-stub bodies, contiguous run) and that a clean export
passes. If any of these regress, the safety net has a hole.
"""

from gemini_export.models import ROLE_MODEL, ROLE_USER, Conversation, Turn
from gemini_export.parsers import parse_legacy_txt
from gemini_export.verify import verify_conversations


def test_corrupted_export_is_flagged(fixtures_dir):
    convs = parse_legacy_txt(fixtures_dir / "corrupted_sample.txt")
    r = verify_conversations(convs)

    assert r.passed is False
    # 3 unique conversations + 1 repeated stub body = 4 distinct hashes.
    assert r.distinct_body_hashes == 4
    assert r.dominant_stub is not None
    assert r.dominant_stub.count == 5
    assert r.duplicate_ratio > 0.5
    # The stub run is conversations #4..#8 (5 in a row).
    assert r.contiguous_corruption is not None
    assert r.contiguous_corruption["start_index"] == 4
    assert r.contiguous_corruption["end_index"] == 8
    assert r.contiguous_corruption["length"] == 5
    assert any("fingerprint" in f for f in r.failures)


def test_corrupted_export_exit_nonzero_via_passed(fixtures_dir):
    convs = parse_legacy_txt(fixtures_dir / "corrupted_sample.txt")
    r = verify_conversations(convs)
    # cmd_verify returns 0 if passed else 1.
    assert (0 if r.passed else 1) == 1


def test_clean_export_passes(fixtures_dir):
    convs = parse_legacy_txt(fixtures_dir / "clean_sample.txt")
    r = verify_conversations(convs)

    assert r.passed is True
    assert r.distinct_body_hashes == 4
    assert r.empty_bodies == 1  # the image-only conversation
    assert any("no model text" in w for w in r.warnings)


def test_duplicate_ids_fail():
    convs = [
        Conversation("dup", "a", [Turn(ROLE_USER, "q1"), Turn(ROLE_MODEL, "a1")]),
        Conversation("dup", "b", [Turn(ROLE_USER, "q2"), Turn(ROLE_MODEL, "a2")]),
    ]
    r = verify_conversations(convs)
    assert r.passed is False
    assert "dup" in r.duplicate_ids


def test_expected_ids_missing_fails(fixtures_dir):
    convs = parse_legacy_txt(fixtures_dir / "clean_sample.txt")
    r = verify_conversations(
        convs, expected_ids=["bbbb000000000001", "zzzz999999999999"]
    )
    assert r.passed is False
    assert "zzzz999999999999" in r.missing_ids


def test_empty_export_fails():
    r = verify_conversations([])
    assert r.passed is False
    assert any("zero conversations" in f for f in r.failures)


def test_small_duplicate_under_threshold_warns_not_fails():
    # 100 unique + 1 dup pair would be ~2%, keep it clearly under the 2% default.
    convs = [
        Conversation(f"id{i}", "t", [Turn(ROLE_USER, f"q{i}"), Turn(ROLE_MODEL, f"a{i}")])
        for i in range(200)
    ]
    # Make exactly one extra duplicate of conversation 0 (well under 2%).
    convs.append(
        Conversation("idDUPBODY", "t", [Turn(ROLE_USER, "q0"), Turn(ROLE_MODEL, "a0")])
    )
    r = verify_conversations(convs, min_run=5)
    # Two conversations share a body, but ratio is < 2% -> warning, still passes.
    assert r.duplicated_conversation_count == 2
    assert r.passed is True
    assert any("duplicated body" in w for w in r.warnings)
