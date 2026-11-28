"""Optional CNN star detection + trilateration centroiding (Zhao et al., arXiv:2404.19108).

Uses the authors' public MobileUNet checkpoint. Classical CoG remains the default
fallback when weights are missing or inference fails.
"""
from __future__ import annotations
import logging
import os
import sys
from pathlib import Path
from typing import Optional
import cv2
import numpy as np
from scipy import ndimage
from scipy.linalg import lstsq
from .camera import CameraModel
from .centroid import CentroidDetector, Centroids
from .simulator import Radiometry
_LOGGER = logging.getLogger(__name__)
_AUTHOR_MEAN = (25.36114133,)
_AUTHOR_STD = (44.31162568,)
_D_TH = 2.0
_SEG_PROB_MIN = 0.5
_NMS_SIZE = 10
_R_BG = 10
_YY_BG, _XX_BG = np.ogrid[-_R_BG:_R_BG + 1, -_R_BG:_R_BG + 1]
_R2_BG = _XX_BG * _XX_BG + _YY_BG * _YY_BG
_ANNULUS_BG = (_R2_BG >= 16) & (_R2_BG <= _R_BG * _R_BG)
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_WEIGHTS = _REPO_ROOT / 'third_party' / 'cnn_star_centroid' / 'saved_models' / 'MobileUNet_B10_50.pt'
DEFAULT_WEIGHTS_PATH = _DEFAULT_WEIGHTS
_VENDOR_DIR = _DEFAULT_WEIGHTS.parent.parent
_DEFAULT_CHECKPOINT_REL = 'third_party/cnn_star_centroid/saved_models/MobileUNet_B10_50.pt'
_DEFAULT_CHECKPOINT_SHA256 = 'e02d7723b832d12cf2535a8a9794eaedc822023722f07da3126dcd8473cbe062'
_MIN_CHECKPOINT_BYTES = 1_000_000


def _sanitize_path_display(path: Path | str) -> str:
    """Format a checkpoint path without leaking absolute OS/user/container directories."""
    p = Path(path)
    try:
        rel = p.resolve().relative_to(_REPO_ROOT.resolve())
        return rel.as_posix()
    except Exception:
        pass
    parts = p.parts
    for anchor in ('third_party', 'data', 'config', 'src', 'scripts'):
        if anchor in parts:
            idx = parts.index(anchor)
            return '/'.join(parts[idx:])
    return p.name or str(p)


def _sanitize_error_text(text: str) -> str:
    """Strip absolute repo/temp/container path prefixes from diagnostic error strings."""
    import re
    out = str(text)
    for root_str in (str(_REPO_ROOT.resolve()), _REPO_ROOT.resolve().as_posix()):
        if root_str in out:
            out = out.replace(root_str + '\\', '').replace(root_str + '/', '').replace(root_str, '')
    # Replace remaining Windows/POSIX absolute paths with relative anchor path or basename
    def _repl_abs(match: re.Match[str]) -> str:
        raw = match.group(0)
        return _sanitize_path_display(raw)

    out = re.sub(r'[A-Za-z]:\\[^\s\'"()]+', _repl_abs, out)
    out = re.sub(r'(?:^|(?<=[\s:(]))/(?:app|tmp|var|home|Users|opt|root)/[^\s\'"()]+', _repl_abs, out)
    return out


def expected_default_checkpoint_sha256() -> str:
    """Read canonical checkpoint SHA-256 from CHECKSUMS.sha256 (with hardcoded fallback)."""
    try:
        from .repro_bundle import CHECKSUM_FILE, parse_checksums_file
        cs = parse_checksums_file(_REPO_ROOT / CHECKSUM_FILE)
        if _DEFAULT_CHECKPOINT_REL in cs:
            return cs[_DEFAULT_CHECKPOINT_REL]
    except Exception:
        pass
    return _DEFAULT_CHECKPOINT_SHA256


