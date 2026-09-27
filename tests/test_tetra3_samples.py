"""tetra3 sample frames, solved with the same custom-optics path as the app.

The TIFFs are real FLIR/Fujinon exposures (35 mm, 6.9 µm after 2×2 binning),
not the demo camera. Alt60 contains enough Yale V≤6 stars to confirm a field.
Alt40 contains only three such stars, so a 3-star lock is not reported.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.camera import CameraModel
from src.demo_session import load_catalog, load_pipeline_cfg, match_tolerance_arcsec
from src.kvector import build_or_load
from src.pipeline import StarTrackerPipeline
from src.quaternion import boresight_ra_dec_deg

TETRA_DIR = Path(__file__).resolve().parents[2] / "third_party" / "tetra3" / "examples" / "data"
# Boresights measured by tetra3 itself on these files (degrees).
REFERENCE = {
    "Alt60": (240.46407740375525, 28.940573467352813),
    "Alt40": (230.66735971690508, 11.034222635156594),
}


def _sep_arcsec(ra: float, dec: float, name: str) -> float:
    ra2, dec2 = REFERENCE[name]
    r1, d1, r2, d2 = map(np.radians, (ra, dec, ra2, dec2))
    c = np.sin(d1) * np.sin(d2) + np.cos(d1) * np.cos(d2) * np.cos(r1 - r2)
    return float(np.degrees(np.arccos(np.clip(c, -1.0, 1.0))) * 3600.0)


@pytest.fixture(scope="module")
def tetra_pipe(star_tracker_root, bsc5_path):
    if not bsc5_path.exists():
        pytest.skip("BSC5 catalog missing")
    files = sorted(TETRA_DIR.glob("*.tif*"))
    if len(files) < 2:
        pytest.skip("tetra3 sample TIFFs missing")
    cat, _synthetic = load_catalog("bsc5", 6.0, star_tracker_root / "data" / "catalogs")
    kv = build_or_load(cat, star_tracker_root / "data" / "catalogs", 0.02, 19.5)
    cam = CameraModel(width=1024, height=768, pixel_um=6.9, focal_mm=35.0)
    cfg = load_pipeline_cfg("fast", star_tracker_root)
    cfg.angular_tol_rad = np.radians(match_tolerance_arcsec(cam, None) / 3600.0)
    cfg.tol_frac = 0.008
    pipe = StarTrackerPipeline(cam, cat, kv, cfg)
    return pipe, files


def test_tetra3_alt60_matches_published_field(tetra_pipe):
    import cv2

    pipe, files = tetra_pipe
    path = next(p for p in files if "Alt60" in p.name)
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    result = pipe.process_frame(img)
    assert result.glare_mask is not None
    assert float(result.glare_mask.mean()) < 0.05
    assert result.success, result.error
    assert len(result.ident.cat_idx) >= 4
    ra, dec = boresight_ra_dec_deg(result.q)
    assert _sep_arcsec(ra, dec, "Alt60") < 120.0


def test_tetra3_alt40_does_not_publish_a_wrong_field(tetra_pipe):
    import cv2

    pipe, files = tetra_pipe
    path = next(p for p in files if "Alt40" in p.name)
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    result = pipe.process_frame(img)
    assert result.centroids is not None and len(result.centroids.uv) >= 3
    if not result.success:
        return
    ra, dec = boresight_ra_dec_deg(result.q)
    assert _sep_arcsec(ra, dec, "Alt40") < 120.0
