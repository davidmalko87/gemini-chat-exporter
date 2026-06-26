# tests/test_reconcile.py — scraper-vs-Takeout reconciliation.
# Author: David Malko

"""Tests that reconcile identifies which corrupt scraper rows Takeout can recover."""

from gemini_export.models import ROLE_MODEL, ROLE_USER, Conversation, Turn
from gemini_export.reconcile import reconcile


def _stub():
    return [Turn(ROLE_USER, "stub prompt"), Turn(ROLE_MODEL, "STALE STUB BODY")]


def test_reconcile_marks_recoverable_and_unrecoverable():
    scraper = [
        Conversation("real1", "r1", [Turn(ROLE_USER, "a"), Turn(ROLE_MODEL, "unique1")]),
        Conversation("dup1", "d1", _stub()),
        Conversation("dup2", "d2", _stub()),
    ]
    takeout = [
        Conversation(
            "dup1",
            "d1-real",
            [Turn(ROLE_USER, "a"), Turn(ROLE_MODEL, "REAL CONTENT FROM TAKEOUT")],
        ),
    ]
    rep = reconcile(scraper, takeout)

    assert rep["corrupt_in_scraper"] == 2
    recoverable_ids = [r["id"] for r in rep["recoverable_from_takeout"]]
    assert recoverable_ids == ["dup1"]
    unrecoverable_ids = [r["id"] for r in rep["corrupt_not_in_takeout"]]
    assert unrecoverable_ids == ["dup2"]
    # dup2 has no Takeout match, so it is also "only in scraper" (sorted).
    assert rep["only_in_scraper"] == ["dup2", "real1"]


def test_reconcile_clean_scraper_has_no_corruption():
    scraper = [
        Conversation("a", "a", [Turn(ROLE_USER, "qa"), Turn(ROLE_MODEL, "ans-a")]),
        Conversation("b", "b", [Turn(ROLE_USER, "qb"), Turn(ROLE_MODEL, "ans-b")]),
    ]
    rep = reconcile(scraper, [])
    assert rep["corrupt_in_scraper"] == 0
