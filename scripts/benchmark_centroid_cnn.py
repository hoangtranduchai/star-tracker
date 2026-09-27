#!/usr/bin/env python3
"""Small centroid benchmark: classical CoG vs Zhao et al. public MobileUNet.

Generates ~N FAST synthetic frames (demo camera 4×4 bin), compares centroid
error in pixels against simulator ground-truth UV, and writes a JSON summary.
Supports --resume via incremental checkpoint. Does not retrain.
"""

from __future__ import annotations

import argparse
import gc
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from generate_sim_dataset import load_radiometry  # noqa: E402
from src.camera import demo_camera  # noqa: E402
from src.catalog import CatalogManager  # noqa: E402
from src.centroid import CentroidDetector  # noqa: E402
from src.centroid_cnn import (  # noqa: E402
    CNNCentroidDetector,
    match_centroid_rmse,
    weights_available,
)
from src.quaternion import looking_at, random_quaternion  # noqa: E402
from src.simulator import SkySimulator  # noqa: E402


def load_catalog():
    path = ROOT / "data" / "catalogs" / "bsc5_v6.0.npz"
    if path.is_file():
        return CatalogManager.load_npz(path)
    bsc5 = ROOT / "data" / "catalogs" / "BSC5"
    if not bsc5.is_file():
        CatalogManager.fetch_bsc5(bsc5)
    cat = CatalogManager.filter_close_pairs(
        CatalogManager.load_bsc5(bsc5, max_mag=6.0, epoch_year=2026.7), 60.0
    )
    CatalogManager.save_npz(cat, path)
    return cat


def _summarize(rmses: list[float | None], n_matched: list[int], n_gt: list[int], times_ms: list[float]) -> dict:
    ok = [float(x) for x in rmses if x is not None]
    return {
        "n_frames": len(rmses),
        "n_frames_with_matches": len(ok),
        "rmse_px_mean": float(np.mean(ok)) if ok else None,
        "rmse_px_median": float(np.median(ok)) if ok else None,
        "rmse_px_p90": float(np.percentile(ok, 90)) if ok else None,
        "matched_stars_total": int(sum(n_matched)),
        "gt_stars_total": int(sum(n_gt)),
        "time_ms_mean": float(np.mean(times_ms)) if times_ms else None,
        "time_ms_median": float(np.median(times_ms)) if times_ms else None,
    }


def _summary_from_rows(rows: list[dict], meta: dict) -> dict:
    cl_rmse = [r["classical"].get("rmse_px") for r in rows]
    cl_matched = [int(r["classical"].get("n_matched") or 0) for r in rows]
    cl_gt = [int(r["classical"].get("n_gt") or 0) for r in rows]
    cl_t = [float(r["classical"].get("time_ms") or 0.0) for r in rows]
    has_cnn = any("cnn" in r for r in rows)
    summary = {
        "paper": meta["paper"],
        "camera": meta["camera"],
        "n_requested": meta["n_requested"],
        "seed": meta["seed"],
        "match_radius_px": meta["match_radius_px"],
        "wall_s": meta.get("wall_s"),
        "classical": _summarize(cl_rmse, cl_matched, cl_gt, cl_t),
        "institution": meta["institution"],
    }
    if has_cnn:
        cnn_rows = [r["cnn"] for r in rows if "cnn" in r]
        summary["cnn"] = _summarize(
            [x.get("rmse_px") for x in cnn_rows],
            [int(x.get("n_matched") or 0) for x in cnn_rows],
            [int(x.get("n_gt") or 0) for x in cnn_rows],
            [float(x.get("time_ms") or 0.0) for x in cnn_rows],
        )
    else:
        summary["cnn"] = {"status": "chưa kiểm được", "error": meta.get("cnn_error")}
    return summary


