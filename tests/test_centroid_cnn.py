"""Tests for optional CNN centroid helpers and evaluation metrics."""
from __future__ import annotations
from types import SimpleNamespace
import numpy as np
from src.centroid import Centroids
from src.centroid_cnn import (
    _frame_bit_regime,
    _frame_is_high_bit,
    _to_author_intensity,
    match_centroid_rmse,
    trilateration_centroids,
    weights_available,
)
from src.metrics import evaluate
from src.quaternion import multiply, normalize
from src.simulator import RenderTruth

def test_match_centroid_rmse_perfect() -> object:
    gt: object = np.array([[10.0, 20.0], [30.5, 40.25]])
    pred: object = gt.copy()
    m: object = match_centroid_rmse(pred, gt, match_radius_px=2.0)
    assert m['n_matched'] == 2
    assert m['n_false_pos'] == 0
    assert m['n_false_neg'] == 0
    assert m['precision'] == 1.0
    assert m['recall'] == 1.0
    assert m['f1'] == 1.0
    assert m['rmse_px'] is not None and m['rmse_px'] < 1e-09

def test_match_centroid_rmse_no_match() -> object:
    gt: object = np.array([[0.0, 0.0]])
    pred: object = np.array([[50.0, 50.0]])
    m: object = match_centroid_rmse(pred, gt, match_radius_px=5.0)
    assert m['n_matched'] == 0
    assert m['n_false_pos'] == 1
    assert m['n_false_neg'] == 1
    assert m['precision'] == 0.0
    assert m['recall'] == 0.0
    assert m['f1'] == 0.0
    assert m['rmse_px'] is None

def test_match_centroid_rmse_precision_recall_f1_edge_cases() -> object:
    gt: object = np.array([[10.0, 10.0], [20.0, 20.0], [30.0, 30.0], [40.0, 40.0], [50.0, 50.0]])
    pred: object = np.array([[10.5, 10.0], [20.0, 20.5], [30.0, 30.0], [100.0, 100.0]])
    m: object = match_centroid_rmse(pred, gt, match_radius_px=5.0)
    assert m['n_pred'] == 4 and m['n_gt'] == 5
    assert m['n_matched'] == 3
    assert m['n_false_pos'] == 1
    assert m['n_false_neg'] == 2
    assert np.isclose(m['precision'], 0.75)
    assert np.isclose(m['recall'], 0.6)
    assert np.isclose(m['f1'], 2.0 * 0.75 * 0.6 / (0.75 + 0.6))
    empty: object = np.empty((0, 2), dtype=np.float64)
    m_empty_pred: object = match_centroid_rmse(empty, gt[:2], match_radius_px=5.0)
    assert m_empty_pred['precision'] == 0.0 and m_empty_pred['recall'] == 0.0 and m_empty_pred['f1'] == 0.0
    assert m_empty_pred['n_false_pos'] == 0 and m_empty_pred['n_false_neg'] == 2
    m_empty_gt: object = match_centroid_rmse(pred[:2], empty, match_radius_px=5.0)
    assert m_empty_gt['precision'] == 0.0 and m_empty_gt['recall'] is None and m_empty_gt['f1'] is None
    assert m_empty_gt['n_false_pos'] == 2 and m_empty_gt['n_false_neg'] == 0
    m_both_empty: object = match_centroid_rmse(empty, empty, match_radius_px=5.0)
    assert m_both_empty['precision'] == 1.0 and m_both_empty['recall'] is None and m_both_empty['f1'] is None

