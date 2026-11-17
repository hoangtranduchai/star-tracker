"""Prepare and verify ground-truth manifest for real calibrated sky frames.

Covers four real-sky dataset groups under e:\\SangTaoTreQG:
1. ESA tetra3 lab/night-sky frames (data/tetra3/*.tiff)
2. Zhao et al. calibrated MT9V022 frames (data/real_calibrated/zhao_mt9v022/*.npy)
3. UW LOST Mount St. Helens outdoor wide-FOV photo (data/uploads/mount_st_helens_1.png)
4. NTNU wide-angle uncalibrated distortion stress frame (data/uploads/real_sky/images/0006.png)

All quaternions follow StarTracker scalar-first convention q = [w, x, y, z]
such that b_cam = to_dcm(q) @ r_icrs with camera +Z boresight, +X right, +Y down,
and pixel centers at (0, 0) top-left (principal point ((W-1)/2, (H-1)/2) unless
explicitly calibrated otherwise).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import label
from scipy.optimize import least_squares

# NumPy 2.x removed np.math, which third_party/tetra3_ref references.
if not hasattr(np, 'math'):
    np.math = math

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / 'scripts') not in sys.path:
    sys.path.insert(0, str(ROOT / 'scripts'))
TETRA3_DIR = ROOT / 'third_party' / 'tetra3_ref'
if TETRA3_DIR.is_dir() and str(TETRA3_DIR) not in sys.path:
    sys.path.insert(0, str(TETRA3_DIR))

from compare_mount_st_helens_centroids import terrain_mask
from src.attitude import WahbaSolver
from src.camera import CameraModel
from src.catalog import CatalogManager, StarCatalog, vectors_to_ra_dec
from src.centroid import CentroidDetector
from src.centroid_cnn import CNNCentroidDetector, weights_available
from src.demo_session import (
    DemoEngine,
    load_frame,
    load_pipeline_cfg,
    match_tolerance_arcsec,
    theta_max_deg_for_fov,
)
from src.pipeline import StarTrackerPipeline
from src.quaternion import (
    ARCSEC_PER_RAD,
    angular_error_arcsec,
    boresight_ra_dec_deg,
    format_dec_dms,
    format_ra_hms,
    from_dcm,
    to_dcm,
)
from src.starnames import lookup_hip, lookup_hr

# Zhao et al. MT9V022 MATLAB calibration constants (main_detection_centroiding.py L243-246)
ZHAO_FOCAL_PX = 2680.049125
ZHAO_PIXEL_UM = 6.0
ZHAO_FOCAL_MM = ZHAO_FOCAL_PX * (ZHAO_PIXEL_UM * 0.001)  # 16.08029475 mm
ZHAO_CX = 352.84399
ZHAO_CY = 199.46077
ZHAO_HEIKKILA_P = (
    4.72251629e-06,
    -1.47548083e-11,
    5.40718521e-10,
    3.15303463e-10,
    -1.47546930e-11,
    1.26044011e-15,
    -2.20571693e-14,
    4.72252718e-06,
)
UW_LOST_MSH_RA_DEG = 310.446
UW_LOST_MSH_DEC_DEG = 36.0229
MAX_VERIFY_RMS_PX = 1.5
MAX_ALT60_SEP_DEG = 0.5


def rodrigues(rotvec: np.ndarray) -> np.ndarray:
    """Convert 3-vector axis-angle (rad) to a 3x3 SO(3) rotation matrix."""
    theta = float(np.linalg.norm(rotvec))
    if theta < 1e-15:
        return np.eye(3, dtype=np.float64)
    kx, ky, kz = rotvec / theta
    skew = np.array(
        [[0.0, -kz, ky], [kz, 0.0, -kx], [-ky, kx, 0.0]],
        dtype=np.float64,
    )
    return (
        np.eye(3, dtype=np.float64)
        + math.sin(theta) * skew
        + (1.0 - math.cos(theta)) * (skew @ skew)
    )


def ang_sep_deg(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    """Great-circle angular separation between two (RA, Dec) sky coordinates in degrees."""
    r1, d1, r2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    cos_ang = math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(r1 - r2)
    return float(math.degrees(math.acos(max(-1.0, min(1.0, cos_ang)))))


def zhao_distortion_correction(
    centroids_distorted: np.ndarray,
    p: tuple[float, ...],
    u_0: float,
    v_0: float,
) -> np.ndarray:
    """Apply Zhao et al. / Heikkila polynomial inverse distortion model to pixel centroids."""
    a1, a2, a3, a4, a5, a6, a7, a8 = p
    out = np.empty((len(centroids_distorted), 2), dtype=np.float64)
    for i, (u, v) in enumerate(centroids_distorted):
        ud = float(u) - u_0
        vd = float(v) - v_0
        r2 = ud * ud + vd * vd
        r4 = r2 * r2
        g_den = (a5 * r2 + a6 * ud + a7 * vd + a8) * r2 + 1.0
        uu = (1.0 / g_den) * (ud + ud * (a1 * r2 + a2 * r4) + 2.0 * a3 * ud * vd + a4 * (r2 + 2.0 * ud * ud))
        vv = (1.0 / g_den) * (vd + vd * (a1 * r2 + a2 * r4) + a3 * (r2 + 2.0 * vd * vd) + 2.0 * a4 * ud * vd)
        out[i, 0] = uu + u_0
        out[i, 1] = vv + v_0
    return out


def zhao_forward_distort(
    uv_undistorted: np.ndarray,
    p: tuple[float, ...],
    u_0: float,
    v_0: float,
    n_iter: int = 6,
) -> np.ndarray:
    """Invert Zhao's undistortion map via fixed-point iteration to project onto raw image."""
    uv_g = np.asarray(uv_undistorted, dtype=np.float64).copy()
    for _ in range(n_iter):
        pred_u = zhao_distortion_correction(uv_g, p, u_0, v_0)
        uv_g += uv_undistorted - pred_u
    return uv_g


