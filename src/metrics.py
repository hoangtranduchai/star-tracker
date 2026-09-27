"""Accuracy metrics vs ground-truth quaternion and centroids."""

from __future__ import annotations

from typing import Optional

import numpy as np

from .quaternion import (
    angular_error_arcsec,
    axis_error_arcsec,
    boresight_ra_dec_deg,
    format_dec_dms,
    format_ra_hms,
)
from .simulator import RenderTruth
from .pipeline import TrackerResult


def centroid_rms_px(det_uv: np.ndarray, truth_uv: np.ndarray, max_match_px: float = 3.0) -> float:
    if len(det_uv) == 0 or len(truth_uv) == 0:
        return float("nan")
    dist = np.linalg.norm(det_uv[:, None, :] - truth_uv[None, :, :], axis=2)
    dmin = dist.min(axis=1)
    ok = dmin < max_match_px
    if not np.any(ok):
        return float("nan")
    return float(np.sqrt(np.mean(dmin[ok] ** 2)))


def evaluate(
    result: TrackerResult,
    truth: RenderTruth,
    attitude_limit_arcsec: float,
    have_gt: bool = True,
) -> dict:
    out: dict = {
        "success": bool(result.success),
        "n_truth": int(len(truth.cat_idx)),
        "n_detected": int(result.centroids.uv.shape[0]) if result.centroids is not None else 0,
        "n_matched": int(result.ident.obs_idx.size) if result.ident is not None else 0,
        "attitude_error_arcsec": None,
        "axis_error_arcsec": None,
        "centroid_rms_px": None,
        "verdict": "FAIL",
        "limit_arcsec": attitude_limit_arcsec,
        "boresight_gt_ra_deg": None,
        "boresight_gt_dec_deg": None,
        "boresight_est_ra_deg": None,
        "boresight_est_dec_deg": None,
        "boresight_gt_ra_hms": None,
        "boresight_gt_dec_dms": None,
        "boresight_est_ra_hms": None,
        "boresight_est_dec_dms": None,
    }
    if have_gt:
        ra_gt, dec_gt = boresight_ra_dec_deg(truth.q_gt)
        out["boresight_gt_ra_deg"] = ra_gt
        out["boresight_gt_dec_deg"] = dec_gt
        out["boresight_gt_ra_hms"] = format_ra_hms(ra_gt)
        out["boresight_gt_dec_dms"] = format_dec_dms(dec_gt)
        if result.centroids is not None and len(truth.uv_mid):
            out["centroid_rms_px"] = centroid_rms_px(result.centroids.uv, truth.uv_mid)
    if result.success and result.q is not None:
        ra_est, dec_est = boresight_ra_dec_deg(result.q)
        out["boresight_est_ra_deg"] = ra_est
        out["boresight_est_dec_deg"] = dec_est
        out["boresight_est_ra_hms"] = format_ra_hms(ra_est)
        out["boresight_est_dec_dms"] = format_dec_dms(dec_est)
        if have_gt:
            err = angular_error_arcsec(result.q, truth.q_gt)
            axes = axis_error_arcsec(result.q, truth.q_gt)
            out["attitude_error_arcsec"] = err
            out["axis_error_arcsec"] = axes.tolist()
            out["verdict"] = "PASS" if err < attitude_limit_arcsec else "WARN"
        else:
            out["verdict"] = "SOLVED_NO_GT"
    out["timing_ms"] = result.timing_ms
    out["error"] = result.error
    return out
