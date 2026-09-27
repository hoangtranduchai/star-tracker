"""K-vector brute-force agreement and timing tests."""

from __future__ import annotations

import time

import numpy as np

from src.catalog import CatalogManager
from src.kvector import KVectorTable


def _brute_pairs(vectors: np.ndarray, theta: float, eps: float) -> set[tuple[int, int]]:
    n = len(vectors)
    lo, hi = theta - eps, theta + eps
    out: set[tuple[int, int]] = set()
    dots = np.clip(vectors @ vectors.T, -1.0, 1.0)
    ang = np.arccos(dots)
    for i in range(n):
        for j in range(i + 1, n):
            if lo <= ang[i, j] <= hi:
                out.add((i, j))
    return out


def test_query_matches_bruteforce():
    cat = CatalogManager.synthetic(120, 6.0, seed=7)
    table = KVectorTable.build(cat, theta_min_deg=0.02, theta_max_deg=19.5)
    rng = np.random.default_rng(0)
    n_ok = 0
    for _ in range(200):
        theta = float(rng.uniform(table.theta_min, table.theta_max))
        eps = float(rng.uniform(1e-5, 5e-4))
        got = table.query(theta, eps)
        got_set = {tuple(sorted((int(a), int(b)))) for a, b in got}
        ref = _brute_pairs(cat.vectors, theta, eps)
        assert got_set == ref
        n_ok += 1
    assert n_ok == 200


def test_no_pairs_outside_range():
    cat = CatalogManager.synthetic(80, 6.0, seed=3)
    table = KVectorTable.build(cat, theta_min_deg=1.0, theta_max_deg=5.0)
    got = table.query(np.radians(10.0), np.radians(0.1))
    assert len(got) == 0


def test_save_load_roundtrip(tmp_path):
    cat = CatalogManager.synthetic(60, 6.0, seed=4)
    table = KVectorTable.build(cat)
    path = tmp_path / "k.npz"
    table.save(path)
    loaded = KVectorTable.load(path)
    np.testing.assert_array_equal(loaded.pairs, table.pairs)
    np.testing.assert_allclose(loaded.angles, table.angles)
    assert loaded.catalog_fingerprint == cat.fingerprint()


def test_query_time_independent_of_n():
    """Query cost should not grow with catalog size (O(1) index)."""
    rng = np.random.default_rng(1)
    times = []
    for n in (80, 800):
        cat = CatalogManager.synthetic(n, 6.0, seed=n)
        table = KVectorTable.build(cat, theta_min_deg=0.02, theta_max_deg=19.5)
        theta = float(np.radians(8.0))
        eps = float(np.radians(0.01))
        table.query(theta, eps)  # warmup
        t0 = time.perf_counter()
        for _ in range(2000):
            table.query(theta, eps)
        times.append((time.perf_counter() - t0) / 2000.0)
    # Allow 8x slack (cache effects) but not 10x of n (which is 10x).
    assert times[1] < times[0] * 8.0 + 5e-5