def load_hipparcos_and_bsc5_bridge(
    epoch_year: float,
    max_mag: float = 8.0,
    max_match_arcsec: float = 15.0,
) -> tuple[StarCatalog, dict[int, int]]:
    """Load Hipparcos I/239 TSV at `epoch_year` and build HIP->HR lookup from BSC5."""
    tsv_path = ROOT / 'data' / 'catalogs' / 'starcat.tsv'
    bsc_path = ROOT / 'data' / 'catalogs' / 'bsc5_v6.0.npz'
    cat_hip = CatalogManager.load_hipparcos_tsv(tsv_path, max_mag=max_mag, epoch_year=epoch_year)
    hip_to_hr: dict[int, int] = {}
    if bsc_path.is_file():
        cat_bsc = CatalogManager.load_npz(bsc_path)
        cos_thresh = math.cos(math.radians(max_match_arcsec / 3600.0))
        # Block-wise dot product to map each BSC5 star to nearest Hipparcos entry.
        step = 256
        best_hip = np.full(cat_bsc.num_stars, -1, dtype=np.int32)
        best_cos = np.full(cat_bsc.num_stars, -1.0, dtype=np.float64)
        for start in range(0, cat_bsc.num_stars, step):
            stop = min(start + step, cat_bsc.num_stars)
            gram = cat_bsc.vectors[start:stop] @ cat_hip.vectors.T
            idx = np.argmax(gram, axis=1)
            vals = gram[np.arange(stop - start), idx]
            best_hip[start:stop] = cat_hip.ids[idx]
            best_cos[start:stop] = vals
        for i in range(cat_bsc.num_stars):
            if best_cos[i] >= cos_thresh:
                hip_id = int(best_hip[i])
                hr_id = int(cat_bsc.ids[i])
                if hip_id not in hip_to_hr:
                    hip_to_hr[hip_id] = hr_id
    return cat_hip, hip_to_hr


def project_with_custom_optics(
    vec_cam: np.ndarray,
    width: int,
    height: int,
    focal_mm: float,
    pixel_um: float,
    cx: float,
    cy: float,
    k1: float = 0.0,
    k2: float = 0.0,
    edge_margin_px: float = 2.0,
    forward_distort_fn=None,
) -> tuple[np.ndarray, np.ndarray]:
    """Project camera-frame J2000 vectors to pixel coordinates with arbitrary (cx, cy)."""
    vx, vy, vz = vec_cam[:, 0], vec_cam[:, 1], vec_cam[:, 2]
    front = vz > 0.1
    uv_out = np.full((len(vec_cam), 2), np.nan, dtype=np.float64)
    if not np.any(front):
        return uv_out, np.zeros(len(vec_cam), dtype=bool)
    f_px = focal_mm / (pixel_um * 0.001)
    xu = vx[front] / vz[front]
    yu = vy[front] / vz[front]
    if k1 != 0.0 or k2 != 0.0:
        r2 = xu * xu + yu * yu
        rad = 1.0 + k1 * r2 + k2 * (r2 * r2)
        xu = xu * rad
        yu = yu * rad
    uv_front = np.column_stack((f_px * xu + cx, f_px * yu + cy))
    if forward_distort_fn is not None:
        uv_front = forward_distort_fn(uv_front)
    uv_out[front] = uv_front
    u_all, v_all = uv_out[:, 0], uv_out[:, 1]
    inside = (
        front
        & (u_all >= edge_margin_px)
        & (u_all < width - edge_margin_px)
        & (v_all >= edge_margin_px)
        & (v_all < height - edge_margin_px)
    )
    return uv_out, inside


def build_stars_in_fov(
    q_gt: np.ndarray,
    width: int,
    height: int,
    focal_mm: float,
    pixel_um: float,
    cx: float,
    cy: float,
    cat_hip: StarCatalog,
    hip_to_hr: dict[int, int],
    max_mag: float,
    k1: float = 0.0,
    k2: float = 0.0,
    forward_distort_fn=None,
    sky_mask: np.ndarray | None = None,
) -> list[dict]:
    """Project in-FOV catalog stars (mag <= max_mag) and format manifest records."""
    dcm = to_dcm(q_gt)
    cam_vecs = (dcm @ cat_hip.vectors.T).T
    uv_all, inside = project_with_custom_optics(
        cam_vecs,
        width=width,
        height=height,
        focal_mm=focal_mm,
        pixel_um=pixel_um,
        cx=cx,
        cy=cy,
        k1=k1,
        k2=k2,
        edge_margin_px=2.0,
        forward_distort_fn=forward_distort_fn,
    )
    cand_indices = np.flatnonzero(inside & (cat_hip.mags <= float(max_mag)))
    ra_rad, dec_rad = vectors_to_ra_dec(cat_hip.vectors[cand_indices])
    rows = []
    for pos, c_idx in enumerate(cand_indices):
        u_px, v_px = float(uv_all[c_idx, 0]), float(uv_all[c_idx, 1])
        if sky_mask is not None:
            ui, vi = int(round(u_px)), int(round(v_px))
            if not (0 <= ui < width and 0 <= vi < height) or bool(sky_mask[vi, ui]):
                continue
        hip_id = int(cat_hip.ids[c_idx])
        hr_id = hip_to_hr.get(hip_id)
        iau = lookup_hip(hip_id) or (lookup_hr(hr_id) if hr_id is not None else None) or {}
        iau_name = iau.get('name')
        desig = iau.get('designation') or None
        if iau_name:
            label_str = f'{iau_name} (HIP {hip_id})'
        elif hr_id is not None:
            label_str = f'HR {hr_id} / HIP {hip_id}'
        else:
            label_str = f'HIP {hip_id}'
        rows.append(
            {
                'hip': hip_id,
                'hr': hr_id,
                'iau_name': iau_name,
                'designation': desig,
                'label': label_str,
                'mag': float(cat_hip.mags[c_idx]),
                'u_px': u_px,
                'v_px': v_px,
                'ra_deg': float(math.degrees(ra_rad[pos])),
                'dec_deg': float(math.degrees(dec_rad[pos])),
            }
        )
    rows.sort(key=lambda item: item['mag'])
    return rows


