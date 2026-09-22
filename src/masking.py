"""Glare and Earth-limb detector masking via connected components and block-median elevation."""
from cv2 import CC_STAT_AREA, CC_STAT_HEIGHT, CC_STAT_WIDTH, MORPH_ELLIPSE, connectedComponentsWithStats, dilate, getStructuringElement
from numpy import abs as npabs, asarray, float32, median, pad, repeat, std, uint8, zeros

def _is_glare_blob(area_val: object, span_w: object, span_h: object, min_area: object, min_span: object) -> object:
    if not area_val > min_area:
        return False
    short_side, long_side = (span_w, span_h) if span_w <= span_h else (span_h, span_w)
    is_disk: object = short_side >= 28 and area_val >= 350
    return long_side >= min_span or is_disk

class GlareMasker:
    """Identifies extended bright regions (Earth limb, Sun, Moon) while sparing point-source stars."""

    def __init__(self, bright_frac: object=0.5, min_area_px: object=30, dilate_px: object=25, bg_excess_k: object=3.0, full_scale: object=4095.0, bg_block: object=64, min_span_px: object=48) -> object:
        self.bright_frac, self.min_area_px, self.dilate_px, self.bg_excess_k, self.full_scale, self.bg_block, self.min_span_px = (float(bright_frac), int(min_area_px), int(dilate_px), float(bg_excess_k), float(full_scale), int(bg_block), int(min_span_px))

    def make_mask(self, image: object) -> object:
        arr: object = asarray(image, dtype=float32)
        rows, cols = arr.shape
        mask_out: object = zeros((rows, cols), dtype=bool)
        dyn_ceil: object = max(self.full_scale, float(arr.max()) if arr.size else 0.0)
        binary_hi: object = (arr >= self.bright_frac * dyn_ceil).astype(uint8)
        num_cc, cc_map, cc_stats, _ = connectedComponentsWithStats(binary_hi, connectivity=8)
        valid_labels: object = [lbl for lbl in range(1, int(num_cc)) if _is_glare_blob(int(cc_stats[lbl, CC_STAT_AREA]), int(cc_stats[lbl, CC_STAT_WIDTH]), int(cc_stats[lbl, CC_STAT_HEIGHT]), self.min_area_px, self.min_span_px)]
        if valid_labels:
            blob_img: object = zeros((rows, cols), dtype=uint8)
            for lbl in valid_labels:
                blob_img[cc_map == lbl] = 1
            if self.dilate_px > 0:
                diam: object = 2 * int(self.dilate_px) + 1
                se: object = getStructuringElement(MORPH_ELLIPSE, (diam, diam))
                blob_img: object = dilate(blob_img, se)
            mask_out |= blob_img.astype(bool)
        b_sz: object = self.bg_block
        med_global: object = float(median(arr))
        mad_global: object = float(median(npabs(arr - med_global)))
        noise_est: object = 1.4826 * mad_global if mad_global > 1e-06 else float(std(arr))
        cutoff: object = med_global + self.bg_excess_k * noise_est
        grid_r, grid_c = ((rows + b_sz - 1) // b_sz, (cols + b_sz - 1) // b_sz)
        pad_r, pad_c = (grid_r * b_sz - rows, grid_c * b_sz - cols)
        ext_img: object = pad(arr, ((0, pad_r), (0, pad_c)), mode='edge')
        tiles: object = ext_img.reshape(grid_r, b_sz, grid_c, b_sz).swapaxes(1, 2)
        hot_tiles: object = median(tiles, axis=(-2, -1)) > cutoff
        upsampled: object = repeat(repeat(hot_tiles, b_sz, axis=0), b_sz, axis=1)
        mask_out |= upsampled[:rows, :cols]
        return mask_out
