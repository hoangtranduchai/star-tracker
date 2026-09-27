"""Copy of the star tracker pipeline for a wide real photo.

The original pipeline is unchanged. This copy keeps a solution when enough
bright catalog stars land on detected blobs. It does not demand that every
faint catalog star in a 60° field be visible.
"""

from __future__ import annotations

import time

import numpy as np

from .attitude import WahbaSolver
from .camera import CameraModel
from .catalog import StarCatalog
from .centroid import Centroids
from .identification import IdResult
from .kvector import KVectorTable
from .pipeline import PipelineConfig, StarTrackerPipeline, TrackerResult


def wide_field_config(camera: CameraModel) -> PipelineConfig:
    """Detection settings for the wide sample frames (12 mm, 5320×4600)."""
    return PipelineConfig(
        k_sigma=10.0,
        bg_block=128,
        min_area=12,
        max_area=400,
        max_area_sat=2500,
        max_axis_ratio=3.0,
        saturation_dn=250.0,
        binary_open=True,
        cog_pad=1,
        angular_tol_rad=4.0 * float(camera.ifov_rad),
        n_false_sky=800,
        p_max=1.0e-3,
        max_stars=15,
        cutoff=2000,
        solver="svd",
        residual_n_sigma=3.0,
        max_refine=2,
        mask_bright_frac=0.99,
        mask_min_area_px=80,
        mask_min_span_px=80,
        mask_dilate_px=15,
        mask_bg_excess_k=4.0,
        mask_full_scale=255.0,
        min_stars=4,
    )


