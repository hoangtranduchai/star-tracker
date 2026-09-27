"""Regression locks for the CNN centroid path (src/centroid_cnn.py).

Three behaviours broke each other several times in one evening because
agents edited the same seed-selection code:

1. 8-bit LOST mountain photo (data/uploads/mount_st_helens_1.png, 4.2 mm,
   4.1 µm): NMS yields ~1000 seeds. Raster order spends max_stars=80 on the
   first rows (y≈0 glare band) → 0 ID. Contrast/SNR-ranked seeds → ~63/79 ID,
   boresight RA≈310.5°, Dec≈+36.0° (LOST reference 310.446 / 36.023).
2. FAST seed-42 clean 12-bit sim (1500×1000): bit depth detected by max DN,
   raster seeds, V≤6 peak-DN gate, DN flux → ~30/35 ID, error a few arcsec.
3. hd1024/0000.tif (12-bit, 1024×683): CNN must still solve.

All three run through DemoEngine, the same path the web app uses.
Skipped when torch / the public weights / the images are missing.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from src.centroid_cnn import (
    nms_seed_pixels,
    outdoor_seed_scores,
    trilateration_centroids,
    weights_available,
)

ROOT = Path(__file__).resolve().parent.parent
MOUNTAIN = ROOT / "data" / "uploads" / "mount_st_helens_1.png"
HD1024_TIF = ROOT / "data" / "sim_dataset" / "hd1024" / "0000.tif"
HD1024_JSON = HD1024_TIF.with_suffix(".json")

# Web-app run: mountain 63/79 ID; sim 30/35; hd1024 41/42 (2026-09-26). Keep margin.
MIN_ID = 20


def _need_cnn() -> None:
    pytest.importorskip("torch")
    if not weights_available():
        pytest.skip("public MobileUNet_B10_50.pt weights missing")


@pytest.fixture(scope="module")
def engine():
    _need_cnn()
    from src.demo_session import DemoEngine

    return DemoEngine(ROOT)


def _run(engine, tmp_path, **kw):
    from src.demo_session import RunRequest

    req = RunRequest(mode="fast", seed=42, centroid_backend="cnn", out_dir=tmp_path, save_png=False, **kw)
    return engine.run(req)


# ----------------------------------------------------------------------------
# Pure-numpy locks (no weights needed)
# ----------------------------------------------------------------------------


def _star_maps(h: int, w: int, centers: list[tuple[float, float]]):
    dist = np.full((h, w), 10.0, dtype=np.float64)
    seg = np.zeros((h, w), dtype=np.float64)
    yy, xx = np.mgrid[0:h, 0:w]
    for cu, cv in centers:
        d = np.hypot((xx + 0.5) - cu, (yy + 0.5) - cv)
        dist = np.minimum(dist, d)
        seg[d < 4.0] = 1.0
    return dist, seg


def test_seed_scores_rank_before_raster_cap():
    """A capped budget must go to the highest-scored seeds, not to the first rows."""
    h = w = 96
    centers = [(12.5, 8.5), (40.5, 20.5), (70.5, 60.5), (20.5, 80.5)]  # raster order = this order
    dist, seg = _star_maps(h, w, centers)
    rows, cols = nms_seed_pixels(dist, seg, d_th=0.8)
    assert len(rows) == 4
    # Raster order: first two seeds are the small-y ones.
    uv_raster = trilateration_centroids(dist, seg, radius=7, d_th=0.8, max_stars=2, seeds=(rows, cols))
    assert np.all(uv_raster[:, 1] < 30.0)
    # Ranked: the two bottom stars score highest and must win the budget.
    scores = np.array([0.1, 0.2, 5.0, 4.0])
    uv_ranked = trilateration_centroids(
        dist, seg, radius=7, d_th=0.8, max_stars=2, seed_scores=scores, seeds=(rows, cols)
    )
    assert len(uv_ranked) == 2
    assert np.all(uv_ranked[:, 1] > 50.0)
    # Full-frame score map is accepted too.
    score_map = np.zeros((h, w))
    score_map[rows, cols] = scores
    uv_map = trilateration_centroids(dist, seg, radius=7, d_th=0.8, max_stars=2, seed_scores=score_map)
    assert np.allclose(np.sort(uv_map, axis=0), np.sort(uv_ranked, axis=0))


def test_outdoor_seed_scores_prefer_star_over_glare_blob():
    rng = np.random.default_rng(0)
    raw = rng.normal(64.0, 3.0, size=(128, 128)).astype(np.float32)
    # Dark, noisy top band with a faint blob (glare band at y≈0).
    raw[:24] = rng.normal(22.0, 6.0, size=(24, 128))
    raw[6, 30] += 25.0
    # Compact star on the smooth sky.
    raw[80, 60] += 120.0
    raw[79:82, 59:62] += 40.0
    scores = outdoor_seed_scores(raw, np.array([6, 80]), np.array([30, 60]))
    assert scores[1] > 3.0 * scores[0]


# ----------------------------------------------------------------------------
# End-to-end locks (weights + images)
# ----------------------------------------------------------------------------


@pytest.mark.skipif(not MOUNTAIN.is_file(), reason="mount_st_helens_1.png not present")
def test_mountain_8bit_cnn_solves(engine, tmp_path):
    from src.demo_session import load_frame

    img = load_frame(MOUNTAIN)
    assert img.dtype == np.uint8 and img.shape == (1024, 1024)
    out = _run(engine, tmp_path, image=MOUNTAIN, focal_mm=4.2, pixel_um=4.1)
    p = out.payload
    assert p["centroid_detector"] == "cnn_zhao2024", p.get("centroid_error")
    assert not p["centroid_fallback"]
    det = out.result.centroids
    assert det is not None and len(det.uv) >= 60
    # Not the raster failure mode: seeds must cover the sky, not hug the top edge.
    v = det.uv[:, 1]
    assert float(np.median(v)) > 150.0, "CNN seeds bunched along the top edge (raster order regression)"
    assert int(np.count_nonzero(v >= 320.0)) >= 20
    assert p["success"], p["error"]
    assert p["metrics"]["n_matched"] >= MIN_ID
    bore = p["boresight_est"]
    assert 310.4 <= bore["ra_deg"] <= 310.6, bore
    assert 35.9 <= bore["dec_deg"] <= 36.1, bore


def test_fast_seed42_clean_sim_cnn_solves(engine, tmp_path):
    out = _run(engine, tmp_path)
    p = out.payload
    st = p["input_stats"]
    assert (st["width"], st["height"]) == (1500, 1000)
    assert out.image.dtype == np.uint16 and int(out.image.max()) > 255  # 12-bit branch
    assert p["centroid_detector"] == "cnn_zhao2024", p.get("centroid_error")
    assert not p["centroid_fallback"]
    assert p["success"], p["error"]
    assert p["metrics"]["n_matched"] >= MIN_ID
    assert p["metrics"]["attitude_error_arcsec"] < 10.0
    # V≤6 gate active on the sim branch: raw ≥ gated, and the gate kept most stars.
    assert p["centroid_n_raw"] >= p["centroid_n_after_gate"] >= MIN_ID


@pytest.mark.skipif(not (HD1024_TIF.is_file() and HD1024_JSON.is_file()), reason="hd1024/0000 not present")
def test_hd1024_frame_cnn_solves(engine, tmp_path):
    cam = json.loads(HD1024_JSON.read_text(encoding="utf-8"))["camera"]
    out = _run(engine, tmp_path, image=HD1024_TIF, focal_mm=cam["focal_mm"], pixel_um=cam["pixel_um"])
    p = out.payload
    assert p["centroid_detector"] == "cnn_zhao2024", p.get("centroid_error")
    assert not p["centroid_fallback"]
    assert p["success"], p["error"]
    assert p["metrics"]["n_matched"] >= MIN_ID
    # 21.8 µm pixels → IFOV ≈ 90″; FAST verdict limit is 40″ (measured ≈ 21″).
    assert p["metrics"]["attitude_error_arcsec"] < 40.0