def inspect_checkpoint_status(path: Path | None = DEFAULT_WEIGHTS_PATH, expected_sha256: str | None = None) -> dict[str, str | None]:
    """Inspect checkpoint existence, minimum size, and SHA-256 integrity without invoking torch.load.

    Returns ``{"status": ..., "sha256": ..., "error": ...}`` where ``status`` is one of:
    ``"verified"``, ``"checksum_mismatch"``, ``"corrupted_truncated"``, or ``"missing"``.
    """
    p = Path(path) if path is not None else _DEFAULT_WEIGHTS
    disp = _sanitize_path_display(p)
    if not p.is_file():
        return {
            'status': 'missing',
            'sha256': None,
            'error': f'missing public weights: {disp}',
        }
    size_b = int(p.stat().st_size)
    from .repro_bundle import sha256_file
    actual = sha256_file(p)
    if size_b < _MIN_CHECKPOINT_BYTES:
        return {
            'status': 'corrupted_truncated',
            'sha256': actual,
            'error': f'CHECKPOINT_TRUNCATED: file too small ({size_b} bytes < {_MIN_CHECKPOINT_BYTES}) ({disp})',
        }
    exp = expected_sha256
    if exp is None and (p.resolve() == _DEFAULT_WEIGHTS.resolve() or p.name == _DEFAULT_WEIGHTS.name):
        exp = expected_default_checkpoint_sha256()
    if exp is not None and actual.lower() != str(exp).strip().lower():
        return {
            'status': 'checksum_mismatch',
            'sha256': actual,
            'error': f'CHECKPOINT_SHA256_MISMATCH: expected {str(exp)[:16]}..., got {actual[:16]}... ({disp})',
        }
    return {
        'status': 'verified',
        'sha256': actual,
        'error': None,
    }


def verify_checkpoint_integrity(weights_path: Path, expected_sha256: str | None = None) -> str:
    """Verify existence, size, and SHA-256 digest of a checkpoint BEFORE calling torch.load(..., weights_only=False)."""
    info = inspect_checkpoint_status(weights_path, expected_sha256=expected_sha256)
    status = info['status']
    if status == 'missing':
        raise FileNotFoundError(str(info['error']))
    if status in ('corrupted_truncated', 'checksum_mismatch'):
        raise ValueError(str(info['error']))
    assert info['sha256'] is not None
    return info['sha256']

def peak_dn_for_magnitude(mag: float, radiometry: Radiometry | None=None, t_exp_s: float=0.15, psf_sigma_px: float=1.2) -> float:
    """Expected peak DN for a Gaussian PSF star of visual magnitude ``mag`` (simulator radiometry)."""
    r: object = radiometry or Radiometry()
    electrons: object = r.e_per_s_v0 * 10.0 ** (-0.4 * float(mag)) * r.qe * float(t_exp_s)
    peak_e: object = electrons / (2.0 * np.pi * float(psf_sigma_px) ** 2)
    return float(peak_e * r.gain_dn_per_e + r.bias_dn)

def weights_available(path: Path | None=None) -> bool:
    p: object = Path(path) if path is not None else _DEFAULT_WEIGHTS
    return p.is_file() and p.stat().st_size >= _MIN_CHECKPOINT_BYTES

def _pad_to_multiple(img: np.ndarray, multiple: int=32) -> tuple[np.ndarray, tuple[int, int]]:
    h, w = img.shape
    nh: object = (h + multiple - 1) // multiple * multiple
    nw: object = (w + multiple - 1) // multiple * multiple
    if nh == h and nw == w:
        return (img, (h, w))
    out: object = np.zeros((nh, nw), dtype=img.dtype)
    out[:h, :w] = img
    return (out, (h, w))

def _frame_bit_regime(image: np.ndarray) -> str:
    """Classify frame intensity regime as '8bit' (<=255.5), '12bit' (<=4095.5), or '16bit' (>4095.5)."""
    img: object = np.asarray(image)
    if img.size == 0:
        return '8bit'
    max_val: float = float(np.max(img))
    if max_val <= 255.5:
        return '8bit'
    if max_val <= 4095.5:
        return '12bit'
    return '16bit'

