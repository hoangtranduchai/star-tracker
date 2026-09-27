"""Matplotlib verification plots and viewport PNG renderers for star tracker results."""
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import matplotlib
matplotlib.use('Agg')
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
    ax.set_facecolor('#000000')
    ax.imshow(_asinh_stretch(image), cmap='gray', origin='upper')
    if result is None:
        return
    if result.glare_mask is not None and result.glare_mask.any():
        rgba_mask: object = zeros((*result.glare_mask.shape, 4))
        rgba_mask[result.glare_mask] = (0.9, 0.2, 0.2, 0.25)
        ax.imshow(rgba_mask, origin='upper')
    cents: object = result.centroids
    if cents is None or not len(cents.uv):
        return
    uv_pts: object = cents.uv
    u_all, v_all = (uv_pts[:, 0], uv_pts[:, 1])
    ax.scatter(u_all, v_all, s=40, facecolors='none', edgecolors='#38BDF8', linewidths=1.1, label=f'Detected ({len(uv_pts)})')
    id_res: object = result.ident
    identified_set: object = set()
    if id_res is not None and len(id_res.obs_idx):
        uv_id: object = uv_pts[id_res.obs_idx]
        ax.scatter(uv_id[:, 0], uv_id[:, 1], s=70, facecolors='none', edgecolors='#4ADE80', linewidths=1.6, label=f'Identified ({len(uv_id)})')
        for obs_i, cat_i in zip(id_res.obs_idx, id_res.cat_idx):
            c_idx: object = int(cat_i)
            lbl: object = compact_tag(catalog, c_idx, lookup=lookup) if catalog is not None and 0 <= c_idx < catalog.num_stars else f'idx {c_idx}'
            uo, vo = uv_pts[int(obs_i)]
            ax.text(uo + 4, vo + 4, lbl, color='#BBF7D0', fontsize=7)
            identified_set.add(int(obs_i))
    for det_i, (u_p, v_p) in enumerate(uv_pts):
        if det_i not in identified_set:
            ax.text(u_p + 4, v_p + 4, 'chưa ID', color='#7DD3FC', fontsize=7)
    if cents.axis_ratio is not None:
        for det_i, (u_p, v_p) in enumerate(uv_pts[:20]):
            if cents.axis_ratio[det_i] > 1.4:
                theta: object = cents.angle_rad[det_i]
                ax.annotate('', xy=(u_p + 8.0 * float(cos(theta)), v_p + 8.0 * float(sin(theta))), xytext=(u_p, v_p), arrowprops=dict(arrowstyle='->', color='#FBBF24', lw=0.8))

def _save_viewport_png(path: object, image: object, result: object=None, catalog: object=None, lookup: object=False) -> object:
    import matplotlib.pyplot as plt
    dest: object = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    vis_img, vis_res = _decimate_for_png(image, result)
    h_vis, w_vis = vis_img.shape[:2]
    fig, ax = plt.subplots(figsize=(9.2, 5.4), facecolor='#02050b')
    _draw_starfield(ax, vis_img, vis_res, catalog, lookup)
    if vis_res is not None:
        ax.axhline(h_vis * 0.5, color='#38BDF8', lw=0.4, alpha=0.35)
        ax.axvline(w_vis * 0.5, color='#38BDF8', lw=0.4, alpha=0.35)
        if result.centroids is not None and len(result.centroids.uv):
            ax.legend(loc='upper right', facecolor='#0a1322', edgecolor='#334155', labelcolor='white', fontsize=8, framealpha=0.9)
    ax.tick_params(colors='#64748b', labelsize=8)
    ax.set_xlim(0, w_vis)
    ax.set_ylim(h_vis, 0)
    fig.subplots_adjust(left=0.06, right=0.995, top=0.995, bottom=0.06)
    fig.savefig(dest, dpi=130, facecolor=fig.get_facecolor())
    plt.close(fig)
    return dest

def save_input_png(image: object, path: object, stats: object=None) -> object:
    return _save_viewport_png(path, image)

def save_output_png(image: object, result: object, path: object, catalog: object=None, lookup: object=False, stats: object=None) -> object:
    return _save_viewport_png(path, image, result=result, catalog=catalog, lookup=lookup)

