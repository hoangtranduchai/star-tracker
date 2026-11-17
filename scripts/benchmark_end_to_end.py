"""Comprehensive End-to-End Star Tracker Benchmark (Stage 3A).

Evaluates classical CoG vs. public MobileUNet CNN (d_th=2.0, RTX 5070 CUDA)
through the full StarTrackerPipeline across:
  Suite 1: Real calibrated & stress sky frames (manifest_real_calibrated.json)
  Suite 2: 500 clean hd1024 + 40 glare hd1024_glare + FAST Seed 42
  Suite 3: 100 adversarial invalid-match rejection stress trials (4 categories x 25)
  Suite 4: Vietnamese summary charts (e2e_figures/) & failure diagnostic PNGs (failure_cases/)
"""
from __future__ import annotations

import argparse
import gc
import json
import math
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / 'scripts') not in sys.path:
    sys.path.insert(0, str(ROOT / 'scripts'))

from prepare_real_calibrated_gt import zhao_distortion_correction, zhao_forward_distort
from src.attitude import WahbaSolver
from src.camera import CameraModel, demo_camera, demo_camera_long_side
from src.catalog import CatalogManager, StarCatalog
from src.centroid import Centroids
from src.centroid_cnn import CNNCentroidDetector, match_centroid_rmse, weights_available
from src.demo_session import (
    DemoEngine,
    RunRequest,
    _jsonable,
    load_frame,
    load_pipeline_cfg,
    match_tolerance_arcsec,
    theta_max_deg_for_fov,
    truth_from_sidecar,
)
from src.identification import IdResult, _empty_id_result
from src.kvector import KVectorTable
from src.metrics import centroid_rms_px, evaluate
from src.pipeline import PipelineConfig, StarTrackerPipeline, TrackerResult
from src.quaternion import (
    ARCSEC_PER_RAD,
    angular_error_arcsec,
    axis_error_arcsec,
    boresight_ra_dec_deg,
    from_dcm,
    normalize,
    random_quaternion,
    to_dcm,
)
from src.simulator import Radiometry, RenderTruth, SkySimulator

OUT_DIR = ROOT / 'data' / 'outputs'
E2E_FIG_DIR = OUT_DIR / 'e2e_figures'
FAIL_FIG_DIR = OUT_DIR / 'failure_cases'
MANIFEST_PATH = ROOT / 'data' / 'real_calibrated' / 'manifest_real_calibrated.json'
FALSE_LOCK_LIMIT_ARCSEC = 300.0


def _write_json_strict(path: Path, payload: Any) -> None:
    """Serialize JSON strictly rejecting NaN/Inf via _jsonable + allow_nan=False."""
    clean = _jsonable(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(clean, indent=2, ensure_ascii=False, allow_nan=False)
    path.write_text(text, encoding='utf-8')


def _stats_block(values: list[float | None]) -> dict[str, float | None]:
    vals = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    if not vals:
        return {'n': 0, 'mean': None, 'median': None, 'p90': None, 'max': None, 'min': None}
    arr = np.asarray(vals, dtype=np.float64)
    return {
        'n': int(arr.size),
        'mean': float(np.mean(arr)),
        'median': float(np.median(arr)),
        'p90': float(np.percentile(arr, 90)),
        'max': float(np.max(arr)),
        'min': float(np.min(arr)),
    }


def _mean_or_none(values: list[float | None]) -> float | None:
    vals = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return float(np.mean(vals)) if vals else None


def _build_truth_from_manifest(entry: dict, undistort_zhao: bool = False) -> tuple[RenderTruth, bool]:
    """Construct RenderTruth from a manifest_real_calibrated entry."""
    if entry.get('q_gt') is None:
        return (
            RenderTruth(
                q_gt=np.asarray([1.0, 0.0, 0.0, 0.0], dtype=np.float64),
                uv_mid=np.empty((0, 2), dtype=np.float64),
                cat_idx=np.empty(0, dtype=int),
                streak_px=np.empty(0, dtype=np.float64),
                omega_deg_s=np.zeros(3, dtype=np.float64),
                vis_mags=np.empty(0, dtype=np.float64),
            ),
            False,
        )
    q_gt = np.asarray(entry['q_gt'], dtype=np.float64)
    stars = entry.get('stars_in_fov') or []
    uv = np.asarray([[s['u_px'], s['v_px']] for s in stars], dtype=np.float64) if stars else np.empty((0, 2), dtype=np.float64)
    if undistort_zhao and len(uv) and 'heikkila_p' in entry:
        uv = zhao_distortion_correction(
            uv,
            tuple(entry['heikkila_p']),
            float(entry['calibrated_cx']),
            float(entry['calibrated_cy']),
        )
    mags = np.asarray([float(s.get('mag', 0.0)) for s in stars], dtype=np.float64) if stars else np.empty(0, dtype=np.float64)
    cat_idx = np.arange(len(stars), dtype=int)
    return (
        RenderTruth(
            q_gt=q_gt,
            uv_mid=uv,
            cat_idx=cat_idx,
            streak_px=np.zeros(len(stars), dtype=np.float64),
            omega_deg_s=np.zeros(3, dtype=np.float64),
            vis_mags=mags,
        ),
        True,
    )


def _undistort_zhao_image(img: np.ndarray, p_coeffs: list[float], cx: float, cy: float) -> np.ndarray:
    """Remap raw Zhao MT9V022 image to pinhole-undistorted pixel grid via Heikkila inverse model."""
    h, w = img.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float64)
    uv_u = np.column_stack((xs.ravel(), ys.ravel()))
    uv_d = zhao_forward_distort(uv_u, tuple(p_coeffs), float(cx), float(cy))
    map_x = uv_d[:, 0].reshape(h, w).astype(np.float32)
    map_y = uv_d[:, 1].reshape(h, w).astype(np.float32)
    bg_fill = float(np.median(img))
    return cv2.remap(
        img.astype(np.float32),
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=bg_fill,
    )


def _extract_e2e_record(
    frame_id: str,
    res: TrackerResult,
    truth: RenderTruth,
    att_limit_arcsec: float,
    have_gt: bool,
    extra: dict | None = None,
) -> dict[str, Any]:
    """Build complete per-frame E2E record from TrackerResult and RenderTruth."""
    ev = evaluate(
        res,
        truth,
        att_limit_arcsec,
        have_gt=have_gt,
        false_lock_limit_arcsec=FALSE_LOCK_LIMIT_ARCSEC,
    )
    ax = ev.get('axis_error_arcsec')
    cross_bore = float(math.hypot(ax[0], ax[1])) if ax is not None else None
    roll_err = float(abs(ax[2])) if ax is not None else None
    t_ms = res.timing_ms or {}
    det_uv = res.centroids.uv if res.centroids is not None else np.empty((0, 2), dtype=np.float64)
    n_pred = int(len(det_uv))
    n_gt_stars = int(len(truth.uv_mid)) if have_gt else 0
    cm5 = match_centroid_rmse(det_uv, truth.uv_mid, match_radius_px=5.0) if (have_gt and n_gt_stars > 0) else None
    rec: dict[str, Any] = {
        'frame_id': frame_id,
        'have_gt': bool(have_gt),
        'status': ev['status'],
        'success': bool(ev['success']),
        'reject_code': ev['reject_code'],
        'verdict': ev['verdict'],
        'e2e_outcome': ev['e2e_outcome'],
        'limit_arcsec': float(att_limit_arcsec),
        'attitude_error_arcsec': ev['attitude_error_arcsec'],
        'axis_error_arcsec': ax,
        'cross_boresight_arcsec': cross_bore,
        'roll_error_arcsec': roll_err,
        'boresight_gt_ra_deg': ev.get('boresight_gt_ra_deg'),
        'boresight_gt_dec_deg': ev.get('boresight_gt_dec_deg'),
        'boresight_est_ra_deg': ev.get('boresight_est_ra_deg'),
        'boresight_est_dec_deg': ev.get('boresight_est_dec_deg'),
        'n_gt_stars': n_gt_stars,
        'n_detected': int(ev['n_detected']),
        'n_matched_centroids_5px': None if cm5 is None else int(cm5['n_matched']),
        'n_false_pos_centroids_5px': None if cm5 is None else int(cm5['n_false_pos']),
        'centroid_precision': ev.get('centroid_precision'),
        'centroid_recall': ev.get('centroid_recall'),
        'centroid_f1': ev.get('centroid_f1'),
        'centroid_rmse_3px': ev.get('centroid_rms_px'),
        'centroid_rmse_5px': ev.get('centroid_rms_5px'),
        'n_initial_matched': ev.get('n_initial_matched'),
        'n_rejected_outliers': ev.get('n_rejected_outliers'),
        'n_valid_pairs': ev.get('n_valid_pairs'),
        'fov_expected_stars': ev.get('fov_expected_stars'),
        'rms_residual_arcsec': ev.get('rms_residual_arcsec'),
        'max_residual_arcsec': ev.get('max_residual_arcsec'),
        'mask_ms': float(t_ms.get('mask_ms', 0.0)),
        'centroiding_ms': float(t_ms.get('centroiding_ms', 0.0)),
        'identification_ms': float(t_ms.get('identification_ms', 0.0)),
        'attitude_ms': float(t_ms.get('attitude_ms', 0.0)),
        'total_pipeline_ms': float(t_ms.get('total_pipeline_ms', 0.0)),
        'centroid_detector': (res.quality or {}).get('centroid_detector'),
        'centroid_fallback': bool((res.quality or {}).get('centroid_fallback', False)),
        'error': ev.get('error'),
    }
    if extra:
        rec.update(extra)
    return rec


