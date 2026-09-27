"""End-to-end star tracker: mask → centroid → Pyramid ID → Wahba → residual gate."""

from __future__ import annotations

import struct
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from .attitude import WahbaSolver
from .camera import CameraModel
from .catalog import StarCatalog
from .centroid import CentroidDetector, Centroids
from .identification import IdResult, StarIdentifier
from .kvector import KVectorTable
from .masking import GlareMasker
from .quaternion import normalize


@dataclass
class PipelineConfig:
    k_sigma: float = 4.0
    bg_block: int = 64
    min_area: int = 3
    max_area: int = 120
    max_area_sat: int = 2500
    max_axis_ratio: float = 3.0
    saturation_dn: float = 4000.0
    binary_open: bool = True
    cog_pad: int = 1
    angular_tol_rad: float = 4.85e-5
    n_false_sky: int = 300
    p_max: float = 1e-4
    max_stars: int = 12
    cutoff: int = 2000
    solver: str = "svd"
    residual_n_sigma: float = 3.0
    max_refine: int = 2
    mask_bright_frac: float = 0.5
    mask_min_area_px: int = 30
    mask_min_span_px: int = 48
    mask_dilate_px: int = 25
    mask_bg_excess_k: float = 3.0
    mask_full_scale: float = 4095.0
    attitude_error_limit_arcsec: float = 10.0
    min_stars: int = 4
    tol_frac: float = 0.0
    # classical (default) | cnn — CNN uses Zhao et al. public MobileUNet weights.
    centroid_backend: str = "classical"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PipelineConfig":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class TrackerResult:
    success: bool
    q: np.ndarray | None
    a: np.ndarray | None
    centroids: Centroids | None
    ident: IdResult | None
    residuals_arcsec: np.ndarray | None
    cov_rad2: np.ndarray | None
    timing_ms: dict
    quality: dict
    error: str | None = None
    glare_mask: np.ndarray | None = None

    def to_downlink_bytes(self) -> bytes:
        if self.q is None:
            return b"\x00" * 16
        q = normalize(self.q)
        return struct.pack("<4f", float(q[0]), float(q[1]), float(q[2]), float(q[3]))


