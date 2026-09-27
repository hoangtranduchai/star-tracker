"""Pyramid identification tests."""

from __future__ import annotations

import time

import numpy as np

from src.catalog import CatalogManager, StarCatalog
from src.identification import StarIdentifier, _chirality
from src.kvector import KVectorTable
from src.quaternion import random_quaternion, to_dcm


def _fov_catalog(n_fov=10, n_sky=250, seed=0):
    rng = np.random.default_rng(seed)
    xy = rng.uniform(-0.07, 0.07, size=(n_fov, 2))
    fov = np.column_stack((xy[:, 0], xy[:, 1], np.ones(n_fov)))
    fov /= np.linalg.norm(fov, axis=1, keepdims=True)
    u = rng.uniform(-1, 1, n_sky)
    th = rng.uniform(0, 2 * np.pi, n_sky)
    sky = np.column_stack((np.sqrt(1 - u**2) * np.cos(th), np.sqrt(1 - u**2) * np.sin(th), u))
    # drop sky stars that land in FOV
    keep = sky[:, 2] < 0.85
    sky = sky[keep]
    vecs = np.vstack((fov, sky))
    mags = np.concatenate((np.linspace(1.0, 4.5, n_fov), rng.uniform(3.0, 6.0, len(sky))))
    cat = StarCatalog(
        ids=np.arange(len(vecs), dtype=np.int32),
        vectors=vecs,
        mags=mags.astype(np.float32),
        source="SYNTHETIC",
    )
    return cat, n_fov


def test_identifies_noisy_fov_stars():
    cat, n_fov = _fov_catalog()
    kv = KVectorTable.build(cat, theta_min_deg=0.02, theta_max_deg=19.5)
    ident = StarIdentifier(cat, kv, tol_rad=np.radians(0.02), max_stars=12)
    b = cat.vectors[:n_fov].copy()
    rng = np.random.default_rng(1)
    b += rng.normal(scale=5e-6, size=b.shape)
    b /= np.linalg.norm(b, axis=1, keepdims=True)
    flux = 10.0 ** (-0.4 * cat.mags[:n_fov])
    res = ident.identify(b, flux)
    assert res.success
    assert len(res.obs_idx) >= 4
    # matched catalog indices should be the first n_fov stars
    assert set(res.cat_idx.tolist()).issubset(set(range(n_fov)))


def test_survives_three_false_stars():
    cat, n_fov = _fov_catalog(seed=2)
    kv = KVectorTable.build(cat)
    ident = StarIdentifier(cat, kv, tol_rad=np.radians(0.03), max_stars=12, n_false_sky=400)
    b = cat.vectors[:n_fov].copy()
    rng = np.random.default_rng(2)
    false = rng.normal(size=(3, 3))
    false[:, 2] = np.abs(false[:, 2]) + 0.8
    false /= np.linalg.norm(false, axis=1, keepdims=True)
    obs = np.vstack((b, false))
    flux = np.concatenate((np.linspace(10, 5, n_fov), np.array([9.0, 8.0, 7.0])))
    res = ident.identify(obs, flux)
    assert res.success
    assert set(res.cat_idx.tolist()).issubset(set(range(n_fov)))


def test_chirality_rejects_mirror():
    a = np.array([1.0, 0.0, 0.0])
    b = np.array([0.0, 1.0, 0.0])
    c = np.array([0.0, 0.0, 1.0])
    assert _chirality(a, b, c) == -_chirality(a, c, b)


def test_milky_way_capped_runtime():
    rng = np.random.default_rng(4)
    n = 180
    xy = rng.uniform(-0.08, 0.08, size=(n, 2))
    fov = np.column_stack((xy[:, 0], xy[:, 1], np.ones(n)))
    fov /= np.linalg.norm(fov, axis=1, keepdims=True)
    extra = rng.normal(size=(400, 3))
    extra /= np.linalg.norm(extra, axis=1, keepdims=True)
    vecs = np.vstack((fov, extra))
    cat = StarCatalog(
        ids=np.arange(len(vecs), dtype=np.int32),
        vectors=vecs,
        mags=np.clip(rng.uniform(1, 6, len(vecs)), 0.5, 6).astype(np.float32),
        source="SYNTHETIC",
    )
    kv = KVectorTable.build(cat, theta_min_deg=0.02, theta_max_deg=19.5)
    ident = StarIdentifier(cat, kv, tol_rad=np.radians(0.03), max_stars=12, cutoff=2000)
    flux = np.linspace(20, 1, 120)
    t0 = time.perf_counter()
    ident.identify(fov[:120], flux)
    dt_ms = (time.perf_counter() - t0) * 1000.0
    assert dt_ms < 20.0


def test_mount_st_helens_wide_field_matches_lost(star_tracker_root, bsc5_path):
    """Ground photo: trees are not stars, and the field is the one LOST published."""
    import cv2

    from src.camera import CameraModel
    from src.centroid import CentroidDetector
    from src.demo_session import load_catalog
    from src.kvector import build_or_load
    from src.pipeline import PipelineConfig, StarTrackerPipeline
    from src.quaternion import boresight_ra_dec_deg

    image_path = star_tracker_root / "data" / "uploads" / "mount_st_helens_1.png"
    if not image_path.is_file() or not bsc5_path.exists():
        return
    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    cam = CameraModel(width=1024, height=1024, pixel_um=4.1, focal_mm=4.2)
    det = CentroidDetector(cam, bg_block=31, min_area=3)
    cents = det.detect(image)
    assert 20 <= len(cents.uv) <= 160
    cat, _synthetic = load_catalog("bsc5", 6.0, star_tracker_root / "data" / "catalogs")
    kv = build_or_load(cat, star_tracker_root / "data" / "catalogs", 0.02, 19.5)
    cfg = PipelineConfig(
        angular_tol_rad=0.88 * cam.ifov_rad,
        bg_block=31,
        k_sigma=4.0,
        min_area=3,
        max_area=120,
        saturation_dn=4000,
        n_false_sky=300,
        p_max=1e-4,
        max_stars=12,
        mask_bright_frac=0.99,
        mask_full_scale=255.0,
    )
    result = StarTrackerPipeline(cam, cat, kv, cfg).process_frame(image)
    assert result.success, result.error
    ra, dec = boresight_ra_dec_deg(result.q)
    assert abs(dec - 36.023) < 1.0
    dra = (ra - 310.446 + 180.0) % 360.0 - 180.0
    assert abs(dra) < 1.0