def match_centroids_to_catalog(
    det_uv: np.ndarray,
    stars_in_fov: list[dict],
    max_dist_px: float = 3.0,
) -> tuple[float | None, float | None, int]:
    """Mutual/nearest residual stats between detected centroids and projected catalog stars."""
    if len(det_uv) == 0 or not stars_in_fov:
        return None, None, 0
    cat_uv = np.array([[s['u_px'], s['v_px']] for s in stars_in_fov], dtype=np.float64)
    dists = np.hypot(det_uv[:, 0:1] - cat_uv[None, :, 0], det_uv[:, 1:2] - cat_uv[None, :, 1])
    min_d = dists.min(axis=1)
    inliers = min_d[min_d < max_dist_px]
    if inliers.size == 0:
        return None, None, 0
    rms = float(np.sqrt(np.mean(inliers * inliers)))
    med = float(np.median(inliers))
    return rms, med, int(inliers.size)


def solve_tetra3_frame(
    tiff_path: Path,
    t3,
    cat_hip: StarCatalog,
    hip_to_hr: dict[int, int],
    engine: DemoEngine,
) -> dict:
    """Solve full 3-DOF J2000 reference q_gt + (f, k1) for an ESA tetra3 TIFF frame."""
    with Image.open(tiff_path) as im:
        sol = t3.solve_from_image(im, distortion=[-0.2, 0.1], return_matches=True)
    if sol.get('RA') is None:
        raise RuntimeError(f'tetra3 failed to solve {tiff_path}')
    img = load_frame(tiff_path)
    height, width = img.shape[:2]
    pixel_um = 6.9
    nominal_f_mm = 35.0
    cam_nom = CameraModel(width=width, height=height, pixel_um=pixel_um, focal_mm=nominal_f_mm)
    cx, cy = float(cam_nom.cx), float(cam_nom.cy)

    # Convert tetra3 (y, x) centroids with (0.5, 0.5) pixel origin to StarTracker (0, 0) origin.
    m_yx = np.asarray(sol['matched_centroids'], dtype=np.float64)
    m_uv_st = np.column_stack((m_yx[:, 1] - 0.5, m_yx[:, 0] - 0.5))
    hip_map = {int(hid): i for i, hid in enumerate(cat_hip.ids)}
    keep_idx, vecs = [], []
    for pos, hid in enumerate(sol['matched_catID']):
        c_i = hip_map.get(int(hid))
        if c_i is not None:
            keep_idx.append(pos)
            vecs.append(cat_hip.vectors[c_i])
    m_uv_st = m_uv_st[keep_idx]
    m_vecs = np.asarray(vecs, dtype=np.float64)

    _, a_init = WahbaSolver.solve_svd(cam_nom.unproject(m_uv_st), m_vecs)
    px_mm = pixel_um * 0.001

    def res_fn(params: np.ndarray) -> np.ndarray:
        dcm = rodrigues(params[:3]) @ a_init
        f_mm, k1 = float(params[3]), float(params[4])
        vc = (dcm @ m_vecs.T).T
        xu, yu = vc[:, 0] / vc[:, 2], vc[:, 1] / vc[:, 2]
        rad = 1.0 + k1 * (xu * xu + yu * yu)
        u_pred = (f_mm / px_mm) * (xu * rad) + cx
        v_pred = (f_mm / px_mm) * (yu * rad) + cy
        return np.concatenate((u_pred - m_uv_st[:, 0], v_pred - m_uv_st[:, 1]))

    opt = least_squares(res_fn, np.array([0.0, 0.0, 0.0, nominal_f_mm, 0.0], dtype=np.float64))
    a_cal = rodrigues(opt.x[:3]) @ a_init
    q_gt = from_dcm(a_cal)
    f_cal, k1_cal = float(opt.x[3]), float(opt.x[4])
    ra_deg, dec_deg = boresight_ra_dec_deg(q_gt)

    # Verify against StarTracker CentroidDetector CoG detections.
    cam_cal = CameraModel(width=width, height=height, pixel_um=pixel_um, focal_mm=f_cal, k1=k1_cal)
    cents_cog = CentroidDetector(cam_cal, k_sigma=4.0, bg_block=64, min_area=3).detect(img)
    stars_fov = build_stars_in_fov(
        q_gt=q_gt,
        width=width,
        height=height,
        focal_mm=f_cal,
        pixel_um=pixel_um,
        cx=cx,
        cy=cy,
        cat_hip=cat_hip,
        hip_to_hr=hip_to_hr,
        max_mag=7.0,
        k1=k1_cal,
    )
    rms_cog, med_cog, n_matched_cog = match_centroids_to_catalog(cents_cog.uv, stars_fov, max_dist_px=3.0)
    t3_res = opt.fun.reshape(2, -1)
    rms_t3 = float(np.sqrt(np.mean(t3_res[0] ** 2 + t3_res[1] ** 2)))
    ref_rms = rms_cog if rms_cog is not None else rms_t3
    if ref_rms >= MAX_VERIFY_RMS_PX:
        raise RuntimeError(f'{tiff_path.name} ref_rms_px={ref_rms:.3f} >= {MAX_VERIFY_RMS_PX}')

    crosscheck = {
        'tetra3_ra_deg': float(sol['RA']),
        'tetra3_dec_deg': float(sol['Dec']),
        'tetra3_fov_deg': float(sol['FOV']),
        'tetra3_matches': int(sol['Matches']),
        'tetra3_reproj_rms_px': rms_t3,
        'boresight_sep_vs_tetra3_deg': ang_sep_deg(ra_deg, dec_deg, float(sol['RA']), float(sol['Dec'])),
    }

    # On Alt60, verify 3-DOF angular agreement against StarTrackerPipeline with nominal f=35mm.
    if 'Alt60' in tiff_path.name:
        cat_b, _, kv_b = engine.stack('bsc5', 6.0, theta_max_deg_for_fov(float(cam_nom.fov_deg[2])))
        cfg = load_pipeline_cfg('fast')
        cfg.angular_tol_rad = match_tolerance_arcsec(cam_nom) / ARCSEC_PER_RAD
        cfg.tol_frac = 0.008
        st_res = StarTrackerPipeline(cam_nom, cat_b, kv_b, cfg).process_frame(img)
        if not st_res.success:
            raise RuntimeError(f'StarTrackerPipeline failed on {tiff_path.name}: {st_res.error}')
        sep_3dof_deg = angular_error_arcsec(st_res.q, q_gt) / 3600.0
        if sep_3dof_deg >= MAX_ALT60_SEP_DEG:
            raise RuntimeError(f'Alt60 3-DOF sep {sep_3dof_deg:.4f} deg >= {MAX_ALT60_SEP_DEG}')
        crosscheck['startracker_bsc5_3dof_sep_deg'] = float(sep_3dof_deg)
        crosscheck['startracker_bsc5_matched'] = int(len(st_res.ident.obs_idx))

    rel_path = str(tiff_path.relative_to(ROOT)).replace('\\', '/')
    return {
        'path': rel_path,
        'dataset_group': 'esa_tetra3',
        'width': int(width),
        'height': int(height),
        'focal_mm': f_cal,
        'focal_mm_nominal': nominal_f_mm,
        'pixel_um': pixel_um,
        'calibrated_cx': cx,
        'calibrated_cy': cy,
        'k1': k1_cal,
        'k2': 0.0,
        'distortion_note': (
            f'FLIR Blackfly S IMX265 (nominal f={nominal_f_mm} mm, pixel={pixel_um} um); '
            f'scipy least-squares refined f={f_cal:.5f} mm, radial k1={k1_cal:.5f} '
            'in StarTracker 0-origin pixel convention.'
        ),
        'q_gt': q_gt.tolist(),
        'boresight_ra_deg': ra_deg,
        'boresight_dec_deg': dec_deg,
        'boresight_ra_hms': format_ra_hms(ra_deg),
        'boresight_dec_dms': format_dec_dms(dec_deg),
        'gt_source': 'esa_tetra3_hipparcos_plus_scipy_f_k1',
        'catalog_max_mag': 7.0,
        'ref_rms_px': float(ref_rms),
        'ref_median_px': med_cog,
        'n_detected_cog': int(len(cents_cog.uv)),
        'n_matched_cog': n_matched_cog,
        'crosscheck': crosscheck,
        'stars_in_fov': stars_fov,
    }