def _frame_is_high_bit(image: np.ndarray) -> bool:
    """True only for 12-bit synthetic sim frames (255.5 < max <= 4095.5)."""
    return _frame_bit_regime(image) == '12bit'

def _to_author_intensity(image: np.ndarray) -> np.ndarray:
    """Map 8-bit, 12-bit sim (/16), or 16-bit camera (/256) DN toward the authors' ~8-bit scale."""
    img: object = np.asarray(image, dtype=np.float32)
    regime: str = _frame_bit_regime(img)
    if regime == '12bit':
        return img / 16.0
    if regime == '16bit':
        return img / 256.0
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
        cy_i, cx_i = (int(cy), int(cx))
        if work_seg[cy_i, cx_i] <= 0:
            continue
        y0, y1 = (max(0, cy_i - radius), min(h, cy_i + radius + 1))
        x0, x1 = (max(0, cx_i - radius), min(w, cx_i + radius + 1))
        sub_seg = work_seg[y0:y1, x0:x1]
        ly, lx = np.nonzero(sub_seg > 0)
        n = int(len(ly))
        if n < 3:
            sub_seg[ly, lx] = 0.0
            continue
        ys = (ly + y0).astype(np.float64) + 0.5
        xs = (lx + x0).astype(np.float64) + 0.5
        rs = dist[ly + y0, lx + x0]
        sub_seg[ly, lx] = 0.0
        xn, yn, rn = (float(xs[-1]), float(ys[-1]), float(rs[-1]))
        xi, yi, ri = (xs[:-1], ys[:-1], rs[:-1])
        a = np.empty((n - 1, 2), dtype=np.float64)
        a[:, 0] = 2.0 * (xn - xi)
        a[:, 1] = 2.0 * (yn - yi)
        b = ri * ri - rn * rn - xi * xi - yi * yi + (xn * xn + yn * yn)
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
    """MobileUNet semantic star filter with optional local sub-pixel CoG refinement (CNN-Hybrid).

    When ``refine_subpixel=True`` (default), MobileUNet suppresses extended terrain,
    cloud, and horizon clutter while each candidate seed undergoes local
    background-subtracted hollow-annulus SNR gating, single-pixel hot-pixel
    rejection, and connected-component aperture CoG sub-pixel refinement.
    Setting ``refine_subpixel=False`` restores raw Zhao et al. trilateration for
    ablation benchmarks.

    Hard failures (missing weights, torch crash) may fall back to classical CoG;
    empty CNN output after a successful forward pass does **not** — callers see
    zero CNN centroids so Pyramid / KPIs reflect the CNN path.
    """

    def __init__(self, camera: CameraModel, classical: CentroidDetector | None=None, weights_path: Path | None=None, device: str | None=None, radius: int=7, max_stars: int=80, min_mag_gate: float | None=6.0, radiometry: Radiometry | None=None, t_exp_s: float=0.15, psf_sigma_px: float=1.2, seg_prob_min: float=_SEG_PROB_MIN, refine_subpixel: bool=True, expected_sha256: str | None=None) -> object:
        self.camera = camera
        self.classical = classical or CentroidDetector(camera)
        self.weights_path = Path(weights_path) if weights_path else _DEFAULT_WEIGHTS
        self.expected_sha256 = expected_sha256
        self.checkpoint_sha256: str | None = None
        self.checkpoint_status: str | None = None
        self.radius = int(radius)
        self.max_stars = int(max_stars)
        self.min_mag_gate = min_mag_gate
        self.radiometry = radiometry or Radiometry()
        self.t_exp_s = float(t_exp_s)
        self.psf_sigma_px = float(psf_sigma_px)
        self.seg_prob_min = float(seg_prob_min)
        self.refine_subpixel = bool(refine_subpixel)
        if min_mag_gate is None:
            self.min_peak_dn = 0.0
        else:
            self.min_peak_dn = peak_dn_for_magnitude(float(min_mag_gate), radiometry=self.radiometry, t_exp_s=self.t_exp_s, psf_sigma_px=self.psf_sigma_px)
        self._model = None
        self._torch = None
        self._device = device
        self.device_name = 'cpu'
        self.last_backend = 'classical'
        self.last_mode = 'hybrid_cog' if self.refine_subpixel else 'raw_trilateration'
        self.last_error: str | None = None
        self.last_fallback = False
        self.last_n_raw: int = 0
        self.last_n_after_gate: int = 0
        self.last_seed_policy: str = 'raster'

    def _ensure_model(self) -> object:
        if self._model is not None:
            return
        # Inspect existence, size, and SHA-256 BEFORE calling torch.load(..., weights_only=False)
        info = inspect_checkpoint_status(self.weights_path, expected_sha256=self.expected_sha256)
        self.checkpoint_status = info['status']
        self.checkpoint_sha256 = info['sha256']
        if info['status'] == 'missing':
            raise FileNotFoundError(str(info['error']))
        if info['status'] in ('corrupted_truncated', 'checksum_mismatch'):
            raise ValueError(str(info['error']))
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
        if device == 'cpu':
            try:
                torch.set_num_threads(min(4, max(1, os.cpu_count() or 2)))
            except Exception:
                pass
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
            self.last_error = _sanitize_error_text(f'{type(exc).__name__}: {exc}')
            _LOGGER.warning('CNN centroid backend unavailable (%s); falling back explicitly to classical CoG.', self.last_error)
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
        mask_bool: np.ndarray | None = None
        if mask is not None:
            mask_bool = np.asarray(mask, dtype=bool)
            if mask_bool.shape == seg.shape:
                seg = seg & ~mask_bool
        regime: str = _frame_bit_regime(raw)
        is_12bit_sim: bool = regime == '12bit'
        is_8bit: bool = regime == '8bit'
        rows, cols = nms_seed_pixels(dist, seg, _D_TH)
        if not self.refine_subpixel:
            self.last_mode = 'raw_trilateration'
            if is_12bit_sim:
                seed_scores: object = None
                self.last_seed_policy = 'raster'
            else:
                seed_scores = outdoor_seed_scores(raw, rows, cols)
                self.last_seed_policy = 'contrast_snr_16bit' if regime == '16bit' else 'contrast_snr'
            uv: object = trilateration_centroids(dist, seg, radius=self.radius, max_stars=int(self.max_stars), seed_scores=seed_scores, seeds=(rows, cols))
            self.last_fallback = False
            if uv.size == 0:
                self.last_n_raw = 0
                self.last_n_after_gate = 0
                self.last_backend = 'cnn_zhao2024'
                self.last_error = None
                return _empty_centroids(self.camera)
            keep: object = (uv[:, 0] >= 1.0) & (uv[:, 1] >= 1.0) & (uv[:, 0] < ow - 1.0) & (uv[:, 1] < oh - 1.0)
            uv = uv[keep]
            if len(uv) == 0:
                self.last_n_raw = 0
                self.last_n_after_gate = 0
                self.last_backend = 'cnn_zhao2024'
                self.last_error = None
                return _empty_centroids(self.camera)
            flux: object = np.zeros(len(uv), dtype=np.float64)
            peak: object = np.zeros(len(uv), dtype=np.float64)
            area: object = np.full(len(uv), 9.0, dtype=np.float64)
            h, w = raw.shape
            for i, (u, v) in enumerate(uv):
                pk, _ = _local_peak_and_bg(raw, float(u), float(v))
                peak[i] = pk
                x0: object = max(0, int(u) - 2)
                x1: object = min(w, int(u) + 3)
                y0: object = max(0, int(v) - 2)
                y1: object = min(h, int(v) + 3)
                flux[i] = float(raw[y0:y1, x0:x1].sum())
            self.last_n_raw = int(len(uv))
            if self.min_peak_dn > 0.0 and is_12bit_sim:
                bright: object = peak >= self.min_peak_dn
                uv = uv[bright]
                flux = flux[bright]
                peak = peak[bright]
                area = area[bright]
            self.last_n_after_gate = int(len(uv))
            if len(uv) == 0:
                self.last_backend = 'cnn_zhao2024'
                self.last_error = None
                return _empty_centroids(self.camera)
            order: object = np.argsort(-flux)
            if int(self.max_stars) > 0 and len(order) > int(self.max_stars):
                order = order[:int(self.max_stars)]
            uv = uv[order]
            flux = flux[order]
            peak = peak[order]
            area = area[order]
            z: object = np.zeros(len(uv), dtype=np.float64)
            vectors: object = self.camera.unproject(uv)
            self.last_backend = 'cnn_zhao2024'
            self.last_error = None
            return Centroids(uv=uv, flux=flux, area=area, peak=peak, mu20=z, mu02=z, mu11=z, axis_ratio=np.ones(len(uv), dtype=np.float64), angle_rad=z, vectors=vectors, sigma_px=np.full(len(uv), 0.5, dtype=np.float64))

        # CNN-Hybrid path: MobileUNet semantic mask + background-subtracted local CoG refinement + SNR gate
        self.last_mode = 'hybrid_cog'
        self.last_fallback = False
        if len(rows) == 0:
            self.last_n_raw = 0
            self.last_n_after_gate = 0
            self.last_backend = 'cnn_zhao2024'
            self.last_error = None
            return _empty_centroids(self.camera)

        smooth_bg: np.ndarray = cv2.boxFilter(raw, ddepth=-1, ksize=(31, 31), normalize=True, borderType=cv2.BORDER_REPLICATE)
        net: np.ndarray = raw - smooth_bg
        flat_net: np.ndarray = net.ravel()
        med_g: float = float(np.median(flat_net))
        mad_g: float = float(np.median(np.abs(flat_net - med_g)))
        sig_g: float = max(1.4826 * mad_g, 1.0)

        if is_12bit_sim:
            seed_scores = net[rows, cols].astype(np.float64)
            self.last_seed_policy = 'net_contrast_12bit'
            cap_raw: int = max(int(self.max_stars) * 2, 160) if int(self.max_stars) > 0 else 0
        else:
            seed_scores = outdoor_seed_scores(raw, rows, cols)
            self.last_seed_policy = 'contrast_snr_16bit' if regime == '16bit' else 'contrast_snr'
            cap_raw = int(self.max_stars) if int(self.max_stars) > 0 else 0

        uv_raw: np.ndarray = trilateration_centroids(dist, seg, radius=self.radius, max_stars=cap_raw, seed_scores=seed_scores, seeds=(rows, cols))
        if uv_raw.size == 0:
            self.last_n_raw = 0
            self.last_n_after_gate = 0
            self.last_backend = 'cnn_zhao2024'
            self.last_error = None
            return _empty_centroids(self.camera)

        h, w = raw.shape
        keep_bounds = (uv_raw[:, 0] >= 2.0) & (uv_raw[:, 1] >= 2.0) & (uv_raw[:, 0] < w - 2.0) & (uv_raw[:, 1] < h - 2.0)
        uv_raw = uv_raw[keep_bounds]
        self.last_n_raw = int(len(uv_raw))
        if len(uv_raw) == 0:
            self.last_n_after_gate = 0
            self.last_backend = 'cnn_zhao2024'
            self.last_error = None
            return _empty_centroids(self.camera)

        snr_gate: float = 1.5 if is_8bit else (4.0 if is_12bit_sim else 3.5)
        min_area: int = 1 if is_8bit else 3
        sat_thresh: float = 3900.0 if is_12bit_sim else (60000.0 if regime == '16bit' else 250.0)
        out_uv: list[tuple[float, float]] = []
        out_flux: list[float] = []
        out_peak: list[float] = []
        out_area: list[float] = []
        out_sig: list[float] = []

        for u0, v0 in uv_raw:
            ui, vi = (int(round(float(u0))), int(round(float(v0))))
            if mask_bool is not None and mask_bool.shape == raw.shape and bool(mask_bool[vi, ui]):
                continue
            sy0, sy1 = (max(0, vi - 2), min(h, vi + 3))
            sx0, sx1 = (max(0, ui - 2), min(w, ui + 3))
            sub_s = net[sy0:sy1, sx0:sx1]
            sub_max = float(sub_s.max())
            # Center on plateau when saturated or tied so bright stars do not bias top-left
            plat_y, plat_x = np.nonzero(sub_s >= sub_max - max(1.0, 0.01 * abs(sub_max)))
            if len(plat_y) > 1:
                py = sy0 + int(round(float(np.mean(plat_y))))
                px = sx0 + int(round(float(np.mean(plat_x))))
            else:
                flat_idx = int(np.argmax(sub_s))
                py = sy0 + flat_idx // sub_s.shape[1]
                px = sx0 + flat_idx % sub_s.shape[1]
            pk_raw = float(raw[py, px])
            if is_12bit_sim and self.min_peak_dn > 0.0 and pk_raw < self.min_peak_dn:
                continue

            by0, by1 = (max(0, py - _R_BG), min(h, py + _R_BG + 1))
            bx0, bx1 = (max(0, px - _R_BG), min(w, px + _R_BG + 1))
            patch_net = net[by0:by1, bx0:bx1]
            my0, my1 = (_R_BG - (py - by0), _R_BG + (by1 - py))
            mx0, mx1 = (_R_BG - (px - bx0), _R_BG + (bx1 - px))
            ann_vals = patch_net[_ANNULUS_BG[my0:my1, mx0:mx1]]
            bg_loc = float(np.median(ann_vals)) if ann_vals.size >= 8 else 0.0
            mad_loc = float(np.median(np.abs(ann_vals - bg_loc))) if ann_vals.size >= 8 else 0.0
            sig_loc = max(1.4826 * mad_loc, 0.5 * sig_g, 1.0)
            pk_net = float(net[py, px]) - bg_loc
            snr = pk_net / sig_loc
            if snr < snr_gate:
                continue

            r_ap: int = 2 if is_8bit else (5 if pk_raw >= sat_thresh else 3)
            ay0, ay1 = (max(0, py - r_ap), min(h, py + r_ap + 1))
            ax0, ax1 = (max(0, px - r_ap), min(w, px + r_ap + 1))
            gy, gx = np.mgrid[ay0:ay1, ax0:ax1]
            r2_ap = (gx - px) ** 2 + (gy - py) ** 2
            ap_net = net[ay0:ay1, ax0:ax1] - bg_loc
            thr = (1.5 if is_8bit else 2.0) * sig_loc
            active = (r2_ap <= (r_ap + 0.5) ** 2) & (ap_net > thr)
            cy_l, cx_l = (py - ay0, px - ax0)
            active[cy_l, cx_l] = ap_net[cy_l, cx_l] > 0.0
            _, cc_lbl = cv2.connectedComponents(active.astype(np.uint8), connectivity=8)
            pk_lbl = int(cc_lbl[cy_l, cx_l])
            in_star = (cc_lbl == pk_lbl) if pk_lbl > 0 else ((r2_ap <= 4.0) & (ap_net > 0.0))
            area_px = int(np.count_nonzero(in_star))
            if area_px < min_area:
                continue

            wt = np.where(in_star, np.maximum(ap_net, 0.0), 0.0)
            f_sum = float(wt.sum())
            # Reject single-pixel hot pixels & cosmic rays (>75% of aperture energy in 1 pixel)
            if not is_8bit and f_sum > 0.0 and (pk_net / f_sum) > 0.75:
                continue
            if f_sum > 0.0:
                u_ref = float((wt * gx).sum() / f_sum)
                v_ref = float((wt * gy).sum() / f_sum)
                if float(np.hypot(u_ref - float(u0), v_ref - float(v0))) <= 3.0:
                    u_fin, v_fin = (u_ref, v_ref)
                else:
                    u_fin, v_fin = (float(u0), float(v0))
            else:
                u_fin, v_fin = (float(u0), float(v0))

            if any(float(np.hypot(u_fin - eu, v_fin - ev)) < 2.2 for eu, ev in out_uv):
                continue

            snr_flux = f_sum / max(sig_loc * float(np.sqrt(max(area_px, 1))), 1.0)
            pos_sig = self.psf_sigma_px / max(float(np.sqrt(max(snr_flux, 1.0))), 1.0)
            if is_8bit:
                pos_sig = max(pos_sig, 0.5)
                fx0, fx1 = (max(0, int(u_fin) - 2), min(w, int(u_fin) + 3))
                fy0, fy1 = (max(0, int(v_fin) - 2), min(h, int(v_fin) + 3))
                rank_flux = float(raw[fy0:fy1, fx0:fx1].sum())
            else:
                rank_flux = max(f_sum, pk_net, 1.0)
            out_uv.append((u_fin, v_fin))
            out_flux.append(rank_flux)
            out_peak.append(pk_raw)
            out_area.append(float(area_px))
            out_sig.append(pos_sig)

        self.last_n_after_gate = int(len(out_uv))
        if not out_uv:
            self.last_backend = 'cnn_zhao2024'
            self.last_error = None
            return _empty_centroids(self.camera)

        uv_arr = np.asarray(out_uv, dtype=np.float64)
        flux_arr = np.asarray(out_flux, dtype=np.float64)
        peak_arr = np.asarray(out_peak, dtype=np.float64)
        area_arr = np.asarray(out_area, dtype=np.float64)
        sig_arr = np.asarray(out_sig, dtype=np.float64)
        order = np.argsort(-flux_arr)
        if int(self.max_stars) > 0 and len(order) > int(self.max_stars):
            order = order[:int(self.max_stars)]
        uv_arr = uv_arr[order]
        flux_arr = flux_arr[order]
        peak_arr = peak_arr[order]
        area_arr = area_arr[order]
        sig_arr = sig_arr[order]
        z = np.zeros(len(uv_arr), dtype=np.float64)
        vectors = self.camera.unproject(uv_arr)
        self.last_backend = 'cnn_zhao2024'
        self.last_error = None
        return Centroids(uv=uv_arr, flux=flux_arr, area=area_arr, peak=peak_arr, mu20=z, mu02=z, mu11=z, axis_ratio=np.ones(len(uv_arr), dtype=np.float64), angle_rad=z, vectors=vectors, sigma_px=sig_arr)

