"""Sky simulator tests: pinhole truth, streaks, 12-bit clipping."""

from __future__ import annotations

import numpy as np

from src.camera import demo_camera
from src.catalog import CatalogManager, StarCatalog, ra_dec_to_vectors
from src.quaternion import to_dcm
from src.simulator import GlareSpec, Radiometry, SkySimulator


def _cog(img: np.ndarray) -> tuple[float, float]:
    img_f = img.astype(np.float64)
    bg = np.median(img_f)
    w = np.maximum(img_f - bg, 0.0)
    if w.sum() <= 0:
        raise AssertionError("no flux")
    yy, xx = np.indices(img_f.shape)
    return float((w * xx).sum() / w.sum()), float((w * yy).sum() / w.sum())


def test_bright_star_cog_matches_truth():
    cam = demo_camera().downscaled(4)
    # Single star on boresight in camera frame when q = identity → catalog z-axis
    vecs = np.array([[0.0, 0.0, 1.0]])
    cat = StarCatalog(ids=np.array([1]), vectors=vecs, mags=np.array([1.0], dtype=np.float32), source="SYNTHETIC")
    sim = SkySimulator(cam, cat, radiometry=Radiometry(hot_pixel_frac=0.0, cosmic_rate_per_frame=0.0), seed=0)
    q = np.array([1.0, 0.0, 0.0, 0.0])
    img, truth = sim.render(q, omega_deg_s=(0.0, 0.0, 0.0), t_exp_s=0.15, add_noise=False)
    assert img.dtype == np.uint16
    assert img.max() <= 4095
    u, v = _cog(img)
    np.testing.assert_allclose([u, v], truth.uv_mid[0], atol=0.02)
    np.testing.assert_allclose(truth.uv_mid[0], [cam.cx, cam.cy], atol=1e-6)


def test_mid_exposure_matches_q_gt():
    cam = demo_camera().downscaled(4)
    cat = CatalogManager.synthetic(400, 6.0, seed=1)
    sim = SkySimulator(cam, cat, radiometry=Radiometry(hot_pixel_frac=0.0, cosmic_rate_per_frame=0.0), seed=1)
    q = SkySimulator.generate_random_quaternion(seed=9)
    img, truth = sim.render(q, omega_deg_s=(0.0, 0.06, 0.0), t_exp_s=0.15, add_noise=False)
    a = to_dcm(q)
    cam_v = (a @ cat.vectors.T).T
    uv, infov = cam.project(cam_v)
    np.testing.assert_array_equal(np.nonzero(infov)[0], truth.cat_idx)
    np.testing.assert_allclose(uv[infov], truth.uv_mid, atol=1e-9)
    assert img.max() <= 4095


def test_streak_length_matches_omega():
    cam = demo_camera().downscaled(4)
    vecs = np.array([[0.0, 0.0, 1.0]])
    cat = StarCatalog(ids=np.array([1]), vectors=vecs, mags=np.array([1.0], dtype=np.float32), source="SYNTHETIC")
    sim = SkySimulator(cam, cat, radiometry=Radiometry(hot_pixel_frac=0.0, cosmic_rate_per_frame=0.0), seed=0)
    q = np.array([1.0, 0.0, 0.0, 0.0])
    omega_deg_s = 0.5
    t = 0.15
    img, truth = sim.render(
        q, omega_deg_s=(omega_deg_s, 0.0, 0.0), t_exp_s=t, add_noise=False, psf_sigma_px=1.0
    )
    from src.quaternion import propagate

    omega_rad = np.array([np.radians(omega_deg_s), 0.0, 0.0])
    uv0, _ = cam.project((to_dcm(propagate(q, omega_rad, -0.5 * t)) @ vecs.T).T)
    uv1, _ = cam.project((to_dcm(propagate(q, omega_rad, 0.5 * t)) @ vecs.T).T)
    l_geom = float(np.linalg.norm(uv1[0] - uv0[0]))
    l_pred = np.radians(omega_deg_s) * t * cam.fx
    assert abs(l_geom - l_pred) < 0.3
    np.testing.assert_allclose(truth.streak_px[0], l_pred, rtol=0.05)
    u, v = _cog(img)
    np.testing.assert_allclose([u, v], truth.uv_mid[0], atol=0.1)


