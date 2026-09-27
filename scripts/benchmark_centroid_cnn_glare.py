#!/usr/bin/env python3
"""Small hd1024-class set with strong sun/stray glare: classical vs CNN centroids.

Does not retrain. Does not touch centroid_benchmark_hd1024_thr2.json.
Writes frames under data/sim_dataset/hd1024_glare and a JSON under data/outputs/.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from generate_sim_dataset import load_radiometry, star_rows, write_frame  # noqa: E402
from src.camera import demo_camera_long_side  # noqa: E402
from src.catalog import CatalogManager  # noqa: E402
from src.centroid import CentroidDetector  # noqa: E402
from src.centroid_cnn import (  # noqa: E402
    CNNCentroidDetector,
    match_centroid_rmse,
    weights_available,
)
from src.quaternion import boresight_ra_dec_deg, format_dec_dms, format_ra_hms, looking_at, random_quaternion  # noqa: E402
from src.simulator import GlareSpec, SkySimulator  # noqa: E402


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


def strong_sun_glare(cam) -> GlareSpec:
    """Wide stray-light bloom (baffle not modeled); photosphere 0.5°."""
    uw, vh = 0.18 * cam.width, 0.22 * cam.height
    sig = max(40.0, 0.28 * min(cam.width, cam.height))
    return GlareSpec(kind="sun", u=uw, v=vh, sigma_px=sig, peak_dn=4095.0)


def _summarize(rmses, n_matched, n_gt, times_ms) -> dict:
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
        "time_s_per_frame_mean": float(np.mean(times_ms) / 1000.0) if times_ms else None,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Strong-glare hd1024 classical/CNN centroid compare")
    p.add_argument("--n", type=int, default=40)
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--long-side", type=int, default=1024)
    p.add_argument("--out-dir", type=Path, default=ROOT / "data" / "sim_dataset" / "hd1024_glare")
    p.add_argument(
        "--out-json",
        type=Path,
        default=ROOT / "data" / "outputs" / "centroid_benchmark_hd1024_glare_sun_strong.json",
    )
    p.add_argument("--match-radius-px", type=float, default=5.0)
    p.add_argument("--skip-write", action="store_true")
    p.add_argument("--skip-cnn", action="store_true")
    args = p.parse_args()

    cam = demo_camera_long_side(args.long_side)
    cat = load_catalog()
    rad = load_radiometry()
    sim = SkySimulator(cam, cat, rad)
    glare = strong_sun_glare(cam)
    n_cat = int(len(cat.vectors))
    dest = Path(args.out_dir)
    dest.mkdir(parents=True, exist_ok=True)

    classical = CentroidDetector(cam)
    cnn = None
    cnn_error = None
    device_name = "cpu"
    if not args.skip_cnn:
        if not weights_available():
            cnn_error = "chưa kiểm được: thiếu file trọng số công khai MobileUNet_B10_50.pt"
        else:
            try:
                import torch

                print(
                    f"[*] torch={torch.__version__} cuda_available={torch.cuda.is_available()} "
                    f"cuda={torch.version.cuda}",
                    flush=True,
                )
                if torch.cuda.is_available():
                    print(f"[*] device0={torch.cuda.get_device_name(0)}", flush=True)
                cnn = CNNCentroidDetector(cam, classical=classical)
                _ = cnn.detect(np.zeros((cam.height, cam.width), dtype=np.uint16))
                device_name = getattr(cnn, "device_name", None) or cnn._device or "cpu"
                print(f"[*] CNN backend device={cnn._device} name={device_name}", flush=True)
            except Exception as exc:  # noqa: BLE001
                cnn_error = f"chưa kiểm được: {type(exc).__name__}: {exc}"
                cnn = None

    rng = np.random.default_rng(args.seed)
    rows = []
    cl_rmse, cnn_rmse = [], []
    cl_matched, cnn_matched = [], []
    cl_gt, cnn_gt = [], []
    cl_t, cnn_t = [], []
    gen_s = 0.0
    infer_s = 0.0

    t0 = time.perf_counter()
    for i in range(int(args.n)):
        stem = f"{i:04d}"
        tif = dest / f"{stem}.tif"
        side = dest / f"{stem}.json"

        if args.skip_write and tif.is_file() and side.is_file():
            img = cv2.imread(str(tif), cv2.IMREAD_UNCHANGED)
            if img is None:
                raise RuntimeError(f"failed to read {tif}")
            meta = json.loads(side.read_text(encoding="utf-8"))
            gt = np.asarray([[s["u_px"], s["v_px"]] for s in meta.get("stars_in_fov", [])], dtype=np.float64)
            if gt.size == 0:
                gt = np.empty((0, 2), dtype=np.float64)
        else:
            tg0 = time.perf_counter()
            if i % 5 == 0:
                idx = int(rng.integers(0, n_cat))
                q = looking_at(cat.vectors[idx])
            else:
                q = random_quaternion(rng)
            omega = np.zeros(3) if (i % 4) else np.array([0.0, 0.06, 0.0])
            noise = (i % 7) != 0
            sim.rng = np.random.default_rng(int(args.seed) * 1_000_003 + i)
            img, truth = sim.render(
                q,
                omega_deg_s=omega,
                t_exp_s=0.15,
                add_noise=noise,
                false_stars=0,
                glare=glare,
            )
            gt = np.asarray(truth.uv_mid, dtype=np.float64)
            ra, dec = boresight_ra_dec_deg(q)
            meta = {
                "mode": "hd1024_glare",
                "glare": {
                    "kind": "sun",
                    "preset": "sun_strong",
                    "u": glare.u,
                    "v": glare.v,
                    "sigma_px": glare.sigma_px,
                    "peak_dn": glare.peak_dn,
                    "diam_deg": glare.diam_deg,
                },
                "seed_base": args.seed,
                "index": i,
                "q_gt": q.tolist(),
                "omega_deg_s": omega.tolist(),
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
                    "note": "Demo FOV class: long side ~1024, 50 mm, pixel scaled. No sensor/lens brand.",
                },
                "stars_in_fov": star_rows(cat, truth),
                "image": f"hd1024_glare/{stem}.tif",
            }
            write_frame(dest, stem, img, meta)
            gen_s += time.perf_counter() - tg0

        ti0 = time.perf_counter()
        t1 = time.perf_counter()
        c_cl = classical.detect(img)
        cl_ms = (time.perf_counter() - t1) * 1000.0
        m_cl = match_centroid_rmse(c_cl.uv, gt, match_radius_px=args.match_radius_px)
        cl_rmse.append(m_cl["rmse_px"])
        cl_matched.append(int(m_cl["n_matched"]))
        cl_gt.append(int(m_cl["n_gt"]))
        cl_t.append(cl_ms)

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
            cnn_rmse.append(m_nn["rmse_px"])
            cnn_matched.append(int(m_nn["n_matched"]))
            cnn_gt.append(int(m_nn["n_gt"]))
            cnn_t.append(nn_ms)
            row["cnn"] = {
                **m_nn,
                "time_ms": nn_ms,
                "n_pred": int(len(c_nn.uv)),
                "backend": getattr(cnn, "last_backend", None),
                "error": getattr(cnn, "last_error", None),
            }
        infer_s += time.perf_counter() - ti0
        rows.append(row)
        if (i + 1) % 10 == 0 or i == 0:
            print(f"  frame {i+1}/{args.n}", flush=True)

    cl_sum = _summarize(cl_rmse, cl_matched, cl_gt, cl_t)
    nn_sum = (
        _summarize(cnn_rmse, cnn_matched, cnn_gt, cnn_t)
        if cnn is not None
        else {"status": "chưa kiểm được", "error": cnn_error}
    )

    cnn_better = False
    verdict = "chưa kiểm được"
    if cnn is not None and cl_sum["rmse_px_mean"] is not None and nn_sum.get("rmse_px_mean") is not None:
        cnn_better = float(nn_sum["rmse_px_mean"]) < float(cl_sum["rmse_px_mean"])
        if cnn_better:
            verdict = (
                f"Dưới lóa mạnh (sun_strong), CNN tốt hơn CoG về RMSE "
                f"({nn_sum['rmse_px_mean']:.4f} < {cl_sum['rmse_px_mean']:.4f} px)."
            )
        else:
            verdict = (
                f"Dưới lóa mạnh (sun_strong), CNN không tốt hơn CoG về RMSE "
                f"(CoG {cl_sum['rmse_px_mean']:.4f} vs CNN {nn_sum['rmse_px_mean']:.4f} px)."
            )

    summary = {
        "camera": {
            "mode": "hd1024_glare",
            "width": cam.width,
            "height": cam.height,
            "pixel_um": cam.pixel_um,
            "focal_mm": cam.focal_mm,
            "note": "APS-C class still camera demo, long side ~1024. No sensor/lens brand.",
        },
        "glare_preset": "sun_strong",
        "glare": {
            "kind": "sun",
            "u": glare.u,
            "v": glare.v,
            "sigma_px": glare.sigma_px,
            "peak_dn": glare.peak_dn,
            "diam_deg": glare.diam_deg,
        },
        "dataset_dir": str(dest.relative_to(ROOT)).replace("\\", "/"),
        "n_frames_written": int(args.n) if not args.skip_write else int(len(list(dest.glob("*.tif")))),
        "device": device_name,
        "cnn_torch_device": getattr(cnn, "_device", None) if cnn is not None else None,
        "n_requested": int(args.n),
        "seed": int(args.seed),
        "match_radius_px": float(args.match_radius_px),
        "wall_s": float(time.perf_counter() - t0),
        "generate_s": float(gen_s),
        "infer_s": float(infer_s),
        "classical": cl_sum,
        "cnn": nn_sum,
        "cnn_better_under_glare": cnn_better,
        "verdict_vi": verdict,
        "distance_map_threshold": 2.0,
        "weights": "third_party/cnn_star_centroid/saved_models/MobileUNet_B10_50.pt",
        "note": "Small glare stress set only. Does not replace clean-set thr2 numbers.",
        "institution": {
            "school": "Trường Đại học Bách khoa, Đại học Đà Nẵng",
            "faculty": "Khoa Công nghệ thông tin",
        },
    }
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    payload = {"summary": summary, "frames": rows}
    args.out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (dest / "manifest_hd1024_glare.json").write_text(
        json.dumps(
            {
                "mode": "hd1024_glare",
                "glare_preset": "sun_strong",
                "n": int(args.n),
                "camera": summary["camera"],
                "frames": [f"{i:04d}.tif" for i in range(int(args.n))],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    # Avoid Windows console cp1252 crashing on Vietnamese verdict text.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"[*] wrote {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