def _extract_zhao_cog(arr: np.ndarray) -> np.ndarray:
    """Extract multi-pixel CoG centroids sorted brightest-first on Zhao float64 MT9V022 frames."""
    bg = float(np.median(arr))
    mad = float(np.median(np.abs(arr - bg)))
    sig_bg = 1.4826 * mad if mad > 1e-6 else float(np.std(arr))
    thresh = max(bg + 4.0 * max(sig_bg, 0.5), 4.0)
    lbl_img, n_cc = label(arr > thresh)
    pts = []
    for idx in range(1, int(n_cc) + 1):
        mask = lbl_img == idx
        if int(mask.sum()) < 2:
            continue
        ys, xs = np.nonzero(mask)
        weights = np.maximum(arr[mask] - bg, 0.0)
        flux = float(weights.sum())
        if flux <= 0.0:
            continue
        u_c = float((xs * weights).sum() / flux)
        v_c = float((ys * weights).sum() / flux)
        pts.append((flux, u_c, v_c))
    pts.sort(reverse=True)
    if not pts:
        return np.empty((0, 2), dtype=np.float64)
    return np.asarray([[item[1], item[2]] for item in pts], dtype=np.float64)


def solve_zhao_frame(
    npy_path: Path,
    t3,
    cat_hip: StarCatalog,
    hip_to_hr: dict[int, int],
) -> dict:
    """Solve full 3-DOF J2000 reference for Zhao et al. MT9V022 frames or document sparsity."""
    arr = np.load(npy_path).astype(np.float64)
    height, width = arr.shape[:2]
    uv_cog = _extract_zhao_cog(arr)
    uv_und = zhao_distortion_correction(uv_cog, ZHAO_HEIKKILA_P, ZHAO_CX, ZHAO_CY)
    rel_path = str(npy_path.relative_to(ROOT)).replace('\\', '/')
    base_entry = {
        'path': rel_path,
        'dataset_group': 'zhao_mt9v022',
        'width': int(width),
        'height': int(height),
        'focal_mm': ZHAO_FOCAL_MM,
        'focal_mm_nominal': 16.0,
        'pixel_um': ZHAO_PIXEL_UM,
        'calibrated_cx': ZHAO_CX,
        'calibrated_cy': ZHAO_CY,
        'k1': 0.0,
        'k2': 0.0,
        'heikkila_p': list(ZHAO_HEIKKILA_P),
    }

    if len(uv_und) < 5:
        # Honest report for sparse/unsolvable 4-star verification image.
        base_entry.update(
            {
                'distortion_note': (
                    f'Aptina MT9V022 (640x480, 6.0 um, f_px={ZHAO_FOCAL_PX}, '
                    f'cx={ZHAO_CX}, cy={ZHAO_CY}); Heikkila polynomial distortion applied. '
                    f'Unsolvable: only {len(uv_und)} multi-pixel spots detected on zero background '
                    f'(centroids={np.round(uv_cog, 2).tolist()}), insufficient for unambiguous '
                    '3-DOF lost-in-space plate solving against Hipparcos/BSC5.'
                ),
                'q_gt': None,
                'boresight_ra_deg': None,
                'boresight_dec_deg': None,
                'boresight_ra_hms': None,
                'boresight_dec_dms': None,
                'gt_source': f'unsolvable_sparse_{len(uv_und)}_stars',
                'catalog_max_mag': None,
                'ref_rms_px': None,
                'ref_median_px': None,
                'n_detected_cog': int(len(uv_cog)),
                'n_matched_cog': 0,
                'stars_in_fov': [],
            }
        )
        return base_entry

    # Shift undistorted coordinates so tetra3 image center aligns with Zhao's (ZHAO_CX, ZHAO_CY).
    fov_h_deg = math.degrees(2.0 * math.atan(width / (2.0 * ZHAO_FOCAL_PX)))
    uv_t3 = np.column_stack((uv_und[:, 1] - ZHAO_CY + height * 0.5, uv_und[:, 0] - ZHAO_CX + width * 0.5))
    sol = t3.solve_from_centroids(
        uv_t3,
        (height, width),
        fov_estimate=fov_h_deg,
        fov_max_error=0.5,
        distortion=None,
        pattern_checking_stars=min(12, len(uv_t3)),
        match_threshold=1e-2,
        return_matches=True,
    )
    if sol.get('RA') is None:
        base_entry.update(
            {
                'distortion_note': 'MT9V022 calibrated optics; plate solver found no match.',
                'q_gt': None,
                'boresight_ra_deg': None,
                'boresight_dec_deg': None,
                'boresight_ra_hms': None,
                'boresight_dec_dms': None,
                'gt_source': 'unsolvable_no_plate_match',
                'catalog_max_mag': None,
                'ref_rms_px': None,
                'ref_median_px': None,
                'n_detected_cog': int(len(uv_cog)),
                'n_matched_cog': 0,
                'stars_in_fov': [],
            }
        )
        return base_entry

    m_yx = np.asarray(sol['matched_centroids'], dtype=np.float64)
    m_uv_und = np.column_stack((m_yx[:, 1] - width * 0.5 + ZHAO_CX, m_yx[:, 0] - height * 0.5 + ZHAO_CY))
    hip_map = {int(hid): i for i, hid in enumerate(cat_hip.ids)}
    keep_idx, vecs = [], []
    for pos, hid in enumerate(sol['matched_catID']):
        c_i = hip_map.get(int(hid))
        if c_i is not None:
            keep_idx.append(pos)
            vecs.append(cat_hip.vectors[c_i])
    m_uv_und = m_uv_und[keep_idx]
    m_vecs = np.asarray(vecs, dtype=np.float64)

    b_vecs = np.column_stack((m_uv_und[:, 0] - ZHAO_CX, m_uv_und[:, 1] - ZHAO_CY, np.full(len(m_uv_und), ZHAO_FOCAL_PX)))
    b_vecs /= np.linalg.norm(b_vecs, axis=1, keepdims=True)
    _, a_init = WahbaSolver.solve_svd(b_vecs, m_vecs)

    # Refine 3-DOF rotation holding Zhao's calibrated intrinsics fixed.
    def res_rot(rotvec: np.ndarray) -> np.ndarray:
        dcm = rodrigues(rotvec) @ a_init
        vc = (dcm @ m_vecs.T).T
        u_pred = ZHAO_FOCAL_PX * (vc[:, 0] / vc[:, 2]) + ZHAO_CX
        v_pred = ZHAO_FOCAL_PX * (vc[:, 1] / vc[:, 2]) + ZHAO_CY
        return np.concatenate((u_pred - m_uv_und[:, 0], v_pred - m_uv_und[:, 1]))

    opt = least_squares(res_rot, np.zeros(3, dtype=np.float64))
    a_cal = rodrigues(opt.x) @ a_init
    q_gt = from_dcm(a_cal)
    ra_deg, dec_deg = boresight_ra_dec_deg(q_gt)

    stars_fov = build_stars_in_fov(
        q_gt=q_gt,
        width=width,
        height=height,
        focal_mm=ZHAO_FOCAL_MM,
        pixel_um=ZHAO_PIXEL_UM,
        cx=ZHAO_CX,
        cy=ZHAO_CY,
        cat_hip=cat_hip,
        hip_to_hr=hip_to_hr,
        max_mag=7.0,
        forward_distort_fn=lambda uv_u: zhao_forward_distort(uv_u, ZHAO_HEIKKILA_P, ZHAO_CX, ZHAO_CY),
    )
    rms_cog, med_cog, n_matched = match_centroids_to_catalog(uv_cog, stars_fov, max_dist_px=3.0)
    if rms_cog is None or rms_cog >= MAX_VERIFY_RMS_PX:
        raise RuntimeError(f'{npy_path.name} ref_rms_px={rms_cog} >= {MAX_VERIFY_RMS_PX}')

    # Cross-check with StarTracker's CentroidDetector too.
    cam_z = CameraModel(width=width, height=height, pixel_um=ZHAO_PIXEL_UM, focal_mm=ZHAO_FOCAL_MM)
    st_cog = CentroidDetector(cam_z, k_sigma=3.0, bg_block=31, min_area=3, min_contrast_sigma=5.0).detect(arr)
    rms_st, med_st, n_st = match_centroids_to_catalog(st_cog.uv, stars_fov, max_dist_px=3.0)

    base_entry.update(
        {
            'distortion_note': (
                f'Aptina MT9V022 MATLAB calibration from Zhao main_detection_centroiding.py '
                f'(f_px={ZHAO_FOCAL_PX}, cx={ZHAO_CX}, cy={ZHAO_CY}, Heikkila 8-param p); '
                'stars_in_fov forward-distorted onto raw image pixel coordinates.'
            ),
            'q_gt': q_gt.tolist(),
            'boresight_ra_deg': ra_deg,
            'boresight_dec_deg': dec_deg,
            'boresight_ra_hms': format_ra_hms(ra_deg),
            'boresight_dec_dms': format_dec_dms(dec_deg),
            'gt_source': 'zhao_heikkila_undistort_plus_hipparcos_3dof',
            'catalog_max_mag': 7.0,
            'ref_rms_px': float(rms_cog),
            'ref_median_px': med_cog,
            'n_detected_cog': int(len(uv_cog)),
            'n_matched_cog': n_matched,
            'crosscheck': {
                'tetra3_matches': int(sol['Matches']),
                'tetra3_fov_deg': float(sol['FOV']),
                'st_cog_detected': int(len(st_cog.uv)),
                'st_cog_matched': n_st,
                'st_cog_rms_px': rms_st,
                'st_cog_median_px': med_st,
            },
            'stars_in_fov': stars_fov,
        }
    )
    return base_entry


