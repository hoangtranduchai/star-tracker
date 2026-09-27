"""End-to-end integration tests for the StarTrackerPipeline."""
from __future__ import annotations
import struct
import numpy as np
import pytest
from src.camera import demo_camera
from src.catalog import CatalogManager
from src.demo_session import THETA_MAX_LOCKED_DEG
from src.kvector import KVectorTable
from src.pipeline import PipelineConfig, StarTrackerPipeline
from src.quaternion import angular_error_arcsec
from src.simulator import GlareSpec, Radiometry, SkySimulator

def _check_pipe(cond: bool, msg: str='pipeline assertion failed') -> None:
    if not cond:
        raise AssertionError(msg)

@pytest.fixture(scope='module')
def fast_stack() -> object:
    optics: object = demo_camera().downscaled(4)
    catalog: object = CatalogManager.synthetic(3500, 6.0, seed=99)
    kv_table: object = KVectorTable.build(catalog, theta_min_deg=0.02, theta_max_deg=THETA_MAX_LOCKED_DEG)
    params: object = PipelineConfig(bg_block=32, angular_tol_rad=4.0 * optics.ifov_rad, mask_dilate_px=6, mask_min_area_px=8, max_area=80)
    tracker: object = StarTrackerPipeline(optics, catalog, kv_table, params)
    renderer: object = SkySimulator(optics, catalog, radiometry=Radiometry(hot_pixel_frac=0.0, cosmic_rate_per_frame=0.0), seed=99)
    return (optics, catalog, tracker, renderer)

def test_pipeline_fast_seed_success(fast_stack: object) -> object:
    _, _, tracker, renderer = fast_stack
    solved_out: object = None
    target_q: object = None
    for idx in range(30):
        target_q: object = SkySimulator.generate_random_quaternion(seed=40 + idx)
        frame, gt = renderer.render(target_q, omega_deg_s=(0.0, 0.06, 0.0), add_noise=True)
        if len(gt.cat_idx) >= 8:
            solved_out: object = tracker.process_frame(frame)
            if solved_out.success:
                break
    _check_pipe(solved_out is not None and bool(solved_out.success))
    _check_pipe(angular_error_arcsec(solved_out.q, target_q) < 40.0)

def test_downlink_16_bytes(fast_stack: object) -> object:
    _, _, tracker, renderer = fast_stack
    solved_out: object = None
    for idx in range(30):
        target_q: object = SkySimulator.generate_random_quaternion(seed=70 + idx)
        frame, gt = renderer.render(target_q, omega_deg_s=(0.0, 0.0, 0.0), add_noise=False)
        if len(gt.cat_idx) >= 8:
            solved_out: object = tracker.process_frame(frame)
            if solved_out.success:
                break
    if solved_out is None or not solved_out.success:
        pytest.skip('No solvable frame encountered')
    packet: object = solved_out.to_downlink_bytes()
    _check_pipe(len(packet) == 16)
    decoded: object = np.asarray(struct.unpack('<4f', packet), dtype=np.float64)
    np.testing.assert_allclose(decoded, solved_out.q, rtol=1e-06, atol=1e-06)

def test_remaining_catalog_stars_identified_after_wahba(fast_stack: object) -> object:
    _, _, tracker, renderer = fast_stack
    solved_out: object = None
    for idx in range(80):
        target_q: object = SkySimulator.generate_random_quaternion(seed=200 + idx)
        frame, gt = renderer.render(target_q, omega_deg_s=(0.0, 0.0, 0.0), add_noise=True)
        if len(gt.cat_idx) >= 16:
            solved_out: object = tracker.process_frame(frame)
            if solved_out.success and len(solved_out.centroids.uv) > 12:
                break
    _check_pipe(solved_out is not None and bool(solved_out.success))
    _check_pipe(len(solved_out.centroids.uv) > 12 and len(solved_out.ident.obs_idx) > 12)

def test_pipeline_insufficient_stars(fast_stack: object) -> object:
    _, _, tracker, _ = fast_stack
    blank: object = np.full((tracker.camera.height, tracker.camera.width), 64, dtype=np.uint16)
    outcome: object = tracker.process_frame(blank)
    _check_pipe(not bool(outcome.success))
    _check_pipe('Insufficient' in (outcome.error or ''))

def test_earth_limb_still_solves_on_sky(fast_stack: object) -> object:
    optics, _, tracker, renderer = fast_stack
    solved_out: object = None
    target_q: object = None
    for idx in range(30):
        target_q: object = SkySimulator.generate_random_quaternion(seed=40 + idx)
        frame, gt = renderer.render(target_q, omega_deg_s=(0.0, 0.0, 0.0), add_noise=True, glare=GlareSpec(kind='earth', peak_dn=2800, edge_frac=0.7))
        horizon_v: object = 0.7 * optics.height
        clear_count: object = int(np.count_nonzero(gt.uv_mid[:, 1] < horizon_v - 8.0)) if len(gt.uv_mid) else 0
        if clear_count >= 8:
            solved_out: object = tracker.process_frame(frame)
            if solved_out.success:
                break
    _check_pipe(solved_out is not None and bool(solved_out.success))
    _check_pipe(solved_out.glare_mask is not None)
    _check_pipe(bool(solved_out.glare_mask[optics.height - 4, optics.width // 2]))
    _check_pipe(not bool(solved_out.glare_mask[12, optics.width // 2]))
    _check_pipe(angular_error_arcsec(solved_out.q, target_q) < 60.0)

def test_moon_disk_is_masked_not_identified(fast_stack: object) -> object:
    optics, _, tracker, renderer = fast_stack
    moon_u, moon_v = (0.18 * optics.width, 0.22 * optics.height)
    target_q: object = SkySimulator.generate_random_quaternion(seed=11)
    frame, gt = renderer.render(target_q, omega_deg_s=(0.0, 0.0, 0.0), add_noise=True, glare=GlareSpec(kind='moon', u=moon_u, v=moon_v, peak_dn=2400))
    if len(gt.cat_idx) < 8:
        pytest.skip('Sparse star field')
    solved_out: object = tracker.process_frame(frame)
    _check_pipe(solved_out.glare_mask is not None and bool(solved_out.glare_mask[int(moon_v), int(moon_u)]))
    if solved_out.centroids is not None and len(solved_out.centroids.uv):
        offsets: object = np.linalg.norm(solved_out.centroids.uv - np.asarray([moon_u, moon_v]), axis=1)
        _check_pipe(float(offsets.min()) > 8.0)