def test_bit_regime_and_16bit_author_scaling() -> object:
    img_8: object = np.array([[0, 255]], dtype=np.uint8)
    img_12: object = np.array([[64, 4095]], dtype=np.uint16)
    img_16: object = np.array([[2464, 53104]], dtype=np.uint16)
    assert _frame_bit_regime(img_8) == '8bit'
    assert _frame_bit_regime(img_12) == '12bit'
    assert _frame_bit_regime(img_16) == '16bit'
    assert _frame_is_high_bit(img_8) is False
    assert _frame_is_high_bit(img_12) is True
    assert _frame_is_high_bit(img_16) is False
    np.testing.assert_allclose(_to_author_intensity(img_8), np.array([[0.0, 255.0]], dtype=np.float32))
    np.testing.assert_allclose(_to_author_intensity(img_12), np.array([[4.0, 4095.0 / 16.0]], dtype=np.float32))
    np.testing.assert_allclose(_to_author_intensity(img_16), np.array([[2464.0 / 256.0, 53104.0 / 256.0]], dtype=np.float32))

def _make_truth(q_gt: np.ndarray, uv_mid: np.ndarray) -> RenderTruth:
    n: int = len(uv_mid)
    return RenderTruth(
        q_gt=q_gt,
        uv_mid=uv_mid,
        cat_idx=np.arange(n, dtype=int),
        streak_px=np.zeros(n, dtype=np.float64),
        omega_deg_s=np.zeros(3, dtype=np.float64),
        vis_mags=np.full(n, 4.0, dtype=np.float64),
    )

def _make_centroids(uv: np.ndarray) -> Centroids:
    n: int = len(uv)
    z: object = np.zeros(n, dtype=np.float64)
    return Centroids(
        uv=uv,
        flux=np.ones(n, dtype=np.float64),
        area=np.full(n, 9.0, dtype=np.float64),
        peak=np.ones(n, dtype=np.float64),
        mu20=z,
        mu02=z,
        mu11=z,
        axis_ratio=np.ones(n, dtype=np.float64),
        angle_rad=z,
        vectors=np.tile([0.0, 0.0, 1.0], (n, 1)),
        sigma_px=np.full(n, 0.5, dtype=np.float64),
    )

