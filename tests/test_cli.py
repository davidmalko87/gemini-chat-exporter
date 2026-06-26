# tests/test_cli.py — end-to-end CLI exit codes and side effects.
# Author: David Malko

"""Tests the CLI returns the right exit codes and writes the right artifacts.

``--verify`` / ``--validate`` must exit non-zero on a corrupt export so they can
gate cron jobs and CI; conversion must honor ``--dry-run``."""

from gemini_export.cli import main


def test_verify_corrupted_returns_1(fixtures_dir, tmp_path):
    rc = main(["--verify", str(fixtures_dir / "corrupted_sample.txt"), "--out", str(tmp_path)])
    assert rc == 1
    assert (tmp_path / "verify_report.json").exists()


def test_validate_clean_returns_0(fixtures_dir, tmp_path):
    rc = main(["--validate", str(fixtures_dir / "clean_sample.txt"), "--out", str(tmp_path)])
    assert rc == 0


def test_convert_dry_run_writes_nothing(fixtures_dir, tmp_path):
    rc = main(
        ["--convert", str(fixtures_dir / "clean_sample.txt"), "--out", str(tmp_path), "--dry-run"]
    )
    assert rc == 0
    assert list(tmp_path.iterdir()) == []


def test_import_takeout_writes_manifest(fixtures_dir, tmp_path):
    takeout = str(fixtures_dir / "takeout_conversations.json")
    rc = main(["--import-takeout", takeout, "--out", str(tmp_path)])
    assert rc == 0
    assert (tmp_path / "manifest.json").exists()


def test_reconcile_cli_writes_report(fixtures_dir, tmp_path):
    rc = main(
        [
            "--reconcile",
            str(fixtures_dir / "corrupted_sample.txt"),
            str(fixtures_dir / "takeout_conversations.json"),
            "--out",
            str(tmp_path),
        ]
    )
    assert rc == 0
    assert (tmp_path / "reconcile_report.json").exists()


def test_dup_ratio_override_makes_corrupted_pass(fixtures_dir, tmp_path):
    # With a permissive threshold the ratio check won't fire, but the contiguous
    # run still will -> still fails. Proves the run check is independent.
    rc = main(
        [
            "--verify",
            str(fixtures_dir / "corrupted_sample.txt"),
            "--dup-ratio",
            "0.99",
            "--out",
            str(tmp_path),
        ]
    )
    assert rc == 1  # contiguous run still trips it
