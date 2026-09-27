"""Synthetic starfield renderer with orbital-rate smearing, radiometric noise, and sky clutter."""
from numpy import asarray, ceil, clip, column_stack, einsum, empty, exp, floor, float32, float64, full, hypot, int64, maximum, mgrid, minimum, nonzero, power, radians, uint16, where, zeros
from numpy.linalg import norm
from numpy.random import default_rng
from .quaternion import propagate, random_quaternion, to_dcm
_CLUTTER_PRESETS = {'none': set(), 'galactic': {'galactic'}, 'milky_way': {'galactic'}, 'mw': {'galactic'}, 'galaxy': {'galaxy'}, 'andromeda': {'galaxy'}, 'm31': {'galaxy'}, 'nebula': {'nebula'}, 'cloud': {'cloud'}, 'typical': {'galactic', 'galaxy', 'nebula', 'cloud'}, 'both': {'galactic', 'galaxy'}, 'all': {'galactic', 'galaxy', 'nebula', 'cloud'}}

class Radiometry:
    """Detector and photometric parameters for synthetic starfield rendering."""

    def __init__(self, assumption: object=True, e_per_s_v0: object=3300000.0, qe: object=1.0, read_noise_e: object=5.0, dark_e_per_s: object=10.0, gain_dn_per_e: object=1.0, full_well_e: object=12000.0, bit_depth: object=12, bias_dn: object=64.0, hot_pixel_frac: object=1e-05, cosmic_rate_per_frame: object=2.0) -> object:
        self.assumption, self.e_per_s_v0, self.qe, self.read_noise_e, self.dark_e_per_s, self.gain_dn_per_e, self.full_well_e, self.bit_depth, self.bias_dn, self.hot_pixel_frac, self.cosmic_rate_per_frame = (bool(assumption), float(e_per_s_v0), float(qe), float(read_noise_e), float(dark_e_per_s), float(gain_dn_per_e), float(full_well_e), int(bit_depth), float(bias_dn), float(hot_pixel_frac), float(cosmic_rate_per_frame))

    @property
    def max_dn(self) -> object:
        return (1 << int(self.bit_depth)) - 1

class GlareSpec:
    """Parameters describing Earth-limb, Sun, or Moon stray-light contamination."""

    def __init__(self, kind: object, edge_frac: object=0.7, peak_dn: object=3500.0, u: object=80.0, v: object=80.0, sigma_px: object=90.0, diam_deg: object=0.5) -> object:
        self.kind, self.edge_frac, self.peak_dn, self.u, self.v, self.sigma_px, self.diam_deg = (str(kind), float(edge_frac), float(peak_dn), float(u), float(v), float(sigma_px), float(diam_deg))

class RenderTruth:
    """Ground-truth metadata accompanying a rendered synthetic starfield."""

    def __init__(self, q_gt: object, uv_mid: object, cat_idx: object, streak_px: object, omega_deg_s: object, vis_mags: object, false_uv: object=None) -> object:
        self.q_gt, self.uv_mid, self.cat_idx, self.streak_px, self.omega_deg_s, self.vis_mags, self.false_uv = (q_gt, uv_mid, cat_idx, streak_px, omega_deg_s, vis_mags, empty((0, 2), dtype=float64) if false_uv is None else false_uv)

def _elliptical_gaussian(xx: object, yy: object, uc: object, vc: object, semi_a: object, semi_b: object, scale_factor: object) -> object:
    dx: object = (xx - float(uc)) / max(float(semi_a), 1.0)
    dy: object = (yy - float(vc)) / max(float(semi_b), 1.0)
    return exp(-float(scale_factor) * (dx * dx + dy * dy))

