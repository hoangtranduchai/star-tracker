"""Pytest shared fixtures for the Star Tracker test suite."""
from __future__ import annotations
import pathlib
import pytest
_SUITE_DIR = pathlib.Path(__file__).resolve().parent
_REPO_BASE = _SUITE_DIR.parent

@pytest.fixture(scope='session')
def star_tracker_root() -> pathlib.Path:
    """Return the root path of the star tracker repository."""
    return _REPO_BASE

@pytest.fixture(scope='session')
def bsc5_path(star_tracker_root: pathlib.Path) -> pathlib.Path:
    """Return the path to the cached BSC5 catalog archive."""
    return star_tracker_root.joinpath('data', 'catalogs', 'bsc5_v6.0.npz')
