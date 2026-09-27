"""Unit tests for scalar-first quaternion algebra, DCM conversion, and boresight kinematics."""
from __future__ import annotations
import numpy as np
from scipy.spatial.transform import Rotation
from src.quaternion import angular_error_arcsec, axis_error_arcsec, boresight_ra_dec_deg, format_dec_dms, format_ra_hms, from_dcm, from_scipy_xyzw, inverse, looking_at, looking_at_ra_dec, multiply, normalize, propagate, random_quaternion, to_dcm, to_scipy_xyzw

def _assert_quat(cond: bool, msg: str='quaternion check failed') -> None:
    if not cond:
        raise AssertionError(msg)

def test_roundtrip_q_dcm() -> object:
    prng: object = np.random.default_rng(seed=0)
    for _ in range(50):
        q_orig: object = random_quaternion(prng)
        mat: object = to_dcm(q_orig)
        q_reconstructed: object = from_dcm(mat)
        _assert_quat(abs(float(np.dot(q_orig, q_reconstructed))) > 1.0 - 1e-12)
        np.testing.assert_allclose(to_dcm(q_reconstructed), mat, atol=1e-12)

def test_matches_scipy_xyzw() -> object:
    prng: object = np.random.default_rng(seed=1)
    q_sample: object = random_quaternion(prng)
    scipy_rot: object = Rotation.from_quat(to_scipy_xyzw(q_sample))
    np.testing.assert_allclose(to_dcm(q_sample), scipy_rot.as_matrix(), atol=1e-12)
    q_round: object = from_scipy_xyzw(scipy_rot.as_quat())
    _assert_quat(abs(float(np.dot(q_sample, q_round))) > 1.0 - 1e-12)

def test_multiply_inverse_is_identity() -> object:
    prng: object = np.random.default_rng(seed=2)
    q_sample: object = random_quaternion(prng)
    prod: object = multiply(q_sample, inverse(q_sample))
    if prod[0] < 0.0:
        prod: object = -prod
    np.testing.assert_allclose(prod, [1.0, 0.0, 0.0, 0.0], atol=1e-12)

def test_double_cover_zero_error() -> object:
    prng: object = np.random.default_rng(seed=3)
    q_sample: object = random_quaternion(prng)
    _assert_quat(angular_error_arcsec(q_sample, -q_sample) < 1e-06)

def test_propagate_negative_dt_inverts() -> object:
    prng: object = np.random.default_rng(seed=8)
    q_init: object = random_quaternion(prng)
    rate_vec: object = np.asarray([0.02, -0.01, 0.0], dtype=np.float64)
    q_step: object = propagate(q_init, rate_vec, 0.1)
    q_rewound: object = propagate(q_step, rate_vec, -0.1)
    _assert_quat(angular_error_arcsec(q_init, q_rewound) < 0.0001)

def test_propagate_matches_scipy() -> object:
    prng: object = np.random.default_rng(seed=4)
    q_init: object = random_quaternion(prng)
    rate_vec: object = np.asarray([0.01, -0.02, 0.03], dtype=np.float64)
    dt_sec: object = 0.15
    q_prop: object = propagate(q_init, rate_vec, dt_sec)
    delta_rot: object = Rotation.from_rotvec(rate_vec * dt_sec)
    combined: object = Rotation.from_quat(to_scipy_xyzw(q_init)) * delta_rot
    q_expected: object = from_scipy_xyzw(combined.as_quat())
    _assert_quat(angular_error_arcsec(q_prop, q_expected) < 0.0001)

def test_normalize_unit_length() -> object:
    scaled: object = normalize(np.asarray([2.0, 0.0, 0.0, 0.0]))
    np.testing.assert_allclose(scaled, [1.0, 0.0, 0.0, 0.0])

def test_axis_error_small_rotation() -> object:
    rad_10_arcsec: object = np.deg2rad(10.0 / 3600.0)
    q_ref: object = np.asarray([1.0, 0.0, 0.0, 0.0])
    q_tilted: object = np.asarray([np.cos(0.5 * rad_10_arcsec), np.sin(0.5 * rad_10_arcsec), 0.0, 0.0])
    err_xyz: object = axis_error_arcsec(q_tilted, q_ref)
    np.testing.assert_allclose(err_xyz, [10.0, 0.0, 0.0], atol=1e-06)

def test_boresight_identity_is_north_celestial_pole() -> object:
    ra_deg, dec_deg = boresight_ra_dec_deg(np.asarray([1.0, 0.0, 0.0, 0.0]))
    _assert_quat(abs(dec_deg - 90.0) < 1e-09)
    _assert_quat(format_ra_hms(162.13673747731067).startswith('10h'))

def test_boresight_known_equator() -> object:
    dcm_eq: object = np.asarray([[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]], dtype=np.float64)
    ra_deg, dec_deg = boresight_ra_dec_deg(from_dcm(dcm_eq))
    _assert_quat(abs(ra_deg) < 1e-06 or abs(ra_deg - 360.0) < 1e-06)
    _assert_quat(abs(dec_deg) < 1e-06)
    _assert_quat(format_dec_dms(0.0).startswith('+00d'))

def test_looking_at_puts_vector_on_camera_z() -> object:
    target_dir: object = np.asarray([0.2, -0.5, 0.84], dtype=np.float64)
    target_dir /= np.linalg.norm(target_dir)
    q_aim: object = looking_at(target_dir)
    np.testing.assert_allclose(to_dcm(q_aim) @ target_dir, [0.0, 0.0, 1.0], atol=1e-10)

def test_looking_at_ra_dec_sets_boresight() -> object:
    q_aim: object = looking_at_ra_dec(123.4, -5.6)
    ra_deg, dec_deg = boresight_ra_dec_deg(q_aim)
    _assert_quat(abs(ra_deg - 123.4) < 1e-06 or abs(abs(ra_deg - 123.4) - 360.0) < 1e-06)
    _assert_quat(abs(dec_deg + 5.6) < 1e-06)
