"""4-Way Scientific End-to-End Benchmark: CoG vs ESA tetra3-Threshold vs CNN-Raw vs CNN-Hybrid.

Evaluates four centroid extraction backends through the exact same StarTrackerPipeline
(Pyramid K-vector + Weighted Wahba SVD + Req-1 Post-Fit Residual Rejection) on:
  1. 500 clean 12-bit frames (data/sim_dataset/hd1024)
  2. 40 glare 12-bit frames (data/sim_dataset/hd1024_glare)
  3. 20 Earth-limb + sky-clutter + false-star stress frames (SkySimulator)
  4. 6 real-sky frames (data/real_calibrated/manifest_real_calibrated.json:
     ESA tetra3 Alt40/Alt60, Zhao MT9V022 nightsky/verification,
     UW LOST Mount St. Helens, NTNU 0006.png) + Alt40 Hipparcos V<=7.0

Outputs:
  data/outputs/benchmark_3way_comparison.json
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

from benchmark_end_to_end import (  # noqa: E402
    FALSE_LOCK_LIMIT_ARCSEC,
    MANIFEST_PATH,
    OUT_DIR,
    _aggregate_e2e_records,
    _build_custom_cfg,
    _build_truth_from_manifest,
    _extract_e2e_record,
    _init_cnn_template,
    _undistort_zhao_image,
    _write_json_strict,
)
from src.camera import CameraModel, demo_camera_long_side  # noqa: E402
from src.catalog import CatalogManager  # noqa: E402
from src.centroid_cnn import CNNCentroidDetector  # noqa: E402
from src.demo_session import (  # noqa: E402
    DemoEngine,
    load_frame,
    load_pipeline_cfg,
    theta_max_deg_for_fov,
    truth_from_sidecar,
)
from src.kvector import KVectorTable  # noqa: E402
from src.pipeline import PipelineConfig, StarTrackerPipeline  # noqa: E402
from src.quaternion import ARCSEC_PER_RAD  # noqa: E402
from src.simulator import GlareSpec, SkySimulator  # noqa: E402

BACKENDS = ('classical', 'tetra3', 'cnn_raw', 'cnn', 'auto')
BACKEND_LABELS = {
    'classical': 'CoG (Nhóm)',
    'tetra3': 'Ngưỡng kiểu tetra3 (ESA)',
    'cnn_raw': 'CNN gốc (Trilateration)',
    'cnn': 'CNN-Hybrid (MobileUNet + Local CoG)',
    'auto': 'Auto (CoG → CNN-Hybrid)',
}


def _make_4way_pipeline(
    camera: CameraModel,
    catalog: Any,
    kvector: KVectorTable,
    cfg: PipelineConfig,
    cnn_template: CNNCentroidDetector | None,
) -> StarTrackerPipeline:
    pipe = StarTrackerPipeline(camera, catalog, kvector, cfg)
    be = str(cfg.centroid_backend).lower()
    if be in ('cnn', 'cnn_raw') and cnn_template is not None and cnn_template._model is not None:
        det = CNNCentroidDetector(
            camera,
            classical=pipe.centroid_detector.classical,
            refine_subpixel=(be == 'cnn'),
        )
        det._model = cnn_template._model
        det._torch = cnn_template._torch
        det._normalize = cnn_template._normalize
        det._device = cnn_template._device
        det.device_name = cnn_template.device_name
        pipe.centroid_detector = det
    elif be == 'auto' and cnn_template is not None and cnn_template._model is not None:
        det = CNNCentroidDetector(
            camera,
            classical=pipe._base_det,
            refine_subpixel=True,
        )
        det._model = cnn_template._model
        det._torch = cnn_template._torch
        det._normalize = cnn_template._normalize
        det._device = cnn_template._device
        det.device_name = cnn_template.device_name
        pipe._auto_cnn_detector = det
    return pipe


def _run_sim_dir_suite(
    suite_name: str,
    sim_dir: Path,
    engine: DemoEngine,
    cnn_tmpl: CNNCentroidDetector | None,
    limit: int | None = None,
) -> dict[str, Any]:
    tifs = sorted(sim_dir.glob('*.tif'))
    if limit is not None:
        tifs = tifs[:limit]
    print(f'\n=== Suite: {suite_name} ({len(tifs)} frames x 4 backends) ===', flush=True)
    cat, _, kv = engine.stack('bsc5', 6.0, 30.5)
    recs: dict[str, list[dict[str, Any]]] = {be: [] for be in BACKENDS}

    first_meta = json.loads(tifs[0].with_suffix('.json').read_text(encoding='utf-8'))
    cam_m = first_meta['camera']
    cam = CameraModel(
        width=int(cam_m['width']),
        height=int(cam_m['height']),
        pixel_um=float(cam_m['pixel_um']),
        focal_mm=float(cam_m['focal_mm']),
    )
    tol_arc = 40.0
    pipes: dict[str, StarTrackerPipeline] = {}
    for be in BACKENDS:
        cfg = load_pipeline_cfg('fast', ROOT)
        cfg.angular_tol_rad = float(tol_arc) / ARCSEC_PER_RAD
        cfg.attitude_error_limit_arcsec = float(tol_arc)
        cfg.centroid_backend = be
        pipes[be] = _make_4way_pipeline(cam, cat, kv, cfg, cnn_tmpl)

    t0 = time.perf_counter()
    for idx, tif in enumerate(tifs):
        raw = load_frame(tif)
        meta = json.loads(tif.with_suffix('.json').read_text(encoding='utf-8'))
        truth = truth_from_sidecar(meta, cat)
        for be in BACKENDS:
            res = pipes[be].process_frame(raw)
            rec = _extract_e2e_record(tif.stem, res, truth, tol_arc, True)
            recs[be].append(rec)
        if (idx + 1) % 100 == 0 or (idx + 1) == len(tifs):
            el = time.perf_counter() - t0
            print(f'  [{suite_name}] {idx + 1}/{len(tifs)} done in {el:.1f}s', flush=True)

    summary = {be: _aggregate_e2e_records(recs[be]) for be in BACKENDS}
    for be in BACKENDS:
        s = summary[be]
        att_med = s['attitude_error_arcsec']['median']
        prec_m = (s['centroid_precision_micro'] or 0.0) * 100.0
        rec_m = (s['centroid_recall_micro'] or 0.0) * 100.0
        rmse5 = s['centroid_rmse_5px']
        lat = s['total_pipeline_ms']['mean']
        print(
            f"  {be:10s}: solved={s['n_solved']:3d}/{s['n_frames']:3d} correct={s['n_correct']:3d} "
            f"FL={s['n_false_lock']} med_dTh={att_med:.2f}\" Prec={prec_m:5.1f}% Rec={rec_m:5.1f}% "
            f"FP={s['centroid_false_pos_5px_total']:4d} RMSE5={rmse5:.4f}px lat={lat:.1f}ms",
            flush=True,
        )
    return {'n_frames': len(tifs), 'summary': summary}


def _run_clutter_stress_suite(
    engine: DemoEngine,
    cnn_tmpl: CNNCentroidDetector | None,
    n_frames: int = 20,
) -> dict[str, Any]:
    print(f'\n=== Suite: sim_earth_clutter ({n_frames} frames x 4 backends) ===', flush=True)
    cam = demo_camera_long_side(1024)
    cat, _, kv = engine.stack('bsc5', 6.0, 30.5)
    tol_arc = 40.0
    pipes: dict[str, StarTrackerPipeline] = {}
    for be in BACKENDS:
        cfg = load_pipeline_cfg('fast', ROOT)
        cfg.angular_tol_rad = float(tol_arc) / ARCSEC_PER_RAD
        cfg.attitude_error_limit_arcsec = float(tol_arc)
        cfg.centroid_backend = be
        pipes[be] = _make_4way_pipeline(cam, cat, kv, cfg, cnn_tmpl)

    recs: dict[str, list[dict[str, Any]]] = {be: [] for be in BACKENDS}
    glare_spec = GlareSpec(kind='earth', peak_dn=2800.0, edge_frac=0.72)
    for i in range(n_frames):
        seed = 900 + i
        sim = SkySimulator(cam, cat, radiometry=engine.radiometry, seed=seed)
        q_gt = SkySimulator.generate_random_quaternion(seed)
        raw, truth = sim.render(
            q_gt,
            omega_deg_s=(0.0, 0.06, 0.0),
            t_exp_s=0.15,
            glare=glare_spec,
            false_stars=5,
            add_noise=True,
            sky_clutter='typical',
        )
        for be in BACKENDS:
            res = pipes[be].process_frame(raw)
            recs[be].append(_extract_e2e_record(f'clutter_{seed}', res, truth, tol_arc, True))

    summary = {be: _aggregate_e2e_records(recs[be]) for be in BACKENDS}
    for be in BACKENDS:
        s = summary[be]
        att_med = s['attitude_error_arcsec']['median']
        prec_m = (s['centroid_precision_micro'] or 0.0) * 100.0
        rec_m = (s['centroid_recall_micro'] or 0.0) * 100.0
        rmse5 = s['centroid_rmse_5px']
        print(
            f"  {be:10s}: solved={s['n_solved']:2d}/{s['n_frames']:2d} correct={s['n_correct']:2d} "
            f"FL={s['n_false_lock']} med_dTh={att_med if att_med is not None else -1:.2f}\" "
            f"Prec={prec_m:5.1f}% Rec={rec_m:5.1f}% FP={s['centroid_false_pos_5px_total']:3d} "
            f"RMSE5={rmse5 if rmse5 is not None else -1:.4f}px",
            flush=True,
        )
    return {'n_frames': n_frames, 'summary': summary}


def _run_real_4way_suite(engine: DemoEngine, cnn_tmpl: CNNCentroidDetector | None) -> dict[str, Any]:
    print('\n=== Suite: real_calibrated (6 frames x 4 backends) ===', flush=True)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
    frames = manifest['frames']

    tsv_path = ROOT / 'data' / 'catalogs' / 'starcat.tsv'
    cat_hip7 = CatalogManager.filter_close_pairs(
        CatalogManager.load_hipparcos_tsv(tsv_path, max_mag=7.0, epoch_year=2026.7),
        60.0,
    )
    kv_hip7_cache: dict[float, KVectorTable] = {}

    def get_hip7_kv(tmax: float) -> KVectorTable:
        key = round(float(tmax), 2)
        if key not in kv_hip7_cache:
            kv_hip7_cache[key] = KVectorTable.build(cat_hip7, theta_min_deg=0.02, theta_max_deg=float(tmax))
        return kv_hip7_cache[key]

    cal_records: dict[str, list[dict[str, Any]]] = {be: [] for be in BACKENDS}
    alt40_hip7: dict[str, dict[str, Any]] = {}
    ntnu_counts: dict[str, int] = {}

    for entry in frames:
        rel_path = entry['path']
        full_path = ROOT / rel_path
        fname = full_path.name
        raw = np.load(full_path) if rel_path.endswith('.npy') else load_frame(full_path)
        w, h, px_um = int(entry['width']), int(entry['height']), float(entry['pixel_um'])
        has_heikkila = 'heikkila_p' in entry
        has_calibrated = (entry.get('k1') is not None) or has_heikkila

        if not has_calibrated:
            # NTNU 0006.png uncalibrated wide-angle clutter count check (avoid 60s Pyramid stall)
            cam_nom = CameraModel(width=w, height=h, pixel_um=px_um, focal_mm=float(entry['focal_mm_nominal']))
            cat_n, _, kv_n = engine.stack('bsc5', 6.0, theta_max_deg_for_fov(float(cam_nom.fov_deg[2])))
            for be in BACKENDS:
                cfg_n, _ = _build_custom_cfg(cam_nom, be, calibrated=False)
                pipe_n = _make_4way_pipeline(cam_nom, cat_n, kv_n, cfg_n, cnn_tmpl)
                cents = pipe_n.centroid_detector.detect(raw)
                ntnu_counts[be] = int(len(cents.uv))
            print(f'  [Uncal Stress] {fname}: detected counts = {ntnu_counts}', flush=True)
            continue

        img_cal = (
            _undistort_zhao_image(raw, entry['heikkila_p'], entry['calibrated_cx'], entry['calibrated_cy'])
            if has_heikkila
            else raw
        )
        cam_cal = CameraModel(
            width=w,
            height=h,
            pixel_um=px_um,
            focal_mm=float(entry['focal_mm']),
            k1=float(entry.get('k1') or 0.0),
            k2=float(entry.get('k2') or 0.0),
            cx=entry.get('calibrated_cx'),
            cy=entry.get('calibrated_cy'),
        )
        truth_cal, have_gt = _build_truth_from_manifest(entry, undistort_zhao=has_heikkila)
        tmax_cal = theta_max_deg_for_fov(float(cam_cal.fov_deg[2]))
        cat_bsc, _, kv_bsc = engine.stack('bsc5', 6.0, tmax_cal)

        for be in BACKENDS:
            cfg_cal, tol_cal = _build_custom_cfg(cam_cal, be, calibrated=True)
            pipe = _make_4way_pipeline(cam_cal, cat_bsc, kv_bsc, cfg_cal, cnn_tmpl)
            res = pipe.process_frame(img_cal)
            rec = _extract_e2e_record(
                fname,
                res,
                truth_cal,
                tol_cal,
                have_gt,
                extra={'path': rel_path, 'dataset_group': entry['dataset_group'], 'catalog': 'bsc5_v6.0'},
            )
            cal_records[be].append(rec)
            err_s = f"{rec['attitude_error_arcsec']:.2f}\"" if rec['attitude_error_arcsec'] is not None else 'n/a'
            rm5 = f"{rec['centroid_rmse_5px']:.3f}px" if rec['centroid_rmse_5px'] is not None else 'n/a'
            print(
                f"  [Cal/BSC5] {fname:36s} {be:9s}: {rec['status']:6s} "
                f"dTh={err_s:8s} valid={rec['n_valid_pairs']}/{rec['n_detected']} "
                f"RMSE5={rm5} t={rec['total_pipeline_ms']:.1f}ms",
                flush=True,
            )

        if 'Alt40' in fname:
            kv_h7 = get_hip7_kv(tmax_cal)
            for be in BACKENDS:
                cfg_h, tol_h = _build_custom_cfg(cam_cal, be, calibrated=True)
                pipe = _make_4way_pipeline(cam_cal, cat_hip7, kv_h7, cfg_h, cnn_tmpl)
                res = pipe.process_frame(img_cal)
                rec = _extract_e2e_record(
                    fname,
                    res,
                    truth_cal,
                    tol_h,
                    True,
                    extra={'path': rel_path, 'dataset_group': entry['dataset_group'], 'catalog': 'hipparcos_v7.0'},
                )
                alt40_hip7[be] = rec
                err_s = f"{rec['attitude_error_arcsec']:.2f}\"" if rec['attitude_error_arcsec'] is not None else 'n/a'
                print(
                    f"  [Cal/Hip7] {fname:36s} {be:9s}: {rec['status']:6s} "
                    f"dTh={err_s:8s} valid={rec['n_valid_pairs']}/{rec['n_detected']} t={rec['total_pipeline_ms']:.1f}ms",
                    flush=True,
                )

    return {
        'calibrated_bsc5_summary': {be: _aggregate_e2e_records(cal_records[be]) for be in BACKENDS},
        'calibrated_bsc5_frames': cal_records,
        'alt40_hipparcos_v7': alt40_hip7,
        'ntnu_0006_detected_counts': ntnu_counts,
    }


def main() -> None:
    t_all = time.perf_counter()
    engine = DemoEngine(ROOT)
    cnn_tmpl, device_name, cnn_err = _init_cnn_template()
    if cnn_err:
        print(f'[WARN] CNN unavailable: {cnn_err}', flush=True)

    real_data = _run_real_4way_suite(engine, cnn_tmpl)
    glare_data = _run_sim_dir_suite('sim_glare', ROOT / 'data' / 'sim_dataset' / 'hd1024_glare', engine, cnn_tmpl)
    clutter_data = _run_clutter_stress_suite(engine, cnn_tmpl, n_frames=20)
    clean_data = _run_sim_dir_suite('sim_hd1024', ROOT / 'data' / 'sim_dataset' / 'hd1024', engine, cnn_tmpl)

    payload = {
        'benchmark': '4way_centroid_e2e_comparison',
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'evaluation_scope': 'PC/laptop benchmark (not flight-qualified spacecraft hardware)',
        'device': device_name,
        'false_lock_limit_arcsec': FALSE_LOCK_LIMIT_ARCSEC,
        'backends': BACKEND_LABELS,
        'sim_hd1024': clean_data,
        'sim_glare': glare_data,
        'sim_earth_clutter': clutter_data,
        'real_calibrated': real_data,
        'elapsed_s': round(time.perf_counter() - t_all, 2),
    }
    out_path = OUT_DIR / 'benchmark_3way_comparison.json'
    _write_json_strict(out_path, payload)
    print(f'\n[DONE] Saved 4-way audited benchmark to {out_path} in {payload["elapsed_s"]}s', flush=True)


if __name__ == '__main__':
    main()
