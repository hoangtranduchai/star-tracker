"""Sub-pixel star centroid extraction via local background subtraction and intensity moments."""
from cv2 import BORDER_REPLICATE, CC_STAT_AREA, CC_STAT_HEIGHT, CC_STAT_LEFT, CC_STAT_TOP, CC_STAT_WIDTH, MORPH_CROSS, MORPH_OPEN, boxFilter, connectedComponentsWithStats, getStructuringElement, morphologyEx
from numpy import abs as npabs, any as npany, arctan2, asarray, empty, float32, float64, indices, maximum, median, ogrid, sqrt, std, uint8
_RING_RAD = 8
_YY_RING, _XX_RING = ogrid[-_RING_RAD:_RING_RAD + 1, -_RING_RAD:_RING_RAD + 1]
_R2_GRID = _YY_RING * _YY_RING + _XX_RING * _XX_RING
_ANNULUS_MASK = (_R2_GRID >= 16) & (_R2_GRID <= _RING_RAD * _RING_RAD)

class Centroids:
    """Detected sub-pixel star centroids, second moments, and unit camera vectors."""

    def __init__(self, uv: object, flux: object, area: object, peak: object, mu20: object, mu02: object, mu11: object, axis_ratio: object, angle_rad: object, vectors: object, sigma_px: object) -> object:
        self.uv, self.flux, self.area, self.peak, self.mu20, self.mu02, self.mu11, self.axis_ratio, self.angle_rad, self.vectors, self.sigma_px = (uv, flux, area, peak, mu20, mu02, mu11, axis_ratio, angle_rad, vectors, sigma_px)

def _empty_centroids() -> object:
    z1: object = empty(0, dtype=float64)
    return Centroids(empty((0, 2), dtype=float64), z1, z1, z1, z1, z1, z1, z1, z1, empty((0, 3), dtype=float64), z1)

def _moment_shape(sub_img: object, dx_rel: object, dy_rel: object, inv_flux: object) -> object:
    m20: object = float((sub_img * (dx_rel * dx_rel)).sum() * inv_flux)
    m02: object = float((sub_img * (dy_img := (dy_rel * dy_rel))).sum() * inv_flux)
    m11: object = float((sub_img * (dx_rel * dy_rel)).sum() * inv_flux)
    diff: object = m20 - m02
    disc: object = float(sqrt(max(0.0, diff * diff + 4.0 * m11 * m11)))
    trace_m: object = m20 + m02
    l_maj: object = 0.5 * (trace_m + disc)
    l_min: object = 0.5 * (trace_m - disc)
    ratio: object = float(sqrt(l_maj / max(l_min, 1e-08)))
    orient: object = 0.5 * float(arctan2(2.0 * m11, diff))
    return (m20, m02, m11, ratio, orient)

