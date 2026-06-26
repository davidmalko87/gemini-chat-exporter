# reconcile.py — Cross-check a scraper export against Google Takeout.
# Author: David Malko

"""Reconcile a (possibly corrupt) scraper export against authoritative Takeout.

Two independent sources let each cover the other's weakness:

* the **scraper** can silently duplicate a stale body (the incident);
* **Takeout** is authoritative but prompt-centric / lower-fidelity.

`reconcile` finds scraper conversations whose body is a duplicated stub and, when
Takeout has the same conversation id with real, distinct content, marks it
**recoverable from Takeout** — the path back for the conversations the last run
overwrote. It reports, it does not mutate; merging is an explicit follow-up.
"""

from __future__ import annotations

from collections import defaultdict

from .models import Conversation


def _duplicate_hashes(convs: list[Conversation]) -> set[str]:
    by_hash: defaultdict[str, int] = defaultdict(int)
    for c in convs:
        if c.body_text().strip():
            by_hash[c.body_hash()] += 1
    return {h for h, n in by_hash.items() if n > 1}


def reconcile(
    scraper_convs: list[Conversation], takeout_convs: list[Conversation]
) -> dict:
    """Diff scraper output against Takeout and report recoverable conversations."""
    dup_hashes = _duplicate_hashes(scraper_convs)
    takeout_by_id = {c.id: c for c in takeout_convs}
    takeout_ids = set(takeout_by_id)
    scraper_ids = {c.id for c in scraper_convs}

    recoverable: list[dict] = []
    corrupt_unrecoverable: list[dict] = []
    for c in scraper_convs:
        if not c.body_text().strip() or c.body_hash() not in dup_hashes:
            continue  # this conversation looks fine
        t = takeout_by_id.get(c.id)
        if t and t.body_text().strip() and t.body_hash() != c.body_hash():
            recoverable.append(
                {"id": c.id, "title": c.title, "takeout_title": t.title}
            )
        else:
            corrupt_unrecoverable.append({"id": c.id, "title": c.title})

    return {
        "scraper_total": len(scraper_convs),
        "takeout_total": len(takeout_convs),
        "corrupt_in_scraper": len(recoverable) + len(corrupt_unrecoverable),
        "recoverable_from_takeout": recoverable,
        "corrupt_not_in_takeout": corrupt_unrecoverable,
        "only_in_takeout": sorted(takeout_ids - scraper_ids),
        "only_in_scraper": sorted(scraper_ids - takeout_ids),
    }


def format_reconcile(report: dict) -> str:
    """ASCII-only summary of a reconcile report."""
    lines = [
        "=" * 60,
        "  Scraper vs Takeout reconciliation",
        "=" * 60,
        f"  Scraper conversations : {report['scraper_total']}",
        f"  Takeout conversations : {report['takeout_total']}",
        f"  Corrupt in scraper    : {report['corrupt_in_scraper']}",
        f"  Recoverable (Takeout) : {len(report['recoverable_from_takeout'])}",
        f"  Corrupt, no Takeout   : {len(report['corrupt_not_in_takeout'])}",
        f"  Only in Takeout       : {len(report['only_in_takeout'])}",
        f"  Only in scraper       : {len(report['only_in_scraper'])}",
        "=" * 60,
    ]
    return "\n".join(lines)
