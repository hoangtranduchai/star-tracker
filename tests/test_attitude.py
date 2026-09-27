"""Attitude tests: Wahba SVD/QUEST, weights, residuals, covariance."""

from __future__ import annotations

import numpy as np

from src.attitude import WahbaSolver
from src.quaternion import angular_error_arcsec, random_quaternion, to_dcm


def _make_pairs(q, n=8, rng=None, noise_rad=0.0):
    rng = np.random.default_rng(0) if rng is None else rng
    r = rng.normal(size=(n, 3))
    r /= np.linalg.norm(r, axis=1, keepdims=True)
    a = to_dcm(q)
    b = (a @ r.T).T
    if noise_rad > 0:
        noise = rng.normal(scale=noise_rad, size=b.shape)
        b = b + noise
        b /= np.linalg.norm(b, axis=1, keepdims=True)
    return b, r


def test_svd_recovers_known_attitude():
    q = random_quaternion(np.random.default_rng(11))
    b, r = _make_pairs(q, n=6)
    q_est, a_est = WahbaSolver.solve_svd(b, r)
    assert angular_error_arcsec(q_est, q) * np.pi / (180.0 * 3600.0) < 1e-10
    np.testing.assert_allclose(a_est, to_dcm(q), atol=1e-10)


def test_quest_matches_svd():
    q = random_quaternion(np.random.default_rng(12))
    b, r = _make_pairs(q, n=7)
    q_s, a_s = WahbaSolver.solve_svd(b, r)
    q_q, a_q = WahbaSolver.solve_quest(b, r)
    ang = np.arccos(np.clip(0.5 * (np.trace(a_s @ a_q.T) - 1.0), -1.0, 1.0))
    assert ang < 1e-8
    assert angular_error_arcsec(q_s, q_q) * np.pi / (180.0 * 3600.0) < 1e-8


def test_weights_pull_toward_accurate_star():
    rng = np.random.default_rng(13)
    q = random_quaternion(rng)
    b, r = _make_pairs(q, n=4, rng=rng)
    # perturb last observation a lot
    b_bad = b.copy()
    b_bad[-1] = b_bad[-1] + np.array([0.05, 0.0, 0.0])
    b_bad[-1] /= np.linalg.norm(b_bad[-1])
    w_equal = np.ones(4)
    w_down = np.array([1.0, 1.0, 1.0, 1e-6])
    q_eq, _ = WahbaSolver.solve_svd(b_bad, r, w_equal)
    q_w, _ = WahbaSolver.solve_svd(b_bad, r, w_down)
    err_eq = angular_error_arcsec(q_eq, q)
    err_w = angular_error_arcsec(q_w, q)
    assert err_w < err_eq


def test_residuals_zero_when_perfect():
    q = random_quaternion(np.random.default_rng(14))
    b, r = _make_pairs(q, n=5)
    _, a = WahbaSolver.solve_svd(b, r)
    res = WahbaSolver.residuals_arcsec(b, r, a)
    assert np.max(res) < 0.05


def test_covariance_monte_carlo_scale():
    rng = np.random.default_rng(15)
    q = random_quaternion(rng)
    b0, r = _make_pairs(q, n=10, rng=rng)
    sigma_rad = 1e-5  # ~2 arcsec
    p = WahbaSolver.covariance_rad2(b0, np.full(10, sigma_rad))
    pred = np.sqrt(np.trace(p))  # RSS of 3-axis 1-sigma
    errs = []
    for _ in range(200):
        noise = rng.normal(scale=sigma_rad, size=b0.shape)
        b = b0 + noise
        b /= np.linalg.norm(b, axis=1, keepdims=True)
        q_est, _ = WahbaSolver.solve_svd(b, r)
        errs.append(angular_error_arcsec(q_est, q) * np.pi / (180.0 * 3600.0))
    rms = float(np.sqrt(np.mean(np.square(errs))))
    # 3-axis error ≈ sqrt(tr(P)); allow 40% because N=200 is noisy
    assert 0.5 * pred < rms < 1.6 * pred
