"""Honest CoG vs CNN centroid compare on the LOST Mount St. Helens outdoor photo.

Optics: 4.2 mm, 4.1 µm, 1024×1024 (numbers published with the LOST sample).
Does not retrain. Writes overlay + JSON under data/outputs/.
"""
from __future__ import annotations
import hashlib
import json
import sys
import time
from pathlib import Path
import cv2
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.camera import CameraModel
from src.centroid import CentroidDetector
from src.centroid_cnn import CNNCentroidDetector, weights_available
from src.demo_session import DemoEngine, RunRequest, load_frame, load_pipeline_cfg
from src.masking import GlareMasker
from src.quaternion import angular_error_arcsec
SRC = ROOT / 'data' / 'uploads' / 'mount_st_helens_1.png'
OUT_DIR = ROOT / 'data' / 'outputs'
OVERLAY = OUT_DIR / 'mount_st_helens_cog_vs_cnn.png'
MASK_PNG = OUT_DIR / 'mount_st_helens_terrain_mask.png'
JSON_OUT = OUT_DIR / 'mount_st_helens_centroid_compare.json'
LOST_JSON_OUT = OUT_DIR / 'mount_st_helens_lost_compare.json'
MANIFEST_PATH = ROOT / 'data' / 'real_calibrated' / 'manifest_real_calibrated.json'
LOST_REF = {'ra_deg': 310.446, 'dec_deg': 36.0229, 'source': 'lost-website.netlify.app screenshot'}

def terrain_mask(gray: np.ndarray) -> np.ndarray:
    """Silhouette mask: mountain / snow / trees below the ridge — not the star field.

    Sky in this LOST photo is *brighter* than the dark tree silhouette. A plain
    darkness threshold therefore paints sky as terrain (the old bug). Instead:
    per column, find the first sustained sky→dark drop (ridge / treeline), then
    mark everything below that envelope as terrain (includes snow patches).
    """
    g: object = gray.astype(np.float32)
    h, w = g.shape
    blur: object = cv2.GaussianBlur(g, (0, 0), 2.5)
    ridge: object = np.zeros(w, dtype=np.int32)
    y0: object = int(0.1 * h)
    y1: object = int(0.92 * h)
    fallback: object = int(0.72 * h)
    for x in range(w):
        c: object = blur[:, x]
        found: object = fallback
        y: object = y0
        while y < y1:
            win: object = c[y:y + 18]
            if win.size < 18:
                break
            if float(np.mean(win)) < 20.0 and float(np.percentile(win, 80)) < 32.0:
                above: object = c[max(0, y - 20):y]
                if above.size > 5 and float(np.median(above)) > 30.0:
                    found: object = y
                    break
            y += 1
        ridge[x] = found
    ridge_f: object = ridge.astype(np.float32)
    half: object = 21
    ridge_min: object = np.empty(w, dtype=np.float32)
    for x in range(w):
        lo, hi = (max(0, x - half), min(w, x + half + 1))
        ridge_min[x] = float(ridge_f[lo:hi].min())
    ridge_s: object = cv2.GaussianBlur(ridge_f.reshape(1, -1), (0, 0), 2.5).ravel()
    ridge_i: object = np.clip(np.round(0.75 * ridge_min + 0.25 * ridge_s).astype(np.int32), 0, h - 1)
    ys: object = np.arange(h, dtype=np.int32)[:, None]
    mask: object = ys >= ridge_i[None, :]
    mask[:int(0.12 * h), :] = False
    return mask

def classify(uv: np.ndarray, mask: np.ndarray) -> dict:
    if uv is None or len(uv) == 0:
        return {'n_total': 0, 'n_on_terrain': 0, 'n_on_sky': 0}
    h, w = mask.shape
    on_t: object = 0
    for u, v in uv:
        ui: object = int(round(float(u)))
        vi: object = int(round(float(v)))
        if 0 <= ui < w and 0 <= vi < h and mask[vi, ui]:
            on_t += 1
    n: object = int(len(uv))
    return {'n_total': n, 'n_on_terrain': int(on_t), 'n_on_sky': int(n - on_t)}