class CentroidDetector:
    """Classical connected-component center-of-gravity star detector."""

    def __init__(self, camera: object, k_sigma: object=4.0, bg_block: object=64, min_area: object=3, max_area: object=120, max_area_sat: object=2500, max_axis_ratio: object=3.0, saturation_dn: object=4000.0, edge_margin: object=4, binary_open: object=True, cog_pad: object=1, psf_sigma_px: object=1.2, abs_k_sigma: object=0.0, min_contrast_sigma: object=10.0, max_neighbor_hot: object=0.15) -> object:
        self.camera, self.k_sigma, self.bg_block, self.min_area, self.max_area, self.max_area_sat, self.max_axis_ratio, self.saturation_dn, self.edge_margin, self.binary_open, self.cog_pad, self.psf_sigma_px, self.abs_k_sigma, self.min_contrast_sigma, self.max_neighbor_hot = (camera, float(k_sigma), max(3, int(bg_block) | 1), int(min_area), int(max_area), max(int(max_area_sat), int(max_area)), float(max_axis_ratio), float(saturation_dn), int(edge_margin), bool(binary_open), int(cog_pad), float(psf_sigma_px), float(abs_k_sigma), float(min_contrast_sigma), float(max_neighbor_hot))

    def detect(self, image: object, mask: object=None) -> object:
        arr: object = asarray(image, dtype=float32)
        rows, cols = arr.shape
        win: object = self.bg_block
        smooth_bg: object = boxFilter(arr, ddepth=-1, ksize=(win, win), normalize=True, borderType=BORDER_REPLICATE)
        net: object = arr - smooth_bg
        flat_net: object = net.ravel()
        med_val: object = float(median(flat_net))
        mad_val: object = float(median(npabs(flat_net - med_val)))
        sig_bg: object = 1.4826 * mad_val if mad_val > 1e-06 else float(std(flat_net))
        gate_dn: object = self.k_sigma * max(sig_bg, 0.001)
        fg_mask: object = net > gate_dn
        if mask is not None:
            fg_mask: object = fg_mask & ~asarray(mask, dtype=bool)
        if self.abs_k_sigma > 0.0:
            unmasked: object = arr if mask is None else arr[~asarray(mask, dtype=bool)]
            pool: object = arr.ravel() if unmasked.size < 32 else unmasked
            abs_floor: object = float(pool.mean()) + self.abs_k_sigma * float(pool.std())
            fg_mask: object = fg_mask & (arr >= abs_floor)
        if self.binary_open:
            cross_se: object = getStructuringElement(MORPH_CROSS, (3, 3))
            fg_mask: object = morphologyEx(fg_mask.astype(uint8), MORPH_OPEN, cross_se).astype(bool)
        num_labels, lbl_img, cc_stats, _ = connectedComponentsWithStats(fg_mask.astype(uint8), connectivity=8)
        candidates: object = []
        pad_px: object = self.cog_pad
        margin: object = self.edge_margin
        for idx in range(1, int(num_labels)):
            pix_cnt: object = int(cc_stats[idx, CC_STAT_AREA])
            if pix_cnt < self.min_area:
                continue
            bx: object = int(cc_stats[idx, CC_STAT_LEFT])
            by: object = int(cc_stats[idx, CC_STAT_TOP])
            bw: object = int(cc_stats[idx, CC_STAT_WIDTH])
            bh: object = int(cc_stats[idx, CC_STAT_HEIGHT])
            raw_max: object = float(arr[by:by + bh, bx:bx + bw].max()) if bw > 0 and bh > 0 else 0.0
            if pix_cnt > self.max_area and (raw_max < self.saturation_dn or pix_cnt > self.max_area_sat):
                continue
            x_lo, y_lo = (max(0, bx - pad_px), max(0, by - pad_px))
            x_hi, y_hi = (min(cols, bx + bw + pad_px), min(rows, by + bh + pad_px))
            in_cc: object = lbl_img[y_lo:y_hi, x_lo:x_hi] == idx
            weights: object = maximum(net[y_lo:y_hi, x_lo:x_hi], 0.0) * in_cc
            tot_flux: object = float(weights.sum())
            if not tot_flux > 0.0:
                continue
            inv_f: object = 1.0 / tot_flux
            gy, gx = indices(weights.shape)
            u_rel: object = float((weights * gx).sum() * inv_f)
            v_rel: object = float((weights * gy).sum() * inv_f)
            u_c, v_c = (x_lo + u_rel, y_lo + v_rel)
            if not (margin <= u_c < cols - margin and margin <= v_c < rows - margin):
                continue
            pk_val: object = float(arr[y_lo:y_hi, x_lo:x_hi][in_cc].max()) if npany(in_cc) else 0.0
            m20, m02, m11, aspect, theta = _moment_shape(weights, gx - u_rel, gy - v_rel, inv_f)
            if aspect > self.max_axis_ratio:
                continue
            if not self._is_isolated_peak(arr, net, u_c, v_c, sig_bg, gate_dn, pix_cnt):
                continue
            snr_est: object = tot_flux / max(sig_bg * float(sqrt(pix_cnt)), 0.001)
            pos_std: object = self.psf_sigma_px / max(float(sqrt(snr_est)), 1.0)
            candidates.append((u_c, v_c, tot_flux, pix_cnt, pk_val, m20, m02, m11, aspect, theta, pos_std))
        if not candidates:
            return _empty_centroids()
        candidates.sort(key=lambda item: -item[2])
        mat: object = asarray(candidates, dtype=float64)
        uv_coords: object = mat[:, :2]
        cam_dirs: object = self.camera.unproject(uv_coords)
        c_flux, c_area, c_peak, c_m20, c_m02, c_m11, c_ax, c_ang, c_sig = mat[:, 2:].T
        return Centroids(uv=uv_coords, flux=c_flux, area=c_area, peak=c_peak, mu20=c_m20, mu02=c_m02, mu11=c_m11, axis_ratio=c_ax, angle_rad=c_ang, vectors=cam_dirs, sigma_px=c_sig)

    def _is_isolated_peak(self, img: object, resid: object, u: object, v: object, sigma: object, thresh: object, area: object) -> object:
        """Reject extended ridge clutter by verifying contrast against a surrounding 4-8 px annulus."""
        r_px: object = _RING_RAD
        row_c, col_c = (int(round(v)), int(round(u)))
        h_px, w_px = img.shape
        if not (r_px <= row_c < h_px - r_px and r_px <= col_c < w_px - r_px):
            return False
        raw_win: object = img[row_c - r_px:row_c + r_px + 1, col_c - r_px:col_c + r_px + 1]
        ring_diff: object = float(img[row_c, col_c] - median(raw_win[_ANNULUS_MASK]))
        req_diff: object = self.min_contrast_sigma * max(float(sigma), 0.001)
        if ring_diff < req_diff:
            return False
        if int(area) > 20 and ring_diff >= 4.0 * req_diff:
            return True
        res_win: object = resid[row_c - r_px:row_c + r_px + 1, col_c - r_px:col_c + r_px + 1]
        active_frac: object = float((res_win[_ANNULUS_MASK] > thresh).mean())
        return active_frac <= self.max_neighbor_hot
