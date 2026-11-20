"""End-to-end star tracker pipeline: glare masking, centroiding, pattern ID, and Wahba refinement."""
from struct import pack
from time import perf_counter
from numpy import all as npall, arccos, argmin, asarray, clip, concatenate, count_nonzero, degrees, dot, einsum, flatnonzero, float64, hypot, inf, int32, maximum, mean, pi, sqrt
from .attitude import WahbaSolver
from .centroid import CentroidDetector
from .identification import IdResult, StarIdentifier
from .masking import GlareMasker
from .quaternion import ARCSEC_PER_RAD, normalize
_CFG_DEFAULTS = dict(k_sigma=4.0, bg_block=64, min_area=3, max_area=120, max_area_sat=2500, max_axis_ratio=3.0, saturation_dn=4000.0, binary_open=True, cog_pad=1, angular_tol_rad=4.85e-05, n_false_sky=300, p_max=0.0001, max_stars=12, cutoff=2000, solver='svd', residual_n_sigma=3.0, max_refine=2, mask_bright_frac=0.5, mask_min_area_px=30, mask_min_span_px=48, mask_dilate_px=25, mask_bg_excess_k=3.0, mask_full_scale=4095.0, attitude_error_limit_arcsec=10.0, min_stars=4, tol_frac=0.0, centroid_backend='classical')

class PipelineConfig:
    """Configuration parameters for all stages of `StarTrackerPipeline`."""

    def __init__(self, **kwargs) -> object:
        merged: object = dict(_CFG_DEFAULTS)
        for k, v in kwargs.items():
            if k in _CFG_DEFAULTS:
                merged[k] = v
        self.__dict__.update(merged)

    @classmethod
    def from_dict(cls, d: object) -> object:
        return cls(**{k: v for k, v in dict(d).items() if k in _CFG_DEFAULTS})

def _dedup_pairs(obs_idx: object, cat_idx: object, n_det: int, n_cat: int) -> tuple:
    """Enforce 1-to-1 uniqueness and index bounds on observation-catalog match pairs."""
    seen_obs: set = set()
    seen_cat: set = set()
    out_obs: list = []
    out_cat: list = []
    for o_val, c_val in zip(asarray(obs_idx, dtype=int32).ravel().tolist(), asarray(cat_idx, dtype=int32).ravel().tolist()):
        o_i, c_i = (int(o_val), int(c_val))
        if o_i < 0 or o_i >= n_det or c_i < 0 or c_i >= n_cat:
            continue
        if o_i in seen_obs or c_i in seen_cat:
            continue
        seen_obs.add(o_i)
        seen_cat.add(c_i)
        out_obs.append(o_i)
        out_cat.append(c_i)
    return (asarray(out_obs, dtype=int32), asarray(out_cat, dtype=int32))

def _build_match_stats(status: str, reject_code: object, n_detected: int, n_initial_matched: int, n_rejected_outliers: int, n_valid_pairs: int, min_pairs_required: int, rms_residual_arcsec: object, max_residual_arcsec: object, fov_expected_stars: int) -> dict:
    """Construct standardized match & attitude diagnostic summary dictionary."""
    return {
        'status': str(status),
        'reject_code': reject_code,
        'n_detected': int(n_detected),
        'n_initial_matched': int(n_initial_matched),
        'n_rejected_outliers': int(n_rejected_outliers),
        'n_valid_pairs': int(n_valid_pairs),
        'min_pairs_required': int(min_pairs_required),
        'rms_residual_arcsec': None if rms_residual_arcsec is None else float(rms_residual_arcsec),
        'max_residual_arcsec': None if max_residual_arcsec is None else float(max_residual_arcsec),
        'fov_expected_stars': int(fov_expected_stars),
    }

