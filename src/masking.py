"""Glare / Earth-limb mask: bright CC > min_area, dilated, plus bright background blocks."""

from __future__ import annotations

import cv2
import numpy as np


class GlareMasker:
    def __init__(
        self,
        bright_frac: float = 0.5,
        min_area_px: int = 30,
        dilate_px: int = 25,
        bg_excess_k: float = 3.0,
        full_scale: float = 4095.0,
        bg_block: int = 64,
        min_span_px: int = 48,
    ):
        self.bright_frac = bright_frac
        self.min_area_px = min_area_px
        self.dilate_px = dilate_px
        self.bg_excess_k = bg_excess_k
        self.full_scale = full_scale
        self.bg_block = bg_block
        self.min_span_px = int(min_span_px)

    def make_mask(self, image: np.ndarray) -> np.ndarray:
        img = image.astype(np.float32)
        h, w = img.shape
        out = np.zeros((h, w), dtype=bool)
        # 12-bit sim peaks at full_scale. A 16-bit frame can sit entirely above
        # half of 4095; use the frame peak so that pedestal is not treated as glare.
        peak = float(img.max()) if img.size else 0.0
        scale = max(float(self.full_scale), peak)
        thr = self.bright_frac * scale
        bright = (img >= thr).astype(np.uint8)
        n, labels, stats, _ = cv2.connectedComponentsWithStats(bright, connectivity=8)
        hot = np.zeros((h, w), dtype=np.uint8)
        for lab in range(1, n):
            area = int(stats[lab, cv2.CC_STAT_AREA])
            bw = int(stats[lab, cv2.CC_STAT_WIDTH])
            bh = int(stats[lab, cv2.CC_STAT_HEIGHT])
            # Compact saturated PSF (Vega/Sirius) is a star, not Earth/Sun/Moon glare.
            if area <= self.min_area_px:
                continue
            short, long = min(bw, bh), max(bw, bh)
            moon_like = short >= 28 and area >= 350
            if long < self.min_span_px and not moon_like:
                continue
            hot[labels == lab] = 1
        if hot.any() and self.dilate_px > 0:
            k = 2 * int(self.dilate_px) + 1
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
            hot = cv2.dilate(hot, kernel)
            out |= hot.astype(bool)

        bs = self.bg_block
        med = float(np.median(img))
        mad = float(np.median(np.abs(img - med)))
        sigma = 1.4826 * mad if mad > 1e-6 else float(np.std(img))
        limit = med + self.bg_excess_k * sigma
        nh = (h + bs - 1) // bs
        nw = (w + bs - 1) // bs
        hp, wp = nh * bs, nw * bs
        padded = np.pad(img, ((0, hp - h), (0, wp - w)), mode="edge")
        blocks = padded.reshape(nh, bs, nw, bs).swapaxes(1, 2)
        block_med = np.median(blocks, axis=(2, 3))
        hot = np.repeat(np.repeat(block_med > limit, bs, axis=0), bs, axis=1)[:h, :w]
        out |= hot
        return out
