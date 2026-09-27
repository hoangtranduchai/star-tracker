"""Centroid detector tests: 0.1 px, cosmic-ray reject, mask respect."""

from __future__ import annotations

import numpy as np

from src.camera import demo_camera
from src.catalog import CatalogManager, StarCatalog
from src.centroid import CentroidDetector
from src.simulator import Radiometry, SkySimulator
from src.masking import GlareMasker
from src.simulator import GlareSpec


def _match_rms(det_uv, truth_uv) -> float:
    if len(det_uv) == 0 or len(truth_uv) == 0:
        return 1e9
    d = det_uv[:, None, :] - truth_uv[None, :, :]
    dist = np.linalg.norm(d, axis=2)
    assigned = dist.min(axis=1)
    bright = assigned < 3.0
    if not np.any(bright):
        return 1e9
    return float(np.sqrt(np.mean(assigned[bright] ** 2)))


def test_centroid_rms_under_tenth_pixel():
    cam = demo_camera().downscaled(4)
    cat = CatalogManager.synthetic(800, 6.0, seed=21)
    rad = Radiometry(hot_pixel_frac=0.0, cosmic_rate_per_frame=0.0, read_noise_e=2.0)
    sim = SkySimulator(cam, cat, radiometry=rad, seed=21)
    q = SkySimulator.generate_random_quaternion(seed=3)
    img, truth = sim.render(q, omega_deg_s=(0, 0, 0), add_noise=True)
    det = CentroidDetector(cam, k_sigma=4.0, bg_block=32, min_area=3, max_area=80)
    cents = det.detect(img)
    # Keep truth stars brighter than V=5 for SNR>20-ish
    bright = truth.vis_mags <= 5.0
    rms = _match_rms(cents.uv, truth.uv_mid[bright] if np.any(bright) else truth.uv_mid)
    assert rms < 0.1


def test_dark_silhouette_edge_is_not_a_star():
    """A treeline is a dark step. Only the bright core is a star."""
    cam = demo_camera().downscaled(4)
    img = np.full((220, 220), 40, dtype=np.uint8)
    img[140:, :] = 8
    img[40:44, 80:84] = 255
    det = CentroidDetector(cam, bg_block=31, min_area=3, max_area=80)
    cents = det.detect(img)
    assert len(cents.uv) == 1
    assert abs(cents.uv[0, 0] - 81.5) < 1.5
    assert abs(cents.uv[0, 1] - 41.5) < 1.5


def test_rejects_single_pixel_spikes():
    cam = demo_camera().downscaled(4)
    img = np.full((cam.height, cam.width), 64, dtype=np.uint16)
    rng = np.random.default_rng(0)
    ys = rng.integers(20, cam.height - 20, size=40)
    xs = rng.integers(20, cam.width - 20, size=40)
    for y, x in zip(ys, xs):
        img[y, x] = 4000
    det = CentroidDetector(cam, min_area=3)
    cents = det.detect(img)
    assert len(cents.uv) == 0


def test_streak_bias_under_tenth_pixel():
    cam = demo_camera().downscaled(4)
    vecs = np.array([[0.0, 0.0, 1.0]])
    cat = StarCatalog(ids=np.array([1]), vectors=vecs, mags=np.array([1.5], dtype=np.float32), source="SYNTHETIC")
    sim = SkySimulator(
        cam, cat, radiometry=Radiometry(hot_pixel_frac=0.0, cosmic_rate_per_frame=0.0), seed=0
    )
    q = np.array([1.0, 0.0, 0.0, 0.0])
    img, truth = sim.render(q, omega_deg_s=(0.0, 0.06, 0.0), t_exp_s=0.15, add_noise=False)
    det = CentroidDetector(cam, min_area=3, max_area=200, max_axis_ratio=8.0)
    cents = det.detect(img)
    assert len(cents.uv) >= 1
    err = np.linalg.norm(cents.uv[0] - truth.uv_mid[0])
    assert err < 0.1


def test_no_centroid_inside_mask():
    cam = demo_camera().downscaled(4)
    cat = CatalogManager.synthetic(400, 6.0, seed=5)
    sim = SkySimulator(
        cam, cat, radiometry=Radiometry(hot_pixel_frac=0.0, cosmic_rate_per_frame=0.0), seed=5
    )
    q = SkySimulator.generate_random_quaternion(seed=8)
    img, _truth = sim.render(
        q, omega_deg_s=(0, 0, 0), add_noise=False, glare=GlareSpec(kind="sun", u=80, v=80, sigma_px=70, peak_dn=3800)
    )
    masker = GlareMasker(min_area_px=8, dilate_px=6, full_scale=4095)
    mask = masker.make_mask(img)
    det = CentroidDetector(cam)
    cents = det.detect(img, mask=mask)
    if len(cents.uv) == 0:
        return
    yi = np.clip(np.round(cents.uv[:, 1]).astype(int), 0, cam.height - 1)
    xi = np.clip(np.round(cents.uv[:, 0]).astype(int), 0, cam.width - 1)
    assert not np.any(mask[yi, xi])


def test_detects_saturated_boresight_star():
    """Mag ~0 at +Z saturates 12-bit; still a star, must centroid near (cx, cy)."""
    cam = demo_camera().downscaled(4)
    vecs = np.array([[0.0, 0.0, 1.0]])
    cat = StarCatalog(
        ids=np.array([7001]),
        vectors=vecs,
        mags=np.array([0.03], dtype=np.float32),
        source="SYNTHETIC",
    )
    sim = SkySimulator(
        cam, cat, radiometry=Radiometry(hot_pixel_frac=0.0, cosmic_rate_per_frame=0.0), seed=0
    )
    q = np.array([1.0, 0.0, 0.0, 0.0])
    img, truth = sim.render(q, omega_deg_s=(0, 0, 0), add_noise=False)
    assert int(img.max()) >= 4000
    masker = GlareMasker(min_area_px=8, min_span_px=48, dilate_px=6, full_scale=4095, bg_excess_k=100)
    mask = masker.make_mask(img)
    cy, cx = int(round(cam.cy)), int(round(cam.cx))
    assert not mask[cy, cx]
    det = CentroidDetector(cam, min_area=3, max_area=120, max_area_sat=2500, saturation_dn=4000)
    cents = det.detect(img, mask=mask)
    assert len(cents.uv) >= 1
    err = np.linalg.norm(cents.uv[0] - truth.uv_mid[0])
    assert err < 2.0
