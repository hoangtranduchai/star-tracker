"""Verification tests for the real Yale Bright Star Catalog (BSC5) and cached K-vector table."""
from __future__ import annotations
import numpy as np
import pytest
from src.catalog import CatalogManager
from src.kvector import KVectorTable

def _verify(flag: bool, detail: str='') -> None:
    if not flag:
        raise AssertionError(detail)

def test_bsc5_real_stars_present(bsc5_path: object) -> object:
    if not bsc5_path.exists():
        pytest.skip('BSC5 archive not yet fetched; run scripts/fetch_catalog.py first')
    catalog: object = CatalogManager.load_npz(bsc5_path)
    _verify(catalog.source.startswith('BSC5'))
    _verify(4000 <= len(catalog.ids) <= 6000)
    norms: object = np.linalg.norm(catalog.vectors, axis=-1)
    np.testing.assert_allclose(norms, 1.0, atol=1e-12)
    _verify(float(catalog.mags.max()) <= 6.0001)
    id_list: object = catalog.ids.tolist()
    for hr_num, target_mag in ((2491, -1.46), (7001, 0.03)):
        _verify(hr_num in id_list, f'Missing HR {hr_num}')
        pos: object = int(np.where(catalog.ids == hr_num)[0][0])
        _verify(abs(float(catalog.mags[pos]) - target_mag) < 0.1)

def test_bsc5_kvector_loads_and_matches_fingerprint(star_tracker_root: object, bsc5_path: object) -> object:
    kv_archive: object = star_tracker_root.joinpath('data', 'catalogs', 'kvector_bsc5_v6.0.npz')
    if not (bsc5_path.exists() and kv_archive.exists()):
        pytest.skip('Pre-built BSC5 K-vector archive not present')
    catalog: object = CatalogManager.load_npz(bsc5_path)
    kv_index: object = KVectorTable.load(kv_archive)
    _verify(kv_index.catalog_fingerprint == catalog.fingerprint())
    _verify(kv_index.n_pairs > 100000)
    matches: object = kv_index.query(float(np.deg2rad(5.0)), float(np.deg2rad(0.01)))
    _verify(len(matches) > 10)
