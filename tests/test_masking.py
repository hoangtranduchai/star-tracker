"""Glare mask tests."""

from __future__ import annotations

import numpy as np

from src.masking import GlareMasker


def test_masks_large_bright_disk_and_dilates():
    h, w = 400, 600
    img = np.full((h, w), 80, dtype=np.uint16)
    yy, xx = np.ogrid[:h, :w]
    disk = (xx - 200) ** 2 + (yy - 180) ** 2 <= 40**2  # extended glare, not a star PSF
    img[disk] = 3000
    img[50, 500] = 400
    img[50, 501] = 350
    img[51, 500] = 350
    masker = GlareMasker(
        bright_frac=0.5, min_area_px=30, min_span_px=48, dilate_px=10, full_scale=4095, bg_excess_k=100
    )
    mask = masker.make_mask(img)
    assert mask[180, 200]
    assert mask[180, 200 + 18]
    assert not mask[50, 500]


def test_compact_saturated_star_not_glare():
    """Vega-like core: FAST min_area=8 used to mask this as Earth glare."""
    h, w = 200, 200
    img = np.full((h, w), 60, dtype=np.uint16)
    yy, xx = np.ogrid[:h, :w]
    star = (xx - 100) ** 2 + (yy - 100) ** 2 <= 8**2
    img[star] = 4095
    masker = GlareMasker(
        bright_frac=0.5, min_area_px=8, min_span_px=48, dilate_px=6, full_scale=4095, bg_excess_k=100
    )
    mask = masker.make_mask(img)
    assert not mask[100, 100]


def test_masks_moon_sized_disk_not_compact_star():
    h, w = 400, 600
    img = np.full((h, w), 80, dtype=np.uint16)
    yy, xx = np.ogrid[:h, :w]
    moon = (xx - 200) ** 2 + (yy - 180) ** 2 <= 20**2  # ~40 px box, FAST 0.5°
    img[moon] = 2400
    star = (xx - 500) ** 2 + (yy - 50) ** 2 <= 8**2
    img[star] = 4095
    masker = GlareMasker(
        bright_frac=0.5, min_area_px=8, min_span_px=48, dilate_px=4, full_scale=4095, bg_excess_k=100
    )
    mask = masker.make_mask(img)
    assert mask[180, 200]
    assert not mask[50, 500]


def test_earth_limb_does_not_mask_upper_sky():
    h, w = 400, 600
    img = np.full((h, w), 80, dtype=np.uint16)
    limb = int(0.70 * h)
    img[limb:, :] = 2800
    masker = GlareMasker(
        bright_frac=0.5, min_area_px=30, min_span_px=48, dilate_px=8, full_scale=4095, bg_excess_k=3
    )
    mask = masker.make_mask(img)
    assert mask[h - 5, w // 2]
    assert not mask[20, w // 2]


def test_16bit_pedestal_is_not_glare():
    """Sky near 3000 DN must survive a mask whose configured ceiling is 4095."""
    h, w = 220, 320
    rng = np.random.default_rng(0)
    img = rng.normal(3000, 40, size=(h, w)).astype(np.float32)
    img = np.clip(img, 0, 65535).astype(np.uint16)
    img[40, 50] = 52000
    img[40, 51] = 40000
    img[41, 50] = 38000
    masker = GlareMasker(
        bright_frac=0.5, min_area_px=8, min_span_px=48, dilate_px=6, full_scale=4095, bg_excess_k=3
    )
    mask = masker.make_mask(img)
    assert float(mask.mean()) < 0.02
    assert not mask[40, 50]
    assert not mask[h // 2, w // 2]


def test_16bit_extended_disk_still_masked():
    h, w = 400, 600
    img = np.full((h, w), 3000, dtype=np.uint16)
    yy, xx = np.ogrid[:h, :w]
    disk = (xx - 200) ** 2 + (yy - 180) ** 2 <= 40**2
    img[disk] = 50000
    masker = GlareMasker(
        bright_frac=0.5, min_area_px=30, min_span_px=48, dilate_px=8, full_scale=4095, bg_excess_k=100
    )
    mask = masker.make_mask(img)
    assert mask[180, 200]
    assert not mask[20, w // 2]


def test_small_blob_not_glare():
    h, w = 200, 200
    img = np.full((h, w), 60, dtype=np.uint16)
    img[100, 100] = 4000
    img[100, 101] = 4000
    masker = GlareMasker(min_area_px=30, dilate_px=5, bg_excess_k=100)
    mask = masker.make_mask(img)
    assert not mask[100, 100]
