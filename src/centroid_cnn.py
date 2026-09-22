"""Optional CNN star detection + trilateration centroiding (Zhao et al., arXiv:2404.19108).

Uses the authors' public MobileUNet checkpoint. Classical CoG remains the default
fallback when weights are missing or inference fails.
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Optional
import numpy as np
from scipy import ndimage
from scipy.linalg import lstsq
from .camera import CameraModel
from .centroid import CentroidDetector, Centroids
from .simulator import Radiometry
_AUTHOR_MEAN = (25.36114133,)
_AUTHOR_STD = (44.31162568,)
_D_TH = 2.0
_SEG_PROB_MIN = 0.5
_NMS_SIZE = 10
_DEFAULT_WEIGHTS = Path(__file__).resolve().parent.parent / 'third_party' / 'cnn_star_centroid' / 'saved_models' / 'MobileUNet_B10_50.pt'
_VENDOR_DIR = _DEFAULT_WEIGHTS.parent.parent

def peak_dn_for_magnitude(mag: float, radiometry: Radiometry | None=None, t_exp_s: float=0.15, psf_sigma_px: float=1.2) -> float:
    """Expected peak DN for a Gaussian PSF star of visual magnitude ``mag`` (simulator radiometry)."""
    r: object = radiometry or Radiometry()
    electrons: object = r.e_per_s_v0 * 10.0 ** (-0.4 * float(mag)) * r.qe * float(t_exp_s)
    peak_e: object = electrons / (2.0 * np.pi * float(psf_sigma_px) ** 2)
    return float(peak_e * r.gain_dn_per_e + r.bias_dn)

def weights_available(path: Path | None=None) -> bool:
    p: object = Path(path) if path is not None else _DEFAULT_WEIGHTS
    return p.is_file() and p.stat().st_size > 1000000

def _pad_to_multiple(img: np.ndarray, multiple: int=32) -> tuple[np.ndarray, tuple[int, int]]:
    h, w = img.shape
    nh: object = (h + multiple - 1) // multiple * multiple
    nw: object = (w + multiple - 1) // multiple * multiple
    if nh == h and nw == w:
        return (img, (h, w))
    out: object = np.zeros((nh, nw), dtype=img.dtype)
    out[:h, :w] = img
    return (out, (h, w))

def _frame_is_high_bit(image: np.ndarray) -> bool:
    """True for 12/16-bit sim (sparse stars: p99.9 can sit well below 255)."""
    img: object = np.asarray(image)
    if img.size == 0:
        return False
    return float(np.max(img)) > 255.5

def _to_author_intensity(image: np.ndarray) -> np.ndarray:
    """Map project DN (often 12-bit) toward the authors' ~8-bit training scale."""
    img: object = np.asarray(image, dtype=np.float32)
    if _frame_is_high_bit(img):
        img: object = img / 16.0
    return img

def nms_seed_pixels(dist_map: np.ndarray, seg_map: np.ndarray, d_th: float=_D_TH) -> tuple[np.ndarray, np.ndarray]:
    """Upstream evaluation.py seeds: distance-map local minima inside the seg mask.

    Returned in raster (row-major) order, exactly like ``np.nonzero``.
    """
    dist: object = np.asarray(dist_map, dtype=np.float64)
    seg: object = np.asarray(seg_map) > 0
    dist_min: object = ndimage.minimum_filter(dist, size=(_NMS_SIZE, _NMS_SIZE), mode='constant')
    coarse: object = (dist <= d_th) & seg & (dist == dist_min)
    rows, cols = np.nonzero(coarse)
    return (rows, cols)

