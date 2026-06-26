# verify.py — The safety net: prove an export is not silently corrupt.
# Author: David Malko

"""Audit a list of conversations for the failure modes that broke the last run.

This module is the whole reason the project exists. The previous exporter
reported "zero errors" while silently re-saving one stale conversation body into
~280 slots. "Zero exceptions" is not "zero wrong content". The verifier asserts
*completeness and distinctness* instead of trusting that the scrape ran:

* **Duplicate bodies** — two different conversations with an identical non-empty
  body hash are the corruption fingerprint. The dominant duplicate is the stub.
* **Duplicate ratio** — if more than a small fraction of conversations share a
  body, the export FAILS (exit non-zero) so it is never trusted blindly.
* **Contiguous run** — a long stretch of consecutive conversations sharing one
  body is the exact shape of the stale-page bug ("from #190 onward").
* **Duplicate / missing ids**, and (optionally) completeness against an expected
  id set (e.g. the sidebar link list, or a Takeout export).

Empty / image-only bodies are reported as warnings, not failures: a model reply
that is only an image legitimately has no text and must not be mistaken for corruption.

All console output is ASCII-only so it is safe on a Windows code page.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field

from .models import Conversation


@dataclass
class DuplicateGroup:
    """A set of conversations that share one identical, non-empty body."""

    body_hash: str  # first 16 hex chars, enough to identify
    count: int
    sample_title: str
    sample_excerpt: str
    conversation_ids: list[str] = field(default_factory=list)


@dataclass
class VerifyReport:
    """Structured result of an audit. Serializable to JSON."""

    total: int
    unique_ids: int
    duplicate_ids: list[str]
    unique_titles: int
    nonempty_bodies: int
    empty_bodies: int
    distinct_body_hashes: int
    duplicated_conversation_count: int
    duplicate_ratio: float
    duplicate_groups: list[DuplicateGroup]
    dominant_stub: DuplicateGroup | None
    contiguous_corruption: dict | None
    missing_ids: list[str]
    failures: list[str]
    warnings: list[str]
    passed: bool

    def to_dict(self) -> dict:
        return asdict(self)


def _longest_same_body_run(convs: list[Conversation], min_run: int) -> dict | None:
    """Find the longest run of consecutive conversations sharing one body hash."""
    best: dict | None = None
    i, n = 0, len(convs)
    while i < n:
        if not convs[i].body_text().strip():
            i += 1
            continue
        h = convs[i].body_hash()
        j = i
        while (
            j + 1 < n
            and convs[j + 1].body_text().strip()
            and convs[j + 1].body_hash() == h
        ):
            j += 1
        run_len = j - i + 1
        if run_len >= min_run and (best is None or run_len > best["length"]):
            best = {
                "start_index": i + 1,  # 1-based, matches export numbering
                "end_index": j + 1,
                "length": run_len,
                "body_hash": h[:16],
                "sample_title": convs[i].title,
            }
        i = j + 1
    return best


def verify_conversations(
    convs: list[Conversation],
    *,
    dup_ratio_fail: float = 0.02,
    min_run: int = 5,
    expected_ids: Iterable[str] | None = None,
) -> VerifyReport:
    """Audit conversations and return a :class:`VerifyReport`.

    Args:
        convs: conversations in export order (order matters for run detection).
        dup_ratio_fail: fail if the duplicated-body fraction exceeds this.
        min_run: minimum consecutive same-body run length to flag.
        expected_ids: if given, any id in this set missing from `convs` is a failure.
    """
    total = len(convs)
    ids = [c.id for c in convs]
    id_counts = Counter(ids)
    duplicate_ids = sorted(i for i, n in id_counts.items() if n > 1)
    unique_titles = len({c.title for c in convs})

    by_hash: dict[str, list[Conversation]] = defaultdict(list)
    model_empty = 0  # conversations whose model reply is empty (image-only)
    for c in convs:
        if c.is_body_empty():
            model_empty += 1
        if not c.body_text().strip():
            continue  # nothing at all to hash (defensive; user prompt usually present)
        by_hash[c.body_hash()].append(c)
    nonempty = total - model_empty

    groups: list[DuplicateGroup] = []
    for h, members in by_hash.items():
        if len(members) > 1:
            sample = members[0]
            excerpt = " ".join(sample.body_text().split())[:160]
            groups.append(
                DuplicateGroup(
                    body_hash=h[:16],
                    count=len(members),
                    sample_title=sample.title,
                    sample_excerpt=excerpt,
                    conversation_ids=[m.id for m in members][:50],
                )
            )
    groups.sort(key=lambda g: -g.count)
    duplicated_count = sum(g.count for g in groups)
    dup_ratio = duplicated_count / total if total else 0.0
    dominant = groups[0] if groups else None
    contiguous = _longest_same_body_run(convs, min_run)

    missing_ids: list[str] = []
    if expected_ids is not None:
        missing_ids = sorted(set(expected_ids) - set(ids))

    failures: list[str] = []
    warnings: list[str] = []

    if total == 0:
        failures.append("export contains zero conversations")
    if duplicate_ids:
        failures.append(
            f"{len(duplicate_ids)} conversation id(s) appear more than once "
            f"(e.g. {', '.join(duplicate_ids[:3])})"
        )
    if dup_ratio > dup_ratio_fail:
        failures.append(
            f"{duplicated_count}/{total} conversations ({dup_ratio:.1%}) share a body "
            f"with another conversation - exceeds the {dup_ratio_fail:.1%} threshold. "
            f"This is the duplicate-stub scraper-corruption fingerprint."
        )
    elif groups:
        warnings.append(
            f"{duplicated_count} conversation(s) share a duplicated body "
            f"(under the {dup_ratio_fail:.1%} threshold, but inspect them)"
        )
    if contiguous:
        failures.append(
            f"contiguous duplicate run: conversations #{contiguous['start_index']}"
            f"-#{contiguous['end_index']} ({contiguous['length']} in a row) all share "
            f"one body (\"{contiguous['sample_title']}\") - classic stale-page corruption"
        )
    if missing_ids:
        failures.append(
            f"{len(missing_ids)} expected conversation id(s) are missing from the export"
        )
    if model_empty:
        warnings.append(
            f"{model_empty} conversation(s) have no model text "
            "(image-only replies or empties)"
        )

    return VerifyReport(
        total=total,
        unique_ids=len(set(ids)),
        duplicate_ids=duplicate_ids,
        unique_titles=unique_titles,
        nonempty_bodies=nonempty,
        empty_bodies=model_empty,
        distinct_body_hashes=len(by_hash),
        duplicated_conversation_count=duplicated_count,
        duplicate_ratio=round(dup_ratio, 4),
        duplicate_groups=groups,
        dominant_stub=dominant,
        contiguous_corruption=contiguous,
        missing_ids=missing_ids,
        failures=failures,
        warnings=warnings,
        passed=not failures,
    )


def format_report(report: VerifyReport) -> str:
    """Render an ASCII-only, human-readable audit report."""
    lines: list[str] = []
    add = lines.append
    add("=" * 60)
    add("  Gemini export verification report")
    add("=" * 60)
    add(f"  Conversations          : {report.total}")
    add(f"  Unique ids             : {report.unique_ids}")
    add(f"  Unique titles          : {report.unique_titles}")
    add(f"  Distinct body hashes   : {report.distinct_body_hashes}")
    add(f"  Non-empty / empty body : {report.nonempty_bodies} / {report.empty_bodies}")
    add(f"  Duplicated bodies      : {report.duplicated_conversation_count} "
        f"({report.duplicate_ratio:.1%})")
    if report.dominant_stub:
        d = report.dominant_stub
        add("")
        add(f"  Dominant duplicate stub appears {d.count}x:")
        add(f"    title  : {d.sample_title}")
        add(f"    excerpt: {d.sample_excerpt[:100]}")
    if report.contiguous_corruption:
        c = report.contiguous_corruption
        add(f"  Contiguous run: #{c['start_index']}-#{c['end_index']} "
            f"({c['length']} share one body)")
    add("-" * 60)
    for w in report.warnings:
        add(f"  [!]  {w}")
    for f in report.failures:
        add(f"  [FAIL] {f}")
    add("-" * 60)
    add(f"  RESULT: {'PASS' if report.passed else 'FAIL'}")
    add("=" * 60)
    return "\n".join(lines)