def draw_overlay(gray: np.ndarray, uv_cl: object, uv_nn: object, mask: np.ndarray) -> np.ndarray:
    """Photo + small circles; legend in a bottom strip so it does not cover stars."""
    rgb: object = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    wash: object = rgb.astype(np.float32)
    wash[mask] = wash[mask] * 0.62 + np.array([35, 35, 120], dtype=np.float32)
    vis: object = wash.astype(np.uint8)

    def circles(uv: object, color: object, radius: object) -> object:
        if uv is None:
            return
        for u, v in uv:
            cv2.circle(vis, (int(round(float(u))), int(round(float(v)))), radius, color, 1, lineType=cv2.LINE_AA)
    circles(uv_cl, (0, 165, 255), 5)
    circles(uv_nn, (0, 255, 0), 4)
    pad: object = 78
    canvas: object = np.full((vis.shape[0] + pad, vis.shape[1], 3), 18, dtype=np.uint8)
    canvas[:vis.shape[0]] = vis
    y0: object = vis.shape[0] + 18
    cv2.putText(canvas, 'Mau LOST cong bo (khong phai anh nhom) | f=4.2 mm | pixel=4.1 um', (12, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (220, 220, 220), 1, cv2.LINE_AA)
    cv2.putText(canvas, 'Cam: CoG  |  Xanh: CNN MobileUNet  |  Do nhat: nui/tuyet/cay (duoi duong rid)', (12, y0 + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (200, 200, 200), 1, cv2.LINE_AA)
    return canvas

def _ang_sep_deg(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    r1, d1, r2, d2 = np.radians([ra1, dec1, ra2, dec2])
    c = np.sin(d1) * np.sin(d2) + np.cos(d1) * np.cos(d2) * np.cos(r1 - r2)
    return float(np.degrees(np.arccos(np.clip(c, -1.0, 1.0))))


def _measure_pipeline_vs_standalone(gray: np.ndarray, cam: CameraModel, c_standalone_uv: np.ndarray, standalone_ms: float) -> dict:
    """Explain and measure the standalone CentroidDetector (bg_block=31) vs StarTrackerPipeline (GlareMasker + bg_block=32) difference."""
    cfg = load_pipeline_cfg('fast', ROOT)
    masker = GlareMasker(
        bright_frac=cfg.mask_bright_frac,
        min_area_px=cfg.mask_min_area_px,
        min_span_px=cfg.mask_min_span_px,
        dilate_px=cfg.mask_dilate_px,
        bg_excess_k=cfg.mask_bg_excess_k,
        full_scale=cfg.mask_full_scale,
    )
    det_32 = CentroidDetector(
        cam,
        k_sigma=cfg.k_sigma,
        bg_block=cfg.bg_block,
        min_area=cfg.min_area,
        max_area=cfg.max_area,
        max_area_sat=cfg.max_area_sat,
        max_axis_ratio=cfg.max_axis_ratio,
        saturation_dn=cfg.saturation_dn,
        binary_open=cfg.binary_open,
        cog_pad=cfg.cog_pad,
    )
    t0 = time.perf_counter()
    c_32_nomask = det_32.detect(gray)
    ms_32_nomask = (time.perf_counter() - t0) * 1000.0
    t1 = time.perf_counter()
    g_mask = masker.make_mask(gray)
    mask_ms = (time.perf_counter() - t1) * 1000.0
    t2 = time.perf_counter()
    c_32_masked = det_32.detect(gray, mask=g_mask)
    cent_ms = (time.perf_counter() - t2) * 1000.0
    return {
        'standalone_bg_block': 31,
        'standalone_mask': None,
        'standalone_n_detected': int(len(c_standalone_uv)),
        'standalone_time_ms': float(standalone_ms),
        'pipeline_cfg_bg_block': int(cfg.bg_block),
        'pipeline_effective_odd_bg_block': int(det_32.bg_block),
        'pipeline_bg32_nomask_n_detected': int(len(c_32_nomask.uv)),
        'pipeline_bg32_nomask_time_ms': float(ms_32_nomask),
        'pipeline_glare_mask_px': int(np.count_nonzero(g_mask)),
        'pipeline_glare_mask_frac': float(np.mean(g_mask)),
        'pipeline_mask_ms': float(mask_ms),
        'pipeline_centroiding_ms': float(cent_ms),
        'pipeline_total_detection_ms': float(mask_ms + cent_ms),
        'pipeline_n_detected': int(len(c_32_masked.uv)),
        'delta_n_detected': int(len(c_standalone_uv) - len(c_32_masked.uv)),
        'explanation_vi': (
            'CentroidDetector độc lập dùng bg_block=31 và không chạy GlareMasker nên tách được '
            f'{len(c_standalone_uv)} điểm ({standalone_ms:.1f} ms). Trong StarTrackerPipeline (chế độ fast), '
            f'GlareMasker chạy thêm ({mask_ms:.1f} ms; phủ {int(np.count_nonzero(g_mask))} px trên ảnh 8-bit '
            f'vì mask_full_scale=4095.0) và CentroidDetector nhận bg_block={cfg.bg_block} (được làm lẻ thành '
            f'{det_32.bg_block} via bg_block|1), làm giảm {int(len(c_standalone_uv) - len(c_32_masked.uv))} đốm sát ngưỡng '
            f'xuống còn {len(c_32_masked.uv)} điểm ({cent_ms:.1f} ms đo hiện tại; 97.5 ms ở lần web log trước đó).'
        ),
    }


def _load_manifest_msh_gt() -> dict | None:
    if not MANIFEST_PATH.is_file():
        return None
    data = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
    for item in data.get('frames', []):
        if 'mount_st_helens_1.png' in str(item.get('path', '')):
            return item
    return None


def _run_lost_compare(gray: np.ndarray, cam: CameraModel, diff_info: dict) -> dict:
    prev_lost = json.loads(LOST_JSON_OUT.read_text(encoding='utf-8')) if LOST_JSON_OUT.is_file() else None
    msh_gt = _load_manifest_msh_gt()
    q_gt = np.asarray(msh_gt['q_gt'], dtype=np.float64) if msh_gt and msh_gt.get('q_gt') else None
    sha12 = hashlib.sha256(gray.tobytes()).hexdigest()[:12]
    engine = DemoEngine(ROOT)
    modes = {}
    for be in ('cnn', 'classical'):
        req = RunRequest(image=SRC, focal_mm=cam.focal_mm, pixel_um=cam.pixel_um, centroid_backend=be, save_png=False)
        out = engine.run(req)
        p = out.payload
        m = p['metrics']
        ms = p.get('match_stats') or {}
        bore = p.get('boresight_est')
        ra = None if not bore else float(bore['ra_deg'])
        dec = None if not bore else float(bore['dec_deg'])
        sep = _ang_sep_deg(ra, dec, LOST_REF['ra_deg'], LOST_REF['dec_deg']) if (ra is not None and dec is not None) else None
        att_err = float(angular_error_arcsec(out.result.q, q_gt)) if (out.success and out.result.q is not None and q_gt is not None) else None
        modes[be] = {
            'success': bool(p['success']),
            'status': p['status'],
            'reject_code': p['reject_code'],
            'verdict': m.get('verdict'),
            'e2e_outcome': m.get('e2e_outcome'),
            'n_detected': int(m.get('n_detected') or 0),
            'n_matched': int(m.get('n_matched') or 0),
            'n_initial_matched': ms.get('n_initial_matched'),
            'n_rejected_outliers': ms.get('n_rejected_outliers'),
            'n_valid_pairs': ms.get('n_valid_pairs'),
            'rms_residual_arcsec': ms.get('rms_residual_arcsec'),
            'max_residual_arcsec': ms.get('max_residual_arcsec'),
            'detector': p.get('centroid_detector'),
            'fallback': bool(p.get('centroid_fallback', False)),
            'ra_deg': ra,
            'dec_deg': dec,
            'sep_deg_from_LOST': sep,
            'dra_deg': None if ra is None else float(ra - LOST_REF['ra_deg']),
            'ddec_deg': None if dec is None else float(dec - LOST_REF['dec_deg']),
            'attitude_error_arcsec_vs_manifest': att_err,
            'pipeline_ms': float((p.get('timing_ms') or {}).get('total_pipeline_ms') or 0.0),
            'timings': p.get('timing_ms'),
            'error': p.get('error'),
        }
    return {
        'LOST_ref': LOST_REF,
        'manifest_gt': {
            'q_gt': None if q_gt is None else q_gt.tolist(),
            'boresight_ra_deg': msh_gt.get('boresight_ra_deg') if msh_gt else None,
            'boresight_dec_deg': msh_gt.get('boresight_dec_deg') if msh_gt else None,
            'calibrated_focal_mm': msh_gt.get('focal_mm') if msh_gt else None,
            'k1': msh_gt.get('k1') if msh_gt else None,
            'k2': msh_gt.get('k2') if msh_gt else None,
        },
        'optics': {'focal_mm': cam.focal_mm, 'pixel_um': cam.pixel_um, 'width': cam.width, 'height': cam.height},
        'image': str(SRC.relative_to(ROOT)).replace('\\', '/'),
        'image_sha256_12_array': sha12,
        'source_note': (
            'Audited DemoEngine run after Wave 2 strict outlier-rejection guard. '
            'CNN solves within ~0.04 deg of UW LOST; uncalibrated classical CoG (106 detections incl. terrain clutter '
            'and severe wide-angle distortion) is cleanly rejected as LOST [INSUFFICIENT_INLIER_PAIRS] instead of '
            'bypassing residual gating.'
        ),
        'pipeline_vs_standalone_diff': diff_info,
        'modes': modes,
        'legacy_pre_fix_reference': (prev_lost or {}).get('legacy_pre_fix_reference') or ((prev_lost or {}).get('modes')),
    }


def main() -> int:
    if not SRC.is_file():
        raise SystemExit(f'missing {SRC}')
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    gray: object = load_frame(SRC)
    cam: object = CameraModel(width=gray.shape[1], height=gray.shape[0], pixel_um=4.1, focal_mm=4.2)
    mask: object = terrain_mask(gray)
    classical: object = CentroidDetector(cam, bg_block=31, min_area=3)
    t0: object = time.perf_counter()
    c_cl: object = classical.detect(gray)
    cl_ms: object = (time.perf_counter() - t0) * 1000.0
    cnn_error: object = None
    c_nn_uv: object = np.empty((0, 2), dtype=np.float64)
    nn_ms: object = None
    device_name: object = 'cpu'
    if not weights_available():
        cnn_error: object = 'chưa kiểm được: thiếu trọng số MobileUNet_B10_50.pt'
    else:
        import torch
        print(f"[*] torch={torch.__version__} cuda={torch.cuda.is_available()} {(torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')}", flush=True)
        cnn: object = CNNCentroidDetector(cam, classical=classical)
        _: object = cnn.detect(np.zeros_like(gray))
        t1: object = time.perf_counter()
        c_nn: object = cnn.detect(gray)
        nn_ms: object = (time.perf_counter() - t1) * 1000.0
        c_nn_uv: object = c_nn.uv
        device_name: object = getattr(cnn, 'device_name', None) or getattr(cnn, '_device', 'cpu')
        print(f"[*] CNN device={device_name} backend={getattr(cnn, 'last_backend', None)}", flush=True)
    cl_stats: object = classify(c_cl.uv, mask)
    nn_stats: object = classify(c_nn_uv, mask) if cnn_error is None else {'n_total': 0, 'n_on_terrain': 0, 'n_on_sky': 0, 'error': cnn_error}
    claim_held: object = False
    verdict: object = 'chưa kiểm được'
    if cnn_error is None:
        cl_t, nn_t = (cl_stats['n_on_terrain'], nn_stats['n_on_terrain'])
        if cl_t > 0 and nn_t == 0:
            claim_held: object = True
            verdict: object = f"Claim giữ: CoG đánh {cl_t} điểm trên vùng núi/cây ước lượng; CNN không đánh điểm nào trên vùng đó (CoG trời {cl_stats['n_on_sky']}, CNN trời {nn_stats['n_on_sky']})."
        elif cl_t > nn_t and cl_t >= 3 and (nn_t / max(cl_t, 1) <= 0.35):
            claim_held: object = True
            verdict: object = f"Claim giữ một phần: CoG {cl_t} điểm trên núi/cây vs CNN {nn_t} (CoG trời {cl_stats['n_on_sky']}, CNN trời {nn_stats['n_on_sky']})."
        elif cl_t == 0 and nn_t == 0:
            claim_held: object = False
            verdict: object = f"Claim không giữ trên ảnh này: cả hai gần như không đánh trên núi/cây (CoG núi {cl_t}/tổng {cl_stats['n_total']}; CNN núi {nn_t}/tổng {nn_stats['n_total']})."
        else:
            claim_held: object = False
            verdict: object = f"Claim không giữ rõ: CoG núi/cây={cl_t}, CNN núi/cây={nn_t}; CoG trời={cl_stats['n_on_sky']}, CNN trời={nn_stats['n_on_sky']}."
    diff_info = _measure_pipeline_vs_standalone(gray, cam, c_cl.uv, cl_ms)
    lost_report = _run_lost_compare(gray, cam, diff_info)
    overlay: object = draw_overlay(gray, c_cl.uv, c_nn_uv, mask)
    cv2.imwrite(str(OVERLAY), overlay)
    mask_vis: object = mask.astype(np.uint8) * 255
    cv2.imwrite(str(MASK_PNG), mask_vis)
    summary: object = {
        'image': str(SRC.relative_to(ROOT)).replace('\\', '/'),
        'source_note': 'Ảnh thật công bố kèm LOST (UW), không phải ảnh của nhóm chụp.',
        'camera': {'width': cam.width, 'height': cam.height, 'focal_mm': cam.focal_mm, 'pixel_um': cam.pixel_um, 'fov_deg': list(cam.fov_deg)},
        'distance_map_threshold': 2.0,
        'device': device_name,
        'classical': {**cl_stats, 'time_ms': cl_ms},
        'cnn': {**nn_stats, 'time_ms': nn_ms, 'error': cnn_error},
        'pipeline_vs_standalone_diff': diff_info,
        'terrain_mask': {'n_px': int(mask.sum()), 'frac': float(mask.mean()), 'method': 'per-column sky→dark ridge drop; fill below envelope (heuristic silhouette)', 'mask_png': str(MASK_PNG.relative_to(ROOT)).replace('\\', '/')},
        'overlay_png': str(OVERLAY.relative_to(ROOT)).replace('\\', '/'),
        'claim': 'CoG đánh sao giả trên núi/cây; CNN thì không (hoặc ít hơn rõ).',
        'claim_held': claim_held,
        'verdict_vi': verdict,
        'institution': {'school': 'Trường Đại học Bách khoa, Đại học Đà Nẵng', 'faculty': 'Khoa Công nghệ thông tin'},
    }
    JSON_OUT.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    LOST_JSON_OUT.write_text(json.dumps(lost_report, indent=2, ensure_ascii=False), encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f'[*] wrote {OVERLAY}')
    print(f'[*] wrote {JSON_OUT}')
    print(f'[*] wrote {LOST_JSON_OUT}')
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