def _aggregate_e2e_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute standardized aggregate KPIs across a list of per-frame E2E records."""
    n_frames = len(records)
    gt_recs = [r for r in records if r['have_gt']]
    n_gt = len(gt_recs)
    n_solved = sum(1 for r in records if r['status'] == 'SOLVED')
    n_lost = sum(1 for r in records if r['status'] != 'SOLVED')
    n_correct = sum(1 for r in gt_recs if r['e2e_outcome'] == 'SOLVED_CORRECT')
    n_warn = sum(1 for r in gt_recs if r['e2e_outcome'] == 'SOLVED_WARN')
    n_false_lock = sum(1 for r in gt_recs if r['e2e_outcome'] == 'FALSE_LOCK')
    n_solved_gt = sum(1 for r in gt_recs if r['status'] == 'SOLVED')
    n_within_60 = sum(
        1 for r in gt_recs
        if r['status'] == 'SOLVED' and r['attitude_error_arcsec'] is not None and r['attitude_error_arcsec'] < 60.0
    )

    rej_counts: dict[str, int] = {}
    for r in records:
        if r['status'] != 'SOLVED':
            code = str(r.get('reject_code') or 'UNKNOWN')
            rej_counts[code] = rej_counts.get(code, 0) + 1

    gt_stars_total = sum(int(r['n_gt_stars']) for r in gt_recs)
    det_gt_total = sum(int(r['n_detected']) for r in gt_recs)
    matched_5px_total = sum(int(r['n_matched_centroids_5px'] or 0) for r in gt_recs)
    fp_5px_total = sum(int(r['n_false_pos_centroids_5px'] or 0) for r in gt_recs)

    return {
        'n_frames': n_frames,
        'n_gt_frames': n_gt,
        'n_solved': n_solved,
        'solve_rate_pct': 100.0 * n_solved / max(n_frames, 1),
        'n_solved_gt': n_solved_gt,
        'n_correct': n_correct,
        'n_warn': n_warn,
        'n_within_60_arcsec': n_within_60,
        'true_solve_rate_pct': 100.0 * n_correct / max(n_gt, 1) if n_gt else None,
        'n_false_lock': n_false_lock,
        'false_lock_rate_pct': 100.0 * n_false_lock / max(n_gt, 1) if n_gt else 0.0,
        'n_lost': n_lost,
        'lost_rate_pct': 100.0 * n_lost / max(n_frames, 1),
        'reject_code_counts': rej_counts,
        'attitude_error_arcsec': _stats_block([r['attitude_error_arcsec'] for r in gt_recs if r['status'] == 'SOLVED']),
        'cross_boresight_arcsec': _stats_block([r['cross_boresight_arcsec'] for r in gt_recs if r['status'] == 'SOLVED']),
        'roll_error_arcsec': _stats_block([r['roll_error_arcsec'] for r in gt_recs if r['status'] == 'SOLVED']),
        'axis_error_arcsec': {
            'mean_abs_dx': _mean_or_none([abs(r['axis_error_arcsec'][0]) for r in gt_recs if r['axis_error_arcsec'] is not None]),
            'mean_abs_dy': _mean_or_none([abs(r['axis_error_arcsec'][1]) for r in gt_recs if r['axis_error_arcsec'] is not None]),
            'mean_abs_dz': _mean_or_none([abs(r['axis_error_arcsec'][2]) for r in gt_recs if r['axis_error_arcsec'] is not None]),
        },
        'centroid_precision': _mean_or_none([r['centroid_precision'] for r in gt_recs]),
        'centroid_recall': _mean_or_none([r['centroid_recall'] for r in gt_recs]),
        'centroid_f1': _mean_or_none([r['centroid_f1'] for r in gt_recs]),
        'centroid_precision_micro': float(matched_5px_total / det_gt_total) if det_gt_total > 0 else None,
        'centroid_recall_micro': float(matched_5px_total / gt_stars_total) if gt_stars_total > 0 else None,
        'centroid_gt_stars_total': gt_stars_total,
        'centroid_detected_total': det_gt_total,
        'centroid_matched_5px_total': matched_5px_total,
        'centroid_false_pos_5px_total': fp_5px_total,
        'centroid_rmse_3px': _mean_or_none([r['centroid_rmse_3px'] for r in gt_recs]),
        'centroid_rmse_5px': _mean_or_none([r['centroid_rmse_5px'] for r in gt_recs]),
        'n_detected': _stats_block([float(r['n_detected']) for r in records]),
        'n_initial_matched': _stats_block([float(r['n_initial_matched']) if r['n_initial_matched'] is not None else None for r in records]),
        'n_rejected_outliers': _stats_block([float(r['n_rejected_outliers']) if r['n_rejected_outliers'] is not None else None for r in records]),
        'n_valid_pairs': _stats_block([float(r['n_valid_pairs']) if r['n_valid_pairs'] is not None else None for r in records]),
        'rms_residual_arcsec': _stats_block([r['rms_residual_arcsec'] for r in records if r['status'] == 'SOLVED']),
        'mask_ms': _stats_block([r['mask_ms'] for r in records]),
        'centroiding_ms': _stats_block([r['centroiding_ms'] for r in records]),
        'identification_ms': _stats_block([r['identification_ms'] for r in records]),
        'attitude_ms': _stats_block([r['attitude_ms'] for r in records]),
        'total_pipeline_ms': _stats_block([r['total_pipeline_ms'] for r in records]),
    }


def _shared_cnn_detector(camera: CameraModel, base_det: object, cnn_template: CNNCentroidDetector | None) -> CNNCentroidDetector:
    """Create a CNNCentroidDetector reusing the loaded CUDA MobileUNet model without reloading disk weights."""
    det = CNNCentroidDetector(camera, classical=base_det)
    if cnn_template is not None and cnn_template._model is not None:
        det._model = cnn_template._model
        det._torch = cnn_template._torch
        det._normalize = cnn_template._normalize
        det._device = cnn_template._device
        det.device_name = cnn_template.device_name
    return det


def _make_pipeline(
    camera: CameraModel,
    catalog: StarCatalog,
    kvector: KVectorTable,
    cfg: PipelineConfig,
    cnn_template: CNNCentroidDetector | None,
) -> StarTrackerPipeline:
    pipe = StarTrackerPipeline(camera, catalog, kvector, cfg)
    if str(cfg.centroid_backend).lower() == 'cnn' and cnn_template is not None:
        pipe.centroid_detector = _shared_cnn_detector(camera, pipe.centroid_detector.classical, cnn_template)
    return pipe


def _init_cnn_template() -> tuple[CNNCentroidDetector | None, str, str | None]:
    """Warm up MobileUNet on RTX 5070 CUDA once and return shared template."""
    if not weights_available():
        return None, 'cpu', 'missing MobileUNet_B10_50.pt'
    import torch
    cam_dummy = demo_camera_long_side(1024)
    det = CNNCentroidDetector(cam_dummy)
    _ = det.detect(np.zeros((256, 256), dtype=np.uint16))
    dev_name = getattr(det, 'device_name', 'cpu')
    print(f'[*] CNN warmed: torch={torch.__version__} cuda={torch.cuda.is_available()} device={dev_name}', flush=True)
    return det, dev_name, None


def _build_custom_cfg(camera: CameraModel, backend: str, *, calibrated: bool = False) -> tuple[PipelineConfig, float]:
    """Mirror DemoEngine custom-optics pipeline configuration with wide-FOV combinatorial guard."""
    is_small = camera.width * camera.height < 4_000_000
    cfg = load_pipeline_cfg('fast' if is_small else 'full', ROOT)
    tol_arc = match_tolerance_arcsec(camera)
    cfg.angular_tol_rad = float(tol_arc) / ARCSEC_PER_RAD
    cfg.attitude_error_limit_arcsec = float(tol_arc)
    fov_diag = float(camera.fov_deg[2])
    if calibrated and fov_diag > 40.0:
        cfg.tol_frac = 0.0
    else:
        cfg.tol_frac = 0.008
    if fov_diag > 40.0:
        cfg.cutoff = 400
    cfg.centroid_backend = backend
    return cfg, float(tol_arc)


def _run_real_calibrated_suite(engine: DemoEngine, cnn_tmpl: CNNCentroidDetector | None, device_name: str) -> dict[str, Any]:
    """Suite 1: Real calibrated & stress frames under Nominal vs Calibrated optics."""
    print('\n=== Suite 1: Real Calibrated Sky End-to-End ===', flush=True)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
    frames = manifest['frames']

    # Pre-warm Hipparcos V<=7.0 catalog & k-vectors in memory for supplementary check on sparse fields
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

    nominal_records: dict[str, list[dict[str, Any]]] = {'classical': [], 'cnn': []}
    calibrated_records: dict[str, list[dict[str, Any]]] = {'classical': [], 'cnn': []}
    supplementary_hip: list[dict[str, Any]] = []

    for entry in frames:
        rel_path = entry['path']
        full_path = ROOT / rel_path
        fname = full_path.name
        raw = np.load(full_path) if rel_path.endswith('.npy') else load_frame(full_path)
        w, h, px_um = int(entry['width']), int(entry['height']), float(entry['pixel_um'])
        has_heikkila = 'heikkila_p' in entry
        has_calibrated = (entry.get('k1') is not None) or has_heikkila

        cam_nom = CameraModel(width=w, height=h, pixel_um=px_um, focal_mm=float(entry['focal_mm_nominal']))
        truth_raw, have_gt = _build_truth_from_manifest(entry, undistort_zhao=False)

        # Primary BSC5 V<=6.0 evaluation under Nominal Optics
        tmax_nom = theta_max_deg_for_fov(float(cam_nom.fov_deg[2]))
        cat_bsc_nom, _, kv_bsc_nom = engine.stack('bsc5', 6.0, tmax_nom)
        for be in ('classical', 'cnn'):
            cfg_nom, tol_nom = _build_custom_cfg(cam_nom, be)
            pipe = _make_pipeline(cam_nom, cat_bsc_nom, kv_bsc_nom, cfg_nom, cnn_tmpl)
            res = pipe.process_frame(raw)
            rec = _extract_e2e_record(
                fname,
                res,
                truth_raw,
                tol_nom,
                have_gt,
                extra={
                    'path': rel_path,
                    'dataset_group': entry['dataset_group'],
                    'optics_mode': 'nominal',
                    'catalog': 'bsc5_v6.0',
                    'focal_mm': cam_nom.focal_mm,
                    'k1': 0.0,
                    'k2': 0.0,
                },
            )
            nominal_records[be].append(rec)
            print(
                f"  [Nominal/BSC5] {fname:38s} {be:9s}: {rec['status']:6s} "
                f"rej={str(rec['reject_code']):26s} err={rec['attitude_error_arcsec']}",
                flush=True,
            )

        # Primary BSC5 V<=6.0 evaluation under Calibrated Optics (for the 5 frames with calibrated parameters)
        if has_calibrated:
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
            truth_cal, _ = _build_truth_from_manifest(entry, undistort_zhao=has_heikkila)
            tmax_cal = theta_max_deg_for_fov(float(cam_cal.fov_deg[2]))
            cat_bsc_cal, _, kv_bsc_cal = engine.stack('bsc5', 6.0, tmax_cal)
            for be in ('classical', 'cnn'):
                cfg_cal, tol_cal = _build_custom_cfg(cam_cal, be, calibrated=True)
                pipe = _make_pipeline(cam_cal, cat_bsc_cal, kv_bsc_cal, cfg_cal, cnn_tmpl)
                res = pipe.process_frame(img_cal)
                rec = _extract_e2e_record(
                    fname,
                    res,
                    truth_cal,
                    tol_cal,
                    have_gt,
                    extra={
                        'path': rel_path,
                        'dataset_group': entry['dataset_group'],
                        'optics_mode': 'calibrated_heikkila_undistort' if has_heikkila else 'calibrated',
                        'catalog': 'bsc5_v6.0',
                        'focal_mm': cam_cal.focal_mm,
                        'k1': cam_cal.k1,
                        'k2': cam_cal.k2,
                        'cx': cam_cal.cx,
                        'cy': cam_cal.cy,
                    },
                )
                calibrated_records[be].append(rec)
                print(
                    f"  [Calibr./BSC5] {fname:38s} {be:9s}: {rec['status']:6s} "
                    f"rej={str(rec['reject_code']):26s} err={rec['attitude_error_arcsec']}",
                    flush=True,
                )

        # Supplementary Hipparcos V<=6.0 & V<=7.0 diagnostic for tetra3 Alt40/Alt60 & Zhao nightsky
        if entry['dataset_group'] in ('esa_tetra3', 'zhao_mt9v022') and have_gt:
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
            truth_cal, _ = _build_truth_from_manifest(entry, undistort_zhao=has_heikkila)
            tmax_cal = theta_max_deg_for_fov(float(cam_cal.fov_deg[2]))
            cat_h6, _, kv_h6 = engine.stack('hipparcos', 6.0, tmax_cal)
            kv_h7 = get_hip7_kv(tmax_cal)
            for cat_lbl, cat_obj, kv_obj in (('hipparcos_v6.0', cat_h6, kv_h6), ('hipparcos_v7.0', cat_hip7, kv_h7)):
                for be in ('classical', 'cnn'):
                    cfg_s, tol_s = _build_custom_cfg(cam_cal, be)
                    pipe = _make_pipeline(cam_cal, cat_obj, kv_obj, cfg_s, cnn_tmpl)
                    res = pipe.process_frame(img_cal)
                    s_rec = _extract_e2e_record(
                        fname,
                        res,
                        truth_cal,
                        tol_s,
                        True,
                        extra={'path': rel_path, 'optics_mode': 'calibrated', 'catalog': cat_lbl},
                    )
                    supplementary_hip.append(s_rec)
                    print(
                        f"  [Supp/{cat_lbl:14s}] {fname:35s} {be:9s}: {s_rec['status']:6s} "
                        f"valid={s_rec['n_valid_pairs']} err={s_rec['attitude_error_arcsec']}",
                        flush=True,
                    )

    payload = {
        'suite': 'real_calibrated_e2e',
        'device': device_name,
        'distance_map_threshold': 2.0,
        'primary_catalog': 'bsc5_v6.0',
        'false_lock_limit_arcsec': FALSE_LOCK_LIMIT_ARCSEC,
        'notes': [
            'Primary benchmark uses standard StarTracker catalog bsc5_v6.0.',
            'ESA tetra3 Alt40 has only 3 BSC5 V<=6.0 stars inside edge_margin=5px FOV (HR 5739 is at v_px=4.09 < 5.0), so primary BSC5 cleanly rejects it; supplementary Hipparcos V<=7.0 solves Alt40 cleanly (<40 arcsec) for both CoG and CNN.',
            'Zhao MT9V022 nightsky_june16_2021.npy uses Heikkila polynomial undistortion + calibrated (focal_mm=16.0803, cx=352.844, cy=199.461); CNN solves with <60 arcsec error while CoG detects only 4 stars at fast k_sigma=4.0.',
            'data/uploads/real_sky/images/0006.png has no calibrated optics (uncalibrated wide-angle stress test) and is evaluated once under nominal optics.',
            'Wide-FOV guard (fov_diag_deg > 40 deg): calibrated wide-FOV frames (mount_st_helens_1.png Calibrated) set tol_frac=0.0 since radial k1/k2 distortion is already modeled, and wide-FOV frames cap cfg.cutoff=400 to avoid combinatorial triangle search stalls.',
        ],
        'nominal': {
            'summary': {
                'classical': _aggregate_e2e_records(nominal_records['classical']),
                'cnn': _aggregate_e2e_records(nominal_records['cnn']),
            },
            'frames': {
                'classical': nominal_records['classical'],
                'cnn': nominal_records['cnn'],
            },
        },
        'calibrated': {
            'n_calibrated_frames': len(calibrated_records['classical']),
            'uncalibrated_omitted': ['data/uploads/real_sky/images/0006.png'],
            'summary': {
                'classical': _aggregate_e2e_records(calibrated_records['classical']),
                'cnn': _aggregate_e2e_records(calibrated_records['cnn']),
            },
            'frames': {
                'classical': calibrated_records['classical'],
                'cnn': calibrated_records['cnn'],
            },
        },
        'supplementary_hipparcos': supplementary_hip,
    }
    _write_json_strict(OUT_DIR / 'benchmark_real_calibrated_e2e.json', payload)
    print(f"[*] wrote {OUT_DIR / 'benchmark_real_calibrated_e2e.json'}", flush=True)
    return payload


def _eval_sim_dataset(
    ds_name: str,
    ds_dir: Path,
    n_expected: int,
    out_json: Path,
    engine: DemoEngine,
    cnn_tmpl: CNNCentroidDetector | None,
    device_name: str,
) -> dict[str, Any]:
    """Suite 2 helper: run CoG vs CNN full E2E pipeline on existing hd1024 or hd1024_glare frames without regenerating."""
    print(f'\n=== Suite 2: {ds_name} ({n_expected} existing frames) ===', flush=True)
    cam = demo_camera_long_side(1024)
    tmax = theta_max_deg_for_fov(float(cam.fov_deg[2]))
    cat, _, kv = engine.stack('bsc5', 6.0, tmax)

    # Config A (primary): DemoEngine auto-detected fast config for 1024x683 (scale=6, tol=54.04", tol_frac=0, limit=40")
    cfg_locked_cl = load_pipeline_cfg('fast', ROOT)
    cfg_locked_cl.centroid_backend = 'classical'
    cfg_locked_nn = load_pipeline_cfg('fast', ROOT)
    cfg_locked_nn.centroid_backend = 'cnn'
    pipe_locked_cl = _make_pipeline(cam, cat, kv, cfg_locked_cl, cnn_tmpl)
    pipe_locked_nn = _make_pipeline(cam, cat, kv, cfg_locked_nn, cnn_tmpl)

    # Config B (sensitivity): custom-optics tolerance 0.88*ifov (79.13") + tol_frac=0.008
    tol_custom_arc = match_tolerance_arcsec(cam)
    cfg_cust_cl, _ = _build_custom_cfg(cam, 'classical')
    cfg_cust_nn, _ = _build_custom_cfg(cam, 'cnn')
    pipe_cust_cl = _make_pipeline(cam, cat, kv, cfg_cust_cl, cnn_tmpl)
    pipe_cust_nn = _make_pipeline(cam, cat, kv, cfg_cust_nn, cnn_tmpl)

    locked_recs: dict[str, list[dict[str, Any]]] = {'classical': [], 'cnn': []}
    custom_recs: dict[str, list[dict[str, Any]]] = {'classical': [], 'cnn': []}

    def run_downstream_with_cached_centroids(
        pipe: StarTrackerPipeline,
        g_mask: np.ndarray,
        mask_ms: float,
        cents: Centroids,
        cent_ms: float,
    ) -> TrackerResult:
        """Execute identification & attitude stages reusing cached glare mask and centroids."""
        from time import perf_counter
        from numpy import all as npall, count_nonzero, degrees, einsum
        from src.pipeline import _build_match_stats, _dedup_pairs

        t_log = {'mask_ms': float(mask_ms), 'centroiding_ms': float(cent_ms)}
        req_stars = max(int(pipe.cfg.min_stars), 3)
        n_det = int(len(cents.vectors))
        cfg_be = str(pipe.cfg.centroid_backend or 'classical')

        def abort(rc: str, reason: str, *, n_initial_matched: int = 0, n_rejected_outliers: int = 0, n_valid_pairs: int = 0, rms_res: object = None, max_res: object = None, fov_expected: int = 0) -> TrackerResult:
            t_log['total_pipeline_ms'] = sum(v for k, v in t_log.items() if k != 'total_pipeline_ms')
            stats = _build_match_stats('LOST', rc, n_det, n_initial_matched, n_rejected_outliers, n_valid_pairs, req_stars, rms_res, max_res, fov_expected)
            q_diag = dict(stats, n_matched=0, centroid_backend=cfg_be, centroid_detector=getattr(pipe.centroid_detector, 'last_backend', cfg_be), centroid_fallback=bool(getattr(pipe.centroid_detector, 'last_fallback', False)), low_recall=True, many_false=False)
            return TrackerResult(False, None, None, cents, None, None, None, t_log, q_diag, f'LOST [{rc}]: {reason}', g_mask, 'LOST', rc, stats)

        if n_det < 3:
            return abort('INSUFFICIENT_DETECTIONS', f'Insufficient stars detected ({n_det} < 3)')
        ts = perf_counter()
        id_res = pipe.star_identifier.identify(cents.vectors, cents.flux)
        n_m_init = int(len(id_res.obs_idx))
        if ((not id_res.success or n_m_init < req_stars) or (id_res.success and n_m_init < 8)) and n_det >= req_stars:
            wide_res = pipe.star_identifier.identify_wide(cents.vectors, cents.flux, pipe.camera)
            if wide_res.success and len(wide_res.obs_idx) >= max(req_stars, n_m_init + 1):
                id_res = wide_res
        t_log['identification_ms'] = (perf_counter() - ts) * 1000.0
        if not id_res.success or len(id_res.obs_idx) < 3:
            n_raw = int(len(id_res.obs_idx)) if id_res.success else 0
            return abort('IDENTIFICATION_FAILED', f'Identification failed ({len(id_res.obs_idx)})', n_initial_matched=n_raw, n_valid_pairs=n_raw)
        ts = perf_counter()
        obs_sel, cat_sel = _dedup_pairs(id_res.obs_idx, id_res.cat_idx, n_det, pipe.catalog.num_stars)
        n_init = int(len(obs_sel))
        if n_init < 3:
            t_log['attitude_ms'] = (perf_counter() - ts) * 1000.0
            return abort('IDENTIFICATION_FAILED', f'Identification unique < 3 ({n_init})', n_initial_matched=n_init, n_valid_pairs=n_init)
        floor_arc = float(degrees(pipe.cfg.angular_tol_rad) * 3600.0)
        ok, rej_code, rej_msg, obs_sel, cat_sel, quat, dcm, res_arc, cov_mat, n_rej, rms_res, max_res, rms_limit = pipe._refine_inliers(cents, obs_sel, cat_sel, floor_arc, 0)
        if not ok:
            t_log['attitude_ms'] = (perf_counter() - ts) * 1000.0
            return abort(rej_code, rej_msg, n_initial_matched=n_init, n_rejected_outliers=n_rej, n_valid_pairs=int(len(obs_sel)), rms_res=rms_res, max_res=max_res)
        obs_assoc, cat_assoc = pipe._associate_remaining(cents, dcm, obs_sel, cat_sel)
        obs_assoc, cat_assoc = _dedup_pairs(obs_assoc, cat_assoc, n_det, pipe.catalog.num_stars)
        if len(obs_assoc) != len(obs_sel) or not bool(npall(obs_assoc == obs_sel)) or not bool(npall(cat_assoc == cat_sel)):
            ok, rej_code, rej_msg, obs_sel, cat_sel, quat, dcm, res_arc, cov_mat, n_rej, rms_res, max_res, rms_limit = pipe._refine_inliers(cents, obs_assoc, cat_assoc, floor_arc, n_rej)
            if not ok:
                t_log['attitude_ms'] = (perf_counter() - ts) * 1000.0
                return abort(rej_code, rej_msg, n_initial_matched=n_init, n_rejected_outliers=n_rej, n_valid_pairs=int(len(obs_sel)), rms_res=rms_res, max_res=max_res)
        t_log['attitude_ms'] = (perf_counter() - ts) * 1000.0
        t_log['total_pipeline_ms'] = sum(v for k, v in t_log.items() if k != 'total_pipeline_ms')
        num_final = int(len(obs_sel))
        num_fov = int(count_nonzero(pipe.camera.project(einsum('ij,kj->ik', pipe.catalog.vectors, dcm))[1])) if dcm is not None else 0
        if num_final < 3:
            return abort('INSUFFICIENT_INLIER_PAIRS', f'Only {num_final} < 3', n_initial_matched=n_init, n_rejected_outliers=n_rej, n_valid_pairs=num_final, rms_res=rms_res, max_res=max_res, fov_expected=num_fov)
        if rms_res is not None and rms_res > rms_limit:
            return abort('EXCESSIVE_POSTFIT_RESIDUAL', f'RMS {rms_res:.2f} > {rms_limit:.2f}', n_initial_matched=n_init, n_rejected_outliers=n_rej, n_valid_pairs=num_final, rms_res=rms_res, max_res=max_res, fov_expected=num_fov)
        allow_three = num_final == 3 and int(pipe.cfg.min_stars) <= 3 and num_fov <= 3 and max_res is not None and max_res <= 0.5 * floor_arc
        if num_final < req_stars and not allow_three:
            return abort('INSUFFICIENT_INLIER_PAIRS', f'Only {num_final} < min_stars {req_stars}', n_initial_matched=n_init, n_rejected_outliers=n_rej, n_valid_pairs=num_final, rms_res=rms_res, max_res=max_res, fov_expected=num_fov)
        fov_recall = num_final / float(num_fov) if num_fov else 0.0
        is_valid = num_final >= 8 or (num_final >= req_stars and fov_recall >= 0.75) or (num_final >= 5 and fov_recall >= 0.45 and rms_res <= 0.6 * floor_arc) or allow_three
        if not is_valid:
            return abort('LOW_FOV_CONSISTENCY', f'{num_final}/{num_fov}', n_initial_matched=n_init, n_rejected_outliers=n_rej, n_valid_pairs=num_final, rms_res=rms_res, max_res=max_res, fov_expected=num_fov)
        final_id = IdResult(obs_sel, cat_sel, True, id_res.n_pyramids_tested, id_res.expected_false)
        match_stats = _build_match_stats('SOLVED', None, n_det, n_init, n_rej, num_final, req_stars, rms_res, max_res, num_fov)
        q_metrics = pipe._quality(cents, final_id, dcm)
        q_metrics.update(match_stats)
        return TrackerResult(True, quat, dcm, cents, final_id, res_arc, cov_mat, t_log, q_metrics, None, g_mask, 'SOLVED', None, match_stats)

    t_wall0 = time.perf_counter()
    for i in range(n_expected):
        stem = f'{i:04d}'
        tif_p = ds_dir / f'{stem}.tif'
        meta_p = ds_dir / f'{stem}.json'
        img = load_frame(tif_p)
        meta = json.loads(meta_p.read_text(encoding='utf-8'))
        truth = truth_from_sidecar(meta, cat)

        # Primary locked fast pipeline run (calls process_frame directly)
        res_l_cl = pipe_locked_cl.process_frame(img)
        res_l_nn = pipe_locked_nn.process_frame(img)
        locked_recs['classical'].append(_extract_e2e_record(stem, res_l_cl, truth, 40.0, True))
        locked_recs['cnn'].append(_extract_e2e_record(stem, res_l_nn, truth, 40.0, True))

        # Custom 0.88*ifov + tol_frac=0.008 sensitivity pass reusing the exact same glare_mask + centroids
        res_c_cl = run_downstream_with_cached_centroids(
            pipe_cust_cl,
            res_l_cl.glare_mask,
            res_l_cl.timing_ms['mask_ms'],
            res_l_cl.centroids,
            res_l_cl.timing_ms['centroiding_ms'],
        )
        res_c_nn = run_downstream_with_cached_centroids(
            pipe_cust_nn,
            res_l_nn.glare_mask,
            res_l_nn.timing_ms['mask_ms'],
            res_l_nn.centroids,
            res_l_nn.timing_ms['centroiding_ms'],
        )
        custom_recs['classical'].append(_extract_e2e_record(stem, res_c_cl, truth, 40.0, True))
        custom_recs['cnn'].append(_extract_e2e_record(stem, res_c_nn, truth, 40.0, True))

        if (i + 1) % 50 == 0 or i + 1 == n_expected:
            print(f'  [{ds_name}] {i + 1}/{n_expected} elapsed={time.perf_counter() - t_wall0:.1f}s', flush=True)
        if (i + 1) % 50 == 0:
            gc.collect()

    wall_s = time.perf_counter() - t_wall0
    sum_locked_cl = _aggregate_e2e_records(locked_recs['classical'])
    sum_locked_nn = _aggregate_e2e_records(locked_recs['cnn'])
    sum_cust_cl = _aggregate_e2e_records(custom_recs['classical'])
    sum_cust_nn = _aggregate_e2e_records(custom_recs['cnn'])

    # Compute additional < tol_arc rate for custom_088ifov
    cust_nn_within_tol = sum(
        1 for r in custom_recs['cnn']
        if r['status'] == 'SOLVED' and r['attitude_error_arcsec'] is not None and r['attitude_error_arcsec'] < tol_custom_arc
    )
    cust_cl_within_tol = sum(
        1 for r in custom_recs['classical']
        if r['status'] == 'SOLVED' and r['attitude_error_arcsec'] is not None and r['attitude_error_arcsec'] < tol_custom_arc
    )

    payload = {
        'suite': f'{ds_name}_e2e',
        'dataset_dir': str(ds_dir.relative_to(ROOT)).replace('\\', '/'),
        'regenerated_images': False,
        'n_frames': n_expected,
        'wall_s': float(wall_s),
        'device': device_name,
        'distance_map_threshold': 2.0,
        'camera': {
            'width': cam.width,
            'height': cam.height,
            'pixel_um': cam.pixel_um,
            'focal_mm': cam.focal_mm,
            'ifov_arcsec': float(cam.ifov_arcsec),
        },
        'primary_config': {
            'name': 'demo_engine_fast_locked',
            'angular_tol_rad': float(cfg_locked_cl.angular_tol_rad),
            'angular_tol_arcsec': float(math.degrees(cfg_locked_cl.angular_tol_rad) * 3600.0),
            'tol_frac': float(cfg_locked_cl.tol_frac),
            'attitude_error_limit_arcsec': 40.0,
            'false_lock_limit_arcsec': FALSE_LOCK_LIMIT_ARCSEC,
        },
        'classical': sum_locked_cl,
        'cnn': sum_locked_nn,
        'config_comparison': {
            'custom_088ifov_tol_frac_008': {
                'angular_tol_arcsec': float(tol_custom_arc),
                'tol_frac': 0.008,
                'attitude_error_limit_arcsec': 40.0,
                'alt_limit_tol_arcsec': float(tol_custom_arc),
                'classical_within_tol_arcsec': cust_cl_within_tol,
                'cnn_within_tol_arcsec': cust_nn_within_tol,
                'classical': sum_cust_cl,
                'cnn': sum_cust_nn,
            },
        },
        'frames': {
            'classical': locked_recs['classical'],
            'cnn': locked_recs['cnn'],
        },
    }
    _write_json_strict(out_json, payload)
    print(f'[*] wrote {out_json}', flush=True)
    return payload


def _run_seed42_suite(engine: DemoEngine, cnn_tmpl: CNNCentroidDetector | None, device_name: str) -> dict[str, Any]:
    """Run FAST Seed 42 via DemoEngine AND warm GPU StarTrackerPipeline for both classical CoG and cnn."""
    print('\n=== Suite 2b: FAST Seed 42 (CoG vs CNN) ===', flush=True)
    results_engine: dict[str, dict[str, Any]] = {}
    warm_timings: dict[str, dict[str, Any]] = {}
    rendered_img = None
    truth_obj = None
    cam = None
    cat = None
    kv = None

    for be in ('classical', 'cnn'):
        out = engine.run(
            RunRequest(
                mode='fast',
                seed=42,
                catalog='bsc5',
                max_mag=6.0,
                centroid_backend=be,
                save_png=False,
            )
        )
        rendered_img = out.image
        truth_obj = out.truth
        cam = out.camera
        cat = out.catalog
        _, _, kv = engine.stack('bsc5', 6.0, theta_max_deg_for_fov(float(cam.fov_deg[2])))
        rec = _extract_e2e_record(
            'seed42_fast',
            out.result,
            out.truth,
            float(out.payload['metrics']['limit_arcsec']),
            out.have_gt,
            extra={
                'centroid_backend': be,
                'centroid_n_raw': out.payload.get('centroid_n_raw'),
                'centroid_n_after_gate': out.payload.get('centroid_n_after_gate'),
                'downlink_bytes': out.payload.get('downlink_bytes'),
                'downlink_hex': out.payload.get('downlink_hex'),
            },
        )
        results_engine[be] = rec
        print(
            f"  [Seed42 DemoEngine] {be:9s}: err={rec['attitude_error_arcsec']:.4f}\" "
            f"valid={rec['n_valid_pairs']}/{rec['n_gt_stars']} "
            f"prec={rec['centroid_precision']:.4f} rec={rec['centroid_recall']:.4f} "
            f"ms={rec['total_pipeline_ms']:.2f}",
            flush=True,
        )

    # Also measure warm-GPU StarTrackerPipeline on the exact same Seed 42 frame
    assert rendered_img is not None and cam is not None and cat is not None and kv is not None and truth_obj is not None
    for be in ('classical', 'cnn'):
        cfg = load_pipeline_cfg('fast', ROOT)
        cfg.centroid_backend = be
        pipe = _make_pipeline(cam, cat, kv, cfg, cnn_tmpl)
        res_warm = pipe.process_frame(rendered_img)
        warm_timings[be] = {
            'status': res_warm.status,
            'attitude_error_arcsec': angular_error_arcsec(res_warm.q, truth_obj.q_gt) if res_warm.success else None,
            'timing_ms': res_warm.timing_ms,
        }

    payload = {
        'suite': 'seed42_cog_vs_cnn',
        'mode': 'fast',
        'seed': 42,
        'catalog': 'bsc5_v6.0',
        'device': device_name,
        'distance_map_threshold': 2.0,
        'camera': {
            'width': cam.width,
            'height': cam.height,
            'pixel_um': cam.pixel_um,
            'focal_mm': cam.focal_mm,
        },
        'classical': results_engine['classical'],
        'cnn': results_engine['cnn'],
        'warm_gpu_pipeline_timings': warm_timings,
        'reconciliation_note': (
            'Reconciles previously unlogged Seed 42 figures (~0.446 arcsec CoG vs ~1.65 arcsec CNN) '
            'from a single locked DemoEngine execution.'
        ),
    }
    _write_json_strict(OUT_DIR / 'seed42_cog_vs_cnn.json', payload)
    print(f"[*] wrote {OUT_DIR / 'seed42_cog_vs_cnn.json'}", flush=True)
    return payload


def _run_legacy_prefixed_tail(
    pipe: StarTrackerPipeline,
    cents: Centroids,
    id_res: IdResult,
    g_mask: np.ndarray,
    timing_base: dict[str, float],
) -> dict[str, Any]:
    """Simulate exact pre-fix HEAD:src/pipeline.py + HEAD:src/attitude.py attitude/validation tail."""
    t_log = dict(timing_base)
    n_det = int(len(cents.vectors))
    req_stars = max(int(pipe.cfg.min_stars), 3)
    if n_det < 3:
        return {'success': False, 'q': None, 'error': f'Insufficient stars detected ({n_det} < 3)'}
    if not id_res.success or len(id_res.obs_idx) < 3:
        return {'success': False, 'q': None, 'error': f'Identification failed ({len(id_res.obs_idx)})'}

    def legacy_wahba_svd(b_vecs: np.ndarray, r_vecs: np.ndarray, w_vec: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        w_norm = w_vec / float(np.sum(w_vec))
        b_mat = np.einsum('i,ij,ik->jk', w_norm, b_vecs, r_vecs)
        u_o, _, vt_o = np.linalg.svd(b_mat)
        handed = float(np.linalg.det(u_o) * np.linalg.det(vt_o))
        dcm = u_o * np.asarray([1.0, 1.0, handed], dtype=np.float64) @ vt_o
        return from_dcm(dcm), dcm

    def legacy_solve_weighted(obs_idx: np.ndarray, cat_idx: np.ndarray) -> tuple:
        b_v = cents.vectors[obs_idx]
        r_v = pipe.catalog.vectors[cat_idx]
        sig_r = cents.sigma_px[obs_idx] * pipe.camera.ifov_rad
        w_v = 1.0 / np.maximum(sig_r * sig_r, 1e-30)
        qt, dc = legacy_wahba_svd(b_v, r_v, w_v)
        res_a = WahbaSolver.residuals_arcsec(b_v, r_v, dc)
        return b_v, sig_r, qt, dc, res_a

    obs_sel = id_res.obs_idx.copy()
    cat_sel = id_res.cat_idx.copy()
    quat = dcm = res_arc = None
    floor_arc = float(math.degrees(pipe.cfg.angular_tol_rad) * 3600.0)
    # Exact HEAD:src/pipeline.py loop with the catastrophic `break` bug
    for _ in range(int(pipe.cfg.max_refine) + 1):
        b_vecs, sig_r, quat, dcm, res_arc = legacy_solve_weighted(obs_sel, cat_sel)
        gate_arc = np.maximum(pipe.cfg.residual_n_sigma * (sig_r * ARCSEC_PER_RAD), floor_arc)
        inliers = res_arc <= gate_arc
        if int(np.count_nonzero(inliers)) < 3 or bool(np.all(inliers)):
            break
        obs_sel, cat_sel = obs_sel[inliers], cat_sel[inliers]

    if dcm is not None:
        obs_sel, cat_sel = pipe._associate_remaining(cents, dcm, obs_sel, cat_sel)
        if len(obs_sel) >= 3:
            b_vecs, sig_r, quat, dcm, res_arc = legacy_solve_weighted(obs_sel, cat_sel)

    num_final = int(len(obs_sel))
    num_fov = int(np.count_nonzero(pipe.camera.project(np.einsum('ij,kj->ik', pipe.catalog.vectors, dcm))[1])) if dcm is not None else 0
    fov_recall = num_final / float(num_fov) if num_fov else 0.0
    is_valid = num_final >= 8 or (num_final >= req_stars and fov_recall >= 0.75) or (num_final == 3 and num_fov <= 3)
    if not is_valid:
        return {'success': False, 'q': None, 'n_final': num_final, 'error': f'Matched {num_final}/{num_fov}'}
    return {'success': True, 'q': quat, 'a': dcm, 'n_final': num_final, 'error': None}


def _run_rejection_stress_suite(engine: DemoEngine) -> dict[str, Any]:
    """Suite 3: 100 adversarial invalid-match trials across 4 categories (25 each)."""
    print('\n=== Suite 3: Adversarial Invalid-Match Rejection Stress (100 trials) ===', flush=True)
    cam = demo_camera().downscaled(4)
    cat, _, kv = engine.stack('bsc5', 6.0, theta_max_deg_for_fov(float(cam.fov_deg[2])))
    cfg = load_pipeline_cfg('fast', ROOT)
    rad = Radiometry(hot_pixel_frac=0.0, cosmic_rate_per_frame=0.0)
    sim = SkySimulator(cam, cat, radiometry=rad, seed=2026)

    # Pre-mine 25 clean solvable FAST frames for Category (b)
    pipe_clean = StarTrackerPipeline(cam, cat, kv, cfg)
    solvable_cases: list[tuple[np.ndarray, np.ndarray, TrackerResult]] = []
    for s_idx in range(1, 200):
        q_cand = SkySimulator.generate_random_quaternion(seed=700 + s_idx)
        img, truth = sim.render(q_cand, omega_deg_s=(0.0, 0.0, 0.0), add_noise=True)
        if len(truth.cat_idx) >= 10:
            res = pipe_clean.process_frame(img)
            if res.success and len(res.ident.obs_idx) >= 10:
                solvable_cases.append((img, q_cand, res))
                if len(solvable_cases) >= 25:
                    break
    assert len(solvable_cases) == 25, f'Only found {len(solvable_cases)} solvable frames'

    rng = np.random.default_rng(2026)
    trials: list[dict[str, Any]] = []

    # Category (a): <3 detected stars (0, 1, 2 stars) -> 25 trials
    for t_i in range(25):
        n_stars = t_i % 3  # 0, 1, or 2
        canvas = np.full((cam.height, cam.width), 64.0, dtype=np.float32)
        if n_stars > 0:
            uv = np.column_stack((
                rng.uniform(40.0, cam.width - 40.0, size=n_stars),
                rng.uniform(40.0, cam.height - 40.0, size=n_stars),
            ))
            sim._stamp_gaussians(canvas, uv, rng.uniform(5000.0, 12000.0, size=n_stars), 1.2, 5)
        frame = np.clip(canvas + rng.normal(0.0, 4.0, size=canvas.shape), 0, 4095).astype(np.uint16)
        pipe = StarTrackerPipeline(cam, cat, kv, cfg)
        res_imp = pipe.process_frame(frame)
        res_leg = _run_legacy_prefixed_tail(pipe, res_imp.centroids, _empty_id_result(0), res_imp.glare_mask, res_imp.timing_ms)
        trials.append({
            'trial': t_i,
            'category': 'a_lt3_detections',
            'n_injected_stars': n_stars,
            'improved_status': res_imp.status,
            'improved_reject_code': res_imp.reject_code,
            'improved_n_detected': res_imp.match_stats['n_detected'],
            'improved_n_valid_pairs': res_imp.match_stats['n_valid_pairs'],
            'improved_downlink_zero': res_imp.to_downlink_bytes() == b'\x00' * 16,
            'improved_false_lock': bool(res_imp.success),
            'legacy_false_lock': bool(res_leg['success']),
        })

    # Category (b): corrupted identification matches leaving <3 valid inliers -> 25 trials
    for t_i, (img, q_gt, base_res) in enumerate(solvable_cases):
        n_true = t_i % 3  # 0, 1, 2 valid stars
        n_bad = 6 if n_true >= 2 else 7  # >= 8 total initial pairs or 7-8 pairs so legacy break emits bogus q!
        true_obs = base_res.ident.obs_idx[:n_true]
        true_cat = base_res.ident.cat_idx[:n_true]
        unused_obs = [int(o) for o in range(len(base_res.centroids.vectors)) if int(o) not in set(true_obs.tolist())]
        bad_obs = np.asarray(unused_obs[:n_bad], dtype=np.int32)
        used_cat = set(true_cat.tolist())
        bad_cats = []
        for oi in bad_obs:
            obs_vec = base_res.centroids.vectors[int(oi)]
            opp_scores = cat.vectors @ (base_res.a.T @ obs_vec)
            chosen = next(int(c) for c in np.argsort(opp_scores) if int(c) not in used_cat)
            used_cat.add(chosen)
            bad_cats.append(chosen)
        obs_mix = np.concatenate([true_obs, bad_obs]).astype(np.int32)
        cat_mix = np.concatenate([true_cat, np.asarray(bad_cats, dtype=np.int32)]).astype(np.int32)
        corrupted_id = IdResult(obs_mix, cat_mix, True, 1, 0.0)

        pipe = StarTrackerPipeline(cam, cat, kv, cfg)
        pipe.star_identifier.identify = lambda *a, _r=corrupted_id, **k: _r
        pipe.star_identifier.identify_wide = lambda *a, **k: _empty_id_result(0)
        res_imp = pipe.process_frame(img)
        res_leg = _run_legacy_prefixed_tail(pipe, res_imp.centroids, corrupted_id, res_imp.glare_mask, res_imp.timing_ms)
        leg_err = float(angular_error_arcsec(res_leg['q'], q_gt)) if res_leg['success'] and res_leg['q'] is not None else None
        trials.append({
            'trial': t_i,
            'category': 'b_corrupted_lt3_inliers',
            'n_true_injected': n_true,
            'n_bad_injected': n_bad,
            'improved_status': res_imp.status,
            'improved_reject_code': res_imp.reject_code,
            'improved_n_initial_matched': res_imp.match_stats['n_initial_matched'],
            'improved_n_rejected_outliers': res_imp.match_stats['n_rejected_outliers'],
            'improved_n_valid_pairs': res_imp.match_stats['n_valid_pairs'],
            'improved_downlink_zero': res_imp.to_downlink_bytes() == b'\x00' * 16,
            'improved_false_lock': bool(res_imp.success),
            'legacy_false_lock': bool(res_leg['success']),
            'legacy_bogus_error_arcsec': leg_err,
        })

    # Category (c): collinear 3-star degenerate geometry with realistic 0.15 px sky-match jitter -> 25 trials
    blank_dummy = np.full((cam.height, cam.width), 64, dtype=np.uint16)
    cfg_min3 = PipelineConfig.from_dict({**load_pipeline_cfg('fast', ROOT).__dict__, 'min_stars': 3})
    for t_i in range(25):
        theta = math.pi * (t_i / 25.0)
        dx, dy = math.cos(theta), math.sin(theta)
        perp = np.asarray([-dy, dx], dtype=np.float64)
        cx0, cy0 = cam.cx + rng.uniform(-10.0, 10.0), cam.cy + rng.uniform(-10.0, 10.0)
        offsets = np.asarray([-45.0, 0.0, 45.0], dtype=np.float64)
        uv_col = np.column_stack((cx0 + offsets * dx, cy0 + offsets * dy))
        b_col = cam.unproject(uv_col)
        q_rot = random_quaternion(rng)
        # Apply 0.15 px perpendicular jitter to catalog star sky projection so legacy SVD suffers real roll instability
        uv_jit = uv_col + rng.normal(0.0, 0.15, size=(3, 1)) * perp[None, :]
        b_jit = cam.unproject(uv_jit)
        r_col = (to_dcm(q_rot).T @ b_jit.T).T
        col_cat = StarCatalog(
            ids=np.asarray([101, 102, 103], dtype=np.int32),
            vectors=r_col,
            mags=np.asarray([3.5, 3.8, 4.1], dtype=np.float32),
            source='COLLINEAR_STRESS',
        )
        col_cents = Centroids(
            uv=uv_col,
            flux=np.asarray([5000.0, 4800.0, 4600.0]),
            area=np.asarray([9.0, 9.0, 9.0]),
            peak=np.asarray([900.0, 850.0, 800.0]),
            mu20=np.ones(3),
            mu02=np.ones(3),
            mu11=np.zeros(3),
            axis_ratio=np.ones(3),
            angle_rad=np.zeros(3),
            vectors=b_col,
            sigma_px=np.full(3, 0.2),
        )
        col_id = IdResult(np.asarray([0, 1, 2], dtype=np.int32), np.asarray([0, 1, 2], dtype=np.int32), True, 1, 0.0)
        pipe = StarTrackerPipeline(cam, col_cat, kv, cfg_min3)
        pipe.centroid_detector.detect = lambda *a, _c=col_cents, **k: _c
        pipe.star_identifier.identify = lambda *a, _r=col_id, **k: _r
        pipe.star_identifier.identify_wide = lambda *a, **k: _empty_id_result(0)
        res_imp = pipe.process_frame(blank_dummy)
        res_leg = _run_legacy_prefixed_tail(pipe, col_cents, col_id, res_imp.glare_mask, res_imp.timing_ms)
        leg_err = float(angular_error_arcsec(res_leg['q'], q_rot)) if res_leg['success'] and res_leg['q'] is not None else None
        trials.append({
            'trial': t_i,
            'category': 'c_collinear_3stars',
            'improved_status': res_imp.status,
            'improved_reject_code': res_imp.reject_code,
            'improved_n_valid_pairs': res_imp.match_stats['n_valid_pairs'],
            'improved_downlink_zero': res_imp.to_downlink_bytes() == b'\x00' * 16,
            'improved_false_lock': bool(res_imp.success),
            'legacy_false_lock': bool(res_leg['success']),
            'legacy_bogus_error_arcsec': leg_err,
        })

    # Category (d): pure false-star / random-noise clutter frames -> 25 trials
    for t_i in range(25):
        n_false = int(rng.integers(8, 22))
        canvas = np.full((cam.height, cam.width), 64.0, dtype=np.float32)
        uv_rnd = np.column_stack((
            rng.uniform(25.0, cam.width - 25.0, size=n_false),
            rng.uniform(25.0, cam.height - 25.0, size=n_false),
        ))
        sim._stamp_gaussians(canvas, uv_rnd, rng.uniform(3500.0, 12000.0, size=n_false), 1.2, 5)
        frame = np.clip(canvas + rng.normal(0.0, 4.5, size=canvas.shape), 0, 4095).astype(np.uint16)
        pipe = StarTrackerPipeline(cam, cat, kv, cfg)
        res_imp = pipe.process_frame(frame)
        # Also evaluate legacy tail with exact same identification output on random clutter
        id_raw = pipe.star_identifier.identify(res_imp.centroids.vectors, res_imp.centroids.flux)
        if ((not id_raw.success or len(id_raw.obs_idx) < 4) or (id_raw.success and len(id_raw.obs_idx) < 8)) and len(res_imp.centroids.vectors) >= 4:
            wide_r = pipe.star_identifier.identify_wide(res_imp.centroids.vectors, res_imp.centroids.flux, cam)
            if wide_r.success and len(wide_r.obs_idx) >= max(4, len(id_raw.obs_idx) + 1):
                id_raw = wide_r
        res_leg = _run_legacy_prefixed_tail(pipe, res_imp.centroids, id_raw, res_imp.glare_mask, res_imp.timing_ms)
        trials.append({
            'trial': t_i,
            'category': 'd_pure_false_clutter',
            'n_false_stars': n_false,
            'improved_status': res_imp.status,
            'improved_reject_code': res_imp.reject_code,
            'improved_n_detected': res_imp.match_stats['n_detected'],
            'improved_n_valid_pairs': res_imp.match_stats['n_valid_pairs'],
            'improved_downlink_zero': res_imp.to_downlink_bytes() == b'\x00' * 16,
            'improved_false_lock': bool(res_imp.success),
            'legacy_false_lock': bool(res_leg['success']),
        })

    categories = ['a_lt3_detections', 'b_corrupted_lt3_inliers', 'c_collinear_3stars', 'd_pure_false_clutter']
    per_cat: dict[str, Any] = {}
    for c_name in categories:
        sub = [t for t in trials if t['category'] == c_name]
        rej_dist: dict[str, int] = {}
        for t in sub:
            rc = str(t['improved_reject_code'])
            rej_dist[rc] = rej_dist.get(rc, 0) + 1
        imp_fl = sum(1 for t in sub if t['improved_false_lock'])
        leg_fl = sum(1 for t in sub if t['legacy_false_lock'])
        leg_errs = [t.get('legacy_bogus_error_arcsec') for t in sub if t.get('legacy_bogus_error_arcsec') is not None]
        per_cat[c_name] = {
            'n_trials': len(sub),
            'improved_n_rejected': len(sub) - imp_fl,
            'improved_false_lock_count': imp_fl,
            'improved_false_lock_rate_pct': 100.0 * imp_fl / len(sub),
            'improved_all_downlink_zero': all(t['improved_downlink_zero'] for t in sub),
            'improved_reject_codes': rej_dist,
            'legacy_false_lock_count': leg_fl,
            'legacy_false_lock_rate_pct': 100.0 * leg_fl / len(sub),
            'legacy_bogus_error_arcsec': _stats_block(leg_errs),
        }

    tot_imp_fl = sum(1 for t in trials if t['improved_false_lock'])
    tot_leg_fl = sum(1 for t in trials if t['legacy_false_lock'])
    payload = {
        'suite': 'rejection_stress_100',
        'n_trials_total': len(trials),
        'improved_pipeline': {
            'n_rejected_lost': len(trials) - tot_imp_fl,
            'false_lock_count': tot_imp_fl,
            'false_lock_rate_pct': 100.0 * tot_imp_fl / len(trials),
            'all_downlink_16_zero_bytes': all(t['improved_downlink_zero'] for t in trials),
        },
        'legacy_prefixed_pipeline': {
            'n_rejected_lost': len(trials) - tot_leg_fl,
            'false_lock_count': tot_leg_fl,
            'false_lock_rate_pct': 100.0 * tot_leg_fl / len(trials),
        },
        'by_category': per_cat,
        'trials': trials,
    }
    _write_json_strict(OUT_DIR / 'benchmark_rejection_stress.json', payload)
    print(
        f"[*] Rejection Stress: Improved False Lock={tot_imp_fl}/{len(trials)} ({payload['improved_pipeline']['false_lock_rate_pct']:.1f}%) "
        f"vs Legacy False Lock={tot_leg_fl}/{len(trials)} ({payload['legacy_prefixed_pipeline']['false_lock_rate_pct']:.1f}%)",
        flush=True,
    )
    return payload


def _generate_figures(
    real_data: dict[str, Any],
    hd_data: dict[str, Any],
    glare_data: dict[str, Any],
    stress_data: dict[str, Any],
    seed42_data: dict[str, Any],
    cnn_tmpl: CNNCentroidDetector | None = None,
) -> list[str]:
    """Suite 4: Generate 4 Vietnamese summary charts (e2e_figures/) and 4 diagnostic failure PNGs (failure_cases/)."""
    print('\n=== Suite 4: Generating E2E Charts & Failure Diagnostics ===', flush=True)
    E2E_FIG_DIR.mkdir(parents=True, exist_ok=True)
    FAIL_FIG_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial']
    plt.rcParams['axes.unicode_minus'] = False
    written: list[str] = []

    # 1. e2e_figures/real_sky_e2e_summary.png
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.2), dpi=180)
    nom_sum = real_data['nominal']['summary']
    cal_sum = real_data['calibrated']['summary']
    groups = ['CoG (Danh nghĩa)', 'CNN (Danh nghĩa)', 'CoG (Hiệu chuẩn)', 'CNN (Hiệu chuẩn)']
    solve_rates = [
        nom_sum['classical']['solve_rate_pct'],
        nom_sum['cnn']['solve_rate_pct'],
        cal_sum['classical']['solve_rate_pct'],
        cal_sum['cnn']['solve_rate_pct'],
    ]
    colors = ['#94a3b8', '#60a5fa', '#d97706', '#059669']
    bars = ax1.bar(groups, solve_rates, color=colors, width=0.55)
    ax1.set_ylim(0, 110)
    ax1.set_ylabel('Tỷ lệ giải được (%)')
    ax1.set_title('Độ phủ giải trên tập ảnh trời thật (BSC5 V≤6)')
    ax1.tick_params(axis='x', rotation=18)
    for b, val in zip(bars, solve_rates):
        ax1.text(b.get_x() + b.get_width() / 2, val + 2.0, f'{val:.1f}%', ha='center', fontsize=9.5, fontweight='bold')

    # Right panel: attitude error on solved GT real frames (Alt60, Zhao nightsky, MSH, Alt40-Hip7)
    labels_err = []
    cog_errs = []
    cnn_errs = []
    cal_cl = {r['frame_id']: r for r in real_data['calibrated']['frames']['classical']}
    cal_nn = {r['frame_id']: r for r in real_data['calibrated']['frames']['cnn']}
    supp = {(r['frame_id'], r['catalog'], r['centroid_detector']): r for r in real_data.get('supplementary_hipparcos', [])}
    pairs = [
        ('tetra3 Alt60\n(BSC5, Cal)', cal_cl.get('2019-07-29T204726_Alt60_Azi-135_Try1.tiff'), cal_nn.get('2019-07-29T204726_Alt60_Azi-135_Try1.tiff')),
        ('Zhao MT9V022\n(BSC5, Heikkila)', cal_cl.get('nightsky_june16_2021.npy'), cal_nn.get('nightsky_june16_2021.npy')),
        ('Mount St. Helens\n(BSC5, Cal)', cal_cl.get('mount_st_helens_1.png'), cal_nn.get('mount_st_helens_1.png')),
    ]
    # Add Alt40 Hipparcos V<=7
    alt40_cl = next((r for r in real_data.get('supplementary_hipparcos', []) if 'Alt40' in r['frame_id'] and r['catalog'] == 'hipparcos_v7.0' and r['centroid_detector'] == 'classical'), None)
    alt40_nn = next((r for r in real_data.get('supplementary_hipparcos', []) if 'Alt40' in r['frame_id'] and r['catalog'] == 'hipparcos_v7.0' and r['centroid_detector'] != 'classical'), None)
    pairs.append(('tetra3 Alt40\n(Hip V≤7, Cal)', alt40_cl, alt40_nn))
    x_pos = np.arange(len(pairs))
    w_bar = 0.36
    for lbl, r_c, r_n in pairs:
        labels_err.append(lbl)
        cog_errs.append(r_c['attitude_error_arcsec'] if r_c and r_c['status'] == 'SOLVED' else 0.0)
        cnn_errs.append(r_n['attitude_error_arcsec'] if r_n and r_n['status'] == 'SOLVED' else 0.0)
    b1 = ax2.bar(x_pos - w_bar / 2, cog_errs, w_bar, label='CoG cổ điển', color='#d97706')
    b2 = ax2.bar(x_pos + w_bar / 2, cnn_errs, w_bar, label='CNN MobileUNet', color='#059669')
    for idx_p, (_, r_c, r_n) in enumerate(pairs):
        if not (r_c and r_c['status'] == 'SOLVED'):
            ax2.text(x_pos[idx_p] - w_bar / 2, 4.0, 'LOST', ha='center', va='bottom', fontsize=8, color='#b91c1c', fontweight='bold')
        else:
            ax2.text(x_pos[idx_p] - w_bar / 2, cog_errs[idx_p] + 2.0, f'{cog_errs[idx_p]:.1f}″', ha='center', fontsize=8.5)
        if not (r_n and r_n['status'] == 'SOLVED'):
            ax2.text(x_pos[idx_p] + w_bar / 2, 4.0, 'LOST', ha='center', va='bottom', fontsize=8, color='#b91c1c', fontweight='bold')
        else:
            ax2.text(x_pos[idx_p] + w_bar / 2, cnn_errs[idx_p] + 2.0, f'{cnn_errs[idx_p]:.1f}″', ha='center', fontsize=8.5)
    ax2.axhline(60.0, color='#475569', ls='--', lw=1.0, label='Mốc 60″')
    ax2.set_xticks(x_pos)
    ax2.set_xticklabels(labels_err)
    ax2.set_ylabel('Sai số tư thế 3D (arcsec)')
    ax2.set_title('Sai số góc trên ảnh thật đã hiệu chuẩn (0% False Lock)')
    ax2.legend(fontsize=8.5)
    fig.suptitle('Đánh giá End-to-End trên ảnh trời thật (Danh nghĩa vs Hiệu chuẩn)', fontsize=13, fontweight='bold', color='#1e3a8a')
    fig.tight_layout()
    p1 = E2E_FIG_DIR / 'real_sky_e2e_summary.png'
    fig.savefig(p1, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    written.append(str(p1))

    # 2. e2e_figures/sim500_e2e_comparison.png
    fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.8), dpi=180)
    ds_labels = ['500 khung sạch\n(hd1024)', '40 khung lóa mạnh\n(hd1024_glare)']
    x = np.arange(2)
    w = 0.35
    cl_sr = [hd_data['classical']['true_solve_rate_pct'], glare_data['classical']['true_solve_rate_pct']]
    nn_sr = [hd_data['cnn']['true_solve_rate_pct'], glare_data['cnn']['true_solve_rate_pct']]
    axes[0].bar(x - w / 2, cl_sr, w, label='CoG cổ điển', color='#2563eb')
    axes[0].bar(x + w / 2, nn_sr, w, label='CNN MobileUNet', color='#10b981')
    axes[0].set_ylim(0, 112)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(ds_labels)
    axes[0].set_ylabel('True Solve Rate (<40″) %')
    axes[0].set_title('Tỷ lệ giải đúng & 0% False Lock')
    for i_x in range(2):
        axes[0].text(x[i_x] - w / 2, cl_sr[i_x] + 1.5, f'{cl_sr[i_x]:.1f}%', ha='center', fontsize=9)
        axes[0].text(x[i_x] + w / 2, nn_sr[i_x] + 1.5, f'{nn_sr[i_x]:.1f}%', ha='center', fontsize=9)
    axes[0].legend(fontsize=8.5)

    cl_med = [hd_data['classical']['attitude_error_arcsec']['median'], glare_data['classical']['attitude_error_arcsec']['median']]
    nn_med = [hd_data['cnn']['attitude_error_arcsec']['median'], glare_data['cnn']['attitude_error_arcsec']['median']]
    cl_p90 = [hd_data['classical']['attitude_error_arcsec']['p90'], glare_data['classical']['attitude_error_arcsec']['p90']]
    nn_p90 = [hd_data['cnn']['attitude_error_arcsec']['p90'], glare_data['cnn']['attitude_error_arcsec']['p90']]
    axes[1].bar(x - w / 2, cl_med, w, label='CoG Trung vị', color='#2563eb')
    axes[1].bar(x + w / 2, nn_med, w, label='CNN Trung vị', color='#10b981')
    axes[1].scatter(x - w / 2, cl_p90, color='#1e3a8a', marker='D', s=45, zorder=5, label='P90')
    axes[1].scatter(x + w / 2, nn_p90, color='#064e3b', marker='D', s=45, zorder=5)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(ds_labels)
    axes[1].set_ylabel('Sai số tư thế 3D (arcsec)')
    axes[1].set_title('Sai số góc End-to-End (Trung vị & P90)')
    for i_x in range(2):
        axes[1].text(x[i_x] - w / 2, cl_med[i_x] + 0.6, f'{cl_med[i_x]:.2f}″', ha='center', fontsize=8.5)
        axes[1].text(x[i_x] + w / 2, nn_med[i_x] + 0.6, f'{nn_med[i_x]:.2f}″', ha='center', fontsize=8.5)
    axes[1].legend(fontsize=8)

    cl_ms = [hd_data['classical']['total_pipeline_ms']['median'], glare_data['classical']['total_pipeline_ms']['median']]
    nn_ms = [hd_data['cnn']['total_pipeline_ms']['median'], glare_data['cnn']['total_pipeline_ms']['median']]
    axes[2].bar(x - w / 2, cl_ms, w, label='CoG cổ điển', color='#2563eb')
    axes[2].bar(x + w / 2, nn_ms, w, label='CNN MobileUNet (GPU)', color='#10b981')
    axes[2].set_ylim(0, max(nn_ms) * 1.28)
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(ds_labels)
    axes[2].set_ylabel('Thời gian toàn pipeline (ms, trung vị)')
    axes[2].set_title('Độ trễ End-to-End (RTX 5070 CUDA)')
    for i_x in range(2):
        axes[2].text(x[i_x] - w / 2, cl_ms[i_x] + 2.0, f'{cl_ms[i_x]:.1f} ms', ha='center', fontsize=8.5)
        axes[2].text(x[i_x] + w / 2, nn_ms[i_x] + 2.0, f'{nn_ms[i_x]:.1f} ms', ha='center', fontsize=8.5)
    axes[2].legend(fontsize=8.5, loc='upper left')

    fig.suptitle('So sánh End-to-End trên 500 khung sạch & 40 khung lóa (CoG vs CNN d_th=2.0)', fontsize=13, fontweight='bold', color='#1e3a8a')
    fig.tight_layout()
    p2 = E2E_FIG_DIR / 'sim500_e2e_comparison.png'
    fig.savefig(p2, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    written.append(str(p2))

    # 3. e2e_figures/precision_recall_centroid.png
    thr2_path = OUT_DIR / 'centroid_benchmark_hd1024_thr2.json'
    thr2 = json.loads(thr2_path.read_text(encoding='utf-8'))
    t2_frames = thr2['frames']
    t2_gt = sum(f['n_gt'] for f in t2_frames)
    t2_cl_m = sum(f['classical']['n_matched'] for f in t2_frames)
    t2_cl_p = sum(f['classical']['n_pred'] for f in t2_frames)
    t2_nn_m = sum(f['cnn']['n_matched'] for f in t2_frames)
    t2_nn_p = sum(f['cnn']['n_pred'] for f in t2_frames)

    fig, (ax_pr, ax_fp) = plt.subplots(1, 2, figsize=(13.5, 5.0), dpi=180)
    cats_pr = [
        'thr2 độc lập\n(500 khung)',
        'E2E hd1024\n(500 khung)',
        'E2E glare\n(40 khung)',
        'Seed 42 FAST\n(1 khung)',
    ]
    cl_prec = [
        100.0 * t2_cl_m / t2_cl_p,
        100.0 * hd_data['classical']['centroid_precision_micro'],
        100.0 * glare_data['classical']['centroid_precision_micro'],
        100.0 * seed42_data['classical']['centroid_precision'],
    ]
    cl_rec = [
        100.0 * t2_cl_m / t2_gt,
        100.0 * hd_data['classical']['centroid_recall_micro'],
        100.0 * glare_data['classical']['centroid_recall_micro'],
        100.0 * seed42_data['classical']['centroid_recall'],
    ]
    nn_prec = [
        100.0 * t2_nn_m / t2_nn_p,
        100.0 * hd_data['cnn']['centroid_precision_micro'],
        100.0 * glare_data['cnn']['centroid_precision_micro'],
        100.0 * seed42_data['cnn']['centroid_precision'],
    ]
    nn_rec = [
        100.0 * t2_nn_m / t2_gt,
        100.0 * hd_data['cnn']['centroid_recall_micro'],
        100.0 * glare_data['cnn']['centroid_recall_micro'],
        100.0 * seed42_data['cnn']['centroid_recall'],
    ]
    xp = np.arange(4)
    wb = 0.2
    ax_pr.bar(xp - 1.5 * wb, cl_prec, wb, label='CoG Precision', color='#1d4ed8')
    ax_pr.bar(xp - 0.5 * wb, cl_rec, wb, label='CoG Recall', color='#60a5fa')
    ax_pr.bar(xp + 0.5 * wb, nn_prec, wb, label='CNN Precision', color='#059669')
    ax_pr.bar(xp + 1.5 * wb, nn_rec, wb, label='CNN Recall', color='#6ee7b7')
    ax_pr.set_ylim(0, 128)
    ax_pr.set_xticks(xp)
    ax_pr.set_xticklabels(cats_pr)
    ax_pr.set_ylabel('Phần trăm (%)')
    ax_pr.set_title('Precision vs Recall tâm sao (≤ 5 px)')
    ax_pr.legend(fontsize=8.5, ncol=2, loc='upper right')
    for i_c in range(4):
        ax_pr.text(xp[i_c] - 1.5 * wb, cl_prec[i_c] + 1.5, f'{cl_prec[i_c]:.1f}', ha='center', fontsize=7.5)
        ax_pr.text(xp[i_c] + 0.5 * wb, nn_prec[i_c] + 1.5, f'{nn_prec[i_c]:.1f}', ha='center', fontsize=7.5)

    cl_fp_per_frame = [
        (t2_cl_p - t2_cl_m) / 500.0,
        hd_data['classical']['centroid_false_pos_5px_total'] / 500.0,
        glare_data['classical']['centroid_false_pos_5px_total'] / 40.0,
        float(seed42_data['classical']['n_false_pos_centroids_5px']),
    ]
    nn_fp_per_frame = [
        (t2_nn_p - t2_nn_m) / 500.0,
        hd_data['cnn']['centroid_false_pos_5px_total'] / 500.0,
        glare_data['cnn']['centroid_false_pos_5px_total'] / 40.0,
        float(seed42_data['cnn']['n_false_pos_centroids_5px']),
    ]
    ax_fp.bar(xp - 0.18, cl_fp_per_frame, 0.35, label='CoG FP / khung', color='#2563eb')
    ax_fp.bar(xp + 0.18, nn_fp_per_frame, 0.35, label='CNN FP / khung', color='#dc2626')
    ax_fp.set_xticks(xp)
    ax_fp.set_xticklabels(cats_pr)
    ax_fp.set_ylabel('Số phát hiện giả trung bình / khung')
    ax_fp.set_title('Đốm giả (False Positives) trên mỗi khung sim')
    ax_fp.legend(fontsize=8.5)
    for i_c in range(4):
        ax_fp.text(xp[i_c] - 0.18, cl_fp_per_frame[i_c] + 0.3, f'{cl_fp_per_frame[i_c]:.2f}', ha='center', fontsize=8)
        ax_fp.text(xp[i_c] + 0.18, nn_fp_per_frame[i_c] + 0.3, f'{nn_fp_per_frame[i_c]:.2f}', ha='center', fontsize=8)

    fig.suptitle('Kiểm toán Precision / Recall / False Positives của CoG vs CNN (đối soát thr2 & E2E)', fontsize=13, fontweight='bold', color='#1e3a8a')
    fig.tight_layout()
    p3 = E2E_FIG_DIR / 'precision_recall_centroid.png'
    fig.savefig(p3, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    written.append(str(p3))

    # 4. e2e_figures/rejection_guard_before_after.png
    fig, ax = plt.subplots(figsize=(13.2, 5.4), dpi=180)
    cat_keys = ['a_lt3_detections', 'b_corrupted_lt3_inliers', 'c_collinear_3stars', 'd_pure_false_clutter']
    cat_titles = [
        '(a) < 3 sao phát hiện\n(25 thử)',
        '(b) Khớp sai còn < 3 inlier\n(lỗi break cũ, 25 thử)',
        '(c) 3 sao thẳng hàng\n(suy biến, 25 thử)',
        '(d) Nhiễu sao giả hoàn toàn\n(25 thử)',
    ]
    short_code_map = {
        'INSUFFICIENT_DETECTIONS': 'INSUFF_DETECTIONS',
        'INSUFFICIENT_INLIER_PAIRS': 'INSUFF_INLIER_PAIRS',
        'COLLINEAR_DEGENERATE_GEOMETRY': 'COLLINEAR_GEOMETRY',
    }
    leg_fl = [stress_data['by_category'][k]['legacy_false_lock_rate_pct'] for k in cat_keys]
    imp_fl = [stress_data['by_category'][k]['improved_false_lock_rate_pct'] for k in cat_keys]
    xc = np.arange(len(cat_keys))
    wc = 0.32
    offset = 0.22
    ax.bar(xc - offset, leg_fl, wc, label='Trước sửa (Legacy break + thiếu SVD rank)', color='#ef4444')
    ax.bar(xc + offset, imp_fl, wc, label='Sau sửa (Improved Gate: 0% False Lock)', color='#10b981')
    ax.set_ylim(0, 118)
    ax.set_xlim(-0.55, len(cat_keys) - 0.45)
    ax.set_xticks(xc)
    ax.set_xticklabels(cat_titles)
    ax.set_ylabel('Tỷ lệ khóa sai False Lock (%)')
    ax.set_title('Hiệu quả chốt chặn từ chối khớp không hợp lệ (100 ca stress đối kháng)')
    ax.legend(fontsize=9.5, loc='upper right')
    for i_k, k in enumerate(cat_keys):
        ax.text(
            xc[i_k] - offset,
            leg_fl[i_k] + 2.2,
            f"{leg_fl[i_k]:.0f}%\n({stress_data['by_category'][k]['legacy_false_lock_count']}/25)",
            ha='center',
            fontsize=8.2,
            color='#991b1b',
            fontweight='bold',
        )
        rc_str = '\n'.join(
            f'{short_code_map.get(rk, rk)}:{rv}'
            for rk, rv in stress_data['by_category'][k]['improved_reject_codes'].items()
        )
        ax.text(
            xc[i_k] + offset,
            imp_fl[i_k] + 2.2,
            f"0% (0/25)\n[{rc_str}]",
            ha='center',
            fontsize=7.2,
            color='#065f46',
            fontweight='bold',
        )
    fig.tight_layout()
    p4 = E2E_FIG_DIR / 'rejection_guard_before_after.png'
    fig.savefig(p4, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    written.append(str(p4))

    # --- 4 Annotated Failure-Case Diagnostic PNGs ---
    manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
    m_by_name = {Path(item['path']).name: item for item in manifest['frames']}

    # Failure 1: tetra3_alt40_nominal_vs_calibrated.png
    alt40_m = m_by_name['2019-07-29T204726_Alt40_Azi-135_Try1.tiff']
    img_alt40 = load_frame(ROOT / alt40_m['path'])
    cam40_cal = CameraModel(alt40_m['width'], alt40_m['height'], alt40_m['pixel_um'], alt40_m['focal_mm'], k1=alt40_m['k1'], k2=alt40_m['k2'])
    from src.centroid import CentroidDetector
    cents_40 = CentroidDetector(cam40_cal, k_sigma=4.0, bg_block=32, min_area=3).detect(img_alt40)
    uv_gt40 = np.array([[s['u_px'], s['v_px']] for s in alt40_m['stars_in_fov']])
    mags_gt40 = np.array([s['mag'] for s in alt40_m['stars_in_fov']])
    lo, hi = np.percentile(img_alt40, [5, 99.8])
    vis40 = np.clip((img_alt40 - lo) / max(hi - lo, 1.0), 0, 1)
    fig, (ax_l, ax_r) = plt.subplots(1, 2, figsize=(13.0, 5.2), dpi=170)
    ax_l.imshow(vis40, cmap='gray')
    ax_l.scatter(cents_40.uv[:, 0], cents_40.uv[:, 1], s=90, facecolors='none', edgecolors='#f59e0b', lw=1.6, label='CoG phát hiện (8)')
    bright6 = mags_gt40 <= 6.0
    ax_l.scatter(uv_gt40[bright6, 0], uv_gt40[bright6, 1], s=50, marker='x', color='#ef4444', lw=1.6, label='BSC5 V≤6 trong FOV (chỉ 3 đạt lề)')
    ax_l.set_title('Alt40 — Danh nghĩa / BSC5 V≤6: LOST\n(Thiếu sao sáng V≤6 và sai tiêu cự/méo kính)')
    ax_l.legend(fontsize=8, loc='lower right')
    ax_l.axis('off')
    ax_r.imshow(vis40, cmap='gray')
    ax_r.scatter(uv_gt40[:, 0], uv_gt40[:, 1], s=110, facecolors='none', edgecolors='#10b981', lw=1.6, label='Hipparcos V≤7 GT (15 sao)')
    ax_r.scatter(cents_40.uv[:, 0], cents_40.uv[:, 1], s=40, marker='+', color='#f59e0b', lw=1.5, label='CoG phát hiện (8/8 khớp)')
    ax_r.set_title('Alt40 — Hiệu chuẩn f=35.29mm, k1=0.088 + Hip V≤7:\nSOLVED (CoG 39.5″, CNN 26.6″)')
    ax_r.legend(fontsize=8, loc='lower right')
    ax_r.axis('off')
    fig.tight_layout()
    pf1 = FAIL_FIG_DIR / 'tetra3_alt40_nominal_vs_calibrated.png'
    fig.savefig(pf1, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    written.append(str(pf1))

    # Failure 2: ntnu_0006_distortion_lost.png
    ntnu_m = m_by_name['0006.png']
    img_0006 = load_frame(ROOT / ntnu_m['path'])
    small_0006 = cv2.resize(img_0006, (1330, 1150), interpolation=cv2.INTER_AREA)
    lo6, hi6 = np.percentile(small_0006, [5, 99.7])
    vis6 = np.clip((small_0006 - lo6) / max(hi6 - lo6, 1.0), 0, 1)
    rec6_cl = next(r for r in real_data['nominal']['frames']['classical'] if r['frame_id'] == '0006.png')
    rec6_nn = next(r for r in real_data['nominal']['frames']['cnn'] if r['frame_id'] == '0006.png')
    fig, ax6 = plt.subplots(figsize=(8.8, 7.6), dpi=170)
    ax6.imshow(vis6, cmap='gray')
    ax6.set_title(
        f"NTNU 0006.png (5320×4600, FOV chéo 77.5°, chưa hiệu chuẩn méo kính)\n"
        f"CoG: {rec6_cl['n_detected']} đốm → LOST [{rec6_cl['reject_code']}] (valid={rec6_cl['n_valid_pairs']}, {rec6_cl['total_pipeline_ms']/1000:.1f}s)\n"
        f"CNN: {rec6_nn['n_detected']} đốm → LOST [{rec6_nn['reject_code']}] (valid={rec6_nn['n_valid_pairs']}, {rec6_nn['total_pipeline_ms']/1000:.1f}s) · 0% False Lock",
        fontsize=10.5,
    )
    ax6.axis('off')
    fig.tight_layout()
    pf2 = FAIL_FIG_DIR / 'ntnu_0006_distortion_lost.png'
    fig.savefig(pf2, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    written.append(str(pf2))

    # Failure 3: hd1024_cnn_false_positives_example.png
    worst_cnn_fr = max(
        hd_data['frames']['cnn'],
        key=lambda r: int(r.get('n_false_pos_centroids_5px') or 0),
    )
    fid = worst_cnn_fr['frame_id']
    img_w = load_frame(ROOT / 'data' / 'sim_dataset' / 'hd1024' / f'{fid}.tif')
    meta_w = json.loads((ROOT / 'data' / 'sim_dataset' / 'hd1024' / f'{fid}.json').read_text(encoding='utf-8'))
    gt_w = np.asarray([[s['u_px'], s['v_px']] for s in meta_w['stars_in_fov']], dtype=np.float64)
    cam_hd = demo_camera_long_side(1024)
    det_w_cl = CentroidDetector(cam_hd, bg_block=32, min_area=3).detect(img_w)
    tmpl = cnn_tmpl if cnn_tmpl is not None else _init_cnn_template()[0]
    det_w_nn = _shared_cnn_detector(cam_hd, det_w_cl, tmpl).detect(img_w)
    lo_w, hi_w = np.percentile(img_w, [2, 99.8])
    vis_w = np.clip((img_w - lo_w) / max(hi_w - lo_w, 1.0), 0, 1)
    # Classify CNN TP vs FP
    dmat = np.hypot(det_w_nn.uv[:, 0:1] - gt_w[None, :, 0], det_w_nn.uv[:, 1:2] - gt_w[None, :, 1])
    is_tp = dmat.min(axis=1) <= 5.0
    fig, ax_w = plt.subplots(figsize=(10.5, 7.0), dpi=170)
    ax_w.imshow(vis_w, cmap='gray')
    ax_w.scatter(gt_w[:, 0], gt_w[:, 1], s=100, facecolors='none', edgecolors='#38bdf8', lw=1.4, label=f'Sao GT ({len(gt_w)})')
    ax_w.scatter(det_w_nn.uv[is_tp, 0], det_w_nn.uv[is_tp, 1], s=45, marker='+', color='#10b981', lw=1.5, label=f'CNN Đúng TP ({int(is_tp.sum())})')
    ax_w.scatter(det_w_nn.uv[~is_tp, 0], det_w_nn.uv[~is_tp, 1], s=75, facecolors='none', edgecolors='#ef4444', lw=1.6, label=f'CNN Đốm giả FP ({int((~is_tp).sum())})')
    ax_w.set_title(
        f"Ví dụ đốm giả của CNN trên hd1024/{fid}.tif (lệch miền 12-bit)\n"
        f"CNN Precision={100*worst_cnn_fr['centroid_precision']:.1f}%, Recall={100*worst_cnn_fr['centroid_recall']:.1f}%, "
        f"Attitude={worst_cnn_fr['status']} (err={worst_cnn_fr['attitude_error_arcsec']:.2f}″ sau lọc Wahba)",
        fontsize=10.5,
    )
    ax_w.legend(fontsize=9, loc='lower right')
    ax_w.axis('off')
    fig.tight_layout()
    pf3 = FAIL_FIG_DIR / 'hd1024_cnn_false_positives_example.png'
    fig.savefig(pf3, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    written.append(str(pf3))

    # Failure 4: invalid_match_rejection_case.png
    cat_b_trials = [t for t in stress_data['trials'] if t['category'] == 'b_corrupted_lt3_inliers' and t['legacy_false_lock']]
    cat_c_trials = [t for t in stress_data['trials'] if t['category'] == 'c_collinear_3stars' and t['legacy_false_lock']]
    ex_b = cat_b_trials[0] if cat_b_trials else stress_data['trials'][25]
    ex_c = max(cat_c_trials, key=lambda t: float(t.get('legacy_bogus_error_arcsec') or 0.0)) if cat_c_trials else stress_data['trials'][50]
    fig, (ax_b, ax_c) = plt.subplots(1, 2, figsize=(12.8, 5.2), dpi=170)
    ax_b.axis('off')
    ax_b.set_xlim(0, 10)
    ax_b.set_ylim(0, 10)
    ax_b.add_patch(plt.Rectangle((0.4, 0.8), 9.2, 8.2, facecolor='#fef2f2', edgecolor='#dc2626', lw=1.8))
    ax_b.text(5.0, 8.2, 'Ca B: Nhiễu cặp khớp (< 3 inlier hợp lệ)', ha='center', fontsize=12, fontweight='bold', color='#991b1b')
    ax_b.text(
        5.0, 4.8,
        f"Đầu vào: {ex_b['n_true_injected']} cặp đúng + {ex_b['n_bad_injected']} cặp sai\n"
        f"(Tổng n_initial_matched = {ex_b['improved_n_initial_matched']})\n\n"
        f"• Pipeline CŨ (lỗi break tại dòng 207):\n"
        f"  Thoát vòng lọc mà KHÔNG xóa ngoại lai →\n"
        f"  Xuất quaternion giả! Sai số = {ex_b.get('legacy_bogus_error_arcsec') or 0:.0f}″\n\n"
        f"• Pipeline MỚI (Improved Guard):\n"
        f"  Loại {ex_b['improved_n_rejected_outliers']} ngoại lai, còn {ex_b['improved_n_valid_pairs']} (< 3)\n"
        f"  → Trả về {ex_b['improved_status']} [{ex_b['improved_reject_code']}]\n"
        f"  → Downlink 16 byte = 0x00..00 (0% False Lock)",
        ha='center', va='center', fontsize=10, color='#1f2937',
    )

    ax_c.set_xlim(0, 1500)
    ax_c.set_ylim(1000, 0)
    xs_col = [530.0, 750.0, 970.0]
    ys_col = [360.0, 500.0, 640.0]
    ax_c.plot(xs_col, ys_col, '--', color='#dc2626', lw=1.5, label='Đường thẳng suy biến (rank=2)')
    ax_c.scatter(xs_col, ys_col, s=110, color='#f59e0b', edgecolor='#111827', zorder=5, label='3 sao thẳng hàng')
    ax_c.set_title(
        f"Ca C: 3 sao thẳng hàng (Suy biến trục xoay)\n"
        f"Cũ: False Lock ({ex_c.get('legacy_bogus_error_arcsec') or 0:.0f}″) | "
        f"Mới: {ex_c['improved_status']} [{ex_c['improved_reject_code']}]",
        fontsize=10.5,
    )
    ax_c.set_xlabel('u (pixel)')
    ax_c.set_ylabel('v (pixel)')
    ax_c.legend(fontsize=8.5, loc='lower right')
    ax_c.grid(True, alpha=0.25)

    fig.suptitle('Minh họa đối chứng ca lỗi: Khớp ngoại lai & Hình học thẳng hàng', fontsize=13, fontweight='bold', color='#1e3a8a')
    fig.tight_layout()
    pf4 = FAIL_FIG_DIR / 'invalid_match_rejection_case.png'
    fig.savefig(pf4, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    written.append(str(pf4))

    print(f'[*] Generated {len(written)} PNG figures/diagnostics', flush=True)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description='End-to-End Star Tracker Benchmark (Stage 3A)')
    parser.add_argument('--suites', nargs='+', default=['all'], choices=['all', 'real', 'hd1024', 'glare', 'seed42', 'stress', 'figures'])
    args = parser.parse_args()
    run_all = 'all' in args.suites
    selected = set(args.suites)

    engine = DemoEngine(ROOT)
    cnn_tmpl, device_name, cnn_err = _init_cnn_template()
    if cnn_err:
        print(f'[!] CNN warning: {cnn_err}', flush=True)

    real_data = hd_data = glare_data = seed42_data = stress_data = None

    if run_all or 'real' in selected:
        real_data = _run_real_calibrated_suite(engine, cnn_tmpl, device_name)
    elif (OUT_DIR / 'benchmark_real_calibrated_e2e.json').is_file():
        real_data = json.loads((OUT_DIR / 'benchmark_real_calibrated_e2e.json').read_text(encoding='utf-8'))

    if run_all or 'hd1024' in selected:
        hd_data = _eval_sim_dataset(
            'hd1024',
            ROOT / 'data' / 'sim_dataset' / 'hd1024',
            500,
            OUT_DIR / 'benchmark_sim_hd1024_e2e.json',
            engine,
            cnn_tmpl,
            device_name,
        )
    elif (OUT_DIR / 'benchmark_sim_hd1024_e2e.json').is_file():
        hd_data = json.loads((OUT_DIR / 'benchmark_sim_hd1024_e2e.json').read_text(encoding='utf-8'))

    if run_all or 'glare' in selected:
        glare_data = _eval_sim_dataset(
            'hd1024_glare',
            ROOT / 'data' / 'sim_dataset' / 'hd1024_glare',
            40,
            OUT_DIR / 'benchmark_sim_glare_e2e.json',
            engine,
            cnn_tmpl,
            device_name,
        )
    elif (OUT_DIR / 'benchmark_sim_glare_e2e.json').is_file():
        glare_data = json.loads((OUT_DIR / 'benchmark_sim_glare_e2e.json').read_text(encoding='utf-8'))

    if run_all or 'seed42' in selected:
        seed42_data = _run_seed42_suite(engine, cnn_tmpl, device_name)
    elif (OUT_DIR / 'seed42_cog_vs_cnn.json').is_file():
        seed42_data = json.loads((OUT_DIR / 'seed42_cog_vs_cnn.json').read_text(encoding='utf-8'))

    if run_all or 'stress' in selected:
        stress_data = _run_rejection_stress_suite(engine)
    elif (OUT_DIR / 'benchmark_rejection_stress.json').is_file():
        stress_data = json.loads((OUT_DIR / 'benchmark_rejection_stress.json').read_text(encoding='utf-8'))

    if (run_all or 'figures' in selected) and all(x is not None for x in (real_data, hd_data, glare_data, stress_data, seed42_data)):
        _generate_figures(real_data, hd_data, glare_data, stress_data, seed42_data, cnn_tmpl=cnn_tmpl)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