def solve_mount_st_helens(
    png_path: Path,
    cat_hip: StarCatalog,
    hip_to_hr: dict[int, int],
    engine: DemoEngine,
) -> dict:
    """Solve & verify full 3-DOF J2000 reference for UW LOST Mount St. Helens photo."""
    gray = load_frame(png_path)
    height, width = gray.shape[:2]
    pixel_um = 4.1
    nominal_f_mm = 4.2
    cam_nom = CameraModel(width=width, height=height, pixel_um=pixel_um, focal_mm=nominal_f_mm)
    cx, cy = float(cam_nom.cx), float(cam_nom.cy)
    mask_terrain = terrain_mask(gray)

    # Initial lost-in-space solve using StarTrackerPipeline (CNN when weights exist for speed).
    cat_id, _, kv_id = engine.stack('hipparcos', 6.0, theta_max_deg_for_fov(float(cam_nom.fov_deg[2])))
    cfg = load_pipeline_cfg('fast')
    cfg.angular_tol_rad = match_tolerance_arcsec(cam_nom) / ARCSEC_PER_RAD
    cfg.tol_frac = 0.008
    cfg.centroid_backend = 'cnn' if weights_available() else 'classical'
    init_res = StarTrackerPipeline(cam_nom, cat_id, kv_id, cfg).process_frame(gray)
    if not init_res.success:
        raise RuntimeError(f'Mount St. Helens initial pipeline failed: {init_res.error}')

    # Refine attitude + (f_mm, k1, k2) strictly on sky-only classical CoG centroids.
    c_sky_cog = CentroidDetector(cam_nom, bg_block=31, min_area=3).detect(gray, mask=mask_terrain)
    px_mm = pixel_um * 0.001
    a_cur = init_res.a
    f_cur, k1_cur, k2_cur = nominal_f_mm, 0.0, 0.0
    for it_idx in range(4):
        uv_cat, in_fov = project_with_custom_optics(
            (a_cur @ cat_hip.vectors.T).T,
            width=width,
            height=height,
            focal_mm=f_cur,
            pixel_um=pixel_um,
            cx=cx,
            cy=cy,
            k1=k1_cur,
            k2=k2_cur,
        )
        vis_idx = np.flatnonzero(in_fov & (cat_hip.mags <= 7.0))
        sky_idx = [
            int(ci)
            for ci in vis_idx
            if 0 <= int(round(uv_cat[ci, 0])) < width
            and 0 <= int(round(uv_cat[ci, 1])) < height
            and not bool(mask_terrain[int(round(uv_cat[ci, 1])), int(round(uv_cat[ci, 0]))])
        ]
        sky_idx = np.asarray(sky_idx, dtype=np.intp)
        sky_uv = uv_cat[sky_idx]
        rad_gate = 6.0 if it_idx == 0 else 2.5
        dists = np.hypot(c_sky_cog.uv[:, 0:1] - sky_uv[None, :, 0], c_sky_cog.uv[:, 1:2] - sky_uv[None, :, 1])
        obs_sel, cat_sel = [], []
        used_cat = set()
        for oi in range(len(c_sky_cog.uv)):
            ci = int(np.argmin(dists[oi]))
            if dists[oi, ci] < rad_gate and ci not in used_cat and int(np.argmin(dists[:, ci])) == oi:
                used_cat.add(ci)
                obs_sel.append(oi)
                cat_sel.append(sky_idx[ci])
        obs_uv = c_sky_cog.uv[obs_sel]
        cat_vecs = cat_hip.vectors[cat_sel]

        def res_msh(params: np.ndarray) -> np.ndarray:
            dcm = rodrigues(params[:3]) @ a_cur
            f_mm, k1_v, k2_v = float(params[3]), float(params[4]), float(params[5])
            vc = (dcm @ cat_vecs.T).T
            xu, yu = vc[:, 0] / vc[:, 2], vc[:, 1] / vc[:, 2]
            r2 = xu * xu + yu * yu
            rad_f = 1.0 + k1_v * r2 + k2_v * (r2 * r2)
            u_p = (f_mm / px_mm) * (xu * rad_f) + cx
            v_p = (f_mm / px_mm) * (yu * rad_f) + cy
            return np.concatenate((u_p - obs_uv[:, 0], v_p - obs_uv[:, 1]))

        opt = least_squares(
            res_msh,
            np.array([0.0, 0.0, 0.0, f_cur, k1_cur, k2_cur], dtype=np.float64),
            loss='soft_l1' if it_idx < 3 else 'linear',
            f_scale=0.5,
        )
        a_cur = rodrigues(opt.x[:3]) @ a_cur
        f_cur, k1_cur, k2_cur = float(opt.x[3]), float(opt.x[4]), float(opt.x[5])

    q_gt = from_dcm(a_cur)
    ra_deg, dec_deg = boresight_ra_dec_deg(q_gt)
    sep_lost_deg = ang_sep_deg(ra_deg, dec_deg, UW_LOST_MSH_RA_DEG, UW_LOST_MSH_DEC_DEG)
    if sep_lost_deg >= 0.5:
        raise RuntimeError(f'Mount St. Helens boresight diverges from UW LOST by {sep_lost_deg:.3f} deg')

    stars_fov = build_stars_in_fov(
        q_gt=q_gt,
        width=width,
        height=height,
        focal_mm=f_cur,
        pixel_um=pixel_um,
        cx=cx,
        cy=cy,
        cat_hip=cat_hip,
        hip_to_hr=hip_to_hr,
        max_mag=6.0,
        k1=k1_cur,
        k2=k2_cur,
        sky_mask=mask_terrain,
    )
    # Also include matched sky detections up to mag 7.0 in verification check
    all_sky_7 = build_stars_in_fov(
        q_gt=q_gt,
        width=width,
        height=height,
        focal_mm=f_cur,
        pixel_um=pixel_um,
        cx=cx,
        cy=cy,
        cat_hip=cat_hip,
        hip_to_hr=hip_to_hr,
        max_mag=7.0,
        k1=k1_cur,
        k2=k2_cur,
        sky_mask=mask_terrain,
    )
    rms_sky, med_sky, n_matched_sky = match_centroids_to_catalog(c_sky_cog.uv, all_sky_7, max_dist_px=3.0)
    if rms_sky is None or rms_sky >= MAX_VERIFY_RMS_PX:
        raise RuntimeError(f'Mount St. Helens ref_rms_px={rms_sky} >= {MAX_VERIFY_RMS_PX}')

    rel_path = str(png_path.relative_to(ROOT)).replace('\\', '/')
    return {
        'path': rel_path,
        'dataset_group': 'uw_lost_outdoor',
        'width': int(width),
        'height': int(height),
        'focal_mm': f_cur,
        'focal_mm_nominal': nominal_f_mm,
        'pixel_um': pixel_um,
        'calibrated_cx': cx,
        'calibrated_cy': cy,
        'k1': k1_cur,
        'k2': k2_cur,
        'distortion_note': (
            f'UW LOST published outdoor Mount St. Helens photo (nominal f={nominal_f_mm} mm, '
            f'pixel={pixel_um} um, ~53x53 deg FOV); refined on sky-only CoG centroids to '
            f'f={f_cur:.5f} mm, k1={k1_cur:.5f}, k2={k2_cur:.5f}. Terrain occluded stars '
            'excluded via scripts/compare_mount_st_helens_centroids.terrain_mask.'
        ),
        'q_gt': q_gt.tolist(),
        'boresight_ra_deg': ra_deg,
        'boresight_dec_deg': dec_deg,
        'boresight_ra_hms': format_ra_hms(ra_deg),
        'boresight_dec_dms': format_dec_dms(dec_deg),
        'gt_source': 'startracker_hipparcos_sky_only_scipy_f_k1_k2',
        'catalog_max_mag': 6.0,
        'ref_rms_px': float(rms_sky),
        'ref_median_px': med_sky,
        'n_detected_cog': int(len(c_sky_cog.uv)),
        'n_matched_cog': n_matched_sky,
        'crosscheck': {
            'uw_lost_ra_deg': UW_LOST_MSH_RA_DEG,
            'uw_lost_dec_deg': UW_LOST_MSH_DEC_DEG,
            'sep_from_uw_lost_deg': sep_lost_deg,
            'init_backend': cfg.centroid_backend,
        },
        'stars_in_fov': stars_fov,
    }


