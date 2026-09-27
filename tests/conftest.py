"""Pytest path bootstrap so `from src...` works from repo root or star_tracker/."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

STAR_TRACKER_ROOT = Path(__file__).resolve().parent.parent
if str(STAR_TRACKER_ROOT) not in sys.path:
    sys.path.insert(0, str(STAR_TRACKER_ROOT))

CATALOG_DIR = STAR_TRACKER_ROOT / "data" / "catalogs"
BSC5_PATH = CATALOG_DIR / "BSC5"


@pytest.fixture(scope="session")
def star_tracker_root() -> Path:
    return STAR_TRACKER_ROOT


@pytest.fixture(scope="session")
def bsc5_path() -> Path:
    return BSC5_PATH
