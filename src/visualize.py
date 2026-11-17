"""Matplotlib verification plots and viewport PNG renderers for star tracker results."""
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import matplotlib
matplotlib.use('Agg')
import cv2
from cv2 import INTER_AREA, INTER_NEAREST, resize as cv_resize
from numpy import arcsinh, ascontiguousarray, asarray, clip, cos, float64, median, percentile, sin, uint8, zeros
from .starnames import compact_tag
PNG_MAX_SIDE = 1600

def _decimate_for_png(image: object, result: object=None, max_side: object=PNG_MAX_SIDE) -> object:
    raw: object = asarray(image)
    h_orig, w_orig = raw.shape[:2]
    longest: object = max(h_orig, w_orig)
    if longest <= int(max_side):
        scaled_img: object = ascontiguousarray(raw)
    else:
        ratio: object = float(max_side) / float(longest)
        new_w, new_h = (max(1, int(round(w_orig * ratio))), max(1, int(round(h_orig * ratio))))
        scaled_img: object = cv_resize(raw, (new_w, new_h), interpolation=INTER_AREA)
    if result is None:
        return (scaled_img, None)
    h_vis, w_vis = scaled_img.shape[:2]
    scale_xy: object = asarray([w_vis / float(w_orig), h_vis / float(h_orig)], dtype=float64)
    g_mask: object = cv_resize(result.glare_mask.astype(uint8), (w_vis, h_vis), interpolation=INTER_NEAREST).astype(bool) if result.glare_mask is not None else None
    c_obj: object = result.centroids
    if c_obj is not None and c_obj.uv is not None and len(c_obj.uv):
        c_obj: object = SimpleNamespace(uv=asarray(c_obj.uv, dtype=float64) * scale_xy, axis_ratio=c_obj.axis_ratio, angle_rad=c_obj.angle_rad)
    return (scaled_img, SimpleNamespace(glare_mask=g_mask, centroids=c_obj, ident=result.ident))

def _asinh_stretch(img: object) -> object:
    shifted: object = clip(asarray(img, dtype=float64) - float(median(img)), 0.0, None)
    nz: object = shifted[shifted > 0.0]
    soft_val: object = float(percentile(nz, 50)) if nz.size else 1.0
    mapped: object = arcsinh(shifted / (soft_val + 1e-06))
    return mapped / (float(mapped.max()) + 1e-09)

def image_stats(image: object) -> object:
    arr: object = asarray(image)
    h_px, w_px = arr.shape[:2]
    digest_12: object = sha256(ascontiguousarray(arr).tobytes()).hexdigest()[:12]
    return dict(width=int(w_px), height=int(h_px), dtype=str(arr.dtype), dn_min=int(arr.min()), dn_max=int(arr.max()), dn_mean=float(arr.mean()), n_pixels=int(arr.size), sha256_12=digest_12)

def _draw_starfield(ax: object, image: object, result: object, catalog: object, lookup: object) -> object:
    ax.set_facecolor('#05070B')
    ax.imshow(_asinh_stretch(image), cmap='gray', origin='upper')
    if result is None:
        return
    if result.glare_mask is not None and result.glare_mask.any():
        rgba_mask: object = zeros((*result.glare_mask.shape, 4))
        rgba_mask[result.glare_mask] = (248.0 / 255.0, 113.0 / 255.0, 113.0 / 255.0, 0.18)
        ax.imshow(rgba_mask, origin='upper')
    cents: object = result.centroids
    if cents is None or not len(cents.uv):
        return
    uv_pts: object = cents.uv
    u_all, v_all = (uv_pts[:, 0], uv_pts[:, 1])
    ax.scatter(u_all, v_all, s=36, facecolors='none', edgecolors='#7DD3FC', linewidths=1.0, label=f'Tâm sao phát hiện ({len(uv_pts)})')
    id_res: object = result.ident
    if id_res is not None and len(id_res.obs_idx):
        uv_id: object = uv_pts[id_res.obs_idx]
        ax.scatter(uv_id[:, 0], uv_id[:, 1], s=68, facecolors='none', edgecolors='#34D399', linewidths=1.4, label=f'Sao khớp danh mục ({len(uv_id)})')
        for obs_i, cat_i in zip(id_res.obs_idx, id_res.cat_idx):
            c_idx: object = int(cat_i)
            lbl: object = compact_tag(catalog, c_idx, lookup=lookup) if catalog is not None and 0 <= c_idx < catalog.num_stars else f'idx {c_idx}'
            uo, vo = uv_pts[int(obs_i)]
            ax.text(uo + 4.5, vo + 4.5, lbl, color='#E2E8F0', fontsize=7.5)
    if cents.axis_ratio is not None:
        for det_i, (u_p, v_p) in enumerate(uv_pts[:20]):
            if cents.axis_ratio[det_i] > 1.4:
                theta: object = cents.angle_rad[det_i]
                ax.annotate('', xy=(u_p + 8.0 * float(cos(theta)), v_p + 8.0 * float(sin(theta))), xytext=(u_p, v_p), arrowprops=dict(arrowstyle='->', color='#FCD34D', lw=0.75))

