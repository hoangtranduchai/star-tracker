#!/usr/bin/env python3
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

from src.camera import CameraModel  # noqa: E402
from src.centroid import CentroidDetector  # noqa: E402
from src.centroid_cnn import CNNCentroidDetector, weights_available  # noqa: E402
from src.demo_session import load_frame  # noqa: E402

SRC = ROOT / "data" / "uploads" / "mount_st_helens_1.png"
OUT_DIR = ROOT / "data" / "outputs"
OVERLAY = OUT_DIR / "mount_st_helens_cog_vs_cnn.png"
MASK_PNG = OUT_DIR / "mount_st_helens_terrain_mask.png"
JSON_OUT = OUT_DIR / "mount_st_helens_centroid_compare.json"


def terrain_mask(gray: np.ndarray) -> np.ndarray:
    """Silhouette mask: mountain / snow / trees below the ridge — not the star field.

    Sky in this LOST photo is *brighter* than the dark tree silhouette. A plain
    darkness threshold therefore paints sky as terrain (the old bug). Instead:
    per column, find the first sustained sky→dark drop (ridge / treeline), then
    mark everything below that envelope as terrain (includes snow patches).
    """
    g = gray.astype(np.float32)
    h, w = g.shape
    blur = cv2.GaussianBlur(g, (0, 0), 2.5)

    ridge = np.zeros(w, dtype=np.int32)
    y0 = int(0.10 * h)
    y1 = int(0.92 * h)
    fallback = int(0.72 * h)
    for x in range(w):
        c = blur[:, x]
        found = fallback
        y = y0
        while y < y1:
            win = c[y : y + 18]
            if win.size < 18:
                break
            # Entering dark silhouette under brighter sky.
            if float(np.mean(win)) < 20.0 and float(np.percentile(win, 80)) < 32.0:
                above = c[max(0, y - 20) : y]
                if above.size > 5 and float(np.median(above)) > 30.0:
                    found = y
                    break
            y += 1
        ridge[x] = found

    ridge_f = ridge.astype(np.float32)
    # Keep tree crowns (local min y) while lightly smoothing the envelope.
    half = 21
    ridge_min = np.empty(w, dtype=np.float32)
    for x in range(w):
        lo, hi = max(0, x - half), min(w, x + half + 1)
        ridge_min[x] = float(ridge_f[lo:hi].min())
    ridge_s = cv2.GaussianBlur(ridge_f.reshape(1, -1), (0, 0), 2.5).ravel()
    ridge_i = np.clip(np.round(0.75 * ridge_min + 0.25 * ridge_s).astype(np.int32), 0, h - 1)

    ys = np.arange(h, dtype=np.int32)[:, None]
    mask = ys >= ridge_i[None, :]
    # Never claim the uppermost sky band.
    mask[: int(0.12 * h), :] = False
    return mask


def classify(uv: np.ndarray, mask: np.ndarray) -> dict:
    if uv is None or len(uv) == 0:
        return {"n_total": 0, "n_on_terrain": 0, "n_on_sky": 0}
    h, w = mask.shape
    on_t = 0
    for u, v in uv:
        ui = int(round(float(u)))
        vi = int(round(float(v)))
        if 0 <= ui < w and 0 <= vi < h and mask[vi, ui]:
            on_t += 1
    n = int(len(uv))
    return {"n_total": n, "n_on_terrain": int(on_t), "n_on_sky": int(n - on_t)}


