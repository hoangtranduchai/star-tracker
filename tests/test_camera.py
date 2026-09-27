"""Demo APS-C + 50 mm pinhole / Brown-Conrady tests."""

from __future__ import annotations

import numpy as np

from src.camera import CameraModel, demo_camera


def test_demo_fov_and_ifov():
    cam = demo_camera()
    h, v, d = cam.fov_deg
    assert abs(h - 25.16) < 0.02
    assert abs(v - 16.93) < 0.02
    assert abs(d - 30.03) < 0.02
    assert abs(cam.ifov_arcsec - 15.35) < 0.02
    assert abs(cam.fx - 13440.860215) < 0.01
    np.testing.assert_allclose(cam.cx, 2999.5)
    np.testing.assert_allclose(cam.cy, 1999.5)
    assert cam.width == 6000
    assert cam.height == 4000
    assert abs(cam.pixel_um - 3.72) < 1e-12


def test_fast_downscale():
    cam = demo_camera().downscaled(4)
    assert cam.width == 1500
    assert cam.height == 1000
    np.testing.assert_allclose(cam.cx, 749.5)
    np.testing.assert_allclose(cam.cy, 499.5)
    assert abs(cam.ifov_arcsec - 61.38) < 0.05
    h, v, d = cam.fov_deg
    assert abs(h - 25.16) < 0.02
    assert abs(v - 16.93) < 0.02


def test_project_unproject_no_distortion():
    cam = demo_camera()
    rng = np.random.default_rng(5)
    xy = rng.uniform(-0.12, 0.12, size=(200, 2))
    z = np.ones(200)
    vec = np.column_stack((xy[:, 0], xy[:, 1], z))
    vec /= np.linalg.norm(vec, axis=1, keepdims=True)
    uv, in_fov = cam.project(vec)
    assert in_fov.all()
    back = cam.unproject(uv)
    chord = np.linalg.norm(vec - back, axis=1)
    assert np.max(chord) < 1e-9


def test_brown_conrady_roundtrip():
    cam = CameraModel(
        width=6000,
        height=4000,
        pixel_um=3.72,
        focal_mm=50.0,
        k1=-0.02,
        k2=0.005,
        k3=0.0,
        p1=1e-4,
        p2=-5e-5,
    )
    rng = np.random.default_rng(6)
    xy = rng.uniform(-0.10, 0.10, size=(80, 2))
    vec = np.column_stack((xy[:, 0], xy[:, 1], np.ones(80)))
    vec /= np.linalg.norm(vec, axis=1, keepdims=True)
    uv, in_fov = cam.project(vec)
    back = cam.unproject(uv[in_fov])
    chord = np.linalg.norm(vec[in_fov] - back, axis=1)
    assert np.max(chord) < 1e-8


def test_boresight_projects_to_principal_point():
    cam = demo_camera()
    uv, in_fov = cam.project(np.array([[0.0, 0.0, 1.0]]))
    assert in_fov[0]
    np.testing.assert_allclose(uv[0], [cam.cx, cam.cy], atol=1e-9)
