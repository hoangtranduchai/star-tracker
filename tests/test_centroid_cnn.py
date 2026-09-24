"""Tests for optional CNN centroid helpers (no weight download required)."""
from __future__ import annotations
import numpy as np
from src.centroid_cnn import match_centroid_rmse, trilateration_centroids, weights_available

def test_match_centroid_rmse_perfect() -> object:
    gt: object = np.array([[10.0, 20.0], [30.5, 40.25]])
    pred: object = gt.copy()
    m: object = match_centroid_rmse(pred, gt, match_radius_px=2.0)
    assert m['n_matched'] == 2
    assert m['rmse_px'] is not None and m['rmse_px'] < 1e-09

def test_match_centroid_rmse_no_match() -> object:
    gt: object = np.array([[0.0, 0.0]])
    pred: object = np.array([[50.0, 50.0]])
    m: object = match_centroid_rmse(pred, gt, match_radius_px=5.0)
    assert m['n_matched'] == 0
    assert m['rmse_px'] is None

def test_trilateration_single_star() -> object:
    h = w = 32
    dist: object = np.full((h, w), 10.0, dtype=np.float64)
    seg: object = np.zeros((h, w), dtype=np.float64)
    cu, cv = (15.3, 16.7)
    for y in range(h):
        for x in range(w):
            d: object = np.hypot(x + 0.5 - cu, y + 0.5 - cv)
            dist[y, x] = d
            if d < 4.0:
                seg[y, x] = 1.0
    uv: object = trilateration_centroids(dist, seg, radius=7, d_th=0.8)
    assert len(uv) >= 1
    err: object = np.min(np.linalg.norm(uv - np.array([cu, cv]), axis=1))
    assert err < 0.25

def test_weights_path_check_is_bool() -> object:
    assert isinstance(weights_available(), bool)