def draw_overlay(gray: np.ndarray, uv_cl, uv_nn, mask: np.ndarray) -> np.ndarray:
    """Photo + small circles; legend in a bottom strip so it does not cover stars."""
    rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    wash = rgb.astype(np.float32)
    wash[mask] = wash[mask] * 0.62 + np.array([35, 35, 120], dtype=np.float32)
    vis = wash.astype(np.uint8)

    def circles(uv, color, radius):
        if uv is None:
            return
        for u, v in uv:
            cv2.circle(vis, (int(round(float(u))), int(round(float(v)))), radius, color, 1, lineType=cv2.LINE_AA)

    circles(uv_cl, (0, 165, 255), 5)  # orange = classical
    circles(uv_nn, (0, 255, 0), 4)  # green = CNN

    # Caption strip below the photo (does not cover the star field).
    pad = 78
    canvas = np.full((vis.shape[0] + pad, vis.shape[1], 3), 18, dtype=np.uint8)
    canvas[: vis.shape[0]] = vis
    y0 = vis.shape[0] + 18
    cv2.putText(
        canvas,
        "Mau LOST cong bo (khong phai anh nhom) | f=4.2 mm | pixel=4.1 um",
        (12, y0),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (220, 220, 220),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        "Cam: CoG  |  Xanh: CNN MobileUNet  |  Do nhat: nui/tuyet/cay (duoi duong rid)",
        (12, y0 + 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (200, 200, 200),
        1,
        cv2.LINE_AA,
    )
    return canvas


def main() -> int:
    if not SRC.is_file():
        raise SystemExit(f"missing {SRC}")
    # Ensure copy under an_danh uploads (already present; re-copy if needed).
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    gray = load_frame(SRC)
    cam = CameraModel(width=gray.shape[1], height=gray.shape[0], pixel_um=4.1, focal_mm=4.2)
    mask = terrain_mask(gray)

    classical = CentroidDetector(cam, bg_block=31, min_area=3)
    t0 = time.perf_counter()
    c_cl = classical.detect(gray)
    cl_ms = (time.perf_counter() - t0) * 1000.0

    cnn_error = None
    c_nn_uv = np.empty((0, 2), dtype=np.float64)
    nn_ms = None
    device_name = "cpu"
    if not weights_available():
        cnn_error = "chưa kiểm được: thiếu trọng số MobileUNet_B10_50.pt"
    else:
        import torch

        print(
            f"[*] torch={torch.__version__} cuda={torch.cuda.is_available()} "
            f"{torch.cuda.get_device_name(0) if torch.cuda.is_available() else ''}",
            flush=True,
        )
        cnn = CNNCentroidDetector(cam, classical=classical)
        _ = cnn.detect(np.zeros_like(gray))  # warm-up
        t1 = time.perf_counter()
        c_nn = cnn.detect(gray)
        nn_ms = (time.perf_counter() - t1) * 1000.0
        c_nn_uv = c_nn.uv
        device_name = getattr(cnn, "device_name", None) or getattr(cnn, "_device", "cpu")
        print(f"[*] CNN device={device_name} backend={getattr(cnn,'last_backend',None)}", flush=True)

    cl_stats = classify(c_cl.uv, mask)
    nn_stats = classify(c_nn_uv, mask) if cnn_error is None else {"n_total": 0, "n_on_terrain": 0, "n_on_sky": 0, "error": cnn_error}

    claim_held = False
    verdict = "chưa kiểm được"
    if cnn_error is None:
        # Claim: classical marks mountain/trees; CNN does not (or much less).
        cl_t, nn_t = cl_stats["n_on_terrain"], nn_stats["n_on_terrain"]
        if cl_t > 0 and nn_t == 0:
            claim_held = True
            verdict = (
                f"Claim giữ: CoG đánh {cl_t} điểm trên vùng núi/cây ước lượng; "
                f"CNN không đánh điểm nào trên vùng đó (CoG trời {cl_stats['n_on_sky']}, "
                f"CNN trời {nn_stats['n_on_sky']})."
            )
        elif cl_t > nn_t and cl_t >= 3 and (nn_t / max(cl_t, 1)) <= 0.35:
            claim_held = True
            verdict = (
                f"Claim giữ một phần: CoG {cl_t} điểm trên núi/cây vs CNN {nn_t} "
                f"(CoG trời {cl_stats['n_on_sky']}, CNN trời {nn_stats['n_on_sky']})."
            )
        elif cl_t == 0 and nn_t == 0:
            claim_held = False
            verdict = (
                f"Claim không giữ trên ảnh này: cả hai gần như không đánh trên núi/cây "
                f"(CoG núi {cl_t}/tổng {cl_stats['n_total']}; CNN núi {nn_t}/tổng {nn_stats['n_total']})."
            )
        else:
            claim_held = False
            verdict = (
                f"Claim không giữ rõ: CoG núi/cây={cl_t}, CNN núi/cây={nn_t}; "
                f"CoG trời={cl_stats['n_on_sky']}, CNN trời={nn_stats['n_on_sky']}."
            )

    overlay = draw_overlay(gray, c_cl.uv, c_nn_uv, mask)
    cv2.imwrite(str(OVERLAY), overlay)
    mask_vis = (mask.astype(np.uint8) * 255)
    cv2.imwrite(str(MASK_PNG), mask_vis)

    summary = {
        "image": str(SRC.relative_to(ROOT)).replace("\\", "/"),
        "source_note": "Ảnh thật công bố kèm LOST (UW), không phải ảnh của nhóm chụp.",
        "camera": {
            "width": cam.width,
            "height": cam.height,
            "focal_mm": cam.focal_mm,
            "pixel_um": cam.pixel_um,
            "fov_deg": list(cam.fov_deg),
        },
        "distance_map_threshold": 2.0,
        "device": device_name,
        "classical": {**cl_stats, "time_ms": cl_ms},
        "cnn": {**nn_stats, "time_ms": nn_ms, "error": cnn_error},
        "terrain_mask": {
            "n_px": int(mask.sum()),
            "frac": float(mask.mean()),
            "method": "per-column sky→dark ridge drop; fill below envelope (heuristic silhouette)",
            "mask_png": str(MASK_PNG.relative_to(ROOT)).replace("\\", "/"),
        },
        "overlay_png": str(OVERLAY.relative_to(ROOT)).replace("\\", "/"),
        "claim": "CoG đánh sao giả trên núi/cây; CNN thì không (hoặc ít hơn rõ).",
        "claim_held": claim_held,
        "verdict_vi": verdict,
        "institution": {
            "school": "Trường Đại học Bách khoa, Đại học Đà Nẵng",
            "faculty": "Khoa Công nghệ thông tin",
        },
    }
    JSON_OUT.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"[*] wrote {OVERLAY}")
    print(f"[*] wrote {JSON_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