class WideFieldPipeline(StarTrackerPipeline):
    """Same steps as StarTrackerPipeline, with a wide-field acceptance rule."""

    def __init__(
        self,
        camera: CameraModel,
        catalog: StarCatalog,
        kvector: KVectorTable,
        cfg: PipelineConfig | None = None,
        mag_limit: float = 4.5,
        # Four catalog stars are enough to publish names. The wide 12 mm
        # sample frames lock four stars at about one pixel; a gate of six drops them.
        min_matched: int = 4,
        associate_px: float = 8.0,
    ):
        super().__init__(camera, catalog, kvector, cfg or wide_field_config(camera))
        self.mag_limit = float(mag_limit)
        self.min_matched = int(min_matched)
        self.associate_px = float(associate_px)
        self.wahba = WahbaSolver()

    def process_frame(self, image: np.ndarray) -> TrackerResult:
        timings: dict[str, float] = {}
        t0 = time.perf_counter()
        mask = self.masker.make_mask(image)
        timings["mask_ms"] = (time.perf_counter() - t0) * 1000.0

        t1 = time.perf_counter()
        cents = self.centroid_detector.detect(image, mask=mask)
        timings["centroiding_ms"] = (time.perf_counter() - t1) * 1000.0

        def fail(msg: str) -> TrackerResult:
            return TrackerResult(False, None, None, cents, None, None, None, timings, {}, msg, mask)

        need = max(int(self.cfg.min_stars), 3)
        if len(cents.vectors) < 3:
            return fail(f"Insufficient stars detected ({len(cents.vectors)} < 3)")

        t2 = time.perf_counter()
        ident = self.star_identifier.identify(cents.vectors, cents.flux)
        if (not ident.success or len(ident.obs_idx) < need) and len(cents.vectors) >= need:
            wide = self.star_identifier.identify_wide(cents.vectors, cents.flux, self.camera)
            if wide.success and len(wide.obs_idx) >= need:
                ident = wide
        timings["identification_ms"] = (time.perf_counter() - t2) * 1000.0
        if not ident.success or len(ident.obs_idx) < 3:
            return fail(
                f"Identification failed to match at least 3 stars (matched {len(ident.obs_idx)})"
            )

        t3 = time.perf_counter()
        obs_idx = ident.obs_idx.copy()
        cat_idx = ident.cat_idx.copy()
        q = a = res = cov = None
        for _ in range(self.cfg.max_refine + 1):
            b = cents.vectors[obs_idx]
            r = self.catalog.vectors[cat_idx]
            sig_rad = cents.sigma_px[obs_idx] * self.camera.ifov_rad
            w = 1.0 / np.maximum(sig_rad**2, 1e-30)
            if self.cfg.solver.lower() == "quest":
                q, a = self.wahba.solve_quest(b, r, w)
            else:
                q, a = self.wahba.solve_svd(b, r, w)
            res = self.wahba.residuals_arcsec(b, r, a)
            sigma_arc = sig_rad * (180.0 * 3600.0 / np.pi)
            limit = np.maximum(
                self.cfg.residual_n_sigma * sigma_arc,
                np.degrees(self.cfg.angular_tol_rad) * 3600.0,
            )
            keep = res <= limit
            if int(np.count_nonzero(keep)) < 3 or bool(np.all(keep)):
                cov = self.wahba.covariance_rad2(b, sig_rad)
                break
            obs_idx = obs_idx[keep]
            cat_idx = cat_idx[keep]
        if a is not None:
            obs_idx, cat_idx = self._associate_wide(cents, a, obs_idx, cat_idx)
            if len(obs_idx) >= 3:
                b = cents.vectors[obs_idx]
                r = self.catalog.vectors[cat_idx]
                sig_rad = cents.sigma_px[obs_idx] * self.camera.ifov_rad
                w = 1.0 / np.maximum(sig_rad**2, 1e-30)
                if self.cfg.solver.lower() == "quest":
                    q, a = self.wahba.solve_quest(b, r, w)
                else:
                    q, a = self.wahba.solve_svd(b, r, w)
                res = self.wahba.residuals_arcsec(b, r, a)
                cov = self.wahba.covariance_rad2(b, sig_rad)
        timings["attitude_ms"] = (time.perf_counter() - t3) * 1000.0
        timings["total_pipeline_ms"] = sum(timings.values())

        n_id = len(obs_idx)
        n_bright = 0
        if a is not None:
            _uv, in_fov = self.camera.project((a @ self.catalog.vectors.T).T)
            bright = np.asarray(self.catalog.mags) <= self.mag_limit
            n_bright = int(np.count_nonzero(in_fov & bright))
        med = float(np.median(res)) if res is not None and len(res) else 1.0e9
        pixel_limit = self.associate_px * float(self.camera.ifov_arcsec)
        confirmed = n_id >= self.min_matched and med <= pixel_limit
        if not confirmed:
            return fail(
                f"Wide copy matched {n_id} stars, median residual {med:.0f} arcsec, "
                f"bright catalog stars in the field: {n_bright}"
            )

        ident = IdResult(obs_idx, cat_idx, True, ident.n_pyramids_tested, ident.expected_false)
        quality = self._quality(cents, ident, a)
        return TrackerResult(
            success=True,
            q=q,
            a=a,
            centroids=cents,
            ident=ident,
            residuals_arcsec=res,
            cov_rad2=cov,
            timing_ms=timings,
            quality=quality,
            error=None,
            glare_mask=mask,
        )

    def _associate_wide(
        self,
        cents: Centroids,
        a: np.ndarray,
        obs_idx: np.ndarray,
        cat_idx: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        if len(cents.uv) == 0:
            return obs_idx, cat_idx
        used_obs = {int(i) for i in obs_idx}
        used_cat = {int(i) for i in cat_idx}
        cam_v = (a @ self.catalog.vectors.T).T
        uv, infov = self.camera.project(cam_v)
        px_tol = self.associate_px
        extra_o: list[int] = []
        extra_c: list[int] = []
        bright = np.asarray(self.catalog.mags) <= self.mag_limit
        for ci in np.flatnonzero(infov & bright):
            ci = int(ci)
            if ci in used_cat:
                continue
            dist = np.linalg.norm(cents.uv - uv[ci], axis=1)
            j = int(np.argmin(dist))
            if dist[j] > px_tol or j in used_obs:
                continue
            dist[j] = np.inf
            if float(dist.min()) <= px_tol:
                continue
            used_obs.add(j)
            used_cat.add(ci)
            extra_o.append(j)
            extra_c.append(ci)
        if not extra_o:
            return obs_idx, cat_idx
        return (
            np.concatenate([obs_idx, np.asarray(extra_o, dtype=np.int32)]),
            np.concatenate([cat_idx, np.asarray(extra_c, dtype=np.int32)]),
        )
