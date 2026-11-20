"""Systematic Stress Degradation Curves Benchmark (CoG vs tetra3 vs CNN-Hybrid vs Auto).

Sweeps three aerospace operational stress axes on 1024x683 synthetic frames (10 seeds/point):
  1. Angular rate / motion blur omega_deg_s: [0.06, 0.30, 0.60, 1.00, 1.50, 2.00]
  2. Injected false stars / cosmic rays: [0, 5, 10, 20, 30]
  3. Stray-light glare halo peak DN: [0, 1500, 3000, 4095]

Outputs:
  data/outputs/benchmark_stress_curves.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / 'scripts') not in sys.path:
    sys.path.insert(0, str(ROOT / 'scripts'))

from benchmark_3way_centroid_e2e import _make_4way_pipeline  # noqa: E402
from benchmark_end_to_end import (  # noqa: E402
    FALSE_LOCK_LIMIT_ARCSEC,
    OUT_DIR,
    _init_cnn_template,
    _write_json_strict,
)
from src.camera import demo_camera_long_side  # noqa: E402
from src.demo_session import DemoEngine, load_pipeline_cfg  # noqa: E402
from src.metrics import evaluate  # noqa: E402
from src.quaternion import ARCSEC_PER_RAD  # noqa: E402
from src.simulator import GlareSpec, SkySimulator  # noqa: E402

STRESS_BACKENDS = ('classical', 'tetra3', 'cnn', 'auto')
SEEDS = [100 + i * 7 for i in range(10)]


def _eval_sweep_point(
    pipes: dict[str, Any],
    cam: Any,
    cat: Any,
    rad: Any,
    tol_arc: float,
    *,
    omega_deg_s: float = 0.06,
    false_stars: int = 0,
    glare_peak_dn: float = 0.0,
) -> dict[str, Any]:
    g_spec = (
        GlareSpec(kind='sun', u=0.20 * cam.width, v=0.24 * cam.height, sigma_px=180.0, peak_dn=float(glare_peak_dn))
        if glare_peak_dn > 0.0
        else None
    )
    per_be: dict[str, dict[str, Any]] = {}
    for be in STRESS_BACKENDS:
        per_be[be] = {'solved': 0, 'correct': 0, 'false_lock': 0, 'errs': [], 'lat_ms': [], 'auto_cnn_count': 0}

    for seed in SEEDS:
        sim = SkySimulator(cam, cat, radiometry=rad, seed=seed)
        q_gt = SkySimulator.generate_random_quaternion(seed)
        img, truth = sim.render(
            q_gt,
            omega_deg_s=(0.0, float(omega_deg_s), 0.0),
            t_exp_s=0.15,
            glare=g_spec,
            false_stars=int(false_stars),
            add_noise=True,
        )
        for be in STRESS_BACKENDS:
            res = pipes[be].process_frame(img)
            ev = evaluate(res, truth, tol_arc, have_gt=True, false_lock_limit_arcsec=FALSE_LOCK_LIMIT_ARCSEC)
            b = per_be[be]
            b['lat_ms'].append(float((res.timing_ms or {}).get('total_pipeline_ms', 0.0)))
            if ev['status'] == 'SOLVED':
                b['solved'] += 1
                if ev['e2e_outcome'] == 'SOLVED_CORRECT':
                    b['correct'] += 1
                if ev['e2e_outcome'] == 'FALSE_LOCK':
                    b['false_lock'] += 1
                if ev['attitude_error_arcsec'] is not None:
                    b['errs'].append(float(ev['attitude_error_arcsec']))
            if be == 'auto' and isinstance(res.quality, dict) and res.quality.get('auto_router_selected') == 'cnn':
                b['auto_cnn_count'] += 1

    out: dict[str, Any] = {}
    n_tot = len(SEEDS)
    for be, b in per_be.items():
        errs = np.asarray(b['errs'], dtype=np.float64)
        lats = np.asarray(b['lat_ms'], dtype=np.float64)
        out[be] = {
            'n_frames': n_tot,
            'n_solved': b['solved'],
            'n_correct': b['correct'],
            'n_false_lock': b['false_lock'],
            'solve_rate_pct': 100.0 * b['solved'] / n_tot,
            'true_solve_rate_pct': 100.0 * b['correct'] / n_tot,
            'median_err_arcsec': float(np.median(errs)) if errs.size else None,
            'mean_lat_ms': float(np.mean(lats)) if lats.size else None,
            'auto_cnn_escalations': b['auto_cnn_count'],
        }
    return out


def main() -> None:
    t0 = time.perf_counter()
    engine = DemoEngine(ROOT)
    cnn_tmpl, device_name, _ = _init_cnn_template()
    cam = demo_camera_long_side(1024)
    cat, _, kv = engine.stack('bsc5', 6.0, 30.5)
    tol_arc = 40.0

    pipes: dict[str, Any] = {}
    for be in STRESS_BACKENDS:
        cfg = load_pipeline_cfg('fast', ROOT)
        cfg.angular_tol_rad = float(tol_arc) / ARCSEC_PER_RAD
        cfg.attitude_error_limit_arcsec = float(tol_arc)
        cfg.centroid_backend = be
        pipes[be] = _make_4way_pipeline(cam, cat, kv, cfg, cnn_tmpl)

    # 1. Angular rate / motion blur sweep
    omega_vals = [0.06, 0.30, 0.60, 1.00, 1.50, 2.00]
    omega_sweep = []
    print('=== Sweep 1: Angular Rate omega (deg/s) ===', flush=True)
    for wv in omega_vals:
        pt = _eval_sweep_point(pipes, cam, cat, engine.radiometry, tol_arc, omega_deg_s=wv)
        omega_sweep.append({'x': wv, 'results': pt})
        print(
            f"  omega={wv:4.2f} deg/s: "
            + ' | '.join(f"{be}={pt[be]['solve_rate_pct']:5.1f}%({pt[be]['median_err_arcsec'] or -1:5.1f}\", FL={pt[be]['n_false_lock']})" for be in STRESS_BACKENDS),
            flush=True,
        )

    # 2. False stars / cosmic rays sweep
    false_vals = [0, 5, 10, 20, 30]
    false_sweep = []
    print('=== Sweep 2: Injected False Stars ===', flush=True)
    for fv in false_vals:
        pt = _eval_sweep_point(pipes, cam, cat, engine.radiometry, tol_arc, false_stars=fv)
        false_sweep.append({'x': fv, 'results': pt})
        print(
            f"  false={fv:2d}: "
            + ' | '.join(f"{be}={pt[be]['solve_rate_pct']:5.1f}%({pt[be]['median_err_arcsec'] or -1:5.1f}\", FL={pt[be]['n_false_lock']})" for be in STRESS_BACKENDS),
            flush=True,
        )

    # 3. Stray-light glare halo sweep
    glare_vals = [0, 1500, 3000, 4095]
    glare_sweep = []
    print('=== Sweep 3: Stray-Light Glare Halo (peak DN) ===', flush=True)
    for gv in glare_vals:
        pt = _eval_sweep_point(pipes, cam, cat, engine.radiometry, tol_arc, glare_peak_dn=float(gv))
        glare_sweep.append({'x': gv, 'results': pt})
        print(
            f"  glare={gv:4d} DN: "
            + ' | '.join(f"{be}={pt[be]['solve_rate_pct']:5.1f}%({pt[be]['median_err_arcsec'] or -1:5.1f}\", FL={pt[be]['n_false_lock']})" for be in STRESS_BACKENDS),
            flush=True,
        )

    payload = {
        'benchmark': 'stress_degradation_curves',
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'evaluation_scope': 'PC/laptop synthetic stress sweep (1024x683, 10 seeds/point)',
        'device': device_name,
        'n_seeds_per_point': len(SEEDS),
        'backends': list(STRESS_BACKENDS),
        'omega_sweep': omega_sweep,
        'false_stars_sweep': false_sweep,
        'glare_sweep': glare_sweep,
        'elapsed_s': round(time.perf_counter() - t0, 2),
    }
    out_path = OUT_DIR / 'benchmark_stress_curves.json'
    _write_json_strict(out_path, payload)
    print(f'[DONE] Saved stress curves to {out_path} in {payload["elapsed_s"]}s', flush=True)


if __name__ == '__main__':
    main()
