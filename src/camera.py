"""Pinhole + Brown-Conrady camera projection model."""
from numpy import any as npany, arctan, array, asarray, column_stack, degrees, float64, full, hypot, nan, ones_like, zeros
from numpy.linalg import norm
from .quaternion import ARCSEC_PER_RAD

def _radial_tangential_step(x_val: object, y_val: object, k1: object, k2: object, k3: object, p1: object, p2: object) -> object:
    r2: object = x_val * x_val + y_val * y_val
    r4: object = r2 * r2
    rad: object = 1.0 + k1 * r2 + k2 * r4 + k3 * (r4 * r2)
    xy2: object = 2.0 * x_val * y_val
    dx_t: object = p1 * xy2 + p2 * (r2 + 2.0 * x_val * x_val)
    dy_t: object = p1 * (r2 + 2.0 * y_val * y_val) + p2 * xy2
    return (rad, dx_t, dy_t)

class CameraModel:
    """Pinhole + Brown-Conrady camera model with principal point at `((W-1)/2, (H-1)/2)`."""

    def __init__(self, width: object, height: object, pixel_um: object, focal_mm: object, k1: object=0.0, k2: object=0.0, k3: object=0.0, p1: object=0.0, p2: object=0.0, edge_margin_px: object=5.0) -> object:
        attrs: object = dict(width=int(width), height=int(height), pixel_um=float(pixel_um), focal_mm=float(focal_mm), k1=float(k1), k2=float(k2), k3=float(k3), p1=float(p1), p2=float(p2), edge_margin_px=float(edge_margin_px))
        self.__dict__.update(attrs)

    def __setattr__(self, name: object, value: object) -> object:
        raise AttributeError('CameraModel instance is immutable')

    def __eq__(self, other: object) -> object:
        if not isinstance(other, CameraModel):
            return NotImplemented
        return self.__dict__ == other.__dict__

    @property
    def pixel_mm(self) -> object:
        return self.pixel_um * 0.001

    @property
    def fx(self) -> object:
        return self.focal_mm / self.pixel_mm

    @property
    def fy(self) -> object:
        return self.fx

    @property
    def cx(self) -> object:
        return (self.width - 1) * 0.5

    @property
    def cy(self) -> object:
        return (self.height - 1) * 0.5

    @property
    def ifov_rad(self) -> object:
        return self.pixel_mm / self.focal_mm

    @property
    def ifov_arcsec(self) -> object:
        return self.ifov_rad * ARCSEC_PER_RAD

    def angular_diameter_px(self, diam_deg: object) -> object:
        """Convert on-sky angular diameter in degrees to sensor pixels via small-angle IFOV."""
        return float(diam_deg) * 3600.0 / max(float(self.ifov_arcsec), 1e-09)

    @property
    def fov_deg(self) -> object:
        pitch: object = self.pixel_mm
        sw, sh = (self.width * pitch, self.height * pitch)
        sd: object = float(hypot(sw, sh))
        inv_2f: object = 0.5 / self.focal_mm
        return tuple((float(degrees(2.0 * arctan(span * inv_2f))) for span in (sw, sh, sd)))

    @property
    def has_distortion(self) -> object:
        return any((abs(val) > 0.0 for val in (self.k1, self.k2, self.k3, self.p1, self.p2)))

    def intrinsic_matrix(self) -> object:
        f_px, u0, v0 = (self.fx, self.cx, self.cy)
        return asarray([[f_px, 0.0, u0], [0.0, f_px, v0], [0.0, 0.0, 1.0]], dtype=float64)

    def dist_coeffs(self) -> object:
        return asarray([self.k1, self.k2, self.p1, self.p2, self.k3], dtype=float64)

    def downscaled(self, factor: object) -> object:
        fac: object = int(factor)
        if not fac >= 1:
            raise ValueError('downscale factor must be >= 1')
        return CameraModel(width=self.width // fac, height=self.height // fac, pixel_um=self.pixel_um * fac, focal_mm=self.focal_mm, k1=self.k1, k2=self.k2, k3=self.k3, p1=self.p1, p2=self.p2, edge_margin_px=max(1.0, self.edge_margin_px / fac))

    def apply_distortion(self, x_u: object, y_u: object) -> object:
        rad, dx_t, dy_t = _radial_tangential_step(x_u, y_u, self.k1, self.k2, self.k3, self.p1, self.p2)
        return (x_u * rad + dx_t, y_u * rad + dy_t)

    def undistort_iterative(self, x_d: object, y_d: object, n_iter: object=12) -> object:
        xu: object = array(x_d, dtype=float64, copy=True)
        yu: object = array(y_d, dtype=float64, copy=True)
        for _ in range(int(n_iter)):
            rad, dx_t, dy_t = _radial_tangential_step(xu, yu, self.k1, self.k2, self.k3, self.p1, self.p2)
            inv_rad: object = 1.0 / rad
            xu: object = (x_d - dx_t) * inv_rad
            yu: object = (y_d - dy_t) * inv_rad
        return (xu, yu)

    def project(self, vec_cam: object) -> object:
        """Project camera-frame direction vectors to `(uv, in_fov)`."""
        arr: object = asarray(vec_cam, dtype=float64)
        pts: object = arr.reshape(1, 3) if arr.ndim == 1 else arr
        count: object = int(pts.shape[0])
        vx, vy, vz = pts.T
        front: object = vz > 0.1
        uv_out: object = full((count, 2), nan, dtype=float64)
        if not npany(front):
            return (uv_out, zeros(count, dtype=bool))
        inv_z: object = 1.0 / vz[front]
        xu, yu = (vx[front] * inv_z, vy[front] * inv_z)
        if self.has_distortion:
            xu, yu = self.apply_distortion(xu, yu)
        u_px: object = self.fx * xu + self.cx
        v_px: object = self.fy * yu + self.cy
        uv_out[front, 0] = u_px
        uv_out[front, 1] = v_px
        pad: object = self.edge_margin_px
        u_all, v_all = uv_out.T
        inside: object = front & (u_all >= pad) & (u_all < self.width - pad) & (v_all >= pad) & (v_all < self.height - pad)
        return (uv_out, inside)

    def unproject(self, uv: object) -> object:
        """Back-project pixel coordinates `(K, 2)` into unit camera-frame vectors `(K, 3)`."""
        raw: object = asarray(uv, dtype=float64)
        pts: object = raw.reshape(1, 2) if raw.ndim == 1 else raw
        u_px, v_px = pts.T
        xd: object = (u_px - self.cx) * (1.0 / self.fx)
        yd: object = (v_px - self.cy) * (1.0 / self.fy)
        xu, yu = self.undistort_iterative(xd, yd) if self.has_distortion else (xd, yd)
        rays: object = column_stack((xu, yu, ones_like(xu)))
        return rays / norm(rays, axis=-1, keepdims=True)

def demo_camera(**kwargs) -> object:
    """Return default 24 MP APS-C (6000x4000, 3.72 um, f=50 mm) camera configuration."""
    params: object = dict(width=6000, height=4000, pixel_um=3.72, focal_mm=50.0)
    params.update(kwargs)
    return CameraModel(**params)

def demo_camera_long_side(long_side: object=1024, **kwargs) -> object:
    """Scale the APS-C demo camera to `long_side` horizontal pixels while preserving FOV."""
    target_w: object = int(long_side)
    if not target_w >= 32:
        raise ValueError('long_side must be >= 32')
    ref_cam: object = demo_camera(**kwargs)
    ratio: object = ref_cam.width / float(target_w)
    target_h: object = max(32, int(round(ref_cam.height / ratio)))
    return CameraModel(width=target_w, height=target_h, pixel_um=ref_cam.pixel_um * ratio, focal_mm=ref_cam.focal_mm, k1=ref_cam.k1, k2=ref_cam.k2, k3=ref_cam.k3, p1=ref_cam.p1, p2=ref_cam.p2, edge_margin_px=max(1.0, ref_cam.edge_margin_px / ratio))