def _format_summary_card(camera_label: object, result: object, metrics: object, catalog: object, lookup: object) -> object:
    timings: object = result.timing_ms
    att_err: object = metrics.get('attitude_error_arcsec')
    err_txt: object = f'{att_err:.3f}' if att_err is not None else 'n/a'
    ra_e, dec_e = (metrics.get('boresight_est_ra_deg'), metrics.get('boresight_est_dec_deg'))
    ra_g, dec_g = (metrics.get('boresight_gt_ra_deg'), metrics.get('boresight_gt_dec_deg'))
    if ra_e is not None and dec_e is not None:
        gt_row: object = f'  * GT RA / Dec    : {ra_g:.4f} / {dec_g:+.4f} deg\n' if ra_g is not None and dec_g is not None else '  * GT RA / Dec    : (no sidecar)\n'
        pointing_block: object = f"  * Boresight RA   : {ra_e:.4f} deg  ({metrics.get('boresight_est_ra_hms')})\n  * Boresight Dec  : {dec_e:+.4f} deg ({metrics.get('boresight_est_dec_dms')})\n{gt_row}  * Note          : camera +Z on J2000 sky, not lat/lon, not constellation\n"
    else:
        pointing_block: object = '  * Boresight      : n/a (solve failed)\n'
    star_block: object = ''
    if lookup and catalog is not None and (result.ident is not None) and len(result.ident.cat_idx):
        cat_indices: object = result.ident.cat_idx
        tags: object = [compact_tag(catalog, int(c), lookup=True) for c in cat_indices[:18]]
        tail: object = '' if len(cat_indices) <= 18 else '  ...\n'
        star_block: object = '\nSTARS (IAU / Yale HR):\n  ' + '\n  '.join(tags) + '\n' + tail
    lines: object = ['STAR TRACKER DEMO', '-' * 50, str(camera_label), 'Algorithm  : CoG + Pyramid + Wahba (no ML)\n', 'TIMINGS:', f"  * Centroiding    : {timings.get('centroiding_ms', 0):.2f} ms", f"  * Star ID        : {timings.get('identification_ms', 0):.2f} ms", f"  * Wahba          : {timings.get('attitude_ms', 0):.2f} ms", f"  * Total          : {timings.get('total_pipeline_ms', 0):.2f} ms\n", 'SKY POINTING (from quaternion):', pointing_block, 'METRICS:', f"  * Stars in FOV   : {metrics.get('n_truth')}", f"  * Detected       : {metrics.get('n_detected')}", f"  * Matched        : {metrics.get('n_matched')}", f"  * Centroid RMS   : {metrics.get('centroid_rms_px')}", f'  * Attitude error : {err_txt} arcsec', f"  * Limit          : < {metrics.get('limit_arcsec')} arcsec", f"  * Verdict        : {metrics.get('verdict')}"]
    return '\n'.join(lines) + '\n' + star_block

def plot_frame(image: object, result: object, truth: object, metrics: object, camera_label: object, out_path: object, show: object=True, catalog: object=None, lookup: object=False) -> object:
    import matplotlib.pyplot as plt
    dest: object = Path(out_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    vis_img, vis_res = _decimate_for_png(image, result)
    h_vis, w_vis = vis_img.shape[:2]
    fig, (ax_sky, ax_card) = plt.subplots(1, 2, figsize=(14, 7.2), facecolor='#0F172A')
    _draw_starfield(ax_sky, vis_img, vis_res, catalog, lookup)
    ax_sky.axhline(h_vis * 0.5, color='#38BDF8', lw=0.4, alpha=0.35)
    ax_sky.axvline(w_vis * 0.5, color='#38BDF8', lw=0.4, alpha=0.35)
    ra_lbl: object = metrics.get('boresight_est_ra_hms') or metrics.get('boresight_gt_ra_hms') or 'n/a'
    dec_lbl: object = metrics.get('boresight_est_dec_dms') or metrics.get('boresight_gt_dec_dms') or 'n/a'
    ax_sky.set_title(f'Starfield {image.shape[1]}x{image.shape[0]}   boresight  RA {ra_lbl}   Dec {dec_lbl}', color='white', fontsize=11, pad=10)
    ax_sky.legend(loc='upper right', facecolor='#1E293B', edgecolor='#475569', labelcolor='white', fontsize=8)
    ax_sky.tick_params(colors='#94A3B8')
    ax_card.set_facecolor('#1E293B')
    ax_card.axis('off')
    card_text: object = _format_summary_card(camera_label, result, metrics, catalog, lookup)
    ax_card.text(0.08, 0.92, card_text, transform=ax_card.transAxes, color='#F8FAFC', fontsize=10, fontfamily='monospace', verticalalignment='top', bbox=dict(boxstyle='round,pad=0.8', facecolor='#0F172A', edgecolor='#38BDF8', alpha=0.9))
    plt.tight_layout()
    fig.savefig(dest, dpi=150, facecolor=fig.get_facecolor())
    if show:
        plt.show()
    else:
        plt.close(fig)
    return dest