def match_centroid_rmse(pred_uv: np.ndarray, gt_uv: np.ndarray, match_radius_px: float=5.0) -> dict:
    """Greedy nearest-neighbor match; RMSE over matched pairs plus precision/recall/F1."""
    pred: object = np.asarray(pred_uv, dtype=np.float64).reshape(-1, 2)
    gt: object = np.asarray(gt_uv, dtype=np.float64).reshape(-1, 2)
    n_pred: int = int(len(pred))
    n_gt: int = int(len(gt))
    errs: list[float] = []
    if n_pred > 0 and n_gt > 0:
        used: object = np.zeros(n_pred, dtype=bool)
        for g in gt:
            d: object = np.linalg.norm(pred - g, axis=1)
            d[used] = np.inf
            j: int = int(np.argmin(d))
            if not np.isfinite(d[j]) or d[j] > match_radius_px:
                continue
            used[j] = True
            errs.append(float(d[j]))
    n_matched: int = len(errs)
    n_false_pos: int = n_pred - n_matched
    n_false_neg: int = n_gt - n_matched
    precision: float = float(n_matched / n_pred) if n_pred > 0 else (1.0 if n_gt == 0 else 0.0)
    recall: float | None = float(n_matched / n_gt) if n_gt > 0 else None
    if precision is not None and recall is not None and (precision + recall) > 0.0:
        f1: float | None = float(2.0 * precision * recall / (precision + recall))
    else:
        f1 = 0.0 if n_gt > 0 else None
    arr: object = np.asarray(errs, dtype=np.float64)
    return {
        'n_pred': n_pred,
        'n_gt': n_gt,
        'n_matched': n_matched,
        'n_false_pos': n_false_pos,
        'n_false_neg': n_false_neg,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'rmse_px': float(np.sqrt(np.mean(arr ** 2))) if n_matched > 0 else None,
        'mean_err_px': float(np.mean(arr)) if n_matched > 0 else None,
    }