def main() -> int:
    p = argparse.ArgumentParser(description="Benchmark classical vs CNN centroids")
    p.add_argument("--n", type=int, default=500, help="Number of FAST frames")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--out", type=Path, default=ROOT / "data" / "outputs" / "centroid_benchmark_500.json")
    p.add_argument("--ckpt", type=Path, default=None, help="Checkpoint path (default: out.ckpt.json)")
    p.add_argument("--match-radius-px", type=float, default=5.0)
    p.add_argument("--skip-cnn", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--save-every", type=int, default=25)
    args = p.parse_args()
    ckpt_path = args.ckpt or args.out.with_suffix(".ckpt.json")

    cam = demo_camera().downscaled(4)
    cat = load_catalog()
    rad = load_radiometry()
    sim = SkySimulator(cam, cat, rad, seed=int(args.seed))
    n_cat = int(len(cat.vectors))

    classical = CentroidDetector(cam)
    cnn = None
    cnn_error = None
    if not args.skip_cnn:
        if not weights_available():
            cnn_error = "chưa kiểm được: thiếu file trọng số công khai MobileUNet_B10_50.pt"
        else:
            try:
                cnn = CNNCentroidDetector(cam, classical=classical)
                _ = cnn.detect(np.zeros((cam.height, cam.width), dtype=np.uint16))
            except Exception as exc:  # noqa: BLE001
                cnn_error = f"chưa kiểm được: {type(exc).__name__}: {exc}"
                cnn = None

    rows: list[dict] = []
    start_i = 0
    t0 = time.perf_counter()
    if args.resume and ckpt_path.is_file():
        prev = json.loads(ckpt_path.read_text(encoding="utf-8"))
        rows = list(prev.get("frames") or [])
        start_i = len(rows)
        print(f"[*] resume from frame {start_i}", flush=True)

    meta = {
        "paper": {
            "title": "Real-Time Convolutional Neural Network-Based Star Detection and Centroiding Method for CubeSat Star Tracker",
            "arxiv": "2404.19108",
            "weights": "third_party/cnn_star_centroid/saved_models/MobileUNet_B10_50.pt",
            "source": "https://github.com/HongruiZhao/CNNStarDetectCentroid",
        },
        "camera": {
            "mode": "fast",
            "width": cam.width,
            "height": cam.height,
            "pixel_um": cam.pixel_um,
            "focal_mm": cam.focal_mm,
            "note": "APS-C class still camera demo, 4x4 bin. No sensor/lens brand.",
        },
        "n_requested": int(args.n),
        "seed": int(args.seed),
        "match_radius_px": float(args.match_radius_px),
        "institution": {
            "school": "Trường Đại học Bách khoa, Đại học Đà Nẵng",
            "faculty": "Khoa Công nghệ thông tin",
        },
        "cnn_error": cnn_error,
    }

    rng = np.random.default_rng(args.seed)
    # Advance RNG to the resume point so attitudes stay reproducible.
    for _ in range(start_i):
        if (_ % 5) == 0:
            _ = int(rng.integers(0, n_cat))
        else:
            _ = random_quaternion(rng)

    for i in range(start_i, int(args.n)):
        if i % 5 == 0:
            idx = int(rng.integers(0, n_cat))
            q = looking_at(cat.vectors[idx])
        else:
            q = random_quaternion(rng)
        omega = np.zeros(3) if (i % 4) else np.array([0.0, 0.06, 0.0])
        noise = (i % 7) != 0
        sim.rng = np.random.default_rng(int(args.seed) * 1_000_003 + i)
        img, truth = sim.render(q, omega_deg_s=omega, t_exp_s=0.15, add_noise=noise, false_stars=0)
        gt = np.asarray(truth.uv_mid, dtype=np.float64)

        t1 = time.perf_counter()
        c_cl = classical.detect(img)
        cl_ms = (time.perf_counter() - t1) * 1000.0
        m_cl = match_centroid_rmse(c_cl.uv, gt, match_radius_px=args.match_radius_px)
        row = {
            "i": i,
            "n_gt": int(len(gt)),
            "classical": {**m_cl, "time_ms": cl_ms, "n_pred": int(len(c_cl.uv))},
        }

        if cnn is not None:
            t2 = time.perf_counter()
            c_nn = cnn.detect(img)
            nn_ms = (time.perf_counter() - t2) * 1000.0
            m_nn = match_centroid_rmse(c_nn.uv, gt, match_radius_px=args.match_radius_px)
            row["cnn"] = {
                **m_nn,
                "time_ms": nn_ms,
                "n_pred": int(len(c_nn.uv)),
                "backend": getattr(cnn, "last_backend", None),
                "error": getattr(cnn, "last_error", None),
            }
            del c_nn
        rows.append(row)
        del img, truth, c_cl, gt
        if (i + 1) % 10 == 0:
            gc.collect()

        if (i + 1) % int(args.save_every) == 0 or (i + 1) == int(args.n) or i == start_i:
            meta["wall_s"] = float(time.perf_counter() - t0)
            payload = {"summary": _summary_from_rows(rows, meta), "frames": rows}
            ckpt_path.parent.mkdir(parents=True, exist_ok=True)
            ckpt_path.write_text(json.dumps(payload), encoding="utf-8")
            print(f"  frame {i+1}/{args.n}  ckpt={ckpt_path.name}", flush=True)

    meta["wall_s"] = float(time.perf_counter() - t0)
    summary = _summary_from_rows(rows, meta)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"summary": summary, "frames": rows}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"[*] wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