def outdoor_seed_scores(raw: np.ndarray, rows: np.ndarray, cols: np.ndarray, peak_half: int=2, bg_half: int=15) -> np.ndarray:
    """Star-likeness of each NMS seed on an 8-bit outdoor frame (LOST mountain photo).

    score = (peak − local median) / (1.4826·MAD + 1)

    Raster order spends the ``max_stars`` budget on the first image rows (the
    y≈0 glare / noise band), so Pyramid never sees the rest of the sky. Ranking
    seeds by local contrast over robust local noise keeps real stars across the
    whole sky and pushes faint blobs and terrain edges (large local MAD) down
    the list. Measured on mount_st_helens_1.png against a solved attitude:
    raster top-80 → 19 real stars, contrast top-80 → 72, this score → 77.
    """
    img: object = np.asarray(raw, dtype=np.float32)
    h, w = img.shape
    scores: object = np.zeros(len(rows), dtype=np.float64)
    for i, (r, c) in enumerate(zip(rows, cols)):
        r: object = int(r)
        c: object = int(c)
        y0: object = max(0, r - peak_half)
        y1: object = min(h, r + peak_half + 1)
        x0: object = max(0, c - peak_half)
        x1: object = min(w, c + peak_half + 1)
        peak: object = float(img[y0:y1, x0:x1].max())
        by0: object = max(0, r - bg_half)
        by1: object = min(h, r + bg_half + 1)
        bx0: object = max(0, c - bg_half)
        bx1: object = min(w, c + bg_half + 1)
        win: object = img[by0:by1, bx0:bx1]
        med: object = float(np.median(win))
        mad: object = float(np.median(np.abs(win - med)))
        scores[i] = (peak - med) / (1.4826 * mad + 1.0)
    return scores

def trilateration_centroids(dist_map: np.ndarray, seg_map: np.ndarray, radius: int=7, d_th: float=_D_TH, max_stars: int=80, seed_scores: np.ndarray | None=None, seeds: tuple[np.ndarray, np.ndarray] | None=None) -> np.ndarray:
    """Least-squares trilateration on the predicted distance map (Zhao et al.).

    Seeds are local minima of the distance map (upstream evaluation.py NMS), or
    the precomputed ``seeds=(rows, cols)``. When ``max_stars`` is finite, higher
    ``seed_scores`` are trilaterated first so a bright outdoor sky is not starved
    by raster-order false blobs at y≈0. ``seed_scores`` is either a full-frame
    map (indexed at the seed pixels) or a 1-D array aligned with ``seeds``.
    ``max_stars <= 0`` collects every NMS seed (no cap).
    """
    dist: object = dist_map.astype(np.float64)
    seg: object = (seg_map > 0).astype(np.float64)
    work_seg: object = seg.copy()
    if seeds is None:
        rows, cols = nms_seed_pixels(dist, work_seg, d_th)
    else:
        rows: object = np.asarray(seeds[0], dtype=np.intp)
        cols: object = np.asarray(seeds[1], dtype=np.intp)
    if len(rows) == 0:
        return np.empty((0, 2), dtype=np.float64)
    if seed_scores is not None:
        scores: object = np.asarray(seed_scores, dtype=np.float64)
        if scores.ndim == 2:
            scores: object = scores[rows, cols]
        if scores.shape != rows.shape:
            raise ValueError('seed_scores must be a full-frame map or one score per seed')
        order: object = np.argsort(-scores, kind='stable')
        rows: object = rows[order]
        cols: object = cols[order]
    cents: list[list[float]] = []
    h, w = dist.shape
    cap: object = int(max_stars) if int(max_stars) > 0 else None
    for cy, cx in zip(rows, cols):
        if work_seg[cy, cx] <= 0:
            continue
        xs: list[float] = []
        ys: list[float] = []
        rs: list[float] = []
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                y: object = int(cy + dy)
                x: object = int(cx + dx)
                if y < 0 or x < 0 or y >= h or (x >= w):
                    continue
                if work_seg[y, x] <= 0:
                    continue
                xs.append(x + 0.5)
                ys.append(y + 0.5)
                rs.append(float(dist[y, x]))
                work_seg[y, x] = 0.0
        n: object = len(xs)
        if n < 3:
            continue
        xn, yn, rn = (xs[-1], ys[-1], rs[-1])
        a: object = np.zeros((n - 1, 2), dtype=np.float64)
        b: object = np.zeros(n - 1, dtype=np.float64)
        for i in range(n - 1):
            a[i, 0] = 2.0 * (xn - xs[i])
            a[i, 1] = 2.0 * (yn - ys[i])
            b[i] = rs[i] ** 2 - rn ** 2 - xs[i] ** 2 - ys[i] ** 2 + xn ** 2 + yn ** 2
        try:
            sol, *_ = lstsq(a, b, lapack_driver='gelsy')
        except Exception:
            continue
        u, v = (float(sol[0]), float(sol[1]))
        if not np.isfinite(u) or not np.isfinite(v):
            continue
        cents.append([u, v])
        if cap is not None and len(cents) >= cap:
            break
    if not cents:
        return np.empty((0, 2), dtype=np.float64)
    return np.asarray(cents, dtype=np.float64)