def test_evaluate_outcomes_lost_warn_false_lock_and_metrics() -> object:
    q_gt: object = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
    gt_uv: object = np.array([[100.0, 100.0], [200.0, 200.0], [300.0, 300.0], [400.0, 400.0]])
    pred_uv: object = np.array([[100.5, 100.0], [200.0, 200.5], [304.0, 300.0], [700.0, 700.0]])
    truth: object = _make_truth(q_gt, gt_uv)
    cents: object = _make_centroids(pred_uv)
    ident_mock: object = SimpleNamespace(obs_idx=np.array([0, 1, 2]), cat_idx=np.array([0, 1, 2]))
    mstats: object = {
        'n_initial_matched': 4,
        'n_rejected_outliers': 1,
        'n_valid_pairs': 3,
        'min_pairs_required': 4,
        'rms_residual_arcsec': 12.0,
        'max_residual_arcsec': 20.0,
        'fov_expected_stars': 4,
    }
    res_lost: object = SimpleNamespace(
        success=False, status='LOST', reject_code='INSUFFICIENT_INLIER_PAIRS', match_stats=mstats,
        q=None, centroids=cents, ident=None, timing_ms={'total_pipeline_ms': 5.0}, quality=mstats, error='lost'
    )
    rep_lost: object = evaluate(res_lost, truth, attitude_limit_arcsec=30.0, have_gt=True, false_lock_limit_arcsec=300.0)
    assert rep_lost['status'] == 'LOST'
    assert rep_lost['reject_code'] == 'INSUFFICIENT_INLIER_PAIRS'
    assert rep_lost['e2e_outcome'] == 'LOST'
    assert rep_lost['verdict'] == 'FAIL'
    assert rep_lost['n_valid_pairs'] == 3 and rep_lost['n_rejected_outliers'] == 1
    assert np.isclose(rep_lost['centroid_precision'], 0.75)
    assert np.isclose(rep_lost['centroid_recall'], 0.75)
    assert rep_lost['centroid_n_false_pos'] == 1
    assert rep_lost['centroid_rms_5px'] is not None and rep_lost['centroid_rms_px'] < 1.0
    # 5 arcsec offset -> SOLVED_CORRECT / PASS
    half_good: float = 0.5 * float(np.deg2rad(5.0 / 3600.0))
    q_good: object = normalize(multiply(q_gt, np.array([np.cos(half_good), np.sin(half_good), 0.0, 0.0])))
    res_good: object = SimpleNamespace(
        success=True, status='SOLVED', reject_code=None, match_stats=mstats,
        q=q_good, centroids=cents, ident=ident_mock, timing_ms={}, quality=mstats, error=None
    )
    rep_good: object = evaluate(res_good, truth, attitude_limit_arcsec=30.0, have_gt=True, false_lock_limit_arcsec=300.0)
    assert rep_good['e2e_outcome'] == 'SOLVED_CORRECT' and rep_good['verdict'] == 'PASS'
    # 120 arcsec offset -> SOLVED_WARN / WARN
    half_warn: float = 0.5 * float(np.deg2rad(120.0 / 3600.0))
    q_warn: object = normalize(multiply(q_gt, np.array([np.cos(half_warn), np.sin(half_warn), 0.0, 0.0])))
    res_warn: object = SimpleNamespace(**{**res_good.__dict__, 'q': q_warn})
    rep_warn: object = evaluate(res_warn, truth, attitude_limit_arcsec=30.0, have_gt=True, false_lock_limit_arcsec=300.0)
    assert rep_warn['e2e_outcome'] == 'SOLVED_WARN' and rep_warn['verdict'] == 'WARN'
    # 1 deg offset -> FALSE_LOCK
    half_bad: float = 0.5 * float(np.deg2rad(1.0))
    q_bad: object = normalize(multiply(q_gt, np.array([np.cos(half_bad), np.sin(half_bad), 0.0, 0.0])))
    res_bad: object = SimpleNamespace(**{**res_good.__dict__, 'q': q_bad})
    rep_bad: object = evaluate(res_bad, truth, attitude_limit_arcsec=30.0, have_gt=True, false_lock_limit_arcsec=300.0)
    assert rep_bad['e2e_outcome'] == 'FALSE_LOCK' and rep_bad['verdict'] == 'FALSE_LOCK'
    # have_gt=False -> SOLVED_NO_GT
    rep_nogt: object = evaluate(res_good, truth, attitude_limit_arcsec=30.0, have_gt=False)
    assert rep_nogt['e2e_outcome'] == 'SOLVED_NO_GT' and rep_nogt['verdict'] == 'SOLVED_NO_GT'

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


def test_tetra3_threshold_detector_recovers_subpixel_stars() -> None:
    from src.camera import CameraModel
    from src.centroid_tetra3 import Tetra3ThresholdDetector

    cam = CameraModel(width=128, height=128, pixel_um=5.0, focal_mm=25.0)
    rng = np.random.default_rng(7)
    img = np.clip(64.0 + rng.normal(0.0, 2.0, size=(128, 128)), 0.0, 4095.0).astype(np.float32)
    yy, xx = np.mgrid[0:128, 0:128]
    gt = np.array([[34.35, 41.72], [88.61, 79.28], [62.15, 25.84]], dtype=np.float64)
    for u, v in gt:
        img += (1800.0 * np.exp(-((xx - u) ** 2 + (yy - v) ** 2) / (2.0 * 1.4 ** 2))).astype(np.float32)

    det = Tetra3ThresholdDetector(cam, sigma=2.0, filtsize=25, min_area=5, max_area=100)
    cents = det.detect(img)
    assert det.last_backend == 'tetra3_threshold'
    assert len(cents.uv) == 3
    m = match_centroid_rmse(cents.uv, gt, match_radius_px=2.0)
    assert m['n_matched'] == 3 and m['n_false_pos'] == 0
    assert m['rmse_px'] is not None and m['rmse_px'] < 0.15

