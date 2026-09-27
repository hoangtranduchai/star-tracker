"""
Pinhole + Brown–Conrady camera model.

Demo optics follow a common APS-C still camera (6000×4000, 3.72 µm) and a 50 mm lens.
Pixel convention: principal point at ((W-1)/2, (H-1)/2). Camera +Z is boresight,
+X along column u, +Y along row v. Distortion is applied on centroids only.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .quaternion import ARCSEC_PER_RAD


@dataclass(frozen=True)
class CameraModel:
    width: int
    height: int
    pixel_um: float
    focal_mm: float
    k1: float = 0.0
    k2: float = 0.0
    k3: float = 0.0
    p1: float = 0.0
    p2: float = 0.0
    edge_margin_px: float = 5.0

    @property
    def pixel_mm(self) -> float:
        return self.pixel_um * 1e-3

    @property
    def fx(self) -> float:
        return self.focal_mm / self.pixel_mm

    @property
    def fy(self) -> float:
        return self.fx

    @property
    def cx(self) -> float:
        return (self.width - 1) * 0.5

    @property
    def cy(self) -> float:
        return (self.height - 1) * 0.5

    @property
    def ifov_rad(self) -> float:
        return self.pixel_mm / self.focal_mm

    @property
    def ifov_arcsec(self) -> float:
        return self.ifov_rad * ARCSEC_PER_RAD

    def angular_diameter_px(self, diam_deg: float) -> float:
        """Pixels spanning an on-sky angle (small-angle, IFOV)."""
        return float(diam_deg) * 3600.0 / max(float(self.ifov_arcsec), 1e-9)

    @property
    def fov_deg(self) -> tuple[float, float, float]:
        sensor_w = self.width * self.pixel_mm
        sensor_h = self.height * self.pixel_mm
        h = np.degrees(2.0 * np.arctan(sensor_w / (2.0 * self.focal_mm)))
        v = np.degrees(2.0 * np.arctan(sensor_h / (2.0 * self.focal_mm)))
        diag = np.hypot(sensor_w, sensor_h)
        d = np.degrees(2.0 * np.arctan(diag / (2.0 * self.focal_mm)))
        return float(h), float(v), float(d)

    @property
    def has_distortion(self) -> bool:
        return any(abs(x) > 0.0 for x in (self.k1, self.k2, self.k3, self.p1, self.p2))

    def intrinsic_matrix(self) -> np.ndarray:
        return np.array(
            [[self.fx, 0.0, self.cx], [0.0, self.fy, self.cy], [0.0, 0.0, 1.0]],
            dtype=np.float64,
        )

    def dist_coeffs(self) -> np.ndarray:
        return np.array([self.k1, self.k2, self.p1, self.p2, self.k3], dtype=np.float64)

    def downscaled(self, factor: int) -> "CameraModel":
        if factor < 1:
            raise ValueError("downscale factor must be >= 1")
        return CameraModel(
            width=self.width // factor,
            height=self.height // factor,
            pixel_um=self.pixel_um * factor,
            focal_mm=self.focal_mm,
            k1=self.k1,
            k2=self.k2,
            k3=self.k3,
            p1=self.p1,
            p2=self.p2,
            edge_margin_px=max(1.0, self.edge_margin_px / factor),
        )

    def apply_distortion(self, x_u: np.ndarray, y_u: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        r2 = x_u * x_u + y_u * y_u
        radial = 1.0 + self.k1 * r2 + self.k2 * r2 * r2 + self.k3 * r2 * r2 * r2
        x_d = x_u * radial + 2.0 * self.p1 * x_u * y_u + self.p2 * (r2 + 2.0 * x_u * x_u)
        y_d = y_u * radial + self.p1 * (r2 + 2.0 * y_u * y_u) + 2.0 * self.p2 * x_u * y_u
        return x_d, y_d

    def undistort_iterative(
        self, x_d: np.ndarray, y_d: np.ndarray, n_iter: int = 12
    ) -> tuple[np.ndarray, np.ndarray]:
        x_u = np.array(x_d, dtype=np.float64, copy=True)
        y_u = np.array(y_d, dtype=np.float64, copy=True)
        for _ in range(n_iter):
            r2 = x_u * x_u + y_u * y_u
            radial = 1.0 + self.k1 * r2 + self.k2 * r2 * r2 + self.k3 * r2 * r2 * r2
            x_u = (
                x_d - 2.0 * self.p1 * x_u * y_u - self.p2 * (r2 + 2.0 * x_u * x_u)
            ) / radial
            y_u = (
                y_d - self.p1 * (r2 + 2.0 * y_u * y_u) - 2.0 * self.p2 * x_u * y_u
            ) / radial
        return x_u, y_u

    def project(self, vec_cam: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Project camera-frame vectors to pixels. Returns (uv (N,2), in_fov mask)."""
        vec = np.asarray(vec_cam, dtype=np.float64)
        if vec.ndim == 1:
            vec = vec.reshape(1, 3)
        z = vec[:, 2]
        forward = z > 0.1
        uv = np.full((len(vec), 2), np.nan, dtype=np.float64)
        if not np.any(forward):
            return uv, np.zeros(len(vec), dtype=bool)
        x_u = vec[forward, 0] / z[forward]
        y_u = vec[forward, 1] / z[forward]
        if self.has_distortion:
            x_u, y_u = self.apply_distortion(x_u, y_u)
        u = self.fx * x_u + self.cx
        v = self.fy * y_u + self.cy
        uv[forward, 0] = u
        uv[forward, 1] = v
        m = self.edge_margin_px
        in_fov = (
            forward
            & (uv[:, 0] >= m)
            & (uv[:, 0] < self.width - m)
            & (uv[:, 1] >= m)
            & (uv[:, 1] < self.height - m)
        )
        return uv, in_fov

    def unproject(self, uv: np.ndarray) -> np.ndarray:
        """Pixel coordinates (K,2) -> unit camera-frame vectors (K,3)."""
        pts = np.asarray(uv, dtype=np.float64)
        if pts.ndim == 1:
            pts = pts.reshape(1, 2)
        x_d = (pts[:, 0] - self.cx) / self.fx
        y_d = (pts[:, 1] - self.cy) / self.fy
        if self.has_distortion:
            x_u, y_u = self.undistort_iterative(x_d, y_d)
        else:
            x_u, y_u = x_d, y_d
        vec = np.column_stack((x_u, y_u, np.ones_like(x_u)))
        vec /= np.linalg.norm(vec, axis=1, keepdims=True)
        return vec


def demo_camera(**kwargs) -> CameraModel:
    """APS-C class still camera, 24 MP, with a 50 mm lens. Not a named flight sensor."""
    return CameraModel(width=6000, height=4000, pixel_um=3.72, focal_mm=50.0, **kwargs)


def demo_camera_long_side(long_side: int = 1024, **kwargs) -> CameraModel:
    """Scale demo camera so the long side is ~long_side px; keep 50 mm and same FOV class."""
    base = demo_camera(**kwargs)
    if long_side < 32:
        raise ValueError("long_side must be >= 32")
    scale = base.width / float(long_side)
    height = max(32, int(round(base.height / scale)))
    return CameraModel(
        width=int(long_side),
        height=height,
        pixel_um=base.pixel_um * scale,
        focal_mm=base.focal_mm,
        k1=base.k1,
        k2=base.k2,
        k3=base.k3,
        p1=base.p1,
        p2=base.p2,
        edge_margin_px=max(1.0, base.edge_margin_px / scale),
    )