def _local_peak_and_bg(raw: np.ndarray, u: float, v: float, peak_half: int=2, bg_half: int=15) -> tuple[float, float]:
    """Peak in a small window and median in a larger neighborhood (false-blob reject)."""
    h, w = raw.shape
    ui: object = int(round(u))
    vi: object = int(round(v))
    y0: object = max(0, vi - peak_half)
    y1: object = min(h, vi + peak_half + 1)
    x0: object = max(0, ui - peak_half)
    x1: object = min(w, ui + peak_half + 1)
    patch: object = raw[y0:y1, x0:x1]
    peak: object = float(patch.max()) if patch.size else 0.0
    by0: object = max(0, vi - bg_half)
    by1: object = min(h, vi + bg_half + 1)
    bx0: object = max(0, ui - bg_half)
    bx1: object = min(w, ui + bg_half + 1)
    bg: object = float(np.median(raw[by0:by1, bx0:bx1])) if by1 > by0 and bx1 > bx0 else 0.0
    return (peak, bg)

def _empty_centroids(camera: CameraModel) -> Centroids:
    empty: object = np.empty((0, 2), dtype=np.float64)
    z: object = np.empty(0, dtype=np.float64)
    return Centroids(uv=empty, flux=z, area=z, peak=z, mu20=z, mu02=z, mu11=z, axis_ratio=z, angle_rad=z, vectors=np.empty((0, 3), dtype=np.float64), sigma_px=z)

