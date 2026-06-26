# tests/conftest.py — shared pytest fixtures.
# Author: David Malko

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Directory holding the synthetic sample exports (no real personal data)."""
    return FIXTURES
