"""Quaternion utilities: scalar-first [q0, q1, q2, q3], DCM, composition, error."""

from __future__ import annotations

import numpy as np
from scipy.spatial.transform import Rotation

from src.quaternion import (
    angular_error_arcsec,
    axis_error_arcsec,
    from_dcm,
    from_scipy_xyzw,
    inverse,
    looking_at,
    looking_at_ra_dec,
    multiply,
    normalize,
    propagate,
    random_quaternion,
    to_dcm,
    to_scipy_xyzw,
    boresight_ra_dec_deg,
)


def test_roundtrip_q_dcm():
    rng = np.random.default_rng(0)
    for _ in range(50):
        q = random_quaternion(rng)
        a = to_dcm(q)
        q2 = from_dcm(a)
        # q and -q represent the same rotation
        inner = abs(float(np.dot(q, q2)))
        assert inner > 1.0 - 1e-12
        np.testing.assert_allclose(to_dcm(q2), a, atol=1e-12)


def test_matches_scipy_xyzw():
    rng = np.random.default_rng(1)
    q = random_quaternion(rng)
    xyzw = to_scipy_xyzw(q)
    r = Rotation.from_quat(xyzw)
    np.testing.assert_allclose(to_dcm(q), r.as_matrix(), atol=1e-12)
    q_back = from_scipy_xyzw(r.as_quat())
    assert abs(float(np.dot(q, q_back))) > 1.0 - 1e-12


def test_multiply_inverse_is_identity():
    rng = np.random.default_rng(2)
    q = random_quaternion(rng)
    ident = multiply(q, inverse(q))
    expected = np.array([1.0, 0.0, 0.0, 0.0])
    # identity or its negative
    if ident[0] < 0:
        ident = -ident
    np.testing.assert_allclose(ident, expected, atol=1e-12)


def test_double_cover_zero_error():
    rng = np.random.default_rng(3)
    q = random_quaternion(rng)
    err = angular_error_arcsec(q, -q)
    assert err < 1e-6


def test_propagate_negative_dt_inverts():
    rng = np.random.default_rng(8)
    q = random_quaternion(rng)
    omega = np.array([0.02, -0.01, 0.0])
    q_fwd = propagate(q, omega, 0.1)
    q_back = propagate(q_fwd, omega, -0.1)
    assert angular_error_arcsec(q, q_back) < 1e-4


def test_propagate_matches_scipy():
    rng = np.random.default_rng(4)
    q = random_quaternion(rng)
    omega = np.array([0.01, -0.02, 0.03])  # rad/s, camera frame
    dt = 0.15
    q_new = propagate(q, omega, dt)
    angle = np.linalg.norm(omega) * dt
    axis = omega / np.linalg.norm(omega)
    dq_xyzw = Rotation.from_rotvec(axis * angle).as_quat()
    q_xyzw = to_scipy_xyzw(q)
    composed = Rotation.from_quat(q_xyzw) * Rotation.from_quat(dq_xyzw)
    q_ref = from_scipy_xyzw(composed.as_quat())
    assert angular_error_arcsec(q_new, q_ref) < 1e-4


def test_normalize_unit_length():
    q = normalize(np.array([2.0, 0.0, 0.0, 0.0]))
    np.testing.assert_allclose(q, [1.0, 0.0, 0.0, 0.0])


def test_axis_error_small_rotation():
    # 10 arcsec about camera x
    theta = 10.0 / 206264.80624709636
    q_gt = np.array([1.0, 0.0, 0.0, 0.0])
    q_est = np.array([np.cos(theta / 2.0), np.sin(theta / 2.0), 0.0, 0.0])
    axes = axis_error_arcsec(q_est, q_gt)
    np.testing.assert_allclose(axes[0], 10.0, atol=1e-6)
    np.testing.assert_allclose(axes[1:], 0.0, atol=1e-6)


def test_boresight_identity_is_north_celestial_pole():
    from src.quaternion import boresight_ra_dec_deg, format_ra_hms

    ra, dec = boresight_ra_dec_deg(np.array([1.0, 0.0, 0.0, 0.0]))
    assert abs(dec - 90.0) < 1e-9
    assert format_ra_hms(162.13673747731067).startswith("10h")


def test_boresight_known_equator():
    from src.quaternion import boresight_ra_dec_deg, from_dcm, format_dec_dms

    # A maps J2000 +X (RA=0, Dec=0) onto camera +Z.
    a = np.array([[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]], dtype=np.float64)
    q = from_dcm(a)
    ra, dec = boresight_ra_dec_deg(q)
    assert abs(ra) < 1e-6 or abs(ra - 360.0) < 1e-6
    assert abs(dec) < 1e-6
    assert format_dec_dms(0.0).startswith("+00d")


def test_looking_at_puts_vector_on_camera_z():
    r = np.array([0.2, -0.5, 0.84])
    r = r / np.linalg.norm(r)
    q = looking_at(r)
    np.testing.assert_allclose(to_dcm(q) @ r, [0.0, 0.0, 1.0], atol=1e-10)
    ra, dec = boresight_ra_dec_deg(q)
    ra_gt = float(np.degrees(np.mod(np.arctan2(r[1], r[0]), 2 * np.pi)))
    dec_gt = float(np.degrees(np.arcsin(np.clip(r[2], -1, 1))))
    assert abs(ra - ra_gt) < 1e-6 or abs(abs(ra - ra_gt) - 360) < 1e-6
    assert abs(dec - dec_gt) < 1e-6


def test_looking_at_ra_dec_sets_boresight():
    q = looking_at_ra_dec(123.4, -5.6)
    ra, dec = boresight_ra_dec_deg(q)
    assert abs(ra - 123.4) < 1e-6 or abs(abs(ra - 123.4) - 360) < 1e-6
    assert abs(dec - (-5.6)) < 1e-6
