"""Unit tests for pinhole camera projection, back-projection, and downscaling."""
from __future__ import annotations
import numpy as np
from src.camera import demo_camera

def _check(cond: bool, message: str='check failed') -> None:
    if not cond:
        raise AssertionError(message)

def test_fov_and_ifov_ranges() -> object:
    optics: object = demo_camera()
    fov_horizontal, fov_vertical, fov_diagonal = optics.fov_deg
    _check(5.0 < fov_horizontal < 35.0)
    _check(4.0 < fov_vertical < 30.0)
    _check(8.0 < optics.ifov_arcsec < 30.0)
    _check(9.0 < fov_diagonal < 32.0)

def test_project_unproject_roundtrip() -> object:
    optics: object = demo_camera()
    prng: object = np.random.default_rng(seed=42)
    u_coords: object = prng.uniform(low=10.0, high=optics.width - 10.0, size=200)
    v_coords: object = prng.uniform(low=10.0, high=optics.height - 10.0, size=200)
    pixel_pts: object = np.stack([u_coords, v_coords], axis=-1)
    rays: object = optics.unproject(pixel_pts)
    norms: object = np.linalg.norm(rays, axis=-1)
    np.testing.assert_allclose(norms, 1.0, atol=1e-12)
    reprojected_pts, inside_mask = optics.project(rays)
    _check(bool(np.all(inside_mask)))
    np.testing.assert_allclose(reprojected_pts, pixel_pts, atol=1e-09)

def test_boresight_projects_to_principal_point() -> object:
    optics: object = demo_camera()
    optical_axis: object = np.asarray([[0.0, 0.0, 1.0]], dtype=np.float64)
    uv_coords, valid_mask = optics.project(optical_axis)
    _check(bool(valid_mask[0]))
    np.testing.assert_allclose(uv_coords[0], [optics.cx, optics.cy], atol=1e-12)

def test_behind_camera_marked_out_of_fov() -> object:
    optics: object = demo_camera()
    rear_ray: object = np.asarray([[0.0, 0.0, -1.0]], dtype=np.float64)
    _, valid_mask = optics.project(rear_ray)
    _check(not bool(valid_mask[0]))

def test_downscaled_preserves_fov() -> object:
    full_cam: object = demo_camera()
    quarter_cam: object = full_cam.downscaled(4)
    np.testing.assert_allclose(full_cam.fov_deg, quarter_cam.fov_deg, rtol=1e-06)
    _check(abs(quarter_cam.ifov_arcsec - 4.0 * full_cam.ifov_arcsec) < 1e-06)
