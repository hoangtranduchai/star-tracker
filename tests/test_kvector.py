"""Tests for Mortari K-vector range searching, persistence, and O(1) query complexity."""
from __future__ import annotations
import time
import numpy as np
from src.catalog import CatalogManager
from src.kvector import KVectorTable

def _verify_kv(cond: bool, msg: str='kvector check failed') -> None:
    if not cond:
        raise AssertionError(msg)

def _reference_pair_search(unit_vecs: np.ndarray, target_angle: float, half_window: float) -> set[tuple[int, int]]:
    cos_mat: object = np.clip(unit_vecs @ unit_vecs.T, -1.0, 1.0)
    theta_mat: object = np.arccos(cos_mat)
    upper_i, upper_j = np.triu_indices(len(unit_vecs), k=1)
    pair_angles: object = theta_mat[upper_i, upper_j]
    mask: object = (pair_angles >= target_angle - half_window) & (pair_angles <= target_angle + half_window)
    return {(int(i), int(j)) for i, j in zip(upper_i[mask], upper_j[mask])}

def test_query_matches_bruteforce() -> object:
    catalog: object = CatalogManager.synthetic(120, 6.0, seed=7)
    kv_index: object = KVectorTable.build(catalog, theta_min_deg=0.02, theta_max_deg=19.5)
    prng: object = np.random.default_rng(seed=0)
    for _ in range(200):
        angle: object = float(prng.uniform(kv_index.theta_min, kv_index.theta_max))
        tol: object = float(prng.uniform(1e-05, 0.0005))
        candidates: object = kv_index.query(angle, tol)
        found_set: object = {(min(int(u), int(v)), max(int(u), int(v))) for u, v in candidates}
        expected_set: object = _reference_pair_search(catalog.vectors, angle, tol)
        _verify_kv(found_set == expected_set)

def test_no_pairs_outside_range() -> object:
    catalog: object = CatalogManager.synthetic(80, 6.0, seed=3)
    kv_index: object = KVectorTable.build(catalog, theta_min_deg=1.0, theta_max_deg=5.0)
    outside: object = kv_index.query(float(np.deg2rad(10.0)), float(np.deg2rad(0.1)))
    _verify_kv(len(outside) == 0)

def test_save_load_roundtrip(tmp_path: object) -> object:
    catalog: object = CatalogManager.synthetic(60, 6.0, seed=4)
    original: object = KVectorTable.build(catalog)
    archive: object = tmp_path.joinpath('kvector_test.npz')
    original.save(archive)
    restored: object = KVectorTable.load(archive)
    np.testing.assert_array_equal(restored.pairs, original.pairs)
    np.testing.assert_allclose(restored.angles, original.angles)
    _verify_kv(restored.catalog_fingerprint == catalog.fingerprint())

def test_query_time_independent_of_n() -> object:
    avg_latencies: object = []
    query_theta: object = float(np.deg2rad(8.0))
    query_eps: object = float(np.deg2rad(0.01))
    for star_count in (80, 800):
        catalog: object = CatalogManager.synthetic(star_count, 6.0, seed=star_count)
        kv_index: object = KVectorTable.build(catalog, theta_min_deg=0.02, theta_max_deg=19.5)
        kv_index.query(query_theta, query_eps)
        t_start: object = time.perf_counter()
        for _ in range(2000):
            kv_index.query(query_theta, query_eps)
        avg_latencies.append((time.perf_counter() - t_start) / 2000.0)
    _verify_kv(avg_latencies[1] < avg_latencies[0] * 8.0 + 5e-05)
