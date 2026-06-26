# config.py — Load and validate optional configuration.
# Author: David Malko

"""Configuration for the Gemini export toolkit.

Unlike a REST tool, this toolkit needs no credentials — everything it touches is
a local file. Configuration is therefore optional: sensible defaults work out of
the box, and any tunable can be overridden via `.env` or a CLI flag. The `.env`
file (if present) is loaded with python-dotenv; if it is absent we simply use
defaults rather than erroring out.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:  # python-dotenv is a convenience, not a hard requirement.
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - exercised only without the dep
    def load_dotenv(*_args, **_kwargs) -> bool:
        return False


@dataclass
class ExportConfig:
    """All tunables for the Gemini export toolkit."""

    output_root: str = "./out"
    # Verifier: fail when more than this fraction of conversations share a body.
    dup_ratio_fail: float = 0.02
    # Verifier: minimum length of a consecutive same-body run to flag as a run.
    min_run: int = 5
    # Output toggles.
    write_json: bool = True
    write_markdown: bool = True

    def validate(self) -> list[str]:
        """Return a list of validation errors (empty when config is valid)."""
        errors: list[str] = []
        if not 0 <= self.dup_ratio_fail <= 1:
            errors.append("DUP_RATIO_FAIL must be between 0 and 1")
        if self.min_run < 2:
            errors.append("MIN_RUN must be >= 2")
        if not self.write_json and not self.write_markdown:
            errors.append("At least one of WRITE_JSON / WRITE_MARKDOWN must be true")
        return errors


def load_config(env_path: str | None = None) -> ExportConfig:
    """Load configuration from `.env` if present, else use defaults.

    Args:
        env_path: Explicit path to a `.env` file. If None, looks for `./.env`.

    Returns:
        A validated :class:`ExportConfig`.

    Raises:
        ValueError: if an explicitly provided config fails validation.
    """
    dotenv_path = Path(env_path) if env_path else Path(".env")
    if dotenv_path.exists():
        load_dotenv(dotenv_path)

    def _bool(key: str, default: bool) -> bool:
        return os.getenv(key, str(default)).strip().lower() in ("true", "1", "yes")

    def _float(key: str, default: float) -> float:
        try:
            return float(os.getenv(key, str(default)))
        except ValueError:
            return default

    def _int(key: str, default: int) -> int:
        try:
            return int(os.getenv(key, str(default)))
        except ValueError:
            return default

    config = ExportConfig(
        output_root=os.getenv("OUTPUT_ROOT", "./out"),
        dup_ratio_fail=_float("DUP_RATIO_FAIL", 0.02),
        min_run=_int("MIN_RUN", 5),
        write_json=_bool("WRITE_JSON", True),
        write_markdown=_bool("WRITE_MARKDOWN", True),
    )

    errors = config.validate()
    if errors:
        raise ValueError("Invalid configuration: " + "; ".join(errors))
    return config