class CNNCentroidDetector:
    """MobileUNet + trilateration.

    Hard failures (missing weights, torch crash) may fall back to classical CoG;
    empty CNN output after a successful forward pass does **not** — callers see
    zero CNN centroids so Pyramid / KPIs reflect the CNN path.
    """

    def __init__(self, camera: CameraModel, classical: CentroidDetector | None=None, weights_path: Path | None=None, device: str | None=None, radius: int=7, max_stars: int=80, min_mag_gate: float | None=6.0, radiometry: Radiometry | None=None, t_exp_s: float=0.15, psf_sigma_px: float=1.2, seg_prob_min: float=_SEG_PROB_MIN) -> object:
        self.camera = camera
        self.classical = classical or CentroidDetector(camera)
        self.weights_path = Path(weights_path) if weights_path else _DEFAULT_WEIGHTS
        self.radius = int(radius)
        self.max_stars = int(max_stars)
        self.min_mag_gate = min_mag_gate
        self.radiometry = radiometry or Radiometry()
        self.t_exp_s = float(t_exp_s)
        self.psf_sigma_px = float(psf_sigma_px)
        self.seg_prob_min = float(seg_prob_min)
        if min_mag_gate is None:
            self.min_peak_dn = 0.0
        else:
            self.min_peak_dn = peak_dn_for_magnitude(float(min_mag_gate), radiometry=self.radiometry, t_exp_s=self.t_exp_s, psf_sigma_px=self.psf_sigma_px)
        self._model = None
        self._torch = None
        self._device = device
        self.device_name = 'cpu'
        self.last_backend = 'classical'
        self.last_error: str | None = None
        self.last_fallback = False
        self.last_n_raw: int = 0
        self.last_n_after_gate: int = 0
        self.last_seed_policy: str = 'raster'

    def _ensure_model(self) -> object:
        if self._model is not None:
            return
        if not weights_available(self.weights_path):
            raise FileNotFoundError(f'missing public weights: {self.weights_path}')
        import torch
        from torchvision.transforms import Normalize
        self._torch = torch
        self._normalize = Normalize(_AUTHOR_MEAN, _AUTHOR_STD)
        vendor: object = str(_VENDOR_DIR.resolve())
        if vendor not in sys.path:
            sys.path.insert(0, vendor)
        import mobile_unet
        sys.modules.setdefault('neural_net', type(sys)('neural_net'))
        sys.modules['neural_net.mobile_unet'] = sys.modules['mobile_unet']
        if self._device:
            device: object = self._device
        elif torch.cuda.is_available():
            device: object = 'cuda'
        else:
            device: object = 'cpu'
        self._device = device
        model: object = torch.load(self.weights_path, map_location=device, weights_only=False)
        model: object = model.to(device)
        model.eval()
        self._model = model
        self.device_name = torch.cuda.get_device_name(0) if device.startswith('cuda') and torch.cuda.is_available() else 'cpu'

    def detect(self, image: np.ndarray, mask: np.ndarray | None=None) -> Centroids:
        try:
            return self._detect_cnn(image, mask=mask)
        except Exception as exc:
            self.last_backend = 'classical'
            self.last_fallback = True
            self.last_error = f'{type(exc).__name__}: {exc}'
            return self.classical.detect(image, mask=mask)

    def _detect_cnn(self, image: np.ndarray, mask: np.ndarray | None=None) -> Centroids:
        self._ensure_model()
        assert self._torch is not None and self._model is not None
        torch: object = self._torch
        raw: object = np.asarray(image, dtype=np.float32)
        if raw.ndim != 2:
            raise ValueError(f'CNN expects a 2-D mono frame, got shape {raw.shape}')
        img0: object = _to_author_intensity(raw)
        if mask is not None:
            img0: object = img0.copy()
            img0[np.asarray(mask, dtype=bool)] = 0.0
        padded, (oh, ow) = _pad_to_multiple(img0, 32)
        inference_ctx: object = getattr(torch, 'inference_mode', None)
        ctx: object = inference_ctx() if inference_ctx is not None else torch.no_grad()
        with ctx:
            t: object = torch.from_numpy(padded).float().unsqueeze(0).unsqueeze(0)
            t: object = t.to(self._device, non_blocking=True)
            pred: object = self._model(self._normalize(t))
            seg_prob: object = torch.sigmoid(pred[0, 0]).detach().cpu().numpy()
            seg: object = seg_prob > self.seg_prob_min
            dist: object = pred[0, 1].detach().cpu().numpy()
        seg: object = seg[:oh, :ow]
        dist: object = dist[:oh, :ow]
        high_bit: object = _frame_is_high_bit(raw)
        rows, cols = nms_seed_pixels(dist, seg, _D_TH)
        seed_scores: object = None if high_bit else outdoor_seed_scores(raw, rows, cols)
        self.last_seed_policy = 'raster' if high_bit else 'contrast_snr'
        uv: object = trilateration_centroids(dist, seg, radius=self.radius, max_stars=int(self.max_stars), seed_scores=seed_scores, seeds=(rows, cols))
        self.last_fallback = False
        if uv.size == 0:
            self.last_n_raw = 0
            self.last_n_after_gate = 0
            self.last_backend = 'cnn_zhao2024'
            self.last_error = None
            return _empty_centroids(self.camera)
        keep: object = (uv[:, 0] >= 1.0) & (uv[:, 1] >= 1.0) & (uv[:, 0] < ow - 1.0) & (uv[:, 1] < oh - 1.0)
        uv: object = uv[keep]
        if len(uv) == 0:
            self.last_n_raw = 0
            self.last_n_after_gate = 0
            self.last_backend = 'cnn_zhao2024'
            self.last_error = None
            return _empty_centroids(self.camera)
        flux: object = np.zeros(len(uv), dtype=np.float64)
        peak: object = np.zeros(len(uv), dtype=np.float64)
        contrast: object = np.zeros(len(uv), dtype=np.float64)
        area: object = np.full(len(uv), 9.0, dtype=np.float64)
        h, w = raw.shape
        for i, (u, v) in enumerate(uv):
            pk, bg = _local_peak_and_bg(raw, float(u), float(v))
            peak[i] = pk
            contrast[i] = pk - bg
            x0: object = max(0, int(u) - 2)
            x1: object = min(w, int(u) + 3)
            y0: object = max(0, int(v) - 2)
            y1: object = min(h, int(v) + 3)
            flux[i] = float(raw[y0:y1, x0:x1].sum())
        self.last_n_raw = int(len(uv))
        if self.min_peak_dn > 0.0 and high_bit:
            bright: object = peak >= self.min_peak_dn
            uv: object = uv[bright]
            flux: object = flux[bright]
            peak: object = peak[bright]
            contrast: object = contrast[bright]
            area: object = area[bright]
        self.last_n_after_gate = int(len(uv))
        if len(uv) == 0:
            self.last_backend = 'cnn_zhao2024'
            self.last_error = None
            return _empty_centroids(self.camera)
        order: object = np.argsort(-flux)
        if int(self.max_stars) > 0 and len(order) > int(self.max_stars):
            order: object = order[:int(self.max_stars)]
        uv: object = uv[order]
        flux: object = flux[order]
        peak: object = peak[order]
        area: object = area[order]
        z: object = np.zeros(len(uv), dtype=np.float64)
        vectors: object = self.camera.unproject(uv)
        self.last_backend = 'cnn_zhao2024'
        self.last_error = None
        return Centroids(uv=uv, flux=flux, area=area, peak=peak, mu20=z, mu02=z, mu11=z, axis_ratio=np.ones(len(uv), dtype=np.float64), angle_rad=z, vectors=vectors, sigma_px=np.full(len(uv), 0.5, dtype=np.float64))