class TrackerResult:
    """Output container for a single processed star tracker frame."""

    def __init__(self, success: object, q: object, a: object, centroids: object, ident: object, residuals_arcsec: object, cov_rad2: object, timing_ms: object, quality: object, error: object=None, glare_mask: object=None, status: object=None, reject_code: object=None, match_stats: object=None) -> object:
        self.success, self.q, self.a, self.centroids, self.ident, self.residuals_arcsec, self.cov_rad2, self.timing_ms, self.quality, self.error, self.glare_mask = (bool(success), q, a, centroids, ident, residuals_arcsec, cov_rad2, timing_ms, quality, error, glare_mask)
        self.status = str(status) if status is not None else ('SOLVED' if self.success else 'LOST')
        self.reject_code = reject_code
        self.match_stats = match_stats

    def to_downlink_bytes(self) -> object:
        if self.q is None:
            return b'\x00' * 16
        w, x, y, z = normalize(self.q)
        return pack('<4f', float(w), float(x), float(y), float(z))

    def to_telemetry_frame(self, seq_id: int = 0) -> bytes:
        from .telemetry import pack_telemetry_frame
        return pack_telemetry_frame(self, seq_id=seq_id)

class StarTrackerPipeline:
    """Full lost-in-space star tracker execution pipeline."""

    def __init__(self, camera: object, catalog: object, kvector: object, cfg: object=None) -> object:
        conf: object = PipelineConfig() if cfg is None else cfg
        self.camera, self.catalog, self.kvector, self.cfg = (camera, catalog, kvector, conf)
        self.masker = GlareMasker(bright_frac=conf.mask_bright_frac, min_area_px=conf.mask_min_area_px, min_span_px=conf.mask_min_span_px, dilate_px=conf.mask_dilate_px, bg_excess_k=conf.mask_bg_excess_k, full_scale=conf.mask_full_scale)
        base_det: object = CentroidDetector(camera, k_sigma=conf.k_sigma, bg_block=conf.bg_block, min_area=conf.min_area, max_area=conf.max_area, max_area_sat=conf.max_area_sat, max_axis_ratio=conf.max_axis_ratio, saturation_dn=conf.saturation_dn, binary_open=conf.binary_open, cog_pad=conf.cog_pad)
        self._base_det = base_det
        self._auto_cnn_detector = None
        self._is_auto_mode = False
        backend_tag: object = str(conf.centroid_backend or 'classical').lower().strip()
        if backend_tag in ('auto', 'adaptive', 'hybrid_auto'):
            self.centroid_detector = base_det
            self._is_auto_mode = True
        elif backend_tag in ('cnn', 'cnn_hybrid', 'cnn_zhao2024', 'zhao', 'mobileunet'):
            from .centroid_cnn import CNNCentroidDetector
            self.centroid_detector = CNNCentroidDetector(camera, classical=base_det, refine_subpixel=True)
        elif backend_tag in ('cnn_raw', 'cnn_trilateration'):
            from .centroid_cnn import CNNCentroidDetector
            self.centroid_detector = CNNCentroidDetector(camera, classical=base_det, refine_subpixel=False)
        elif backend_tag in ('tetra3', 'tetra3_threshold'):
            from .centroid_tetra3 import Tetra3ThresholdDetector
            self.centroid_detector = Tetra3ThresholdDetector(camera)
        else:
            self.centroid_detector = base_det
        self.star_identifier = StarIdentifier(catalog, kvector, tol_rad=conf.angular_tol_rad, tol_frac=conf.tol_frac, n_false_sky=conf.n_false_sky, p_max=conf.p_max, max_stars=conf.max_stars, cutoff=conf.cutoff)
        self.wahba = WahbaSolver()

    def _solve_weighted_wahba(self, cents: object, obs_idx: object, cat_idx: object) -> object:
        b_vecs: object = cents.vectors[obs_idx]
        r_vecs: object = self.catalog.vectors[cat_idx]
        sig_r: object = cents.sigma_px[obs_idx] * self.camera.ifov_rad
        w_vec: object = 1.0 / maximum(sig_r * sig_r, 1e-30)
        solver_fn: object = self.wahba.solve_quest if self.cfg.solver.lower() == 'quest' else self.wahba.solve_svd
        quat, dcm = solver_fn(b_vecs, r_vecs, w_vec)
        res_arc: object = self.wahba.residuals_arcsec(b_vecs, r_vecs, dcm)
        return (b_vecs, sig_r, quat, dcm, res_arc)

    def _refine_inliers(self, cents: object, obs_sel: object, cat_sel: object, floor_arc: float, n_rejected_outliers: int) -> tuple:
        """Iteratively solve Wahba and strip residual outliers until all surviving pairs satisfy the gate."""
        if len(obs_sel) < 3:
            return (False, 'INSUFFICIENT_INLIER_PAIRS', f'Only {len(obs_sel)} candidate pairs (< 3)', obs_sel, cat_sel, None, None, None, None, n_rejected_outliers, None, None, floor_arc)
        max_iters: int = max(int(self.cfg.max_refine), 0) + 1
        n_sigma: float = float(self.cfg.residual_n_sigma)
        b_vecs = sig_r = quat = dcm = res_arc = gate_arc = None
        solved_clean: bool = False
        for _ in range(max_iters):
            try:
                b_vecs, sig_r, quat, dcm, res_arc = self._solve_weighted_wahba(cents, obs_sel, cat_sel)
            except ValueError as exc:
                return (False, 'COLLINEAR_DEGENERATE_GEOMETRY', str(exc), obs_sel, cat_sel, None, None, None, None, n_rejected_outliers, None, None, floor_arc)
            gate_arc = maximum(n_sigma * (sig_r * ARCSEC_PER_RAD), floor_arc)
            inliers: object = res_arc <= gate_arc
            if bool(npall(inliers)):
                solved_clean = True
                break
            n_rejected_outliers += int(count_nonzero(~inliers))
            obs_sel, cat_sel = (obs_sel[inliers], cat_sel[inliers])
            if len(obs_sel) < 3:
                rms_r = float(sqrt(mean(res_arc * res_arc))) if len(res_arc) else None
                max_r = float(res_arc.max()) if len(res_arc) else None
                return (False, 'INSUFFICIENT_INLIER_PAIRS', f'Only {len(obs_sel)} inlier pairs survived residual gating (< 3)', obs_sel, cat_sel, None, None, None, None, n_rejected_outliers, rms_r, max_r, floor_arc)
        if not solved_clean:
            try:
                b_vecs, sig_r, quat, dcm, res_arc = self._solve_weighted_wahba(cents, obs_sel, cat_sel)
            except ValueError as exc:
                return (False, 'COLLINEAR_DEGENERATE_GEOMETRY', str(exc), obs_sel, cat_sel, None, None, None, None, n_rejected_outliers, None, None, floor_arc)
            gate_arc = maximum(n_sigma * (sig_r * ARCSEC_PER_RAD), floor_arc)
            inliers = res_arc <= gate_arc
            if not bool(npall(inliers)):
                n_rejected_outliers += int(count_nonzero(~inliers))
                obs_sel, cat_sel = (obs_sel[inliers], cat_sel[inliers])
                if len(obs_sel) < 3:
                    rms_r = float(sqrt(mean(res_arc * res_arc))) if len(res_arc) else None
                    max_r = float(res_arc.max()) if len(res_arc) else None
                    return (False, 'INSUFFICIENT_INLIER_PAIRS', f'Only {len(obs_sel)} inlier pairs survived residual gating (< 3)', obs_sel, cat_sel, None, None, None, None, n_rejected_outliers, rms_r, max_r, floor_arc)
                try:
                    b_vecs, sig_r, quat, dcm, res_arc = self._solve_weighted_wahba(cents, obs_sel, cat_sel)
                except ValueError as exc:
                    return (False, 'COLLINEAR_DEGENERATE_GEOMETRY', str(exc), obs_sel, cat_sel, None, None, None, None, n_rejected_outliers, None, None, floor_arc)
                gate_arc = maximum(n_sigma * (sig_r * ARCSEC_PER_RAD), floor_arc)
                inliers = res_arc <= gate_arc
                if not bool(npall(inliers)):
                    rms_r = float(sqrt(mean(res_arc * res_arc)))
                    max_r = float(res_arc.max())
                    return (False, 'EXCESSIVE_POSTFIT_RESIDUAL', f'Outliers persisted after refinement (max residual {max_r:.2f} arcsec)', obs_sel, cat_sel, None, None, None, None, n_rejected_outliers, rms_r, max_r, floor_arc)
        cov_mat: object = self.wahba.covariance_rad2(b_vecs, sig_r)
        rms_r: float = float(sqrt(mean(res_arc * res_arc)))
        max_r: float = float(res_arc.max())
        rms_limit: float = max(floor_arc, 0.8 * float(mean(gate_arc)))
        return (True, None, None, obs_sel, cat_sel, quat, dcm, res_arc, cov_mat, n_rejected_outliers, rms_r, max_r, rms_limit)

    def _ensure_auto_cnn(self) -> object:
        if self._auto_cnn_detector is None:
            from .centroid_cnn import CNNCentroidDetector
            self._auto_cnn_detector = CNNCentroidDetector(self.camera, classical=self._base_det, refine_subpixel=True)
        return self._auto_cnn_detector

    def process_frame(self, image: object) -> object:
        if not self._is_auto_mode:
            return self._process_with_detector(image, self.centroid_detector, str(self.cfg.centroid_backend or 'classical'))
        # Adaptive Auto-Router: fast CoG first (~85 ms); escalate to CNN-Hybrid on LOST or heavy clutter
        res_cog = self._process_with_detector(image, self._base_det, 'classical')
        n_det_cog = int(len(res_cog.centroids.uv)) if (res_cog.centroids is not None and res_cog.centroids.uv is not None) else 0
        if res_cog.success and n_det_cog <= 300:
            if isinstance(res_cog.quality, dict):
                res_cog.quality.update(
                    centroid_backend='auto',
                    auto_router_used=True,
                    auto_router_selected='classical',
                    auto_router_reason='CoG khóa thành công tốc độ cao',
                )
            return res_cog
        cnn_det = self._ensure_auto_cnn()
        res_cnn = self._process_with_detector(image, cnn_det, 'cnn', precomputed_mask=res_cog.glare_mask, mask_ms=0.0)
        cog_ms = float((res_cog.timing_ms or {}).get('total_pipeline_ms', 0.0))
        if isinstance(res_cnn.timing_ms, dict):
            res_cnn.timing_ms['auto_cog_attempt_ms'] = cog_ms
            res_cnn.timing_ms['total_pipeline_ms'] = float(res_cnn.timing_ms.get('total_pipeline_ms', 0.0)) + cog_ms
        trigger_tag = res_cog.reject_code if not res_cog.success else f'CLUTTER_{n_det_cog}'
        if res_cnn.success or not res_cog.success:
            if isinstance(res_cnn.quality, dict):
                res_cnn.quality.update(
                    centroid_backend='auto',
                    auto_router_used=True,
                    auto_router_selected='cnn',
                    auto_router_reason=f'CoG trả {res_cog.status} [{trigger_tag}] → tự động chuyển sang CNN-Hybrid',
                    auto_cog_status=res_cog.status,
                    auto_cog_reject_code=res_cog.reject_code,
                )
            return res_cnn
        if isinstance(res_cog.quality, dict):
            res_cog.quality.update(
                centroid_backend='auto',
                auto_router_used=True,
                auto_router_selected='classical',
                auto_router_reason=f'CoG giải được ({n_det_cog} tâm); giữ kết quả CoG sau đối chiếu CNN-Hybrid',
            )
        return res_cog

    def _process_with_detector(self, image: object, detector: object, cfg_be: str, *, precomputed_mask: object=None, mask_ms: float | None=None) -> object:
        t_log: object = {}
        if precomputed_mask is None:
            ts: object = perf_counter()
            g_mask: object = self.masker.make_mask(image)
            t_log['mask_ms'] = (perf_counter() - ts) * 1000.0
        else:
            g_mask = precomputed_mask
            t_log['mask_ms'] = 0.0 if mask_ms is None else float(mask_ms)
        ts = perf_counter()
        cents: object = detector.detect(image, mask=g_mask)
        t_log['centroiding_ms'] = (perf_counter() - ts) * 1000.0
        req_stars: int = max(int(self.cfg.min_stars), 3)
        n_det: int = int(len(cents.vectors))

        def abort(reject_code: str, reason: str, *, n_initial_matched: int=0, n_rejected_outliers: int=0, n_valid_pairs: int=0, rms_res: object=None, max_res: object=None, fov_expected: int=0) -> TrackerResult:
            t_log['total_pipeline_ms'] = sum((val for key, val in t_log.items() if key != 'total_pipeline_ms'))
            stats = _build_match_stats(status='LOST', reject_code=reject_code, n_detected=n_det, n_initial_matched=n_initial_matched, n_rejected_outliers=n_rejected_outliers, n_valid_pairs=n_valid_pairs, min_pairs_required=req_stars, rms_residual_arcsec=rms_res, max_residual_arcsec=max_res, fov_expected_stars=fov_expected)
            q_diag = dict(stats, n_matched=0, centroid_backend=cfg_be, centroid_detector=getattr(detector, 'last_backend', cfg_be), centroid_fallback=bool(getattr(detector, 'last_fallback', False)), low_recall=True, many_false=False)
            return TrackerResult(success=False, q=None, a=None, centroids=cents, ident=None, residuals_arcsec=None, cov_rad2=None, timing_ms=t_log, quality=q_diag, error=f'LOST [{reject_code}]: {reason}', glare_mask=g_mask, status='LOST', reject_code=reject_code, match_stats=stats)

        if n_det < 3:
            return abort('INSUFFICIENT_DETECTIONS', f'Insufficient stars detected ({n_det} < 3)')
        ts = perf_counter()
        id_res: object = self.star_identifier.identify(cents.vectors, cents.flux)
        n_matched_init: int = int(len(id_res.obs_idx))
        try_wide: bool = (not id_res.success or n_matched_init < req_stars) or (id_res.success and n_matched_init < 8)
        if try_wide and n_det >= req_stars:
            wide_res: object = self.star_identifier.identify_wide(cents.vectors, cents.flux, self.camera)
            if wide_res.success and len(wide_res.obs_idx) >= max(req_stars, n_matched_init + 1):
                id_res = wide_res
        t_log['identification_ms'] = (perf_counter() - ts) * 1000.0
        if not id_res.success or len(id_res.obs_idx) < 3:
            n_raw_id = int(len(id_res.obs_idx)) if id_res.success else 0
            return abort('IDENTIFICATION_FAILED', f'Identification failed to match at least 3 stars (matched {len(id_res.obs_idx)})', n_initial_matched=n_raw_id, n_valid_pairs=n_raw_id)
        ts = perf_counter()
        obs_sel, cat_sel = _dedup_pairs(id_res.obs_idx, id_res.cat_idx, n_det, self.catalog.num_stars)
        n_initial_matched: int = int(len(obs_sel))
        if n_initial_matched < 3:
            t_log['attitude_ms'] = (perf_counter() - ts) * 1000.0
            return abort('IDENTIFICATION_FAILED', f'Identification failed to match at least 3 unique stars (matched {n_initial_matched})', n_initial_matched=n_initial_matched, n_valid_pairs=n_initial_matched)
        floor_arc: float = float(degrees(self.cfg.angular_tol_rad) * 3600.0)
        n_rejected_outliers: int = 0
        ok, rej_code, rej_msg, obs_sel, cat_sel, quat, dcm, res_arc, cov_mat, n_rejected_outliers, rms_res, max_res, rms_limit = self._refine_inliers(cents, obs_sel, cat_sel, floor_arc, n_rejected_outliers)
        if not ok:
            t_log['attitude_ms'] = (perf_counter() - ts) * 1000.0
            return abort(rej_code, rej_msg, n_initial_matched=n_initial_matched, n_rejected_outliers=n_rejected_outliers, n_valid_pairs=int(len(obs_sel)), rms_res=rms_res, max_res=max_res)
        obs_assoc, cat_assoc = self._associate_remaining(cents, dcm, obs_sel, cat_sel)
        obs_assoc, cat_assoc = _dedup_pairs(obs_assoc, cat_assoc, n_det, self.catalog.num_stars)
        if len(obs_assoc) != len(obs_sel) or not bool(npall(obs_assoc == obs_sel)) or not bool(npall(cat_assoc == cat_sel)):
            ok, rej_code, rej_msg, obs_sel, cat_sel, quat, dcm, res_arc, cov_mat, n_rejected_outliers, rms_res, max_res, rms_limit = self._refine_inliers(cents, obs_assoc, cat_assoc, floor_arc, n_rejected_outliers)
            if not ok:
                t_log['attitude_ms'] = (perf_counter() - ts) * 1000.0
                return abort(rej_code, rej_msg, n_initial_matched=n_initial_matched, n_rejected_outliers=n_rejected_outliers, n_valid_pairs=int(len(obs_sel)), rms_res=rms_res, max_res=max_res)
        t_log['attitude_ms'] = (perf_counter() - ts) * 1000.0
        t_log['total_pipeline_ms'] = sum((val for key, val in t_log.items() if key != 'total_pipeline_ms'))
        num_final: int = int(len(obs_sel))
        num_fov: int = int(count_nonzero(self.camera.project(einsum('ij,kj->ik', self.catalog.vectors, dcm))[1])) if dcm is not None else 0
        if num_final < 3:
            return abort('INSUFFICIENT_INLIER_PAIRS', f'Only {num_final} valid inlier pairs (< 3)', n_initial_matched=n_initial_matched, n_rejected_outliers=n_rejected_outliers, n_valid_pairs=num_final, rms_res=rms_res, max_res=max_res, fov_expected=num_fov)
        if rms_res is not None and rms_res > rms_limit:
            return abort('EXCESSIVE_POSTFIT_RESIDUAL', f'Post-fit RMS residual {rms_res:.2f} arcsec exceeds tolerance {rms_limit:.2f} arcsec', n_initial_matched=n_initial_matched, n_rejected_outliers=n_rejected_outliers, n_valid_pairs=num_final, rms_res=rms_res, max_res=max_res, fov_expected=num_fov)
        allow_three: bool = num_final == 3 and int(self.cfg.min_stars) <= 3 and (num_fov <= 3) and (max_res is not None) and (max_res <= 0.5 * floor_arc)
        if num_final < req_stars and not allow_three:
            return abort('INSUFFICIENT_INLIER_PAIRS', f'Only {num_final} valid inlier pairs (< min_stars {req_stars})', n_initial_matched=n_initial_matched, n_rejected_outliers=n_rejected_outliers, n_valid_pairs=num_final, rms_res=rms_res, max_res=max_res, fov_expected=num_fov)
        fov_recall: float = num_final / float(num_fov) if num_fov else 0.0
        is_valid: bool = num_final >= 8 or (num_final >= req_stars and fov_recall >= 0.75) or (num_final >= 5 and fov_recall >= 0.45 and (rms_res <= 0.6 * floor_arc)) or allow_three
        if not is_valid:
            return abort('LOW_FOV_CONSISTENCY', f'Attitude matched only {num_final} of {num_fov} catalog stars in that field', n_initial_matched=n_initial_matched, n_rejected_outliers=n_rejected_outliers, n_valid_pairs=num_final, rms_res=rms_res, max_res=max_res, fov_expected=num_fov)
        final_id: object = IdResult(obs_sel, cat_sel, True, id_res.n_pyramids_tested, id_res.expected_false)
        match_stats: dict = _build_match_stats(status='SOLVED', reject_code=None, n_detected=n_det, n_initial_matched=n_initial_matched, n_rejected_outliers=n_rejected_outliers, n_valid_pairs=num_final, min_pairs_required=req_stars, rms_residual_arcsec=rms_res, max_residual_arcsec=max_res, fov_expected_stars=num_fov)
        q_metrics: object = self._quality(cents, final_id, dcm, detector=detector, cfg_be=cfg_be)
        q_metrics.update(match_stats)
        return TrackerResult(success=True, q=quat, a=dcm, centroids=cents, ident=final_id, residuals_arcsec=res_arc, cov_rad2=cov_mat, timing_ms=t_log, quality=q_metrics, error=None, glare_mask=g_mask, status='SOLVED', reject_code=None, match_stats=match_stats)

    def _associate_remaining(self, cents: object, a: object, obs_idx: object, cat_idx: object) -> object:
        """Greedily associate non-pyramid detected centroids with projected in-FOV catalog stars."""
        if not len(cents.uv):
            return (obs_idx, cat_idx)
        taken_o: object = {int(x) for x in obs_idx}
        taken_c: object = {int(x) for x in cat_idx}
        cam_cat: object = einsum('ij,kj->ik', self.catalog.vectors, a)
        proj_uv, in_fov = self.camera.project(cam_cat)
        plate_scale: object = max(float(self.camera.ifov_arcsec), 1e-09)
        tol_arc: float = float(degrees(self.cfg.angular_tol_rad) * 3600.0)
        rad_px: object = max(2.5, tol_arc / plate_scale)
        # Guard against wide-FOV negative-k1 polynomial fold-back projecting off-axis stars back into image
        max_ang_arc: float = max(rad_px * plate_scale * 1.5, 3.0 * tol_arc)
        det_u, det_v = (cents.uv[:, 0], cents.uv[:, 1])
        more_o, more_c = ([], [])
        for c_i in flatnonzero(in_fov):
            c_idx: object = int(c_i)
            if c_idx in taken_c:
                continue
            r_cam = cam_cat[c_idx]
            if float(r_cam[2]) <= 0.15:
                continue
            pu, pv = proj_uv[c_idx]
            dists: object = hypot(det_u - pu, det_v - pv)
            best_o: object = int(argmin(dists))
            if dists[best_o] <= rad_px and best_o not in taken_o:
                ang_arc = float(degrees(arccos(clip(float(dot(cents.vectors[best_o], r_cam)), -1.0, 1.0))) * 3600.0)
                if ang_arc > max_ang_arc:
                    continue
                dists[best_o] = inf
                if float(dists.min()) > rad_px:
                    taken_o.add(best_o)
                    taken_c.add(c_idx)
                    more_o.append(best_o)
                    more_c.append(c_idx)
        if not more_o:
            return (obs_idx, cat_idx)
        return (concatenate((obs_idx, asarray(more_o, dtype=int32))), concatenate((cat_idx, asarray(more_c, dtype=int32))))

    def _quality(self, cents: object, ident: object, a: object, detector: object=None, cfg_be: str | None=None) -> object:
        n_det: object = int(len(cents.uv))
        n_id: object = int(len(ident.obs_idx))
        det_ref = self.centroid_detector if detector is None else detector
        be_str: object = str(cfg_be if cfg_be is not None else (self.cfg.centroid_backend or 'classical'))
        q_info: object = dict(n_detected=n_det, n_matched=n_id, centroid_backend=be_str, centroid_detector=getattr(det_ref, 'last_backend', be_str), centroid_fallback=bool(getattr(det_ref, 'last_fallback', False)), low_recall=False, many_false=False)
        if a is None:
            return q_info
        proj_uv, in_fov = self.camera.project(einsum('ij,kj->ik', self.catalog.vectors, a))
        if not int(count_nonzero(in_fov)) or not n_det:
            q_info['low_recall'] = True
            return q_info
        vis_uv: object = proj_uv[in_fov]
        sep_mat: object = hypot(vis_uv[:, 0:1] - cents.uv[None, :, 0], vis_uv[:, 1:2] - cents.uv[None, :, 1])
        rec_rate: object = float(mean(sep_mat.min(axis=1) < 2.0))
        spurious_rate: object = 1.0 - n_id / float(max(n_det, 1))
        q_info.update(recall=rec_rate, low_recall=rec_rate < 0.5, unmatched_frac=spurious_rate, many_false=spurious_rate > 0.5)
        return q_info
