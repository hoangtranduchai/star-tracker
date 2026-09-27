#!/usr/bin/env python3
"""Solve the wide sample frames stored with this folder.

Each frame keeps its own focal length and pixel size. Those numbers are not the demo camera.
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.camera import CameraModel  # noqa: E402
from src.demo_session import load_catalog  # noqa: E402
from src.kvector import build_or_load  # noqa: E402
from src.pipeline_wide_field import WideFieldPipeline  # noqa: E402
from src.quaternion import boresight_ra_dec_deg  # noqa: E402
from src.starnames import describe_index  # noqa: E402
from src.visualize import save_input_png, save_output_png  # noqa: E402

FRAMES = ("0006", "0025", "0044")


def main() -> int:
    cat, synthetic = load_catalog("bsc5", 6.0, ROOT / "data" / "catalogs")
    print(f"catalog {cat.source} n={cat.num_stars} synthetic={synthetic}", flush=True)
    cam = CameraModel(width=5320, height=4600, pixel_um=2.74, focal_mm=12.0)
    h, v, d = cam.fov_deg
    theta_max = min(180.0, math.ceil((d + 0.5) * 2.0 - 1e-9) / 2.0)
    kv = build_or_load(cat, ROOT / "data" / "catalogs", 0.02, theta_max)
    print(
        f"camera {cam.width}x{cam.height} f={cam.focal_mm} mm p={cam.pixel_um} um "
        f"FOV {h:.1f}x{v:.1f} deg diag {d:.1f} ifov {cam.ifov_arcsec:.2f} arcsec",
        flush=True,
    )
    pipe = WideFieldPipeline(cam, cat, kv)
    out_dir = ROOT / "data" / "outputs" / "real_sky_wide"
    out_dir.mkdir(parents=True, exist_ok=True)
    image_dir = ROOT / "data" / "uploads" / "real_sky" / "images"

    for name in FRAMES:
        path = image_dir / f"{name}.png"
        image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if image is None:
            print(f"{name} MISSING {path}", flush=True)
            continue
        if image.ndim == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        print(
            f"{name} shape={image.shape} dtype={image.dtype} "
            f"dn={int(image.min())}..{int(image.max())}",
            flush=True,
        )
        t0 = time.perf_counter()
        result = pipe.process_frame(image)
        dt = time.perf_counter() - t0
        n_det = 0 if result.centroids is None else len(result.centroids.uv)
        n_id = 0 if result.ident is None else len(result.ident.cat_idx)
        print(
            f"{name} success={result.success} detected={n_det} identified={n_id} "
            f"seconds={dt:.1f}",
            flush=True,
        )
        if result.error:
            print(f"  error: {result.error}", flush=True)
        if result.success and result.q is not None:
            ra, dec = boresight_ra_dec_deg(result.q)
            med = float(result.residuals_arcsec.mean()) if result.residuals_arcsec is not None else float("nan")
            print(f"  boresight RA {ra:.3f} deg  Dec {dec:+.3f} deg  mean residual {med:.1f} arcsec", flush=True)
            if result.ident is not None:
                residuals = result.residuals_arcsec
                for k, (obs_i, cat_i) in enumerate(zip(result.ident.obs_idx, result.ident.cat_idx)):
                    row = describe_index(cat, int(cat_i))
                    uv = result.centroids.uv[int(obs_i)]
                    res_k = float(residuals[k]) if residuals is not None and k < len(residuals) else float("nan")
                    print(
                        f"  {row['label']}  V={row['mag']:.2f}  "
                        f"pixel=({uv[0]:.1f},{uv[1]:.1f})  residual={res_k:.1f} arcsec",
                        flush=True,
                    )
        save_input_png(image, out_dir / f"{name}_input.png")
        save_output_png(image, result, out_dir / f"{name}_output.png", catalog=cat, lookup=True)
        print(f"  wrote {out_dir / (name + '_input.png')}", flush=True)
        print(f"  wrote {out_dir / (name + '_output.png')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