def test_moon_disk_matches_half_degree():
    cam = demo_camera().downscaled(4)
    vecs = np.array([[0.0, 0.0, 1.0]])
    cat = StarCatalog(ids=np.array([1]), vectors=vecs, mags=np.array([6.0], dtype=np.float32), source="SYNTHETIC")
    sim = SkySimulator(cam, cat, radiometry=Radiometry(hot_pixel_frac=0.0, cosmic_rate_per_frame=0.0), seed=0)
    q = np.array([1.0, 0.0, 0.0, 0.0])
    u, v = 180.0, 140.0
    img, _ = sim.render(
        q,
        omega_deg_s=(0.0, 0.0, 0.0),
        t_exp_s=0.15,
        add_noise=False,
        glare=GlareSpec(kind="moon", u=u, v=v, peak_dn=2400),
    )
    radius = 0.5 * cam.angular_diameter_px(0.50)
    assert 12 < radius < 30
    yy, xx = np.ogrid[: img.shape[0], : img.shape[1]]
    inner = (xx - u) ** 2 + (yy - v) ** 2 <= (0.6 * radius) ** 2
    outer = (xx - u) ** 2 + (yy - v) ** 2 >= (1.4 * radius) ** 2
    assert float(np.median(img[inner])) > 1500
    assert float(np.median(img[outer])) < 200


def test_andromeda_clutter_is_faint():
    cam = demo_camera().downscaled(4)
    vecs = np.array([[0.0, 0.0, 1.0]])
    cat = StarCatalog(ids=np.array([1]), vectors=vecs, mags=np.array([1.0], dtype=np.float32), source="SYNTHETIC")
    sim = SkySimulator(cam, cat, radiometry=Radiometry(hot_pixel_frac=0.0, cosmic_rate_per_frame=0.0), seed=0)
    q = np.array([1.0, 0.0, 0.0, 0.0])
    img, _ = sim.render(
        q, omega_deg_s=(0, 0, 0), t_exp_s=0.15, add_noise=False, sky_clutter="galaxy"
    )
    assert img.max() <= 4095
    assert int(np.count_nonzero(img > 80)) > 200
    img_mw, _ = sim.render(
        q, omega_deg_s=(0, 0, 0), t_exp_s=0.15, add_noise=False, sky_clutter="andromeda"
    )
    assert img_mw.max() <= 4095


def test_earth_limb_keeps_dark_sky_above():
    cam = demo_camera().downscaled(4)
    vecs = np.array([[0.0, 0.0, 1.0]])
    cat = StarCatalog(ids=np.array([1]), vectors=vecs, mags=np.array([6.0], dtype=np.float32), source="SYNTHETIC")
    sim = SkySimulator(cam, cat, radiometry=Radiometry(hot_pixel_frac=0.0, cosmic_rate_per_frame=0.0), seed=0)
    q = np.array([1.0, 0.0, 0.0, 0.0])
    img, _ = sim.render(
        q,
        omega_deg_s=(0, 0, 0),
        t_exp_s=0.15,
        add_noise=False,
        glare=GlareSpec(kind="earth", peak_dn=2800, edge_frac=0.70),
    )
    sky = img[: int(0.40 * cam.height)]
    earth = img[int(0.85 * cam.height) :]
    assert float(np.median(earth)) > 2000
    assert float(np.median(sky)) < 400
    assert img.max() <= 4095


def test_typical_clutter_layers_stack():
    cam = demo_camera().downscaled(4)
    vecs = np.array([[0.0, 0.0, 1.0]])
    cat = StarCatalog(ids=np.array([1]), vectors=vecs, mags=np.array([1.0], dtype=np.float32), source="SYNTHETIC")
    sim = SkySimulator(cam, cat, radiometry=Radiometry(hot_pixel_frac=0.0, cosmic_rate_per_frame=0.0), seed=0)
    q = np.array([1.0, 0.0, 0.0, 0.0])
    img, _ = sim.render(
        q, omega_deg_s=(0, 0, 0), t_exp_s=0.15, add_noise=False, sky_clutter="typical"
    )
    layers = sim._clutter_layers("typical")
    assert layers == {"galactic", "galaxy", "nebula", "cloud"}
    assert img.max() <= 4095