def _save_viewport_png(path: object, image: object, result: object=None, catalog: object=None, lookup: object=False) -> object:
    import matplotlib.pyplot as plt
    dest: object = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    vis_img, vis_res = _decimate_for_png(image, result)
    h_vis, w_vis = vis_img.shape[:2]
    fig, ax = plt.subplots(figsize=(9.2, 5.4), facecolor='#05070B')
    _draw_starfield(ax, vis_img, vis_res, catalog, lookup)
    for sp in ax.spines.values():
        sp.set_color('#1E293B')
        sp.set_linewidth(0.6)
    if vis_res is not None:
        ax.axhline(h_vis * 0.5, color='#7DD3FC', lw=0.4, alpha=0.22)
        ax.axvline(w_vis * 0.5, color='#7DD3FC', lw=0.4, alpha=0.22)
        if result.centroids is not None and len(result.centroids.uv):
            ax.legend(loc='upper right', facecolor='#0B0F17', edgecolor='#1E293B', labelcolor='#E2E8F0', fontsize=8, framealpha=0.88)
    ax.tick_params(colors='#64748B', labelsize=7.5)
    ax.set_xlim(0, w_vis)
    ax.set_ylim(h_vis, 0)
    fig.subplots_adjust(left=0.06, right=0.995, top=0.995, bottom=0.06)
    fig.savefig(dest, dpi=130, facecolor=fig.get_facecolor())
    plt.close(fig)
    return dest

def save_clean_png(image: object, path: object, max_side: object=PNG_MAX_SIDE) -> object:
    """Write a pure borderless 8-bit starfield PNG at exact sensor aspect ratio."""
    dest: object = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    vis_img, _ = _decimate_for_png(image, None, max_side=max_side)
    stretched: object = clip(asarray(_asinh_stretch(vis_img), dtype=float64), 0.0, 1.0)
    black_floor: object = min(0.22, float(percentile(stretched, 92)) * 1.15)
    lifted: object = clip((stretched - black_floor) / max(1.0 - black_floor, 1e-06), 0.0, 1.0)
    polished: object = clip(lifted ** 1.3, 0.0, 1.0)
    u8_img: object = ascontiguousarray((polished * 255.0).round().astype(uint8))
    if not cv2.imwrite(str(dest), u8_img):
        raise OSError(f'Failed to write clean PNG: {dest}')
    return dest

def save_input_png(image: object, path: object, stats: object=None) -> object:
    return _save_viewport_png(path, image)

def save_output_png(image: object, result: object, path: object, catalog: object=None, lookup: object=False, stats: object=None) -> object:
    return _save_viewport_png(path, image, result=result, catalog=catalog, lookup=lookup)

