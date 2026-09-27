"""End-to-end pipeline tests (FAST mode)."""

from __future__ import annotations

import struct

import numpy as np
import pytest

from src.camera import demo_camera
from src.demo_session import THETA_MAX_LOCKED_DEG
from src.catalog import CatalogManager
from src.kvector import KVectorTable
from src.pipeline import PipelineConfig, StarTrackerPipeline
from src.quaternion import angular_error_arcsec
from src.simulator import GlareSpec, Radiometry, SkySimulator


@pytest.fixture(scope="module")
def fast_stack():
    cam = demo_camera().downscaled(4)
    cat = CatalogManager.synthetic(3500, 6.0, seed=99)
    kv = KVectorTable.build(cat, theta_min_deg=0.02, theta_max_deg=THETA_MAX_LOCKED_DEG)
    cfg = PipelineConfig(
        bg_block=32,
        angular_tol_rad=4 * cam.ifov_rad,
        mask_dilate_px=6,
        mask_min_area_px=8,
        max_area=80,
    )
    pipe = StarTrackerPipeline(cam, cat, kv, cfg)
    sim = SkySimulator(
        cam, cat, radiometry=Radiometry(hot_pixel_frac=0.0, cosmic_rate_per_frame=0.0), seed=99
    )
    return cam, cat, pipe, sim


def test_pipeline_fast_seed_success(fast_stack):
    _cam, _cat, pipe, sim = fast_stack
    res = None
    q_gt = None
    for seed in range(30):
        q_gt = SkySimulator.generate_random_quaternion(seed=40 + seed)
        img, truth = sim.render(q_gt, omega_deg_s=(0.0, 0.06, 0.0), add_noise=True)
        if len(truth.cat_idx) < 8:
            continue
        res = pipe.process_frame(img)
        if res.success:
            break
    assert res is not None and res.success, getattr(res, "error", "no field with enough stars")
    err = angular_error_arcsec(res.q, q_gt)
    assert err < 40.0


def test_downlink_16_bytes(fast_stack):
    _cam, _cat, pipe, sim = fast_stack
    res = None
    for seed in range(30):
        q_gt = SkySimulator.generate_random_quaternion(seed=70 + seed)
        img, truth = sim.render(q_gt, omega_deg_s=(0, 0, 0), add_noise=False)
        if len(truth.cat_idx) < 8:
            continue
        res = pipe.process_frame(img)
        if res.success:
            break
    if res is None or not res.success:
        pytest.skip(getattr(res, "error", "could not solve"))
    blob = res.to_downlink_bytes()
    assert len(blob) == 16
    unpacked = np.array(struct.unpack("<4f", blob), dtype=np.float64)
    np.testing.assert_allclose(unpacked, res.q, rtol=1e-6, atol=1e-6)


def test_remaining_catalog_stars_identified_after_wahba(fast_stack):
    """Pyramid uses 12 brightest; leftover detections of catalog stars must still get IDs."""
    _cam, _cat, pipe, sim = fast_stack
    res = None
    n_truth = 0
    for seed in range(80):
        q_gt = SkySimulator.generate_random_quaternion(seed=200 + seed)
        img, truth = sim.render(q_gt, omega_deg_s=(0.0, 0.0, 0.0), add_noise=True)
        n_truth = len(truth.cat_idx)
        if n_truth < 16:
            continue
        res = pipe.process_frame(img)
        if res.success and len(res.centroids.uv) > 12:
            break
    assert res is not None and res.success
    n_det = len(res.centroids.uv)
    n_id = len(res.ident.obs_idx)
    assert n_det > 12
    assert n_id > 12, f"remaining catalog stars not labeled: ID {n_id} / detect {n_det} (GT {n_truth})"


def test_pipeline_insufficient_stars(fast_stack):
    _cam, _cat, pipe, _sim = fast_stack
    img = np.full((pipe.camera.height, pipe.camera.width), 64, dtype=np.uint16)
    res = pipe.process_frame(img)
    assert res.success is False
    assert "Insufficient" in (res.error or "")


def test_earth_limb_still_solves_on_sky(fast_stack):
    cam, _cat, pipe, sim = fast_stack
    res = None
    q_gt = None
    for seed in range(30):
        q_gt = SkySimulator.generate_random_quaternion(seed=40 + seed)
        img, truth = sim.render(
            q_gt,
            omega_deg_s=(0.0, 0.0, 0.0),
            add_noise=True,
            glare=GlareSpec(kind="earth", peak_dn=2800, edge_frac=0.70),
        )
        limb_y = 0.70 * cam.height
        above = int(np.count_nonzero(truth.uv_mid[:, 1] < (limb_y - 8.0))) if len(truth.uv_mid) else 0
        if above < 8:
            continue
        res = pipe.process_frame(img)
        if res.success:
            break
    assert res is not None and res.success, getattr(res, "error", "no limb field with enough sky stars")
    assert res.glare_mask is not None
    assert res.glare_mask[cam.height - 4, cam.width // 2]
    assert not res.glare_mask[12, cam.width // 2]
    err = angular_error_arcsec(res.q, q_gt)
    assert err < 60.0


def test_moon_disk_is_masked_not_identified(fast_stack):
    cam, _cat, pipe, sim = fast_stack
    u, v = 0.18 * cam.width, 0.22 * cam.height
    q_gt = SkySimulator.generate_random_quaternion(seed=11)
    img, truth = sim.render(
        q_gt,
        omega_deg_s=(0.0, 0.0, 0.0),
        add_noise=True,
        glare=GlareSpec(kind="moon", u=u, v=v, peak_dn=2400),
    )
    if len(truth.cat_idx) < 8:
        pytest.skip("sparse field")
    res = pipe.process_frame(img)
    assert res.glare_mask is not None and res.glare_mask[int(v), int(u)]
    if res.centroids is not None and len(res.centroids.uv):
        d = np.linalg.norm(res.centroids.uv - np.array([u, v]), axis=1)
        assert float(d.min()) > 8.0