class StarTrackerPipeline:
    def __init__(
        self,
        camera: CameraModel,
        catalog: StarCatalog,
        kvector: KVectorTable,
        cfg: Optional[PipelineConfig] = None,
    ):
        self.camera = camera
        self.catalog = catalog
        self.kvector = kvector
        self.cfg = cfg or PipelineConfig()
        self.masker = GlareMasker(
            bright_frac=self.cfg.mask_bright_frac,
            min_area_px=self.cfg.mask_min_area_px,
            min_span_px=self.cfg.mask_min_span_px,
            dilate_px=self.cfg.mask_dilate_px,
            bg_excess_k=self.cfg.mask_bg_excess_k,
            full_scale=self.cfg.mask_full_scale,
        )
        classical = CentroidDetector(
            camera,
            k_sigma=self.cfg.k_sigma,
            bg_block=self.cfg.bg_block,
            min_area=self.cfg.min_area,
            max_area=self.cfg.max_area,
            max_area_sat=self.cfg.max_area_sat,
            max_axis_ratio=self.cfg.max_axis_ratio,
            saturation_dn=self.cfg.saturation_dn,
            binary_open=self.cfg.binary_open,
            cog_pad=self.cfg.cog_pad,
        )
        backend = str(self.cfg.centroid_backend or "classical").lower()
        if backend in {"cnn", "cnn_zhao2024", "zhao", "mobileunet"}:
            from .centroid_cnn import CNNCentroidDetector

            self.centroid_detector = CNNCentroidDetector(camera, classical=classical)
        else:
            self.centroid_detector = classical
        self.star_identifier = StarIdentifier(
            catalog,
            kvector,
            tol_rad=self.cfg.angular_tol_rad,
            tol_frac=self.cfg.tol_frac,
            n_false_sky=self.cfg.n_false_sky,
            p_max=self.cfg.p_max,
            max_stars=self.cfg.max_stars,
            cutoff=self.cfg.cutoff,
        )
        self.wahba = WahbaSolver()

    def process_frame(self, image: np.ndarray) -> TrackerResult:
        timings: dict[str, float] = {}
        t0 = time.perf_counter()
        mask = self.masker.make_mask(image)
        timings["mask_ms"] = (time.perf_counter() - t0) * 1000.0

        t1 = time.perf_counter()
        cents = self.centroid_detector.detect(image, mask=mask)
        timings["centroiding_ms"] = (time.perf_counter() - t1) * 1000.0
        # KPIs / overlay must use these centroids (CNN when configured) — never
        # silently re-run classical here. Fallback is only inside CNNCentroidDetector
        # on hard failure, and is reported via last_fallback / last_backend.

        fail = lambda msg: TrackerResult(
            False, None, None, cents, None, None, None, timings, {}, msg, mask
        )
        need = max(int(self.cfg.min_stars), 3)
        if len(cents.vectors) < 3:
            return fail(f"Insufficient stars detected ({len(cents.vectors)} < 3)")

        t2 = time.perf_counter()
        ident = self.star_identifier.identify(cents.vectors, cents.flux)
        # A unique triangle of 3 can fit the wrong sky. Prefer a 4-star wide vote.
        # Also escalate when Pyramid returns a thin set (<8): on wide outdoor
        # frames (e.g. LOST mountain + CNN) that thin lock often fails the
        # post-Wahba recall gate while identify_wide recovers a confirmed field.
        want_wide = (not ident.success or len(ident.obs_idx) < need) or (
            ident.success and len(ident.obs_idx) < 8
        )
        if want_wide and len(cents.vectors) >= need:
            wide = self.star_identifier.identify_wide(cents.vectors, cents.flux, self.camera)
            if wide.success and len(wide.obs_idx) >= max(need, len(ident.obs_idx) + 1):
                ident = wide
        timings["identification_ms"] = (time.perf_counter() - t2) * 1000.0
        if not ident.success or len(ident.obs_idx) < 3:
            return fail(f"Identification failed to match at least 3 stars (matched {len(ident.obs_idx)})")

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
            limit = np.maximum(self.cfg.residual_n_sigma * sigma_arc, np.degrees(self.cfg.angular_tol_rad) * 3600.0)
            keep = res <= limit
            if int(np.count_nonzero(keep)) < 3 or bool(np.all(keep)):
                cov = self.wahba.covariance_rad2(b, sig_rad)
                break
            obs_idx = obs_idx[keep]
            cat_idx = cat_idx[keep]
        if a is not None:
            obs_idx, cat_idx = self._associate_remaining(cents, a, obs_idx, cat_idx)
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
        n_in = 0
        if a is not None:
            _uv, in_fov = self.camera.project((a @ self.catalog.vectors.T).T)
            n_in = int(np.count_nonzero(in_fov))
        recall = n_id / n_in if n_in else 0.0
        # A wrong triangle matches a handful of blobs in a field that should
        # contain many more catalog stars. Three stars are accepted only when
        # that field really has just those three.
        confirmed = n_id >= 8 or (n_id >= need and recall >= 0.75) or (n_id == 3 and n_in <= 3)
        if not confirmed:
            return fail(
                f"Attitude matched only {n_id} of {n_in} catalog stars in that field"
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

    def _associate_remaining(
        self,
        cents: Centroids,
        a: np.ndarray,
        obs_idx: np.ndarray,
        cat_idx: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """After Wahba, map leftover centroids to catalog stars already in the FOV.

        Pyramid only searches max_stars brightest blobs. Simulated stars are still
        in Yale/Hipparcos; they just were not pyramid vertices.
        """
        if len(cents.uv) == 0:
            return obs_idx, cat_idx
        used_obs = {int(i) for i in obs_idx}
        used_cat = {int(i) for i in cat_idx}
        cam_v = (a @ self.catalog.vectors.T).T
        uv, infov = self.camera.project(cam_v)
        ifov = max(float(self.camera.ifov_arcsec), 1e-9)
        px_tol = max(2.5, float(np.degrees(self.cfg.angular_tol_rad) * 3600.0) / ifov)
        extra_o: list[int] = []
        extra_c: list[int] = []
        for ci in np.flatnonzero(infov):
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

    def _quality(self, cents: Centroids, ident: IdResult, a: np.ndarray | None) -> dict:
        quality = {
            "n_detected": int(len(cents.uv)),
            "n_matched": int(len(ident.obs_idx)),
            "centroid_backend": str(self.cfg.centroid_backend or "classical"),
            "centroid_detector": getattr(
                self.centroid_detector, "last_backend", self.cfg.centroid_backend
            ),
            "centroid_fallback": bool(
                getattr(self.centroid_detector, "last_fallback", False)
            ),
            "low_recall": False,
            "many_false": False,
        }
        if a is None:
            return quality
        cam_v = (a @ self.catalog.vectors.T).T
        uv, infov = self.camera.project(cam_v)
        n_pred = int(np.count_nonzero(infov))
        if n_pred == 0:
            quality["low_recall"] = True
            return quality
        # predicted star has a centroid within 2 px?
        if len(cents.uv) == 0:
            quality["low_recall"] = True
            return quality
        pred = uv[infov]
        d = pred[:, None, :] - cents.uv[None, :, :]
        dist = np.linalg.norm(d, axis=2)
        recalled = float(np.mean(dist.min(axis=1) < 2.0))
        quality["recall"] = recalled
        quality["low_recall"] = recalled < 0.5
        unmatched = 1.0 - len(ident.obs_idx) / max(len(cents.uv), 1)
        quality["unmatched_frac"] = unmatched
        quality["many_false"] = unmatched > 0.5
        return quality
