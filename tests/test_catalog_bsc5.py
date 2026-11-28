"""Verification tests for the real Yale Bright Star Catalog (BSC5) and cached K-vector table."""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pytest
from src.catalog import CatalogManager
from src.kvector import KVectorTable, cache_path_for

def _verify(flag: bool, detail: str='') -> None:
    if not flag:
        raise AssertionError(detail)

def _load_or_build_bsc5(star_tracker_root: Path, bsc5_path: Path) -> object:
    if bsc5_path.exists():
        return CatalogManager.load_npz(bsc5_path)
    bsc_bin = star_tracker_root.joinpath('data', 'catalogs', 'BSC5')
    if not bsc_bin.is_file():
        pytest.skip('BSC5 binary not present; run scripts/fetch_catalog.py first')
    raw = CatalogManager.load_bsc5(bsc_bin, max_mag=6.0, epoch_year=2026.7)
    return CatalogManager.filter_close_pairs(raw, 60.0)

def test_bsc5_real_stars_present(star_tracker_root: Path, bsc5_path: Path) -> object:
    catalog: object = _load_or_build_bsc5(star_tracker_root, bsc5_path)
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

def test_bsc5_kvector_loads_and_matches_fingerprint(star_tracker_root: Path, bsc5_path: Path) -> object:
    catalog: object = _load_or_build_bsc5(star_tracker_root, bsc5_path)
    cat_dir: Path = star_tracker_root.joinpath('data', 'catalogs')
    kv_archive: Path = cache_path_for(catalog, cat_dir, 0.02, 30.5)
    if kv_archive.is_file():
        kv_index: object = KVectorTable.load(kv_archive)
    else:
        kv_index = KVectorTable.build(catalog, theta_min_deg=0.02, theta_max_deg=30.5)
    _verify(kv_index.catalog_fingerprint == catalog.fingerprint())
    _verify(kv_index.num_pairs > 100000)
    matches: object = kv_index.query(float(np.deg2rad(5.0)), float(np.deg2rad(0.01)))
    _verify(len(matches) > 10)
