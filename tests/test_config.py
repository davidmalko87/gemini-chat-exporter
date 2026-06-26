# tests/test_config.py — configuration loading and validation.
# Author: David Malko

"""Tests for ExportConfig defaults, validation, and .env overrides."""

import pytest

from gemini_export.config import ExportConfig, load_config


def test_defaults_are_valid():
    cfg = ExportConfig()
    assert cfg.validate() == []
    assert cfg.dup_ratio_fail == 0.02
    assert cfg.write_json and cfg.write_markdown


def test_invalid_ratio_and_run():
    assert ExportConfig(dup_ratio_fail=2.0).validate()
    assert ExportConfig(min_run=1).validate()
    assert ExportConfig(write_json=False, write_markdown=False).validate()


def test_load_config_without_env_uses_defaults(tmp_path):
    # Point at a non-existent .env -> defaults, no error.
    cfg = load_config(str(tmp_path / "nope.env"))
    assert cfg.dup_ratio_fail == 0.02


def test_load_config_reads_env(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("DUP_RATIO_FAIL=0.05\nMIN_RUN=10\nWRITE_MARKDOWN=false\n", encoding="utf-8")
    # Ensure no stray process env overrides the file values.
    monkeypatch.delenv("DUP_RATIO_FAIL", raising=False)
    monkeypatch.delenv("MIN_RUN", raising=False)
    monkeypatch.delenv("WRITE_MARKDOWN", raising=False)
    cfg = load_config(str(env))
    assert cfg.dup_ratio_fail == 0.05
    assert cfg.min_run == 10
    assert cfg.write_markdown is False


def test_load_config_raises_on_invalid_env(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("DUP_RATIO_FAIL=5\n", encoding="utf-8")
    monkeypatch.delenv("DUP_RATIO_FAIL", raising=False)
    with pytest.raises(ValueError):
        load_config(str(env))
