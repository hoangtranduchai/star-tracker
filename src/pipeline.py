"""End-to-end star tracker pipeline: glare masking, centroiding, pattern ID, and Wahba refinement."""
from struct import pack
from time import perf_counter
from numpy import all as npall, argmin, asarray, concatenate, count_nonzero, degrees, einsum, flatnonzero, float64, hypot, inf, int32, maximum, mean, pi
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

class TrackerResult:
    """Output container for a single processed star tracker frame."""

    def __init__(self, success: object, q: object, a: object, centroids: object, ident: object, residuals_arcsec: object, cov_rad2: object, timing_ms: object, quality: object, error: object=None, glare_mask: object=None) -> object:
        self.success, self.q, self.a, self.centroids, self.ident, self.residuals_arcsec, self.cov_rad2, self.timing_ms, self.quality, self.error, self.glare_mask = (bool(success), q, a, centroids, ident, residuals_arcsec, cov_rad2, timing_ms, quality, error, glare_mask)

    def to_downlink_bytes(self) -> object:
        if self.q is None:
            return b'\x00' * 16
        w, x, y, z = normalize(self.q)
        return pack('<4f', float(w), float(x), float(y), float(z))

class StarTrackerPipeline:
    """Full lost-in-space star tracker execution pipeline."""

    def __init__(self, camera: object, catalog: object, kvector: object, cfg: object=None) -> object:
        conf: object = PipelineConfig() if cfg is None else cfg
        self.camera, self.catalog, self.kvector, self.cfg = (camera, catalog, kvector, conf)
        self.masker = GlareMasker(bright_frac=conf.mask_bright_frac, min_area_px=conf.mask_min_area_px, min_span_px=conf.mask_min_span_px, dilate_px=conf.mask_dilate_px, bg_excess_k=conf.mask_bg_excess_k, full_scale=conf.mask_full_scale)
        base_det: object = CentroidDetector(camera, k_sigma=conf.k_sigma, bg_block=conf.bg_block, min_area=conf.min_area, max_area=conf.max_area, max_area_sat=conf.max_area_sat, max_axis_ratio=conf.max_axis_ratio, saturation_dn=conf.saturation_dn, binary_open=conf.binary_open, cog_pad=conf.cog_pad)
        backend_tag: object = str(conf.centroid_backend or 'classical').lower()
        if backend_tag in ('cnn', 'cnn_zhao2024', 'zhao', 'mobileunet'):
            from .centroid_cnn import CNNCentroidDetector
            self.centroid_detector = CNNCentroidDetector(camera, classical=base_det)
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

    def process_frame(self, image: object) -> object:
        t_log: object = {}
        ts: object = perf_counter()
        g_mask: object = self.masker.make_mask(image)
        t_log['mask_ms'] = (perf_counter() - ts) * 1000.0
        ts: object = perf_counter()
        cents: object = self.centroid_detector.detect(image, mask=g_mask)
        t_log['centroiding_ms'] = (perf_counter() - ts) * 1000.0
        abort: object = lambda reason: TrackerResult(False, None, None, cents, None, None, None, t_log, {}, reason, g_mask)
        req_stars: object = max(int(self.cfg.min_stars), 3)
        n_det: object = int(len(cents.vectors))
        if n_det < 3:
            return abort(f'Insufficient stars detected ({n_det} < 3)')
        ts: object = perf_counter()
        id_res: object = self.star_identifier.identify(cents.vectors, cents.flux)
        n_matched_init: object = int(len(id_res.obs_idx))
        try_wide: object = (not id_res.success or n_matched_init < req_stars) or (id_res.success and n_matched_init < 8)
        if try_wide and n_det >= req_stars:
            wide_res: object = self.star_identifier.identify_wide(cents.vectors, cents.flux, self.camera)
            if wide_res.success and len(wide_res.obs_idx) >= max(req_stars, n_matched_init + 1):
                id_res: object = wide_res
        t_log['identification_ms'] = (perf_counter() - ts) * 1000.0
        if not id_res.success or len(id_res.obs_idx) < 3:
            return abort(f'Identification failed to match at least 3 stars (matched {len(id_res.obs_idx)})')
        ts: object = perf_counter()
        obs_sel: object = id_res.obs_idx.copy()
        cat_sel: object = id_res.cat_idx.copy()
        quat = dcm = res_arc = cov_mat = None
        floor_arc: object = float(degrees(self.cfg.angular_tol_rad) * 3600.0)
        for _ in range(int(self.cfg.max_refine) + 1):
            b_vecs, sig_r, quat, dcm, res_arc = self._solve_weighted_wahba(cents, obs_sel, cat_sel)
            gate_arc: object = maximum(self.cfg.residual_n_sigma * (sig_r * ARCSEC_PER_RAD), floor_arc)
            inliers: object = res_arc <= gate_arc
            if int(count_nonzero(inliers)) < 3 or bool(npall(inliers)):
                cov_mat: object = self.wahba.covariance_rad2(b_vecs, sig_r)
                break
            obs_sel, cat_sel = (obs_sel[inliers], cat_sel[inliers])
        if dcm is not None:
            obs_sel, cat_sel = self._associate_remaining(cents, dcm, obs_sel, cat_sel)
            if len(obs_sel) >= 3:
                b_vecs, sig_r, quat, dcm, res_arc = self._solve_weighted_wahba(cents, obs_sel, cat_sel)
                cov_mat: object = self.wahba.covariance_rad2(b_vecs, sig_r)
        t_log['attitude_ms'] = (perf_counter() - ts) * 1000.0
        t_log['total_pipeline_ms'] = sum(t_log.values())
        num_final: object = int(len(obs_sel))
        num_fov: object = int(count_nonzero(self.camera.project(einsum('ij,kj->ik', self.catalog.vectors, dcm))[1])) if dcm is not None else 0
        fov_recall: object = num_final / float(num_fov) if num_fov else 0.0
        is_valid: object = num_final >= 8 or (num_final >= req_stars and fov_recall >= 0.75) or (num_final == 3 and num_fov <= 3)
        if not is_valid:
            return abort(f'Attitude matched only {num_final} of {num_fov} catalog stars in that field')
        final_id: object = IdResult(obs_sel, cat_sel, True, id_res.n_pyramids_tested, id_res.expected_false)
        q_metrics: object = self._quality(cents, final_id, dcm)
        return TrackerResult(success=True, q=quat, a=dcm, centroids=cents, ident=final_id, residuals_arcsec=res_arc, cov_rad2=cov_mat, timing_ms=t_log, quality=q_metrics, error=None, glare_mask=g_mask)

    def _associate_remaining(self, cents: object, a: object, obs_idx: object, cat_idx: object) -> object:
        """Greedily associate non-pyramid detected centroids with projected in-FOV catalog stars."""
        if not len(cents.uv):
            return (obs_idx, cat_idx)
        taken_o: object = {int(x) for x in obs_idx}
        taken_c: object = {int(x) for x in cat_idx}
        proj_uv, in_fov = self.camera.project(einsum('ij,kj->ik', self.catalog.vectors, a))
        plate_scale: object = max(float(self.camera.ifov_arcsec), 1e-09)
        rad_px: object = max(2.5, float(degrees(self.cfg.angular_tol_rad) * 3600.0) / plate_scale)
        det_u, det_v = (cents.uv[:, 0], cents.uv[:, 1])
        more_o, more_c = ([], [])
        for c_i in flatnonzero(in_fov):
            c_idx: object = int(c_i)
            if c_idx in taken_c:
                continue
            pu, pv = proj_uv[c_idx]
            dists: object = hypot(det_u - pu, det_v - pv)
            best_o: object = int(argmin(dists))
            if dists[best_o] <= rad_px and best_o not in taken_o:
                dists[best_o] = inf
                if float(dists.min()) > rad_px:
                    taken_o.add(best_o)
                    taken_c.add(c_idx)
                    more_o.append(best_o)
                    more_c.append(c_idx)
        if not more_o:
            return (obs_idx, cat_idx)
        return (concatenate((obs_idx, asarray(more_o, dtype=int32))), concatenate((cat_idx, asarray(more_c, dtype=int32))))

    def _quality(self, cents: object, ident: object, a: object) -> object:
        n_det: object = int(len(cents.uv))
        n_id: object = int(len(ident.obs_idx))
        cfg_be: object = str(self.cfg.centroid_backend or 'classical')
        q_info: object = dict(n_detected=n_det, n_matched=n_id, centroid_backend=cfg_be, centroid_detector=getattr(self.centroid_detector, 'last_backend', cfg_be), centroid_fallback=bool(getattr(self.centroid_detector, 'last_fallback', False)), low_recall=False, many_false=False)
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
