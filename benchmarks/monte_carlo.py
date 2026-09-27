#!/usr/bin/env python3
"""Monte Carlo lost-in-space solve rate and attitude error vs quaternion GT."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.camera import demo_camera
from src.catalog import CatalogManager
from src.kvector import build_or_load
from src.pipeline import PipelineConfig, StarTrackerPipeline
from src.quaternion import angular_error_arcsec, axis_error_arcsec, random_quaternion
from src.simulator import Radiometry, SkySimulator


def load_cfg(mode: str) -> PipelineConfig:
    blob = json.loads((ROOT / "config" / "pipeline_default.json").read_text(encoding="utf-8"))
    return PipelineConfig.from_dict(blob[mode])


def run_mc(num_trials: int, mode: str, seed: int = 0, catalog_kind: str = "synthetic") -> dict:
    cam = demo_camera()
    if mode == "fast":
        cam = cam.downscaled(4)
    cache = ROOT / "data" / "catalogs"
    if catalog_kind == "bsc5" and (cache / "BSC5").exists():
        cat = CatalogManager.load_bsc5(cache / "BSC5", max_mag=6.0, epoch_year=2026.7)
        cat = CatalogManager.filter_close_pairs(cat, 60.0)
    else:
        cat = CatalogManager.synthetic(3500, 6.0, seed=123)
    kv = build_or_load(cat, cache)
    cfg = load_cfg(mode)
    pipe = StarTrackerPipeline(cam, cat, kv, cfg)
    sim = SkySimulator(
        cam, cat, radiometry=Radiometry(hot_pixel_frac=0.0, cosmic_rate_per_frame=0.0), seed=seed
    )
    rng = np.random.default_rng(seed)
    successes = 0
    usable = 0
    errors = []
    axes = []
    latencies = []
    n_fov = []
    ra_deg = []
    dec_deg = []
    t_cent = []
    t_id = []
    t_att = []
    limit = cfg.attitude_error_limit_arcsec

    for trial in range(1, num_trials + 1):
        q_gt = random_quaternion(rng)
        omega = rng.normal(size=3)
        omega = omega / np.linalg.norm(omega) * 0.06
        n_false = int(rng.integers(0, 3))
        img, truth = sim.render(
            q_gt, omega_deg_s=omega, t_exp_s=0.15, false_stars=n_false, add_noise=True
        )
        if len(truth.cat_idx) < 4:
            continue
        usable += 1
        t0 = time.perf_counter()
        res = pipe.process_frame(img)
        dt = (time.perf_counter() - t0) * 1000.0
        a = truth.q_gt  # unused; sky position from DCM z-row
        from src.quaternion import to_dcm

        r_cam_z = to_dcm(q_gt).T @ np.array([0.0, 0.0, 1.0])
        ra_deg.append(float(np.degrees(np.mod(np.arctan2(r_cam_z[1], r_cam_z[0]), 2 * np.pi))))
        dec_deg.append(float(np.degrees(np.arcsin(np.clip(r_cam_z[2], -1, 1)))))
        n_fov.append(int(len(truth.cat_idx)))
        if res.success:
            err = angular_error_arcsec(res.q, q_gt)
            if err < limit:
                successes += 1
            errors.append(err)
            axes.append(axis_error_arcsec(res.q, q_gt))
            latencies.append(dt)
            t_cent.append(res.timing_ms.get("centroiding_ms", 0.0))
            t_id.append(res.timing_ms.get("identification_ms", 0.0))
            t_att.append(res.timing_ms.get("attitude_ms", 0.0))
        if trial % 10 == 0 or trial == num_trials:
            rate = 100.0 * successes / max(trial, 1)
            print(
                f"    Trial {trial:4d}/{num_trials}: solve-within-limit = {rate:.1f}%",
                flush=True,
            )

    errors_a = np.array(errors, dtype=np.float64) if errors else np.array([])
    axes_a = np.array(axes, dtype=np.float64) if axes else np.empty((0, 3))
    summary = {
        "mode": mode,
        "trials": num_trials,
        "usable_fov": usable,
        "successes_within_limit": successes,
        "solve_rate_pct": 100.0 * successes / max(num_trials, 1),
        "limit_arcsec": limit,
        "mean_error_arcsec": float(np.mean(errors_a)) if errors_a.size else None,
        "median_error_arcsec": float(np.median(errors_a)) if errors_a.size else None,
        "p95_error_arcsec": float(np.percentile(errors_a, 95)) if errors_a.size else None,
        "max_error_arcsec": float(np.max(errors_a)) if errors_a.size else None,
        "rms_error_arcsec": float(np.sqrt(np.mean(errors_a**2))) if errors_a.size else None,
        "mean_axis_arcsec": np.mean(np.abs(axes_a), axis=0).tolist() if axes_a.size else None,
        "mean_latency_ms": float(np.mean(latencies)) if latencies else None,
        "median_centroid_ms": float(np.median(t_cent)) if t_cent else None,
        "median_id_ms": float(np.median(t_id)) if t_id else None,
        "median_wahba_ms": float(np.median(t_att)) if t_att else None,
        "n_fov_mean": float(np.mean(n_fov)) if n_fov else None,
        "ra_deg": ra_deg,
        "dec_deg": dec_deg,
        "errors_arcsec": errors_a.tolist(),
        "n_fov": n_fov,
        "latencies_ms": latencies,
        "catalog": cat.source,
        "n_catalog": cat.num_stars,
    }
    return summary


def save_report(summary: dict, out_dir: Path) -> None:
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    n = summary["trials"]
    mode = summary["mode"]
    json_path = out_dir / f"mc_{mode}_{n}.json"
    slim = {k: v for k, v in summary.items() if k not in ("ra_deg", "dec_deg", "errors_arcsec", "n_fov", "latencies_ms")}
    json_path.write_text(json.dumps(slim, indent=2), encoding="utf-8")
    errors = np.array(summary["errors_arcsec"], dtype=np.float64)
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), facecolor="#0F172A")
    ax = axes[0, 0]
    ax.set_facecolor("#1E293B")
    if errors.size:
        ax.hist(errors, bins=30, color="#38BDF8", edgecolor="white")
    ax.set_title("Attitude error (arcsec)", color="white")
    ax.tick_params(colors="#94A3B8")
    ax = axes[0, 1]
    ax.set_facecolor("#1E293B")
    if errors.size:
        s = np.sort(errors)
        ax.plot(s, np.linspace(0, 1, len(s)), color="#4ADE80")
    ax.set_title("CDF", color="white")
    ax.tick_params(colors="#94A3B8")
    ax = axes[1, 0]
    ax.set_facecolor("#1E293B")
    if summary["n_fov"]:
        ax.scatter(summary["n_fov"][: len(errors)], errors, s=8, c="#FBBF24")
    ax.set_title("Error vs stars in FOV", color="white")
    ax.tick_params(colors="#94A3B8")
    ax = axes[1, 1]
    ax.set_facecolor("#1E293B")
    if summary["ra_deg"]:
        ok = np.zeros(len(summary["ra_deg"]), dtype=bool)
        # approximate: first `successes` not aligned; color by whether we have error entry
        ax.scatter(summary["ra_deg"], summary["dec_deg"], s=8, c="#94A3B8")
    ax.set_title("Boresight RA/Dec sample", color="white")
    ax.tick_params(colors="#94A3B8")
    fig.tight_layout()
    png = out_dir / f"mc_{mode}_{n}.png"
    fig.savefig(png, dpi=120, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"wrote {json_path} and {png}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--trials", type=int, default=100)
    p.add_argument("--mode", choices=["fast", "full"], default="fast")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--catalog", choices=["synthetic", "bsc5"], default="synthetic")
    args = p.parse_args()
    print(f"[*] Monte Carlo {args.trials} trials  mode={args.mode}", flush=True)
    summary = run_mc(args.trials, args.mode, seed=args.seed, catalog_kind=args.catalog)
    print("=" * 50)
    print(json.dumps({k: v for k, v in summary.items() if not isinstance(v, list)}, indent=2))
    save_report(summary, ROOT / "data" / "outputs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
