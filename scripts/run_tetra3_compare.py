#!/usr/bin/env python3
"""Run ESA tetra3 on the two FLIR sample TIFFs and print a side-by-side vs Tracker.

This does not copy tetra3 into the demo pipeline. tetra3 camera = FLIR + Fujinon 35 mm,
FOV 11.4°, ~1024x768. The demo camera is a separate 50 mm model.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
TETRA_ROOT = ROOT / "third_party" / "tetra3"
sys.path.insert(0, str(TETRA_ROOT))

from tetra3 import Tetra3  # noqa: E402

VIN_ROOT = ROOT / "star_tracker"
sys.path.insert(0, str(VIN_ROOT))
from src.camera import CameraModel  # noqa: E402
from src.catalog import CatalogManager  # noqa: E402
from src.kvector import KVectorTable  # noqa: E402
from src.pipeline import PipelineConfig, StarTrackerPipeline  # noqa: E402

TETRA_FOV_DEG = 11.4
OUT = VIN_ROOT / "data" / "outputs"


def tetra_camera(width: int, height: int) -> CameraModel:
    f_over_p = width / (2.0 * np.tan(np.radians(TETRA_FOV_DEG) / 2.0))
    pixel_um = 5.86
    return CameraModel(width=width, height=height, pixel_um=pixel_um, focal_mm=f_over_p * 5.86e-3)


def tracker_on_tiff(path: Path, img: np.ndarray) -> dict:
    hip = VIN_ROOT / "data" / "catalogs" / "hipparcos_v6.npz"
    cat = CatalogManager.load_npz(hip) if hip.exists() else CatalogManager.synthetic(3500, 7.0, seed=0)
    kv = KVectorTable.build(cat, theta_min_deg=0.02, theta_max_deg=16.0)
    cam = tetra_camera(img.shape[1], img.shape[0])
    cfg = PipelineConfig(
        angular_tol_rad=np.radians(0.08),
        bg_block=31,
        k_sigma=3.5,
        min_area=3,
        max_area=400,
        max_axis_ratio=6.0,
        saturation_dn=60000,
        mask_min_area_px=img.size,
        mask_dilate_px=0,
        mask_bg_excess_k=50.0,
        mask_bright_frac=0.99,
        mask_full_scale=65535.0,
        n_false_sky=400,
        p_max=1e-3,
        max_stars=12,
    )
    res = StarTrackerPipeline(cam, cat, kv, cfg).process_frame(img)
    n_det = 0 if res.centroids is None else int(len(res.centroids.uv))
    return {
        "success": bool(res.success),
        "n_detected": n_det,
        "n_matched": 0 if res.ident is None else int(len(res.ident.obs_idx)),
        "error": res.error,
        "q": None if res.q is None else res.q.tolist(),
        "note": "Tracker Pyramid on the uncalibrated FLIR sample, not the demo camera.",
    }


def slim_tetra(sol: dict) -> dict:
    keep = [
        "RA", "Dec", "Roll", "FOV", "distortion", "RMSE", "Matches", "Prob",
        "T_solve", "T_extract", "epoch_equinox", "epoch_proper_motion",
    ]
    out = {k: sol.get(k) for k in keep}
    if sol.get("matched_catID") is not None:
        out["n_matched_catID"] = len(sol["matched_catID"])
    return out


def main() -> int:
    data = TETRA_ROOT / "examples" / "data"
    tiffs = sorted(data.glob("*.tif*"))
    if len(tiffs) < 2:
        print("Need 2 tetra3 TIFFs in", data)
        return 1
    print("Loading tetra3 default_database (FOV 10-30 deg, mag<=7)...")
    t3 = Tetra3()
    OUT.mkdir(parents=True, exist_ok=True)
    report = []
    for path in tiffs[:2]:
        print("\n====", path.name, "====")
        pil = Image.open(path)
        arr = np.array(pil)
        sol = t3.solve_from_image(
            pil,
            distortion=[-0.2, 0.1],
            fov_estimate=11.4,
            fov_max_error=2.0,
            return_matches=True,
            return_visual=True,
        )
        tslim = slim_tetra(sol)
        print("ESA tetra3:", json.dumps(tslim, indent=2, default=str))
        vis = sol.get("visual")
        if vis is not None:
            vis_path = OUT / f"tetra3_{path.stem}_visual.png"
            vis.save(vis_path)
            print("wrote", vis_path)
        vin = tracker_on_tiff(path, arr)
        print("Tracker on same TIFF:", json.dumps(vin, indent=2))
        report.append({"file": path.name, "shape": list(arr.shape), "tetra3": tslim, "tracker": vin})
    dest = OUT / "tetra3_vs_tracker.json"
    dest.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print("\nWrote", dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
