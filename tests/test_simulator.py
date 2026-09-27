"""Tests for the synthetic sky image renderer, motion streaks, and clutter layers."""
from __future__ import annotations
import numpy as np
from src.camera import demo_camera
from src.catalog import CatalogManager, StarCatalog
from src.quaternion import propagate, to_dcm
from src.simulator import GlareSpec, Radiometry, SkySimulator

def _verify_sim(cond: bool, msg: str='simulator check failed') -> None:
    if not cond:
        raise AssertionError(msg)

def _measure_barycenter(frame: np.ndarray) -> tuple[float, float]:
    arr: object = frame.astype(np.float64)
    weights: object = np.maximum(arr - np.median(arr), 0.0)
    total: object = float(weights.sum())
    _verify_sim(total > 0.0, 'Zero signal above median background')
    yy, xx = np.indices(arr.shape)
    return (float((weights * xx).sum() / total), float((weights * yy).sum() / total))

def _single_boresight_sim(mag_val: float=1.0) -> object:
    optics: object = demo_camera().downscaled(4)
    catalog: object = StarCatalog(ids=np.asarray([1], dtype=np.int32), vectors=np.asarray([[0.0, 0.0, 1.0]], dtype=np.float64), mags=np.asarray([mag_val], dtype=np.float32), source='SYNTHETIC')
    renderer: object = SkySimulator(optics, catalog, radiometry=Radiometry(hot_pixel_frac=0.0, cosmic_rate_per_frame=0.0), seed=0)
    return (optics, catalog, renderer, np.asarray([1.0, 0.0, 0.0, 0.0], dtype=np.float64))

def test_bright_star_cog_matches_truth() -> object:
    optics, _, renderer, q_ident = _single_boresight_sim(1.0)
    frame, gt = renderer.render(q_ident, omega_deg_s=(0.0, 0.0, 0.0), t_exp_s=0.15, add_noise=False)
    _verify_sim(frame.dtype == np.uint16 and int(frame.max()) <= 4095)
    u_est, v_est = _measure_barycenter(frame)
    np.testing.assert_allclose([u_est, v_est], gt.uv_mid[0], atol=0.02)
    np.testing.assert_allclose(gt.uv_mid[0], [optics.cx, optics.cy], atol=1e-06)

def test_mid_exposure_matches_q_gt() -> object:
    optics: object = demo_camera().downscaled(4)
    catalog: object = CatalogManager.synthetic(400, 6.0, seed=1)
    renderer: object = SkySimulator(optics, catalog, radiometry=Radiometry(hot_pixel_frac=0.0, cosmic_rate_per_frame=0.0), seed=1)
    q_rand: object = SkySimulator.generate_random_quaternion(seed=9)
    frame, gt = renderer.render(q_rand, omega_deg_s=(0.0, 0.06, 0.0), t_exp_s=0.15, add_noise=False)
    uv_proj, in_fov = optics.project((to_dcm(q_rand) @ catalog.vectors.T).T)
    np.testing.assert_array_equal(np.nonzero(in_fov)[0], gt.cat_idx)
    np.testing.assert_allclose(uv_proj[in_fov], gt.uv_mid, atol=1e-09)
    _verify_sim(int(frame.max()) <= 4095)

def test_streak_length_matches_omega() -> object:
    optics, catalog, renderer, q_ident = _single_boresight_sim(1.0)
    rate_deg_s, exp_s = (0.5, 0.15)
    frame, gt = renderer.render(q_ident, omega_deg_s=(rate_deg_s, 0.0, 0.0), t_exp_s=exp_s, add_noise=False, psf_sigma_px=1.0)
    omega_vec: object = np.asarray([np.deg2rad(rate_deg_s), 0.0, 0.0])
    uv_start, _ = optics.project((to_dcm(propagate(q_ident, omega_vec, -0.5 * exp_s)) @ catalog.vectors.T).T)
    uv_end, _ = optics.project((to_dcm(propagate(q_ident, omega_vec, 0.5 * exp_s)) @ catalog.vectors.T).T)
    expected_len: object = np.deg2rad(rate_deg_s) * exp_s * optics.fx
    _verify_sim(abs(float(np.linalg.norm(uv_end[0] - uv_start[0])) - expected_len) < 0.3)
    np.testing.assert_allclose(gt.streak_px[0], expected_len, rtol=0.05)
    np.testing.assert_allclose(_measure_barycenter(frame), gt.uv_mid[0], atol=0.1)

def test_moon_disk_matches_half_degree() -> object:
    optics, _, renderer, q_ident = _single_boresight_sim(6.0)
    moon_u, moon_v = (180.0, 140.0)
    frame, _ = renderer.render(q_ident, omega_deg_s=(0.0, 0.0, 0.0), t_exp_s=0.15, add_noise=False, glare=GlareSpec(kind='moon', u=moon_u, v=moon_v, peak_dn=2400))
    rad_px: object = 0.5 * optics.angular_diameter_px(0.5)
    _verify_sim(12.0 < rad_px < 30.0)
    yy, xx = np.ogrid[:frame.shape[0], :frame.shape[1]]
    dist_sq: object = (xx - moon_u) ** 2 + (yy - moon_v) ** 2
    _verify_sim(float(np.median(frame[dist_sq <= (0.6 * rad_px) ** 2])) > 1500.0)
    _verify_sim(float(np.median(frame[dist_sq >= (1.4 * rad_px) ** 2])) < 200.0)

def test_andromeda_clutter_is_faint() -> object:
    _, _, renderer, q_ident = _single_boresight_sim(1.0)
    frame_gal, _ = renderer.render(q_ident, omega_deg_s=(0, 0, 0), t_exp_s=0.15, add_noise=False, sky_clutter='galaxy')
    frame_m31, _ = renderer.render(q_ident, omega_deg_s=(0, 0, 0), t_exp_s=0.15, add_noise=False, sky_clutter='andromeda')
    _verify_sim(int(frame_gal.max()) <= 4095 and int(np.count_nonzero(frame_gal > 80)) > 200)
    _verify_sim(int(frame_m31.max()) <= 4095)

def test_earth_limb_keeps_dark_sky_above() -> object:
    optics, _, renderer, q_ident = _single_boresight_sim(6.0)
    frame, _ = renderer.render(q_ident, omega_deg_s=(0, 0, 0), t_exp_s=0.15, add_noise=False, glare=GlareSpec(kind='earth', peak_dn=2800, edge_frac=0.7))
    _verify_sim(float(np.median(frame[int(0.85 * optics.height):])) > 2000.0)
    _verify_sim(float(np.median(frame[:int(0.4 * optics.height)])) < 400.0)
    _verify_sim(int(frame.max()) <= 4095)

def test_typical_clutter_layers_stack() -> object:
    _, _, renderer, q_ident = _single_boresight_sim(1.0)
    frame, _ = renderer.render(q_ident, omega_deg_s=(0, 0, 0), t_exp_s=0.15, add_noise=False, sky_clutter='typical')
    _verify_sim(renderer._clutter_layers('typical') == {'galactic', 'galaxy', 'nebula', 'cloud'})
    _verify_sim(int(frame.max()) <= 4095)
