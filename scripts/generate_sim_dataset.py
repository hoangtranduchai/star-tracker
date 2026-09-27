#!/usr/bin/env python3
"""Build a synthetic demo-camera star-field set with quaternion ground truth.

This is the same class of sim used by UW LOST `--generate` and NASA COTS / ESA tetra3
practice: catalog → pinhole → PSF/noise → known q. It is not an ISO/CCSDS image standard
and radiometry numbers are assumptions, not a camera datasheet.
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

from src.camera import demo_camera
from src.catalog import CatalogManager, vectors_to_ra_dec
from src.quaternion import boresight_ra_dec_deg, format_dec_dms, format_ra_hms, random_quaternion
from src.simulator import Radiometry, SkySimulator
from src.starnames import label_hr, lookup_hr


def load_radiometry() -> Radiometry:
    specs = json.loads((ROOT / "config" / "camera_specs.json").read_text(encoding="utf-8"))
    r = specs.get("radiometry", {})
    return Radiometry(
        assumption=True,
        e_per_s_v0=float(r.get("e_per_s_v0", 3.3e6)),
        qe=float(r.get("qe", 1.0)),
        read_noise_e=float(r.get("read_noise_e", 5.0)),
        dark_e_per_s=float(r.get("dark_e_per_s", 10.0)),
        gain_dn_per_e=float(r.get("gain_dn_per_e", 1.0)),
        full_well_e=float(r.get("full_well_e", 12000.0)),
        bit_depth=int(r.get("bit_depth", 12)),
        bias_dn=float(r.get("bias_dn", 64.0)),
        hot_pixel_frac=float(r.get("hot_pixel_frac", 1e-5)),
        cosmic_rate_per_frame=float(r.get("cosmic_rate_per_frame", 2.0)),
    )


def star_rows(cat, truth) -> list[dict]:
    rows = []
    ra, dec = vectors_to_ra_dec(cat.vectors[truth.cat_idx])
    for i, idx in enumerate(truth.cat_idx):
        hr = int(cat.ids[idx])
        rec = lookup_hr(hr) or {}
        rows.append(
            {
                "catalog_idx": int(idx),
                "hr": hr,
                "iau_name": rec.get("name"),
                "designation": rec.get("designation") or None,
                "label": label_hr(hr, compact=False),
                "mag": float(truth.vis_mags[i]),
                "u_px": float(truth.uv_mid[i, 0]),
                "v_px": float(truth.uv_mid[i, 1]),
                "ra_deg": float(np.degrees(ra[i])),
                "dec_deg": float(np.degrees(dec[i])),
            }
        )
    return rows


def write_frame(out_dir: Path, stem: str, img: np.ndarray, meta: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    tif = out_dir / f"{stem}.tif"
    ok = cv2.imwrite(str(tif), img)
    if not ok:
        raise RuntimeError(f"cv2.imwrite failed: {tif}")
    (out_dir / f"{stem}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    preview = np.clip(img.astype(np.float32) / 16.0, 0, 255).astype(np.uint8)
    cv2.imwrite(str(out_dir / f"{stem}_preview.png"), preview)


def main() -> int:
    p = argparse.ArgumentParser(description="Synthetic demo-camera star-tracker dataset")
    p.add_argument("--n-fast", type=int, default=40)
    p.add_argument("--n-full", type=int, default=3)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--out", type=Path, default=ROOT / "data" / "sim_dataset")
    args = p.parse_args()

    cat_path = ROOT / "data" / "catalogs" / "bsc5_v6.0.npz"
    if not cat_path.exists():
        bsc5 = ROOT / "data" / "catalogs" / "BSC5"
        CatalogManager.fetch_bsc5(bsc5)
        cat = CatalogManager.filter_close_pairs(
            CatalogManager.load_bsc5(bsc5, max_mag=6.0, epoch_year=2026.7), 60.0
        )
        CatalogManager.save_npz(cat, cat_path)
    else:
        cat = CatalogManager.load_npz(cat_path)

    rad = load_radiometry()
    cam_full = demo_camera()
    cam_fast = cam_full.downscaled(4)
    rng = np.random.default_rng(args.seed)
    manifest = {
        "note": (
            "Synthetic lost-in-space frames. "
            "Demo optics: APS-C 6000x4000, 3.72 um, 50 mm. "
            "Not a night-sky photo. Radiometry.assumption=true. "
            "Method class: catalog pinhole + PSF + detector noise + quaternion GT "
            "(same class as UW LOST --generate / tetra3+COTS practice). Not ISO/CCSDS."
        ),
        "catalog": cat.source,
        "n_catalog": cat.num_stars,
        "frames": [],
    }

    jobs = [("fast", cam_fast, args.n_fast), ("full", cam_full, args.n_full)]
    for mode, cam, n in jobs:
        sim = SkySimulator(cam, cat, radiometry=rad, seed=args.seed)
        dest = args.out / mode
        for i in range(n):
            q = random_quaternion(rng)
            omega = rng.normal(size=3)
            omega = omega / np.linalg.norm(omega) * 0.06
            n_false = int(rng.integers(0, 3))
            img, truth = sim.render(
                q, omega_deg_s=omega, t_exp_s=0.15, false_stars=n_false, add_noise=True
            )
            ra, dec = boresight_ra_dec_deg(q)
            stem = f"{i:04d}"
            meta = {
                "mode": mode,
                "seed_base": args.seed,
                "index": i,
                "q_gt": q.tolist(),
                "omega_deg_s": omega.tolist(),
                "t_exp_s": 0.15,
                "false_stars": n_false,
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
                "stars_in_fov": star_rows(cat, truth),
                "image": f"{mode}/{stem}.tif",
            }
            write_frame(dest, stem, img, meta)
            manifest["frames"].append(
                {
                    "file": f"{mode}/{stem}.tif",
                    "sidecar": f"{mode}/{stem}.json",
                    "n_stars": len(truth.cat_idx),
                    "ra_deg": ra,
                    "dec_deg": dec,
                }
            )
            print(f"  wrote {mode}/{stem}.tif  stars={len(truth.cat_idx)}  RA={ra:.2f} Dec={dec:+.2f}")

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (args.out / "README.md").write_text(
        "# Simulated demo-camera frames\n\n"
        "- Raw: `fast/*.tif`, `full/*.tif` (uint16, 12-bit DN 0–4095).\n"
        "- Ground truth: sidecar `.json` (`q_gt`, boresight RA/Dec, HR + IAU name if any).\n"
        "- Preview: `*_preview.png` (8-bit stretch for viewing only).\n\n"
        "Test one frame:\n\n"
        "```\n"
        "python demo_star_tracker.py --image data/sim_dataset/fast/0000.tif --lookup --no-show\n"
        "```\n",
        encoding="utf-8",
    )
    print("manifest", args.out / "manifest.json", "n=", len(manifest["frames"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
