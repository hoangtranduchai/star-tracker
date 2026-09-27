"""Matplotlib verification figure for the laptop demo."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import matplotlib

matplotlib.use("Agg")

import cv2
import numpy as np

from .catalog import StarCatalog
from .pipeline import TrackerResult
from .simulator import RenderTruth
from .starnames import compact_tag

# Viewport PNG is ~9×5" at 130 dpi. Feeding a full-resolution frame into imshow hangs Agg for minutes.
PNG_MAX_SIDE = 1600


def _decimate_for_png(image: np.ndarray, result=None, max_side: int = PNG_MAX_SIDE):
    arr = np.asarray(image)
    h, w = arr.shape[:2]
    if max(h, w) <= max_side:
        vis = np.ascontiguousarray(arr)
    else:
        scale = max_side / float(max(h, w))
        nw = max(1, int(round(w * scale)))
        nh = max(1, int(round(h * scale)))
        vis = cv2.resize(arr, (nw, nh), interpolation=cv2.INTER_AREA)
    if result is None:
        return vis, None
    sx = vis.shape[1] / float(w)
    sy = vis.shape[0] / float(h)
    glare = None
    if result.glare_mask is not None:
        glare = cv2.resize(
            result.glare_mask.astype(np.uint8),
            (vis.shape[1], vis.shape[0]),
            interpolation=cv2.INTER_NEAREST,
        ).astype(bool)
    cents = result.centroids
    if cents is not None and cents.uv is not None and len(cents.uv):
        uv = np.asarray(cents.uv, dtype=np.float64) * np.array([sx, sy], dtype=np.float64)
        cents = SimpleNamespace(uv=uv, axis_ratio=cents.axis_ratio, angle_rad=cents.angle_rad)
    return vis, SimpleNamespace(glare_mask=glare, centroids=cents, ident=result.ident)


def _asinh_stretch(img: np.ndarray) -> np.ndarray:
    x = img.astype(np.float64)
    x = x - np.median(x)
    x = np.clip(x, 0, None)
    pos = x[x > 0]
    mid = float(np.percentile(pos, 50)) if pos.size else 1.0
    y = np.arcsinh(x / (mid + 1e-6))
    y = y / (y.max() + 1e-9)
    return y


def image_stats(image: np.ndarray) -> dict:
    arr = np.asarray(image)
    return {
        "width": int(arr.shape[1]),
        "height": int(arr.shape[0]),
        "dtype": str(arr.dtype),
        "dn_min": int(arr.min()),
        "dn_max": int(arr.max()),
        "dn_mean": float(arr.mean()),
        "n_pixels": int(arr.size),
        "sha256_12": __import__("hashlib").sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()[:12],
    }


def _draw_starfield(ax, image: np.ndarray, result: TrackerResult | None, catalog, lookup: bool) -> None:
    ax.set_facecolor("#000000")
    ax.imshow(_asinh_stretch(image), cmap="gray", origin="upper")
    if result is None:
        return
    if result.glare_mask is not None and result.glare_mask.any():
        overlay = np.zeros((*result.glare_mask.shape, 4))
        overlay[result.glare_mask] = (0.9, 0.2, 0.2, 0.25)
        ax.imshow(overlay, origin="upper")
    if result.centroids is None or not len(result.centroids.uv):
        return
    uv = result.centroids.uv
    ax.scatter(
        uv[:, 0], uv[:, 1], s=40, facecolors="none", edgecolors="#38BDF8", linewidths=1.1,
        label=f"Detected ({len(uv)})",
    )
    if result.ident is not None and len(result.ident.obs_idx):
        matched = uv[result.ident.obs_idx]
        ax.scatter(
            matched[:, 0], matched[:, 1], s=70, facecolors="none", edgecolors="#4ADE80",
            linewidths=1.6, label=f"Identified ({len(matched)})",
        )
        for o, c in zip(result.ident.obs_idx, result.ident.cat_idx):
            idx = int(c)
            if catalog is not None and 0 <= idx < catalog.num_stars:
                tag = compact_tag(catalog, idx, lookup=lookup)
            else:
                tag = f"idx {idx}"
            ax.text(uv[o, 0] + 4, uv[o, 1] + 4, tag, color="#BBF7D0", fontsize=7)
        matched_idx = set(int(i) for i in result.ident.obs_idx)
    else:
        matched_idx = set()
    for i, (u, v) in enumerate(uv):
        if i in matched_idx:
            continue
        ax.text(u + 4, v + 4, "chưa ID", color="#7DD3FC", fontsize=7)
    if result.centroids.axis_ratio is not None:
        for i, (u, v) in enumerate(uv[:20]):
            if result.centroids.axis_ratio[i] > 1.4:
                ang = result.centroids.angle_rad[i]
                L = 8.0
                ax.annotate(
                    "",
                    xy=(u + L * np.cos(ang), v + L * np.sin(ang)),
                    xytext=(u, v),
                    arrowprops=dict(arrowstyle="->", color="#FBBF24", lw=0.8),
                )


def _save_viewport_png(path: Path, image: np.ndarray, result=None, catalog=None, lookup: bool = False) -> Path:
    """Starfield only — captions live in the HTML frame bar, not on the pixels."""
    import matplotlib.pyplot as plt

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    vis, vis_result = _decimate_for_png(image, result)
    fig, ax = plt.subplots(figsize=(9.2, 5.4), facecolor="#02050b")
    _draw_starfield(ax, vis, vis_result, catalog, lookup)
    if vis_result is not None:
        ax.axhline(vis.shape[0] * 0.5, color="#38BDF8", lw=0.4, alpha=0.35)
        ax.axvline(vis.shape[1] * 0.5, color="#38BDF8", lw=0.4, alpha=0.35)
        if result.centroids is not None and len(result.centroids.uv):
            ax.legend(
                loc="upper right",
                facecolor="#0a1322",
                edgecolor="#334155",
                labelcolor="white",
                fontsize=8,
                framealpha=0.9,
            )
    ax.tick_params(colors="#64748b", labelsize=8)
    ax.set_xlim(0, vis.shape[1])
    ax.set_ylim(vis.shape[0], 0)
    fig.subplots_adjust(left=0.06, right=0.995, top=0.995, bottom=0.06)
    fig.savefig(path, dpi=130, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def save_input_png(image: np.ndarray, path: Path, stats: dict | None = None) -> Path:
    return _save_viewport_png(path, image)


def save_output_png(
    image: np.ndarray,
    result: TrackerResult,
    path: Path,
    catalog: StarCatalog | None = None,
    lookup: bool = False,
    stats: dict | None = None,
) -> Path:
    return _save_viewport_png(path, image, result=result, catalog=catalog, lookup=lookup)


def plot_frame(
    image: np.ndarray,
    result: TrackerResult,
    truth: RenderTruth,
    metrics: dict,
    camera_label: str,
    out_path: Path,
    show: bool = True,
    catalog: StarCatalog | None = None,
    lookup: bool = False,
) -> Path:
    import matplotlib.pyplot as plt

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    vis, vis_result = _decimate_for_png(image, result)
    fig, axes = plt.subplots(1, 2, figsize=(14, 7.2), facecolor="#0F172A")
    ax1, ax2 = axes
    _draw_starfield(ax1, vis, vis_result, catalog, lookup)
    ax1.axhline(vis.shape[0] * 0.5, color="#38BDF8", lw=0.4, alpha=0.35)
    ax1.axvline(vis.shape[1] * 0.5, color="#38BDF8", lw=0.4, alpha=0.35)
    ra_s = metrics.get("boresight_est_ra_hms") or metrics.get("boresight_gt_ra_hms") or "n/a"
    dec_s = metrics.get("boresight_est_dec_dms") or metrics.get("boresight_gt_dec_dms") or "n/a"
    ax1.set_title(
        f"Starfield {image.shape[1]}x{image.shape[0]}   boresight  RA {ra_s}   Dec {dec_s}",
        color="white",
        fontsize=11,
        pad=10,
    )
    ax1.legend(loc="upper right", facecolor="#1E293B", edgecolor="#475569", labelcolor="white", fontsize=8)
    ax1.tick_params(colors="#94A3B8")

    ax2.set_facecolor("#1E293B")
    ax2.axis("off")
    t = result.timing_ms
    err = metrics.get("attitude_error_arcsec")
    err_s = f"{err:.3f}" if err is not None else "n/a"
    ra_est = metrics.get("boresight_est_ra_deg")
    dec_est = metrics.get("boresight_est_dec_deg")
    gt_ra = metrics.get("boresight_gt_ra_deg")
    gt_dec = metrics.get("boresight_gt_dec_deg")
    if ra_est is not None and dec_est is not None:
        if gt_ra is not None and gt_dec is not None:
            gt_line = f"  * GT RA / Dec    : {gt_ra:.4f} / {gt_dec:+.4f} deg\n"
        else:
            gt_line = "  * GT RA / Dec    : (no sidecar)\n"
        pointing = (
            f"  * Boresight RA   : {ra_est:.4f} deg  ({metrics.get('boresight_est_ra_hms')})\n"
            f"  * Boresight Dec  : {dec_est:+.4f} deg ({metrics.get('boresight_est_dec_dms')})\n"
            f"{gt_line}"
            "  * Note          : camera +Z on J2000 sky, not lat/lon, not constellation\n"
        )
    else:
        pointing = "  * Boresight      : n/a (solve failed)\n"
    star_lines = ""
    if lookup and catalog is not None and result.ident is not None and len(result.ident.cat_idx):
        names = [compact_tag(catalog, int(c), lookup=True) for c in result.ident.cat_idx[:18]]
        extra = "" if len(result.ident.cat_idx) <= 18 else "  ...\n"
        star_lines = "\nSTARS (IAU / Yale HR):\n  " + "\n  ".join(names) + "\n" + extra
    summary = (
        "STAR TRACKER DEMO\n"
        "--------------------------------------------------\n"
        f"{camera_label}\n"
        "Algorithm  : CoG + Pyramid + Wahba (no ML)\n\n"
        "TIMINGS:\n"
        f"  * Centroiding    : {t.get('centroiding_ms', 0):.2f} ms\n"
        f"  * Star ID        : {t.get('identification_ms', 0):.2f} ms\n"
        f"  * Wahba          : {t.get('attitude_ms', 0):.2f} ms\n"
        f"  * Total          : {t.get('total_pipeline_ms', 0):.2f} ms\n\n"
        "SKY POINTING (from quaternion):\n"
        f"{pointing}\n"
        "METRICS:\n"
        f"  * Stars in FOV   : {metrics.get('n_truth')}\n"
        f"  * Detected       : {metrics.get('n_detected')}\n"
        f"  * Matched        : {metrics.get('n_matched')}\n"
        f"  * Centroid RMS   : {metrics.get('centroid_rms_px')}\n"
        f"  * Attitude error : {err_s} arcsec\n"
        f"  * Limit          : < {metrics.get('limit_arcsec')} arcsec\n"
        f"  * Verdict        : {metrics.get('verdict')}\n"
        f"{star_lines}"
    )
    ax2.text(
        0.08, 0.92, summary, transform=ax2.transAxes, color="#F8FAFC",
        fontsize=10, fontfamily="monospace", verticalalignment="top",
        bbox=dict(boxstyle="round,pad=0.8", facecolor="#0F172A", edgecolor="#38BDF8", alpha=0.9),
    )
    plt.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
    if show:
        plt.show()
    else:
        plt.close(fig)
    return out_path
