"""Tests for Hipparcos catalog loading and proper-motion propagation."""
from __future__ import annotations
import numpy as np
import pytest
from src.catalog import CatalogManager

def _check_hip(cond: bool, msg: str='') -> None:
    if not cond:
        raise AssertionError(msg)

def test_hipparcos_npz_if_available(star_tracker_root: object) -> object:
    hip_file: object = star_tracker_root.joinpath('data', 'catalogs', 'hipparcos_v6.0.npz')
    if not hip_file.exists():
        pytest.skip('Hipparcos archive not present')
    cat: object = CatalogManager.load_npz(hip_file)
    _check_hip(len(cat.ids) > 3000)
    norms: object = np.linalg.norm(cat.vectors, axis=-1)
    np.testing.assert_allclose(norms, 1.0, atol=1e-11)
    _check_hip(float(cat.mags.max()) <= 6.01)
