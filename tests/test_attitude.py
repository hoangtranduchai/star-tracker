"""Validation suite for Markley SVD and Davenport q-method (QUEST) attitude solvers."""
from __future__ import annotations
import numpy as np
import pytest
from src.attitude import WahbaSolver
from src.quaternion import angular_error_arcsec, random_quaternion, to_dcm

def _require(condition: bool, msg: str='attitude assertion failed') -> None:
    if not condition:
        raise AssertionError(msg)

def _generate_synthetic_star_field(star_count: int=12, sigma_rad: float=0.0, rng_seed: int=0) -> object:
    prng: object = np.random.default_rng(rng_seed)
    q_truth: object = random_quaternion(prng)
    dcm_truth: object = to_dcm(q_truth)
    tan_xy: object = prng.uniform(low=-0.18, high=0.18, size=(star_count, 2))
    cam_vecs_true: object = np.hstack([tan_xy, np.ones((star_count, 1), dtype=np.float64)])
    cam_vecs_true /= np.linalg.norm(cam_vecs_true, axis=-1, keepdims=True)
    cat_vecs: object = (dcm_truth.T @ cam_vecs_true.T).T
    if sigma_rad > 0.0:
        perturbation: object = prng.normal(loc=0.0, scale=sigma_rad, size=cam_vecs_true.shape)
        cam_vecs_obs: object = cam_vecs_true + perturbation
        cam_vecs_obs /= np.linalg.norm(cam_vecs_obs, axis=-1, keepdims=True)
    else:
        cam_vecs_obs: object = cam_vecs_true.copy()
    return (q_truth, cat_vecs, cam_vecs_obs)

def test_noiseless_exact_recovery() -> object:
    for idx in range(20):
        q_truth, r_inertial, b_camera = _generate_synthetic_star_field(star_count=10, sigma_rad=0.0, rng_seed=idx)
        q_svd, dcm_svd = WahbaSolver.solve_svd(b_camera, r_inertial)
        q_qst, _ = WahbaSolver.solve_quest(b_camera, r_inertial)
        _require(angular_error_arcsec(q_svd, q_truth) < 0.05)
        _require(angular_error_arcsec(q_qst, q_truth) < 0.05)
        res: object = WahbaSolver.residuals_arcsec(b_camera, r_inertial, dcm_svd)
        _require(float(np.max(res)) < 0.05)

def test_quest_matches_svd_under_noise() -> object:
    sigma: object = np.deg2rad(5.0 / 3600.0)
    for idx in range(30):
        q_truth, r_inertial, b_camera = _generate_synthetic_star_field(star_count=12, sigma_rad=sigma, rng_seed=100 + idx)
        q_svd, _ = WahbaSolver.solve_svd(b_camera, r_inertial)
        q_qst, _ = WahbaSolver.solve_quest(b_camera, r_inertial)
        _require(angular_error_arcsec(q_svd, q_qst) < 0.1)
        _require(angular_error_arcsec(q_svd, q_truth) < 60.0)

def test_covariance_scales_with_sigma() -> object:
    sigma: object = np.deg2rad(5.0 / 3600.0)
    _, _, b_camera = _generate_synthetic_star_field(star_count=10, sigma_rad=sigma, rng_seed=7)
    cov1: object = WahbaSolver.covariance_rad2(b_camera, np.full(10, sigma))
    cov2: object = WahbaSolver.covariance_rad2(b_camera, np.full(10, 2.0 * sigma))
    np.testing.assert_allclose(cov2, 4.0 * cov1, rtol=1e-09)

def test_fewer_than_three_stars_raises() -> object:
    unit_z: object = np.asarray([[0.0, 0.0, 1.0], [0.0, 1.0, 0.0]], dtype=np.float64)
    with pytest.raises(ValueError):
        WahbaSolver.solve_svd(unit_z, unit_z)
