"""Tests for sub-pixel centroiding accuracy, background removal, and glare exclusion."""
from __future__ import annotations
import numpy as np
from src.camera import demo_camera
from src.centroid import CentroidDetector

def _assert_flag(cond: bool, msg: str='assertion failed') -> None:
    if not cond:
        raise AssertionError(msg)

def _synth_psf_frame(rows: int, cols: int, u_true: float, v_true: float, peak_dn: float, sigma_px: float, pedestal: float=100.0) -> np.ndarray:
    yy, xx = np.mgrid[:rows, :cols]
    dist_sq: object = (xx - u_true) ** 2 + (yy - v_true) ** 2
    frame: object = pedestal + peak_dn * np.exp(-dist_sq / (2.0 * sigma_px * sigma_px))
    return np.clip(np.rint(frame), 0, 4095).astype(np.uint16)

def test_single_noiseless_gaussian_subpixel() -> object:
    optics: object = demo_camera().downscaled(4)
    detector: object = CentroidDetector(optics, bg_block=32, k_sigma=4.0, min_area=3)
    target_u, target_v = (123.37, 98.62)
    frame: object = _synth_psf_frame(optics.height, optics.width, target_u, target_v, peak_dn=1500.0, sigma_px=1.6)
    detections: object = detector.detect(frame)
    _assert_flag(len(detections.uv) == 1)
    err_px: object = float(np.hypot(detections.uv[0, 0] - target_u, detections.uv[0, 1] - target_v))
    _assert_flag(err_px < 0.05)

def test_noisy_gaussian_monte_carlo_rmse() -> object:
    optics: object = demo_camera().downscaled(4)
    detector: object = CentroidDetector(optics, bg_block=32, k_sigma=4.0, min_area=3)
    prng: object = np.random.default_rng(seed=12)
    radial_errors: object = []
    for _ in range(40):
        u_gt: object = float(prng.uniform(40.0, optics.width - 40.0))
        v_gt: object = float(prng.uniform(40.0, optics.height - 40.0))
        clean: object = _synth_psf_frame(optics.height, optics.width, u_gt, v_gt, peak_dn=1200.0, sigma_px=1.5)
        noisy: object = np.clip(clean.astype(np.float64) + prng.normal(0.0, 4.0, size=clean.shape), 0, 4095).astype(np.uint16)
        det: object = detector.detect(noisy)
        if len(det.uv) >= 1:
            dists: object = np.linalg.norm(det.uv - np.asarray([[u_gt, v_gt]]), axis=1)
            radial_errors.append(float(dists.min()))
    _assert_flag(len(radial_errors) >= 35)
    rmse: object = float(np.sqrt(np.mean(np.square(radial_errors))))
    _assert_flag(rmse < 0.25)

def test_hot_single_pixel_rejected() -> object:
    optics: object = demo_camera().downscaled(4)
    detector: object = CentroidDetector(optics, bg_block=32, k_sigma=4.0, min_area=3)
    frame: object = np.full((optics.height, optics.width), 90, dtype=np.uint16)
    frame[75, 110] = 3800
    detections: object = detector.detect(frame)
    _assert_flag(len(detections.uv) == 0)

def test_glare_mask_excludes_region() -> object:
    optics: object = demo_camera().downscaled(4)
    detector: object = CentroidDetector(optics, bg_block=32, k_sigma=4.0, min_area=3)
    frame: object = _synth_psf_frame(optics.height, optics.width, 150.0, 120.0, peak_dn=1600.0, sigma_px=1.6)
    exclusion: object = np.zeros(frame.shape, dtype=bool)
    exclusion[110:130, 140:160] = True
    detections: object = detector.detect(frame, mask=exclusion)
    _assert_flag(len(detections.uv) == 0)

def test_nonuniform_background_subtracted() -> object:
    optics: object = demo_camera().downscaled(4)
    detector: object = CentroidDetector(optics, bg_block=32, k_sigma=4.0, min_area=3)
    yy, xx = np.mgrid[:optics.height, :optics.width]
    gradient_bg: object = (80.0 + 0.4 * xx + 0.3 * yy).astype(np.float64)
    u_gt, v_gt = (200.25, 150.75)
    spot: object = 1400.0 * np.exp(-((xx - u_gt) ** 2 + (yy - v_gt) ** 2) / (2.0 * 1.5 ** 2))
    frame: object = np.clip(np.rint(gradient_bg + spot), 0, 4095).astype(np.uint16)
    detections: object = detector.detect(frame)
    _assert_flag(len(detections.uv) >= 1)
    dists: object = np.linalg.norm(detections.uv - np.asarray([[u_gt, v_gt]]), axis=1)
    _assert_flag(float(dists.min()) < 0.15)