def build_ntnu_stress_entry(png_path: Path) -> dict:
    """Record uncalibrated wide-angle NTNU night-sky frame as distortion stress test."""
    img = cv2.imread(str(png_path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(png_path)
    height, width = img.shape[:2]
    pixel_um = 2.74
    focal_mm = 12.0
    cx = (width - 1) * 0.5
    cy = (height - 1) * 0.5
    rel_path = str(png_path.relative_to(ROOT)).replace('\\', '/')
    return {
        'path': rel_path,
        'dataset_group': 'real_sky_uncalibrated_stress',
        'width': int(width),
        'height': int(height),
        'focal_mm': focal_mm,
        'focal_mm_nominal': focal_mm,
        'pixel_um': pixel_um,
        'calibrated_cx': cx,
        'calibrated_cy': cy,
        'k1': None,
        'k2': None,
        'distortion_note': (
            f'NTNU wide-angle real night-sky frame ({width}x{height}, f={focal_mm} mm, '
            f'pixel={pixel_um} um, ~62.5x55.4 deg / 77.5 deg diag FOV, metadata timestamp '
            '2025-01-31T23:39:20.315000). Uncalibrated lens distortion stress test entry; no q_gt.'
        ),
        'q_gt': None,
        'boresight_ra_deg': None,
        'boresight_dec_deg': None,
        'boresight_ra_hms': None,
        'boresight_dec_dms': None,
        'gt_source': 'uncalibrated_wide_angle_stress_test',
        'catalog_max_mag': None,
        'ref_rms_px': None,
        'ref_median_px': None,
        'n_detected_cog': None,
        'n_matched_cog': 0,
        'stars_in_fov': [],
    }


def main() -> int:
    import tetra3

    t3 = tetra3.Tetra3()
    engine = DemoEngine(ROOT)
    cat_hip_2019, hip_to_hr = load_hipparcos_and_bsc5_bridge(epoch_year=2019.58, max_mag=8.0)
    cat_hip_2021, _ = load_hipparcos_and_bsc5_bridge(epoch_year=2021.46, max_mag=8.0)
    cat_hip_2024, _ = load_hipparcos_and_bsc5_bridge(epoch_year=2024.0, max_mag=7.5)

    frames = []
    # 1. ESA tetra3 real-sky frames
    tetra3_dir = ROOT / 'data' / 'tetra3'
    for tiff_p in sorted(list(tetra3_dir.glob('*.tiff')) + list(tetra3_dir.glob('*.tif'))):
        entry = solve_tetra3_frame(tiff_p, t3, cat_hip_2019, hip_to_hr, engine)
        frames.append(entry)

    # 2. Zhao et al. MT9V022 real-sky frames
    zhao_dir = ROOT / 'data' / 'real_calibrated' / 'zhao_mt9v022'
    for npy_p in sorted(zhao_dir.glob('*.npy')):
        entry = solve_zhao_frame(npy_p, t3, cat_hip_2021, hip_to_hr)
        frames.append(entry)

    # 3. UW LOST Mount St. Helens outdoor photo
    msh_path = ROOT / 'data' / 'uploads' / 'mount_st_helens_1.png'
    frames.append(solve_mount_st_helens(msh_path, cat_hip_2024, hip_to_hr, engine))

    # 4. Uncalibrated wide-angle stress test frame 0006.png
    stress_path = ROOT / 'data' / 'uploads' / 'real_sky' / 'images' / '0006.png'
    frames.append(build_ntnu_stress_entry(stress_path))

    solved = [f for f in frames if f['q_gt'] is not None]
    manifest = {
        'schema_version': 'real_calibrated_gt_v1',
        'quaternion_convention': 'scalar-first [w, x, y, z], b_cam = to_dcm(q_gt) @ r_icrs (+Z boresight, +X right, +Y down)',
        'pixel_origin': '0-indexed pixel center (0.0, 0.0) at top-left pixel; matches src.camera.CameraModel and src.centroid.CentroidDetector',
        'summary': {
            'total_frames': len(frames),
            'solved_frames': len(solved),
            'unsolved_or_stress_frames': len(frames) - len(solved),
            'max_ref_rms_px': max((f['ref_rms_px'] for f in solved), default=None),
        },
        'frames': frames,
    }

    out_path = ROOT / 'data' / 'real_calibrated' / 'manifest_real_calibrated.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')

    print(f'Wrote {out_path} ({len(frames)} frames, {len(solved)} solved):')
    for f in frames:
        ra_s = f"{f['boresight_ra_deg']:.4f}" if f['boresight_ra_deg'] is not None else 'None'
        dec_s = f"{f['boresight_dec_deg']:+.4f}" if f['boresight_dec_deg'] is not None else 'None'
        rms_s = f"{f['ref_rms_px']:.4f}" if f['ref_rms_px'] is not None else 'None'
        print(
            f"  - {f['path']} [{f['dataset_group']}] "
            f"RA={ra_s} Dec={dec_s} ref_rms_px={rms_s} "
            f"stars_in_fov={len(f['stars_in_fov'])} source={f['gt_source']}"
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