class SkySimulator:
    """Renders 12-bit synthetic star tracker frames with optional motion blur and stray light."""

    def __init__(self, camera: object, catalog: object, radiometry: object=None, seed: object=0) -> object:
        rad_cfg: object = Radiometry() if radiometry is None else radiometry
        gen: object = default_rng(seed)
        total_px: object = int(camera.width) * int(camera.height)
        hot_cnt: object = int(rad_cfg.hot_pixel_frac * total_px)
        hot_coords: object = column_stack((gen.integers(0, camera.height, size=hot_cnt), gen.integers(0, camera.width, size=hot_cnt))) if hot_cnt > 0 else empty((0, 2), dtype=int64)
        self.camera, self.catalog, self.radiometry, self.rng, self.hot_yx = (camera, catalog, rad_cfg, gen, hot_coords)

    @property
    def width(self) -> object:
        return self.camera.width

    @property
    def height(self) -> object:
        return self.camera.height

    @property
    def fx(self) -> object:
        return self.camera.fx

    @property
    def fy(self) -> object:
        return self.camera.fy

    @property
    def cx(self) -> object:
        return self.camera.cx

    @property
    def cy(self) -> object:
        return self.camera.cy

    @staticmethod
    def generate_random_quaternion(seed: object=None) -> object:
        return random_quaternion(default_rng(seed))

    def quaternion_to_rotation_matrix(self, q: object) -> object:
        return to_dcm(q)

    def electrons(self, mag: object, t_exp_s: object) -> object:
        flux_scale: object = self.radiometry.e_per_s_v0 * self.radiometry.qe * float(t_exp_s)
        return flux_scale * power(10.0, -0.4 * asarray(mag, dtype=float64))

    def render(self, q_gt: object, omega_deg_s: object=(0.0, 0.06, 0.0), t_exp_s: object=0.15, psf_sigma_px: object=1.2, glare: object=None, false_stars: object=0, add_noise: object=True, sky_clutter: object='none') -> object:
        omega_d: object = asarray(omega_deg_s, dtype=float64).ravel()
        omega_r: object = radians(omega_d)
        dcm_mid: object = to_dcm(q_gt)
        cam_vecs: object = einsum('ij,kj->ik', self.catalog.vectors, dcm_mid)
        uv_all, fov_mask = self.camera.project(cam_vecs)
        vis_indices: object = nonzero(fov_mask)[0]
        uv_vis: object = uv_all[fov_mask]
        mags_vis: object = self.catalog.mags[vis_indices]
        streak_len: object = float(norm(omega_r)) * float(t_exp_s) * self.camera.fx
        sub_steps: object = max(int(ceil(streak_len / 0.5)) + 1 if streak_len > 0.05 else 1, 1)
        canvas: object = zeros((self.camera.height, self.camera.width), dtype=float32)
        photo_e: object = self.electrons(mags_vis, t_exp_s)
        patch_rad: object = int(ceil(3.5 * float(psf_sigma_px)))
        sub_vecs: object = self.catalog.vectors[vis_indices]
        for step_idx in range(sub_steps):
            dt_off: object = ((step_idx + 0.5) / float(sub_steps) - 0.5) * float(t_exp_s)
            dcm_step: object = to_dcm(propagate(q_gt, omega_r, dt_off))
            uv_step, mask_step = self.camera.project(einsum('ij,kj->ik', sub_vecs, dcm_step))
            self._stamp_gaussians(canvas, uv_step[mask_step], photo_e[mask_step] * (1.0 / float(sub_steps)), psf_sigma_px, patch_rad)
        spurious_uv: object = empty((0, 2), dtype=float64)
        if int(false_stars) > 0:
            n_sp: object = int(false_stars)
            spurious_uv: object = column_stack((self.rng.uniform(10.0, self.camera.width - 10.0, size=n_sp), self.rng.uniform(10.0, self.camera.height - 10.0, size=n_sp)))
            self._stamp_gaussians(canvas, spurious_uv, self.electrons(full(n_sp, 4.0), t_exp_s), psf_sigma_px, patch_rad)
        dark_level: object = self.radiometry.dark_e_per_s * float(t_exp_s)
        if add_noise:
            noisy_e: object = self.rng.poisson(clip(canvas + dark_level, 0.0, None)).astype(float32)
            read_jitter: object = self.rng.normal(0.0, self.radiometry.read_noise_e, size=canvas.shape).astype(float32)
            canvas: object = noisy_e + read_jitter
        else:
            canvas: object = canvas + dark_level
        dn_frame: object = minimum(canvas, self.radiometry.full_well_e) * self.radiometry.gain_dn_per_e + self.radiometry.bias_dn
        if add_noise:
            if len(self.hot_yx):
                dn_frame[self.hot_yx[:, 0], self.hot_yx[:, 1]] = self.radiometry.max_dn
            if self.radiometry.cosmic_rate_per_frame > 0.0:
                hits: object = int(self.rng.poisson(self.radiometry.cosmic_rate_per_frame))
                for _ in range(hits):
                    ry: object = int(self.rng.integers(0, self.camera.height))
                    rx: object = int(self.rng.integers(0, self.camera.width))
                    dn_frame[ry, rx] = self.radiometry.max_dn
        if glare is not None:
            dn_frame: object = dn_frame + self._glare_dn(glare)
        clutter_key: object = str(sky_clutter or 'none').lower()
        if clutter_key not in ('', 'none'):
            dn_frame: object = dn_frame + self._clutter_dn(clutter_key)
        final_u16: object = clip(dn_frame, 0, self.radiometry.max_dn).astype(uint16)
        truth_obj: object = RenderTruth(q_gt=asarray(q_gt, dtype=float64), uv_mid=uv_vis, cat_idx=vis_indices, streak_px=full(len(vis_indices), streak_len, dtype=float64), omega_deg_s=omega_d, vis_mags=mags_vis, false_uv=spurious_uv)
        return (final_u16, truth_obj)

    def _stamp_gaussians(self, acc: object, uv: object, electrons: object, sigma: object, radius: object) -> object:
        rows, cols = acc.shape
        inv_2s2: object = 1.0 / (2.0 * float(sigma) * float(sigma))
        rad: object = int(radius)
        for (u_c, v_c), e_val in zip(uv, electrons):
            uc_i, vc_i = (int(floor(u_c)), int(floor(v_c)))
            x0, x1 = (max(0, uc_i - rad), min(cols, uc_i + rad + 1))
            y0, y1 = (max(0, vc_i - rad), min(rows, vc_i + rad + 1))
            if x0 < x1 and y0 < y1:
                gy, gx = mgrid[y0:y1, x0:x1]
                psf: object = exp(-((gx - u_c) ** 2 + (gy - v_c) ** 2) * inv_2s2)
                psf_sum: object = float(psf.sum())
                if psf_sum > 0.0:
                    acc[y0:y1, x0:x1] += float(e_val) / psf_sum * psf

    def _disk_dn(self, u: object, v: object, radius_px: object, peak: object, limb_px: object) -> object:
        rows, cols = (self.camera.height, self.camera.width)
        gy, gx = mgrid[0:rows, 0:cols]
        dist: object = hypot(gx - float(u), gy - float(v))
        width_limb: object = max(float(limb_px), 1.0)
        ramp: object = clip((float(radius_px) + 0.5 * width_limb - dist) / width_limb, 0.0, 1.0)
        return (float(peak) * ramp).astype(float32)

    def _glare_dn(self, glare: object) -> object:
        rows, cols = (self.camera.height, self.camera.width)
        mode: object = str(glare.kind).lower()
        if mode == 'earth':
            gy, _ = mgrid[0:rows, 0:cols]
            horizon_y: object = float(glare.edge_frac) * rows
            transition: object = max(6.0, 0.012 * rows)
            albedo: object = float(glare.peak_dn) * clip((gy - horizon_y) / transition, 0.0, 1.0)
            alt_px: object = maximum(horizon_y - gy, 0.0)
            scale_h: object = max(8.0, 0.028 * rows)
            limb_glow: object = where(gy < horizon_y, 380.0 * exp(-(alt_px / scale_h) ** 2), 0.0)
            return (albedo + limb_glow).astype(float32)
        uc, vc = (float(glare.u), float(glare.v))
        r_px: object = 0.5 * self.camera.angular_diameter_px(glare.diam_deg)
        solar_disk: object = self._disk_dn(uc, vc, r_px, glare.peak_dn, limb_px=max(1.5, 0.08 * r_px))
        if mode == 'moon':
            return solar_disk
        gy, gx = mgrid[0:rows, 0:cols]
        sig_val: object = float(glare.sigma_px) if glare.sigma_px > 0 else max(12.0, 3.0 * r_px)
        halo: object = float(glare.peak_dn) * exp(-((gx - uc) ** 2 + (gy - vc) ** 2) / (2.0 * sig_val * sig_val))
        return maximum(solar_disk, halo.astype(float32))

    def _clutter_layers(self, kind: object) -> object:
        return set(_CLUTTER_PRESETS.get(str(kind or 'none').lower().strip(), ()))

    def _clutter_dn(self, kind: object) -> object:
        rows, cols = (self.camera.height, self.camera.width)
        gy, gx = mgrid[0:rows, 0:cols].astype(float32)
        bg: object = zeros((rows, cols), dtype=float32)
        active: object = self._clutter_layers(kind)
        short_dim: object = min(rows, cols)
        if 'galactic' in active:
            bw: object = 0.12 * short_dim
            coord: object = (gx / max(cols, 1) + gy / max(rows, 1) - 1.0) * short_dim * 0.5
            bg += 55.0 * exp(-(coord * coord) / (2.0 * bw * bw))
        ell_specs: object = (('galaxy', 3.0, 1.0, 0.62, 0.38, ((40.0, 0.5),)), ('nebula', 0.8, 0.6, 0.35, 0.62, ((70.0, 1.0), (25.0, 0.35))), ('cloud', 5.5, 4.0, 0.78, 0.72, ((35.0, 0.45),)))
        for tag, deg_a, deg_b, u_rel, v_rel, terms in ell_specs:
            if tag in active:
                sa: object = 0.5 * self.camera.angular_diameter_px(deg_a)
                sb: object = 0.5 * self.camera.angular_diameter_px(deg_b)
                uc, vc = (u_rel * cols, v_rel * rows)
                for amp, decay in terms:
                    bg += amp * _elliptical_gaussian(gx, gy, uc, vc, sa, sb, decay)
        return bg