def _format_summary_card(camera_label: object, result: object, metrics: object, catalog: object, lookup: object) -> object:
    timings: object = result.timing_ms
    att_err: object = metrics.get('attitude_error_arcsec')
    err_txt: object = f'{att_err:.3f}' if att_err is not None else 'n/a'
    status_lbl: object = str(metrics.get('status') or getattr(result, 'status', None) or ('SOLVED' if result.success else 'LOST'))
    ra_e, dec_e = (metrics.get('boresight_est_ra_deg'), metrics.get('boresight_est_dec_deg'))
    ra_g, dec_g = (metrics.get('boresight_gt_ra_deg'), metrics.get('boresight_gt_dec_deg'))
    if ra_e is not None and dec_e is not None:
        gt_row: object = f'  * GT RA / Dec    : {ra_g:.4f} / {dec_g:+.4f} deg\n' if ra_g is not None and dec_g is not None else '  * GT RA / Dec    : (không có nhãn chuẩn)\n'
        pointing_block: object = f"  * Boresight RA   : {ra_e:.4f} deg  ({metrics.get('boresight_est_ra_hms')})\n  * Boresight Dec  : {dec_e:+.4f} deg ({metrics.get('boresight_est_dec_dms')})\n{gt_row}  * Hệ tọa độ      : J2000 (trục quang học +Z)\n"
    else:
        pointing_block: object = f'  * Boresight      : n/a ({status_lbl})\n'
    star_block: object = ''
    if lookup and catalog is not None and (result.ident is not None) and len(result.ident.cat_idx):
        cat_indices: object = result.ident.cat_idx
        tags: object = [compact_tag(catalog, int(c), lookup=True) for c in cat_indices[:18]]
        tail: object = '' if len(cat_indices) <= 18 else '  ...\n'
        star_block: object = '\nSAO KHỚP DANH MỤC (IAU / Yale HR):\n  ' + '\n  '.join(tags) + '\n' + tail
    lines: object = ['BẢN TỔNG HỢP ĐỊNH HƯỚNG SAO', '-' * 50, str(camera_label), f'Trạng thái : {status_lbl}\n', 'THỜI GIAN XỬ LÝ:', f"  * Tâm sao        : {timings.get('centroiding_ms', 0):.2f} ms", f"  * Nhận diện sao  : {timings.get('identification_ms', 0):.2f} ms", f"  * Giải Wahba     : {timings.get('attitude_ms', 0):.2f} ms", f"  * Tổng cộng      : {timings.get('total_pipeline_ms', 0):.2f} ms\n", 'HƯỚNG NGẮM THIÊN CẦU:', pointing_block, 'CHỈ SỐ KIỂM ĐỊNH:', f"  * Sao trong FOV  : {metrics.get('n_truth')}", f"  * Phát hiện      : {metrics.get('n_detected')}", f"  * Khớp danh mục  : {metrics.get('n_matched')}", f"  * Lệch tâm RMS   : {metrics.get('centroid_rms_px')}", f'  * Sai số tư thế  : {err_txt} arcsec', f"  * Ngưỡng đạt     : < {metrics.get('limit_arcsec')} arcsec", f"  * Kết luận       : {metrics.get('verdict')}"]
    return '\n'.join(lines) + '\n' + star_block

def plot_frame(image: object, result: object, truth: object, metrics: object, camera_label: object, out_path: object, show: object=True, catalog: object=None, lookup: object=False) -> object:
    import matplotlib.pyplot as plt
    dest: object = Path(out_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    vis_img, vis_res = _decimate_for_png(image, result)
    h_vis, w_vis = vis_img.shape[:2]
    fig, (ax_sky, ax_card) = plt.subplots(1, 2, figsize=(14, 7.2), facecolor='#05070B')
    _draw_starfield(ax_sky, vis_img, vis_res, catalog, lookup)
    for sp in ax_sky.spines.values():
        sp.set_color('#1E293B')
        sp.set_linewidth(0.6)
    ax_sky.axhline(h_vis * 0.5, color='#7DD3FC', lw=0.4, alpha=0.22)
    ax_sky.axvline(w_vis * 0.5, color='#7DD3FC', lw=0.4, alpha=0.22)
    ra_lbl: object = metrics.get('boresight_est_ra_hms') or metrics.get('boresight_gt_ra_hms') or 'n/a'
    dec_lbl: object = metrics.get('boresight_est_dec_dms') or metrics.get('boresight_gt_dec_dms') or 'n/a'
    ax_sky.set_title(f'Khung ảnh {image.shape[1]}×{image.shape[0]}  ·  RA {ra_lbl}   Dec {dec_lbl}', color='#F8FAFC', fontsize=10.5, pad=10)
    if result is not None and result.centroids is not None and len(result.centroids.uv):
        ax_sky.legend(loc='upper right', facecolor='#0B0F17', edgecolor='#1E293B', labelcolor='#E2E8F0', fontsize=8, framealpha=0.88)
    ax_sky.tick_params(colors='#64748B', labelsize=8)
    ax_card.set_facecolor('#05070B')
    ax_card.axis('off')
    card_text: object = _format_summary_card(camera_label, result, metrics, catalog, lookup)
    ax_card.text(0.06, 0.94, card_text, transform=ax_card.transAxes, color='#E2E8F0', fontsize=9.5, fontfamily=['Consolas', 'Courier New', 'DejaVu Sans'], verticalalignment='top', bbox=dict(boxstyle='round,pad=0.85', facecolor='#0B0F17', edgecolor='#1E293B', linewidth=0.9, alpha=0.96))
    plt.tight_layout()
    fig.savefig(dest, dpi=150, facecolor=fig.get_facecolor())
    if show:
        plt.show()
    else:
        plt.close(fig)
    return dest
