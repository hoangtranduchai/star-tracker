#!/usr/bin/env python3
"""Full-frame demo-camera images with one BSC5 star on camera +Z (center).

Not a night-sky photo. Radiometry.assumption=true. Optics: 6000x4000, 3.72 um, 50 mm.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from generate_sim_dataset import load_radiometry, star_rows  # noqa: E402
from src.camera import demo_camera
from src.catalog import CatalogManager
from src.quaternion import boresight_ra_dec_deg, format_dec_dms, format_ra_hms, looking_at
from src.simulator import SkySimulator
from src.starnames import label_hr, lookup_hr


def write_frame(out_dir: Path, stem: str, img: np.ndarray, meta: dict) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    tif = out_dir / f"{stem}.tif"
    ok = cv2.imwrite(str(tif), img, [int(getattr(cv2, "IMWRITE_TIFF_COMPRESSION", 259)), 8])
    if not ok:
        raise RuntimeError(f"cv2.imwrite failed: {tif}")
    (out_dir / f"{stem}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    preview = np.clip(img.astype(np.float32) / 16.0, 0, 255).astype(np.uint8)
    cv2.imwrite(str(out_dir / f"{stem}_preview.png"), preview)
    return tif


def main() -> int:
    p = argparse.ArgumentParser(description="Boresight-centered synthetic ST frames")
    p.add_argument("--n", type=int, default=10, help="How many catalog stars (brightest first)")
    p.add_argument("--mode", choices=["fast", "full"], default="full")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument(
        "--out",
        type=Path,
        default=ROOT / "data" / "sim_dataset" / "center_full",
    )
    args = p.parse_args()

    cat_path = ROOT / "data" / "catalogs" / "bsc5_v6.0.npz"
    if not cat_path.exists():
        raise SystemExit(f"missing catalog {cat_path}")
    cat = CatalogManager.load_npz(cat_path)
    order = np.argsort(cat.mags)
    n = min(int(args.n), int(cat.num_stars))
    pick = order[:n]

    cam = demo_camera()
    rel = "center_full"
    if args.mode == "fast":
        cam = cam.downscaled(4)
        if args.out == ROOT / "data" / "sim_dataset" / "center_full":
            args.out = ROOT / "data" / "sim_dataset" / "center_fast"
        rel = "center_fast"

    rad = load_radiometry()
    sim = SkySimulator(cam, cat, radiometry=rad, seed=args.seed)
    manifest = {
        "note": (
            "Each frame points camera +Z at one Yale BSC5 V<=6 star (pair-filtered). "
            "Demo camera 6000x4000 / 3.72 um / 50 mm. "
            "Synthetic; radiometry assumption; not night-sky / HIL."
        ),
        "catalog": cat.source,
        "n_catalog": cat.num_stars,
        "mode": args.mode,
        "camera": {"width": cam.width, "height": cam.height, "pixel_um": cam.pixel_um, "focal_mm": cam.focal_mm},
        "frames": [],
    }

    for k, idx in enumerate(pick):
        idx = int(idx)
        hr = int(cat.ids[idx])
        rec = lookup_hr(hr) or {}
        q = looking_at(cat.vectors[idx])
        img, truth = sim.render(
            q, omega_deg_s=(0.0, 0.0, 0.0), t_exp_s=0.15, add_noise=True, false_stars=0
        )
        ra, dec = boresight_ra_dec_deg(q)
        rows = star_rows(cat, truth)
        stem = f"{k:02d}_hr{hr}"
        meta = {
            "mode": args.mode,
            "kind": "catalog_boresight",
            "index": k,
            "center_star": {
                "catalog_idx": idx,
                "hr": hr,
                "iau_name": rec.get("name"),
                "label": label_hr(hr, compact=False),
                "mag": float(cat.mags[idx]),
            },
            "q_gt": q.tolist(),
            "omega_deg_s": [0.0, 0.0, 0.0],
            "t_exp_s": 0.15,
            "false_stars": 0,
            "boresight": {
                "ra_deg": ra,
                "dec_deg": dec,
                "ra_hms": format_ra_hms(ra),
                "dec_dms": format_dec_dms(dec),
                "frame": "J2000 camera +Z",
            },
            "camera": {
                "width": cam.width,
                "height": cam.height,
                "pixel_um": cam.pixel_um,
                "focal_mm": cam.focal_mm,
            },
            "stars_in_fov": rows,
            "image": f"{rel}/{stem}.tif",
        }
        tif = write_frame(args.out, stem, img, meta)
        uv = truth.uv_mid[np.where(truth.cat_idx == idx)[0][0]]
        print(
            f"  {stem}.tif  {label_hr(hr, compact=True):<16}  V={cat.mags[idx]:5.2f}  "
            f"uv=({uv[0]:.1f},{uv[1]:.1f})  FOV={len(truth.cat_idx)}  "
            f"{tif.stat().st_size / 1e6:.1f} MB",
            flush=True,
        )
        manifest["frames"].append(
            {
                "file": f"{rel}/{stem}.tif",
                "sidecar": f"{rel}/{stem}.json",
                "hr": hr,
                "iau_name": rec.get("name"),
                "mag": float(cat.mags[idx]),
                "n_stars": len(truth.cat_idx),
                "ra_deg": ra,
                "dec_deg": dec,
            }
        )

    man_path = args.out / "manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("manifest", man_path, "n=", len(manifest["frames"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
