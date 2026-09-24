"""Tests for extended glare masking (Moon disk, Earth limb, and compact PSF preservation)."""
from __future__ import annotations
import numpy as np
from src.masking import GlareMasker

def _require_mask(cond: bool, msg: str='mask assertion failed') -> None:
    if not cond:
        raise AssertionError(msg)

def _draw_circle(shape: tuple[int, int], center_u: int, center_v: int, radius: int) -> np.ndarray:
    yy, xx = np.ogrid[:shape[0], :shape[1]]
    return (xx - center_u) ** 2 + (yy - center_v) ** 2 <= radius * radius

def test_masks_large_bright_disk_and_dilates() -> object:
    frame: object = np.full((400, 600), 80, dtype=np.uint16)
    frame[_draw_circle(frame.shape, 200, 180, 40)] = 3000
    frame[50, 500:502] = (400, 350)
    frame[51, 500] = 350
    detector: object = GlareMasker(bright_frac=0.5, min_area_px=30, min_span_px=48, dilate_px=10, full_scale=4095, bg_excess_k=100)
    out_mask: object = detector.make_mask(frame)
    _require_mask(bool(out_mask[180, 200]) and bool(out_mask[180, 218]))
    _require_mask(not bool(out_mask[50, 500]))

def test_compact_saturated_star_not_glare() -> object:
    frame: object = np.full((200, 200), 60, dtype=np.uint16)
    frame[_draw_circle(frame.shape, 100, 100, 8)] = 4095
    detector: object = GlareMasker(bright_frac=0.5, min_area_px=8, min_span_px=48, dilate_px=6, full_scale=4095, bg_excess_k=100)
    out_mask: object = detector.make_mask(frame)
    _require_mask(not bool(out_mask[100, 100]))

def test_masks_moon_sized_disk_not_compact_star() -> object:
    frame: object = np.full((400, 600), 80, dtype=np.uint16)
    frame[_draw_circle(frame.shape, 200, 180, 20)] = 2400
    frame[_draw_circle(frame.shape, 500, 50, 8)] = 4095
    detector: object = GlareMasker(bright_frac=0.5, min_area_px=8, min_span_px=48, dilate_px=4, full_scale=4095, bg_excess_k=100)
    out_mask: object = detector.make_mask(frame)
    _require_mask(bool(out_mask[180, 200]))
    _require_mask(not bool(out_mask[50, 500]))

def test_earth_limb_does_not_mask_upper_sky() -> object:
    rows, cols = (400, 600)
    frame: object = np.full((rows, cols), 80, dtype=np.uint16)
    frame[int(0.7 * rows):, :] = 2800
    detector: object = GlareMasker(bright_frac=0.5, min_area_px=30, min_span_px=48, dilate_px=8, full_scale=4095, bg_excess_k=3)
    out_mask: object = detector.make_mask(frame)
    _require_mask(bool(out_mask[rows - 5, cols // 2]))
    _require_mask(not bool(out_mask[20, cols // 2]))

def test_16bit_pedestal_is_not_glare() -> object:
    rows, cols = (220, 320)
    prng: object = np.random.default_rng(seed=0)
    noisy_sky: object = np.clip(prng.normal(3000.0, 40.0, size=(rows, cols)), 0, 65535).astype(np.uint16)
    noisy_sky[40, 50:52] = (52000, 40000)
    noisy_sky[41, 50] = 38000
    detector: object = GlareMasker(bright_frac=0.5, min_area_px=8, min_span_px=48, dilate_px=6, full_scale=4095, bg_excess_k=3)
    out_mask: object = detector.make_mask(noisy_sky)
    _require_mask(float(out_mask.mean()) < 0.02)
    _require_mask(not bool(out_mask[40, 50]) and (not bool(out_mask[rows // 2, cols // 2])))

def test_16bit_extended_disk_still_masked() -> object:
    rows, cols = (400, 600)
    frame: object = np.full((rows, cols), 3000, dtype=np.uint16)
    frame[_draw_circle(frame.shape, 200, 180, 40)] = 50000
    detector: object = GlareMasker(bright_frac=0.5, min_area_px=30, min_span_px=48, dilate_px=8, full_scale=4095, bg_excess_k=100)
    out_mask: object = detector.make_mask(frame)
    _require_mask(bool(out_mask[180, 200]) and (not bool(out_mask[20, cols // 2])))

def test_small_blob_not_glare() -> object:
    frame: object = np.full((200, 200), 60, dtype=np.uint16)
    frame[100, 100:102] = 4000
    detector: object = GlareMasker(min_area_px=30, dilate_px=5, bg_excess_k=100)
    out_mask: object = detector.make_mask(frame)
    _require_mask(not bool(out_mask[100, 100]))
