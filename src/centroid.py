"""Sub-pixel centroiding (OpenCV): local background, CoG, moments."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .camera import CameraModel


@dataclass
class Centroids:
    uv: np.ndarray
    flux: np.ndarray
    area: np.ndarray
    peak: np.ndarray
    mu20: np.ndarray
    mu02: np.ndarray
    mu11: np.ndarray
    axis_ratio: np.ndarray
    angle_rad: np.ndarray
    vectors: np.ndarray
    sigma_px: np.ndarray


class CentroidDetector:
    def __init__(
        self,
        camera: CameraModel,
        k_sigma: float = 4.0,
        bg_block: int = 64,
        min_area: int = 3,
        max_area: int = 120,
        max_area_sat: int = 2500,
        max_axis_ratio: float = 3.0,
        saturation_dn: float = 4000.0,
        edge_margin: int = 4,
        binary_open: bool = True,
        cog_pad: int = 1,
        psf_sigma_px: float = 1.2,
        abs_k_sigma: float = 0.0,
        min_contrast_sigma: float = 10.0,
        max_neighbor_hot: float = 0.15,
    ):
        self.camera = camera
        self.k_sigma = k_sigma
        self.bg_block = max(3, int(bg_block) | 1)  # odd for boxFilter
        self.min_area = min_area
        self.max_area = max_area
        self.max_area_sat = max(int(max_area_sat), int(max_area))
        self.max_axis_ratio = max_axis_ratio
        self.saturation_dn = saturation_dn
        self.edge_margin = edge_margin
        self.binary_open = binary_open
        self.cog_pad = cog_pad
        self.psf_sigma_px = psf_sigma_px
        # Optional hard floor on raw DN. Left off so faint sky stars stay.
        # Extended edges are rejected per blob by _is_isolated_peak.
        self.abs_k_sigma = float(abs_k_sigma)
        self.min_contrast_sigma = float(min_contrast_sigma)
        self.max_neighbor_hot = float(max_neighbor_hot)

    def detect(self, image: np.ndarray, mask: np.ndarray | None = None) -> Centroids:
        img = image.astype(np.float32)
        h, w = img.shape
        k = self.bg_block
        bg = cv2.boxFilter(img, ddepth=-1, ksize=(k, k), normalize=True, borderType=cv2.BORDER_REPLICATE)
        resid = img - bg
        # MAD of residual (robust σ); skip likely stars by using a coarse clip
        finite = resid.reshape(-1)
        med = float(np.median(finite))
        mad = float(np.median(np.abs(finite - med)))
        sigma = 1.4826 * mad if mad > 1e-6 else float(np.std(finite))
        thresh = self.k_sigma * max(sigma, 1e-3)
        star_mask = resid > thresh
        if mask is not None:
            star_mask = star_mask & (~mask.astype(bool))
        if self.abs_k_sigma > 0:
            sample = img if mask is None else img[~np.asarray(mask, dtype=bool)]
            if sample.size < 32:
                sample = img.reshape(-1)
            cutoff = float(sample.mean()) + self.abs_k_sigma * float(sample.std())
            star_mask = star_mask & (img >= cutoff)
        if self.binary_open:
            kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
            star_mask = cv2.morphologyEx(star_mask.astype(np.uint8), cv2.MORPH_OPEN, kernel).astype(bool)

        n_lab, labels, stats, _ = cv2.connectedComponentsWithStats(star_mask.astype(np.uint8), connectivity=8)
        recs: list[tuple] = []
        for lab in range(1, n_lab):
            area = int(stats[lab, cv2.CC_STAT_AREA])
            if area < self.min_area:
                continue
            x = int(stats[lab, cv2.CC_STAT_LEFT])
            y = int(stats[lab, cv2.CC_STAT_TOP])
            bw = int(stats[lab, cv2.CC_STAT_WIDTH])
            bh = int(stats[lab, cv2.CC_STAT_HEIGHT])
            peak = float(img[y : y + bh, x : x + bw].max()) if bw > 0 and bh > 0 else 0.0
            if area > self.max_area:
                if peak < self.saturation_dn or area > self.max_area_sat:
                    continue
            pad = self.cog_pad
            x0 = max(0, x - pad)
            y0 = max(0, y - pad)
            x1 = min(w, x + bw + pad)
            y1 = min(h, y + bh + pad)
            blob = labels[y0:y1, x0:x1] == lab
            sub = np.maximum(resid[y0:y1, x0:x1], 0.0) * blob
            flux = float(sub.sum())
            if flux <= 0:
                continue
            yy, xx = np.indices(sub.shape)
            u = x0 + float((sub * xx).sum() / flux)
            v = y0 + float((sub * yy).sum() / flux)
            if u < self.edge_margin or v < self.edge_margin:
                continue
            if u >= w - self.edge_margin or v >= h - self.edge_margin:
                continue
            peak = float(img[y0:y1, x0:x1][blob].max()) if np.any(blob) else 0.0
            mu20 = float((sub * (xx - (u - x0)) ** 2).sum() / flux)
            mu02 = float((sub * (yy - (v - y0)) ** 2).sum() / flux)
            mu11 = float((sub * (xx - (u - x0)) * (yy - (v - y0))).sum() / flux)
            tmp = np.sqrt(max(0.0, (mu20 - mu02) ** 2 + 4.0 * mu11 * mu11))
            lam1 = 0.5 * ((mu20 + mu02) + tmp)
            lam2 = 0.5 * ((mu20 + mu02) - tmp)
            axis_ratio = float(np.sqrt(lam1 / max(lam2, 1e-8)))
            if axis_ratio > self.max_axis_ratio:
                continue
            if not self._is_isolated_peak(img, resid, u, v, sigma, thresh, area):
                continue
            angle = 0.5 * float(np.arctan2(2.0 * mu11, mu20 - mu02))
            snr = flux / max(sigma * np.sqrt(area), 1e-3)
            sig_px = self.psf_sigma_px / max(np.sqrt(snr), 1.0)
            recs.append((u, v, flux, area, peak, mu20, mu02, mu11, axis_ratio, angle, sig_px))

        if not recs:
            empty = np.empty((0, 2))
            z = np.empty(0)
            return Centroids(
                uv=empty,
                flux=z,
                area=z,
                peak=z,
                mu20=z,
                mu02=z,
                mu11=z,
                axis_ratio=z,
                angle_rad=z,
                vectors=np.empty((0, 3)),
                sigma_px=z,
            )

        recs.sort(key=lambda r: -r[2])
        arr = np.array(recs, dtype=np.float64)
        uv = arr[:, 0:2]
        vectors = self.camera.unproject(uv)
        return Centroids(
            uv=uv,
            flux=arr[:, 2],
            area=arr[:, 3],
            peak=arr[:, 4],
            mu20=arr[:, 5],
            mu02=arr[:, 6],
            mu11=arr[:, 7],
            axis_ratio=arr[:, 8],
            angle_rad=arr[:, 9],
            vectors=vectors,
            sigma_px=arr[:, 10],
        )

    def _is_isolated_peak(
        self,
        img: np.ndarray,
        resid: np.ndarray,
        u: float,
        v: float,
        sigma: float,
        thresh: float,
        area: int,
    ) -> bool:
        """A star stands above a quiet ring. A treeline fragment has more hits around it."""
        rad = 8
        cy = int(round(v))
        cx = int(round(u))
        height, width = img.shape
        if cy < rad or cx < rad or cy >= height - rad or cx >= width - rad:
            return False
        yy, xx = np.ogrid[-rad : rad + 1, -rad : rad + 1]
        radius2 = yy * yy + xx * xx
        ring = (radius2 >= 16) & (radius2 <= rad * rad)
        patch = img[cy - rad : cy + rad + 1, cx - rad : cx + rad + 1]
        contrast = float(img[cy, cx] - np.median(patch[ring]))
        floor = self.min_contrast_sigma * max(sigma, 1e-3)
        if contrast < floor:
            return False
        # A bright core may be larger than the ring. A wide dim blob is a ridge.
        if area > 20 and contrast >= 4.0 * floor:
            return True
        resid_patch = resid[cy - rad : cy + rad + 1, cx - rad : cx + rad + 1]
        hot = float((resid_patch[ring] > thresh).mean())
        return hot <= self.max_neighbor_hot
