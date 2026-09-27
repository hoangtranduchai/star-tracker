"""Synthetic sky for the demo camera (uint16, 12-bit)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .camera import CameraModel
from .catalog import StarCatalog
from .quaternion import propagate, random_quaternion, to_dcm


@dataclass
class Radiometry:
    """Simulation radiometry. All numeric defaults are assumptions, not datasheet."""

    assumption: bool = True
    e_per_s_v0: float = 3.3e6
    qe: float = 1.0
    read_noise_e: float = 5.0
    dark_e_per_s: float = 10.0
    gain_dn_per_e: float = 1.0
    full_well_e: float = 12_000.0
    bit_depth: int = 12
    bias_dn: float = 64.0
    hot_pixel_frac: float = 1.0e-5
    cosmic_rate_per_frame: float = 2.0

    @property
    def max_dn(self) -> int:
        return (1 << self.bit_depth) - 1


@dataclass
class GlareSpec:
    kind: str  # "earth" | "sun" | "moon"
    # Earth = limb in FOV (sky above, albedo below). 0.22 used to wash ~78% of the frame.
    edge_frac: float = 0.70
    peak_dn: float = 3500.0
    u: float = 80.0
    v: float = 80.0
    sigma_px: float = 90.0
    diam_deg: float = 0.50  # mean apparent Sun/Moon diameter; assumption


@dataclass
class RenderTruth:
    q_gt: np.ndarray
    uv_mid: np.ndarray
    cat_idx: np.ndarray
    streak_px: np.ndarray
    omega_deg_s: np.ndarray
    vis_mags: np.ndarray
    false_uv: np.ndarray = field(default_factory=lambda: np.empty((0, 2)))


class SkySimulator:
    """Renders a starfield with optional orbital-rate streaks and detector noise."""

    def __init__(
        self,
        camera: CameraModel,
        catalog: StarCatalog,
        radiometry: Optional[Radiometry] = None,
        seed: int | None = 0,
    ):
        self.camera = camera
        self.catalog = catalog
        self.radiometry = radiometry or Radiometry()
        self.rng = np.random.default_rng(seed)
        n_pix = camera.width * camera.height
        n_hot = int(self.radiometry.hot_pixel_frac * n_pix)
        self.hot_yx = (
            np.column_stack(
                (
                    self.rng.integers(0, camera.height, size=n_hot),
                    self.rng.integers(0, camera.width, size=n_hot),
                )
            )
            if n_hot > 0
            else np.empty((0, 2), dtype=np.int64)
        )

    @property
    def width(self) -> int:
        return self.camera.width

    @property
    def height(self) -> int:
        return self.camera.height

    @property
    def fx(self) -> float:
        return self.camera.fx

    @property
    def fy(self) -> float:
        return self.camera.fy

    @property
    def cx(self) -> float:
        return self.camera.cx

    @property
    def cy(self) -> float:
        return self.camera.cy

    @staticmethod
    def generate_random_quaternion(seed: int | None = None) -> np.ndarray:
        rng = np.random.default_rng(seed)
        return random_quaternion(rng)

    def quaternion_to_rotation_matrix(self, q: np.ndarray) -> np.ndarray:
        return to_dcm(q)

    def electrons(self, mag: np.ndarray, t_exp_s: float) -> np.ndarray:
        return (
            self.radiometry.e_per_s_v0
            * (10.0 ** (-0.4 * np.asarray(mag, dtype=np.float64)))
            * self.radiometry.qe
            * t_exp_s
        )

    def render(
        self,
        q_gt: np.ndarray,
        omega_deg_s: tuple[float, float, float] | np.ndarray = (0.0, 0.06, 0.0),
        t_exp_s: float = 0.15,
        psf_sigma_px: float = 1.2,
        glare: GlareSpec | None = None,
        false_stars: int = 0,
        add_noise: bool = True,
        sky_clutter: str = "none",
    ) -> tuple[np.ndarray, RenderTruth]:
        omega = np.asarray(omega_deg_s, dtype=np.float64).reshape(3)
        omega_rad = np.radians(omega)
        a_mid = to_dcm(q_gt)
        cam_mid = (a_mid @ self.catalog.vectors.T).T
        uv_mid, in_fov = self.camera.project(cam_mid)
        cat_idx = np.nonzero(in_fov)[0]
        uv_keep = uv_mid[in_fov]
        mags = self.catalog.mags[cat_idx]

        omega_norm = float(np.linalg.norm(omega_rad))
        l_char = omega_norm * t_exp_s * self.camera.fx
        n_sub = int(np.ceil(l_char / 0.5)) + 1 if l_char > 0.05 else 1
        n_sub = max(n_sub, 1)

        acc = np.zeros((self.camera.height, self.camera.width), dtype=np.float32)
        electrons = self.electrons(mags, t_exp_s)
        radius = int(np.ceil(3.5 * psf_sigma_px))
        for k in range(n_sub):
            tau = (k + 0.5) / n_sub * t_exp_s - 0.5 * t_exp_s
            q_k = propagate(q_gt, omega_rad, tau)
            a_k = to_dcm(q_k)
            cam_k = (a_k @ self.catalog.vectors[cat_idx].T).T
            uv_k, vis = self.camera.project(cam_k)
            self._stamp_gaussians(
                acc,
                uv_k[vis],
                electrons[vis] / n_sub,
                psf_sigma_px,
                radius,
            )

        false_uv = np.empty((0, 2), dtype=np.float64)
        if false_stars > 0:
            false_uv = np.column_stack(
                (
                    self.rng.uniform(10, self.camera.width - 10, size=false_stars),
                    self.rng.uniform(10, self.camera.height - 10, size=false_stars),
                )
            )
            false_e = self.electrons(np.full(false_stars, 4.0), t_exp_s)
            self._stamp_gaussians(acc, false_uv, false_e, psf_sigma_px, radius)

        # Detector: bias + dark + optional Poisson/read + hot + cosmic
        dark_e = self.radiometry.dark_e_per_s * t_exp_s
        if add_noise:
            acc = self.rng.poisson(np.clip(acc + dark_e, 0, None)).astype(np.float32)
            acc += self.rng.normal(0.0, self.radiometry.read_noise_e, size=acc.shape).astype(
                np.float32
            )
        else:
            acc = acc + dark_e

        acc = np.minimum(acc, self.radiometry.full_well_e)
        img = acc * self.radiometry.gain_dn_per_e + self.radiometry.bias_dn

        if add_noise and len(self.hot_yx) > 0:
            img[self.hot_yx[:, 0], self.hot_yx[:, 1]] = self.radiometry.max_dn
        if add_noise and self.radiometry.cosmic_rate_per_frame > 0:
            n_cos = int(self.rng.poisson(self.radiometry.cosmic_rate_per_frame))
            for _ in range(n_cos):
                y = int(self.rng.integers(0, self.camera.height))
                x = int(self.rng.integers(0, self.camera.width))
                img[y, x] = self.radiometry.max_dn

        if glare is not None:
            img = img + self._glare_dn(glare)
        clutter = str(sky_clutter or "none").lower()
        if clutter not in {"", "none"}:
            img = img + self._clutter_dn(clutter)

        img = np.clip(img, 0, self.radiometry.max_dn).astype(np.uint16)

        # Streak length at each star from perpendicular rate (cross-boresight).
        # For small FOV, L ≈ |ω × b| t fx  with b ≈ boresight + pixel offsets.
        streak = np.full(len(cat_idx), l_char, dtype=np.float64)
        return img, RenderTruth(
            q_gt=np.asarray(q_gt, dtype=np.float64),
            uv_mid=uv_keep,
            cat_idx=cat_idx,
            streak_px=streak,
            omega_deg_s=omega,
            vis_mags=mags,
            false_uv=false_uv,
        )

    def _stamp_gaussians(
        self,
        acc: np.ndarray,
        uv: np.ndarray,
        electrons: np.ndarray,
        sigma: float,
        radius: int,
    ) -> None:
        h, w = acc.shape
        two_s2 = 2.0 * sigma * sigma
        for (u, v), e in zip(uv, electrons):
            x0 = int(np.floor(u))
            y0 = int(np.floor(v))
            x_min = max(0, x0 - radius)
            x_max = min(w, x0 + radius + 1)
            y_min = max(0, y0 - radius)
            y_max = min(h, y0 + radius + 1)
            if x_min >= x_max or y_min >= y_max:
                continue
            yy, xx = np.mgrid[y_min:y_max, x_min:x_max]
            ker = np.exp(-((xx - u) ** 2 + (yy - v) ** 2) / two_s2)
            s = float(ker.sum())
            if s <= 0:
                continue
            acc[y_min:y_max, x_min:x_max] += (e / s) * ker

    def _disk_dn(self, u: float, v: float, radius_px: float, peak: float, limb_px: float) -> np.ndarray:
        h, w = self.camera.height, self.camera.width
        yy, xx = np.mgrid[0:h, 0:w]
        r = np.sqrt((xx - u) ** 2 + (yy - v) ** 2)
        soft = max(float(limb_px), 1.0)
        t = np.clip((radius_px + 0.5 * soft - r) / soft, 0.0, 1.0)
        return (float(peak) * t).astype(np.float32)

    def _glare_dn(self, glare: GlareSpec) -> np.ndarray:
        h, w = self.camera.height, self.camera.width
        kind = str(glare.kind).lower()
        if kind == "earth":
            # Limb like ISS night photos: dark sky + stars above, bright Earth below.
            # Not a full-frame albedo wash (that leaves too few stars for Pyramid).
            yy, _ = np.mgrid[0:h, 0:w]
            limb = float(glare.edge_frac) * h
            rise = max(6.0, 0.012 * h)
            earth = glare.peak_dn * np.clip((yy - limb) / rise, 0.0, 1.0)
            # Thin airglow just above the limb. DN is a simulation assumption.
            above = np.maximum(limb - yy, 0.0)
            glow_sig = max(8.0, 0.028 * h)
            airglow = 380.0 * np.exp(-(above / glow_sig) ** 2)
            airglow = np.where(yy < limb, airglow, 0.0)
            return (earth + airglow).astype(np.float32)

        u = float(glare.u)
        v = float(glare.v)
        radius = 0.5 * self.camera.angular_diameter_px(glare.diam_deg)
        disk = self._disk_dn(u, v, radius, glare.peak_dn, limb_px=max(1.5, 0.08 * radius))
        if kind == "moon":
            return disk
        # Sun: 0.5° photosphere plus wide stray-light bloom (baffle not modeled).
        yy, xx = np.mgrid[0:h, 0:w]
        sig = float(glare.sigma_px) if glare.sigma_px > 0 else max(12.0, 3.0 * radius)
        bloom = glare.peak_dn * np.exp(-((xx - u) ** 2 + (yy - v) ** 2) / (2.0 * sig * sig))
        return np.maximum(disk, bloom.astype(np.float32))

    def _clutter_layers(self, kind: str) -> set[str]:
        k = str(kind or "none").lower().strip()
        aliases = {
            "none": set(),
            "galactic": {"galactic"},
            "milky_way": {"galactic"},
            "mw": {"galactic"},
            "galaxy": {"galaxy"},
            "andromeda": {"galaxy"},
            "m31": {"galaxy"},
            "nebula": {"nebula"},
            "cloud": {"cloud"},
            "typical": {"galactic", "galaxy", "nebula", "cloud"},
            "both": {"galactic", "galaxy"},
            "all": {"galactic", "galaxy", "nebula", "cloud"},
        }
        return aliases.get(k, set())

    def _clutter_dn(self, kind: str) -> np.ndarray:
        """Classes of faint extended sky (assumption DN), not a named DSO catalog.

        Milky Way / Andromeda are examples of galactic-plane glow and a nearby
        galaxy. Nebula / unresolved cloud cover the other shapes centroid sees.
        """
        h, w = self.camera.height, self.camera.width
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        out = np.zeros((h, w), dtype=np.float32)
        layers = self._clutter_layers(kind)
        if "galactic" in layers:
            band_w = 0.12 * min(h, w)
            proj = (xx / max(w, 1) + yy / max(h, 1) - 1.0) * min(h, w) * 0.5
            out += 55.0 * np.exp(-(proj**2) / (2.0 * band_w * band_w))
        if "galaxy" in layers:
            a = 0.5 * self.camera.angular_diameter_px(3.0)
            b = 0.5 * self.camera.angular_diameter_px(1.0)
            uc, vc = 0.62 * w, 0.38 * h
            ell = ((xx - uc) / max(a, 1.0)) ** 2 + ((yy - vc) / max(b, 1.0)) ** 2
            out += 40.0 * np.exp(-0.5 * ell)
        if "nebula" in layers:
            a = 0.5 * self.camera.angular_diameter_px(0.8)
            b = 0.5 * self.camera.angular_diameter_px(0.6)
            uc, vc = 0.35 * w, 0.62 * h
            ell = ((xx - uc) / max(a, 1.0)) ** 2 + ((yy - vc) / max(b, 1.0)) ** 2
            out += 70.0 * np.exp(-ell) + 25.0 * np.exp(-0.35 * ell)
        if "cloud" in layers:
            a = 0.5 * self.camera.angular_diameter_px(5.5)
            b = 0.5 * self.camera.angular_diameter_px(4.0)
            uc, vc = 0.78 * w, 0.72 * h
            ell = ((xx - uc) / max(a, 1.0)) ** 2 + ((yy - vc) / max(b, 1.0)) ** 2
            out += 35.0 * np.exp(-0.45 * ell)
        return out
