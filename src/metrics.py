"""Accuracy evaluation helpers against ground-truth quaternions and star centroids."""
from numpy import asarray, float64, hypot, mean, sqrt
from .quaternion import angular_error_arcsec, axis_error_arcsec, boresight_ra_dec_deg, format_dec_dms, format_ra_hms

def centroid_rms_px(det_uv: object, truth_uv: object, max_match_px: object=3.0) -> object:
    """Compute RMS pixel error for detections matched within `max_match_px` of truth."""
    d_arr: object = asarray(det_uv, dtype=float64)
    t_arr: object = asarray(truth_uv, dtype=float64)
    if not (d_arr.size and t_arr.size):
        return float('nan')
    dx: object = d_arr[:, 0:1] - t_arr[None, :, 0]
    dy: object = d_arr[:, 1:2] - t_arr[None, :, 1]
    nearest: object = hypot(dx, dy).min(axis=-1)
    inliers: object = nearest[nearest < float(max_match_px)]
    return float(sqrt(mean(inliers * inliers))) if inliers.size else float('nan')

def _populate_boresight_fields(target: object, prefix: object, quat: object) -> object:
    ra_val, dec_val = boresight_ra_dec_deg(quat)
    target[f'boresight_{prefix}_ra_deg'] = ra_val
    target[f'boresight_{prefix}_dec_deg'] = dec_val
    target[f'boresight_{prefix}_ra_hms'] = format_ra_hms(ra_val)
    target[f'boresight_{prefix}_dec_dms'] = format_dec_dms(dec_val)

def evaluate(result: object, truth: object, attitude_limit_arcsec: object, have_gt: object=True) -> object:
    """Build a standardized verification dictionary from a `TrackerResult` and `RenderTruth`."""
    cent_obj, ident_obj = (result.centroids, result.ident)
    n_det: object = 0 if cent_obj is None else int(cent_obj.uv.shape[0])
    n_id: object = 0 if ident_obj is None else int(ident_obj.obs_idx.size)
    report: object = dict.fromkeys(('attitude_error_arcsec', 'axis_error_arcsec', 'centroid_rms_px', 'boresight_gt_ra_deg', 'boresight_gt_dec_deg', 'boresight_est_ra_deg', 'boresight_est_dec_deg', 'boresight_gt_ra_hms', 'boresight_gt_dec_dms', 'boresight_est_ra_hms', 'boresight_est_dec_dms'), None)
    report.update(success=bool(result.success), n_truth=int(len(truth.cat_idx)), n_detected=n_det, n_matched=n_id, verdict='FAIL', limit_arcsec=attitude_limit_arcsec, timing_ms=result.timing_ms, error=result.error)
    if have_gt:
        _populate_boresight_fields(report, 'gt', truth.q_gt)
        if cent_obj is not None and len(truth.uv_mid):
            report['centroid_rms_px'] = centroid_rms_px(cent_obj.uv, truth.uv_mid)
    if result.success and result.q is not None:
        _populate_boresight_fields(report, 'est', result.q)
        if have_gt:
            ang_err: object = angular_error_arcsec(result.q, truth.q_gt)
            ax_err: object = axis_error_arcsec(result.q, truth.q_gt)
            report['attitude_error_arcsec'] = ang_err
            report['axis_error_arcsec'] = ax_err.tolist()
            report['verdict'] = 'PASS' if ang_err < attitude_limit_arcsec else 'WARN'
        else:
            report['verdict'] = 'SOLVED_NO_GT'
    return report
