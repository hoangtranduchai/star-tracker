"""ESA tetra3-style traditional thresholding star centroid detector.

Implements the classical local-mean background subtraction + global RMS sigma
thresholding + 3x3 cross binary opening + connected-component area filtering
and intensity-weighted center-of-gravity (CoG) pipeline following ESA/DTU
``tetra3.get_centroids_from_image`` defaults (``filtsize=25``,
``bg_sub_mode='local_mean'``, ``sigma_mode='global_root_square'``,
``sigma=2.0``, ``binary_open=True``, ``min_area=5``, ``max_area=100``),
expressed in this repository's 0-indexed pixel-center convention matching
``CameraModel`` and ``CentroidDetector``.
"""
from __future__ import annotations

import cv2
import numpy as np
from scipy import ndimage

from .camera import CameraModel
from .centroid import Centroids, _empty_centroids, _moment_shape


class Tetra3ThresholdDetector:
    """Traditional local-mean + global-RMS threshold detector (tetra3 style)."""

    def __init__(
        self,
        camera: CameraModel,
        sigma: float = 2.0,
        filtsize: int = 25,
        binary_open: bool = True,
        min_area: int = 5,
        max_area: int = 100,
        max_axis_ratio: float | None = None,
        max_returned: int | None = 80,
        edge_margin: int = 2,
    ) -> None:
        self.camera = camera
        self.sigma = float(sigma)
        fsize = max(3, int(filtsize) | 1)
        self.filtsize = fsize
        self.binary_open = bool(binary_open)
        self.min_area = int(min_area)
        self.max_area = int(max_area)
        self.max_axis_ratio = None if max_axis_ratio is None else float(max_axis_ratio)
        self.max_returned = None if max_returned is None else int(max_returned)
        self.edge_margin = int(edge_margin)
        self.last_backend = 'tetra3_threshold'
        self.last_fallback = False
        self.last_error: str | None = None
        self.last_n_raw: int = 0
        self.last_n_after_gate: int = 0

    def detect(self, image: np.ndarray, mask: np.ndarray | None = None) -> Centroids:
        arr = np.asarray(image, dtype=np.float32)
        if arr.ndim != 2 or arr.size == 0:
            self.last_n_raw = 0
            self.last_n_after_gate = 0
            return _empty_centroids()

        rows, cols = arr.shape
        work = arr
        if mask is not None:
            m_bool = np.asarray(mask, dtype=bool)
            if m_bool.shape == arr.shape and bool(np.any(m_bool)):
                work = arr.copy()
                work[m_bool] = float(np.median(arr[~m_bool])) if not bool(np.all(m_bool)) else float(np.median(arr))

        # 1. Local mean background subtraction (exact match to tetra3 uniform_filter)
        bg = ndimage.uniform_filter(work, size=self.filtsize, output=np.float32)
        net = work - bg

        # 2. Global root-mean-square noise estimate (tetra3 global_root_square)
        img_std = float(np.sqrt(np.mean(net * net, dtype=np.float64)))
        thresh = img_std * self.sigma

        # 3. Binary threshold + optional 3x3 cross binary opening
        bin_mask = net > thresh
        if mask is not None:
            m_bool = np.asarray(mask, dtype=bool)
            if m_bool.shape == bin_mask.shape:
                bin_mask = bin_mask & ~m_bool
        if self.binary_open:
            bin_mask = ndimage.binary_opening(bin_mask)

        # 4. Connected components (4-connectivity matches scipy.ndimage.label default)
        num_labels, lbl_img, cc_stats, _ = cv2.connectedComponentsWithStats(
            bin_mask.astype(np.uint8), connectivity=4
        )
        self.last_n_raw = max(0, int(num_labels) - 1)
        if num_labels <= 1:
            self.last_n_after_gate = 0
            return _empty_centroids()

        candidates: list[tuple[float, ...]] = []
        margin = self.edge_margin
        for idx in range(1, int(num_labels)):
            area = int(cc_stats[idx, cv2.CC_STAT_AREA])
            if area < self.min_area or area > self.max_area:
                continue
            bx = int(cc_stats[idx, cv2.CC_STAT_LEFT])
            by = int(cc_stats[idx, cv2.CC_STAT_TOP])
            bw = int(cc_stats[idx, cv2.CC_STAT_WIDTH])
            bh = int(cc_stats[idx, cv2.CC_STAT_HEIGHT])
            sub_lbl = lbl_img[by : by + bh, bx : bx + bw] == idx
            sub_net = net[by : by + bh, bx : bx + bw]
            weights = np.where(sub_lbl, sub_net, 0.0).astype(np.float64)
            m0 = float(weights.sum())
            if m0 <= 0.0:
                continue
            inv_m0 = 1.0 / m0
            gy, gx = np.indices(weights.shape, dtype=np.float64)
            u_rel = float((weights * gx).sum() * inv_m0)
            v_rel = float((weights * gy).sum() * inv_m0)
            u_c = bx + u_rel
            v_c = by + v_rel
            if not (margin <= u_c < cols - margin and margin <= v_c < rows - margin):
                continue
            m20, m02, m11, ratio, theta = _moment_shape(weights, gx - u_rel, gy - v_rel, inv_m0)
            if self.max_axis_ratio is not None and ratio > self.max_axis_ratio:
                continue
            pk_val = float(arr[by : by + bh, bx : bx + bw][sub_lbl].max())
            snr_est = m0 / max(img_std * float(np.sqrt(area)), 1e-3)
            pos_std = 1.2 / max(float(np.sqrt(max(snr_est, 1.0))), 1.0)
            candidates.append((u_c, v_c, m0, float(area), pk_val, m20, m02, m11, ratio, theta, pos_std))

        self.last_n_after_gate = len(candidates)
        if not candidates:
            return _empty_centroids()

        candidates.sort(key=lambda item: -item[2])
        if self.max_returned is not None and self.max_returned > 0 and len(candidates) > self.max_returned:
            candidates = candidates[: self.max_returned]

        mat = np.asarray(candidates, dtype=np.float64)
        uv_coords = mat[:, :2]
        cam_dirs = self.camera.unproject(uv_coords)
        c_flux, c_area, c_peak, c_m20, c_m02, c_m11, c_ax, c_ang, c_sig = mat[:, 2:].T
        return Centroids(
            uv=uv_coords,
            flux=c_flux,
            area=c_area,
            peak=c_peak,
            mu20=c_m20,
            mu02=c_m02,
            mu11=c_m11,
            axis_ratio=c_ax,
            angle_rad=c_ang,
            vectors=cam_dirs,
            sigma_px=c_sig,
        )