def match_centroid_rmse(pred_uv: np.ndarray, gt_uv: np.ndarray, match_radius_px: float=5.0) -> dict:
    """Greedy nearest-neighbor match; RMSE over matched pairs only."""
    pred: object = np.asarray(pred_uv, dtype=np.float64).reshape(-1, 2)
    gt: object = np.asarray(gt_uv, dtype=np.float64).reshape(-1, 2)
    if len(pred) == 0 or len(gt) == 0:
        return {'n_pred': int(len(pred)), 'n_gt': int(len(gt)), 'n_matched': 0, 'rmse_px': None, 'mean_err_px': None}
    used: object = np.zeros(len(pred), dtype=bool)
    errs: list[float] = []
    for g in gt:
        d: object = np.linalg.norm(pred - g, axis=1)
        d[used] = np.inf
        j: object = int(np.argmin(d))
        if not np.isfinite(d[j]) or d[j] > match_radius_px:
            continue
        used[j] = True
        errs.append(float(d[j]))
    if not errs:
        return {'n_pred': int(len(pred)), 'n_gt': int(len(gt)), 'n_matched': 0, 'rmse_px': None, 'mean_err_px': None}
    arr: object = np.asarray(errs, dtype=np.float64)
    return {'n_pred': int(len(pred)), 'n_gt': int(len(gt)), 'n_matched': int(len(arr)), 'rmse_px': float(np.sqrt(np.mean(arr ** 2))), 'mean_err_px': float(np.mean(arr))}
