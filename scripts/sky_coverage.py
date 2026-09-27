#!/usr/bin/env python3
"""Histogram of catalog stars per demo-camera FOV over random attitudes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.camera import demo_camera  # noqa: E402
from src.catalog import CatalogManager  # noqa: E402
from src.quaternion import random_quaternion, to_dcm  # noqa: E402


def count_in_fov(catalog, camera, n_dir: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    counts = np.empty(n_dir, dtype=np.int32)
    vecs = catalog.vectors
    for i in range(n_dir):
        a = to_dcm(random_quaternion(rng))
        cam_vecs = (a @ vecs.T).T
        _uv, in_fov = camera.project(cam_vecs)
        counts[i] = int(np.count_nonzero(in_fov))
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-dir", type=int, default=2000)
    parser.add_argument("--max-mag", type=float, default=6.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--catalog", choices=["bsc5", "synthetic"], default="bsc5")
    args = parser.parse_args()

    camera = demo_camera()
    if args.catalog == "bsc5":
        bsc5 = ROOT / "data" / "catalogs" / "BSC5"
        if not bsc5.exists():
            CatalogManager.fetch_bsc5(bsc5)
        cat = CatalogManager.load_bsc5(bsc5, max_mag=args.max_mag, epoch_year=2026.7)
    else:
        cat = CatalogManager.synthetic(3500, args.max_mag, seed=123)

    counts = count_in_fov(cat, camera, args.n_dir, args.seed)
    summary = {
        "catalog": cat.source,
        "n_stars": cat.num_stars,
        "max_mag": args.max_mag,
        "n_dir": args.n_dir,
        "mean": float(np.mean(counts)),
        "median": float(np.median(counts)),
        "p5": float(np.percentile(counts, 5)),
        "p95": float(np.percentile(counts, 95)),
        "min": int(np.min(counts)),
        "max": int(np.max(counts)),
        "frac_lt_4": float(np.mean(counts < 4)),
        "frac_lt_6": float(np.mean(counts < 6)),
    }
    out = ROOT / "data" / "outputs" / f"sky_coverage_{cat.source}_v{args.max_mag}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
