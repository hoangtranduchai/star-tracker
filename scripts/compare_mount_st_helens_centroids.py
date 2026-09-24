"""Honest CoG vs CNN centroid compare on the LOST Mount St. Helens outdoor photo.

Optics: 4.2 mm, 4.1 µm, 1024×1024 (numbers published with the LOST sample).
Does not retrain. Writes overlay + JSON under data/outputs/.
"""
from __future__ import annotations
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
from src.demo_session import load_frame
SRC = ROOT / 'data' / 'uploads' / 'mount_st_helens_1.png'
OUT_DIR = ROOT / 'data' / 'outputs'
OVERLAY = OUT_DIR / 'mount_st_helens_cog_vs_cnn.png'
MASK_PNG = OUT_DIR / 'mount_st_helens_terrain_mask.png'
JSON_OUT = OUT_DIR / 'mount_st_helens_centroid_compare.json'

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
    overlay: object = draw_overlay(gray, c_cl.uv, c_nn_uv, mask)
    cv2.imwrite(str(OVERLAY), overlay)
    mask_vis: object = mask.astype(np.uint8) * 255
    cv2.imwrite(str(MASK_PNG), mask_vis)
    summary: object = {'image': str(SRC.relative_to(ROOT)).replace('\\', '/'), 'source_note': 'Ảnh thật công bố kèm LOST (UW), không phải ảnh của nhóm chụp.', 'camera': {'width': cam.width, 'height': cam.height, 'focal_mm': cam.focal_mm, 'pixel_um': cam.pixel_um, 'fov_deg': list(cam.fov_deg)}, 'distance_map_threshold': 2.0, 'device': device_name, 'classical': {**cl_stats, 'time_ms': cl_ms}, 'cnn': {**nn_stats, 'time_ms': nn_ms, 'error': cnn_error}, 'terrain_mask': {'n_px': int(mask.sum()), 'frac': float(mask.mean()), 'method': 'per-column sky→dark ridge drop; fill below envelope (heuristic silhouette)', 'mask_png': str(MASK_PNG.relative_to(ROOT)).replace('\\', '/')}, 'overlay_png': str(OVERLAY.relative_to(ROOT)).replace('\\', '/'), 'claim': 'CoG đánh sao giả trên núi/cây; CNN thì không (hoặc ít hơn rõ).', 'claim_held': claim_held, 'verdict_vi': verdict, 'institution': {'school': 'Trường Đại học Bách khoa, Đại học Đà Nẵng', 'faculty': 'Khoa Công nghệ thông tin'}}
    JSON_OUT.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f'[*] wrote {OVERLAY}')
    print(f'[*] wrote {JSON_OUT}')
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
