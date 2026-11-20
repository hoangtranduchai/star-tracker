"""Generate publication-grade Vietnamese figures (Fig 10 & Fig 11) for Section 6 & Slides.

Reads audited JSON outputs directly:
  - data/outputs/benchmark_3way_comparison.json
  - data/outputs/benchmark_stress_curves.json

Writes:
  - data/outputs/e2e_figures/fig10_4way_ablation_tetra3_hybrid.png
  - data/outputs/e2e_figures/fig11_stress_degradation_curves.png
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / 'data' / 'outputs'
FIG_DIR = OUT_DIR / 'e2e_figures'
FIG_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    'font.family': 'DejaVu Sans',
    'axes.edgecolor': '#CBD5E1',
    'axes.linewidth': 0.9,
    'axes.grid': True,
    'grid.color': '#E2E8F0',
    'grid.linestyle': '--',
    'grid.linewidth': 0.7,
    'figure.facecolor': '#FFFFFF',
    'axes.facecolor': '#FFFFFF',
})

COLORS = {
    'classical': '#2563EB',  # Royal Blue
    'tetra3': '#9333EA',     # Purple
    'cnn_raw': '#F97316',    # Orange (ablation before)
    'cnn': '#059669',        # Emerald (CNN-Hybrid after)
    'auto': '#0F172A',       # Deep Navy (Auto-Router)
}
LABELS = {
    'classical': 'CoG (Nhóm)',
    'tetra3': 'Ngưỡng tetra3',
    'cnn_raw': 'CNN gốc',
    'cnn': 'CNN-Hybrid',
    'auto': 'Auto (CoG→CNN)',
}


def make_fig10() -> Path:
    b3_path = OUT_DIR / 'benchmark_3way_comparison.json'
    d = json.loads(b3_path.read_text(encoding='utf-8'))
    be_list = [b for b in ('classical', 'tetra3', 'cnn_raw', 'cnn', 'auto') if b in (d['sim_hd1024']['summary'] or {})]

    fig, axes = plt.subplots(1, 3, figsize=(16.5, 5.2), dpi=240)
    fig.suptitle(
        'Đối chuẩn 5 phương pháp: CoG ↔ Ngưỡng kiểu ESA tetra3 ↔ CNN gốc ↔ CNN-Hybrid ↔ Auto-Router (PC RTX 5070)',
        fontsize=12.5, fontweight='bold', color='#0F172A', y=0.98,
    )

    # Panel A: Median attitude error (arcsec) on 500 Clean, 40 Glare, 20 Earth-Clutter
    ax = axes[0]
    suites = [('500 sạch\n(hd1024)', 'sim_hd1024'), ('40 lóa\n(glare)', 'sim_glare'), ('20 Rìa TĐ\n+ Mây', 'sim_earth_clutter')]
    x = np.arange(len(suites))
    w = 0.76 / len(be_list)
    for idx, be in enumerate(be_list):
        vals = [float((d[sk]['summary'][be]['attitude_error_arcsec']['median'] or 0.0)) for _, sk in suites]
        bars = ax.bar(x + (idx - (len(be_list) - 1) / 2.0) * w, vals, width=w * 0.92, label=LABELS[be], color=COLORS[be], alpha=0.92)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2.0, val + 0.25, f'{val:.2f}″', ha='center', va='bottom', fontsize=6.8, rotation=90 if len(be_list) >= 5 else 0, color='#1E293B')
    ax.set_xticks(x)
    ax.set_xticklabels([t for t, _ in suites], fontsize=9)
    ax.set_ylabel('Sai số tư thế 3-DOF trung vị Δθ (arcsec)', fontsize=9.5, fontweight='bold', color='#1E293B')
    ax.set_title('A. Sai số góc trung vị Δθ (thấp hơn là tốt hơn)', fontsize=10.5, fontweight='bold', color='#133E68', pad=8)
    ax.set_ylim(0, max(16.5, ax.get_ylim()[1] * 1.22))
    ax.legend(fontsize=7.6, loc='upper left', frameon=True, facecolor='#F8FAFC')

    # Panel B: False Positive Reduction Ablation (CNN raw -> CNN-Hybrid vs CoG / tetra3)
    ax = axes[1]
    fp_suites = [('500 sạch (hd1024)', 'sim_hd1024'), ('40 lóa (glare)', 'sim_glare')]
    x2 = np.arange(len(fp_suites))
    ab_list = [b for b in ('classical', 'tetra3', 'cnn_raw', 'cnn') if b in be_list]
    w2 = 0.72 / len(ab_list)
    for idx, be in enumerate(ab_list):
        vals = [int(d[sk]['summary'][be]['centroid_false_pos_5px_total'] or 0) for _, sk in fp_suites]
        bars = ax.bar(x2 + (idx - (len(ab_list) - 1) / 2.0) * w2, vals, width=w2 * 0.9, label=LABELS[be], color=COLORS[be], alpha=0.92)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2.0, val + max(18, ax.get_ylim()[1] * 0.015), f'{val}', ha='center', va='bottom', fontsize=8.2, fontweight='bold', color='#1E293B')
    ax.set_xticks(x2)
    ax.set_xticklabels([t for t, _ in fp_suites], fontsize=9)
    ax.set_ylabel('Tổng số đốm sáng giả FP (≤ 5 px)', fontsize=9.5, fontweight='bold', color='#1E293B')
    ax.set_title('B. Cắt giảm điểm giả FP: CNN gốc → CNN-Hybrid', fontsize=10.5, fontweight='bold', color='#133E68', pad=8)
    ax.set_ylim(0, max(1280, ax.get_ylim()[1] * 1.15))
    ax.legend(fontsize=7.8, loc='upper right', frameon=True, facecolor='#F8FAFC')

    # Panel C: Real-Sky Calibrated Solves (out of 4 solvable GT frames: Alt60, Alt40 Hip7, Zhao, MSH)
    ax = axes[2]
    rc = d['real_calibrated']
    by_be = rc['calibrated_bsc5_frames']
    a40 = rc.get('alt40_hipparcos_v7') or {}
    frame_names = ['ESA Alt60\n(16-bit)', 'ESA Alt40\n(Hip V≤7)', 'Zhao MT9V022\n(8-bit)', 'Mount St.\nHelens (8-bit)']
    mat = np.zeros((len(be_list), len(frame_names)), dtype=float)
    txt_mat = [['' for _ in frame_names] for _ in be_list]
    for r_i, be in enumerate(be_list):
        f_list = by_be.get(be) or []
        by_id = {f['frame_id']: f for f in f_list}
        entries = [
            by_id.get('2019-07-29T204726_Alt60_Azi-135_Try1.tiff'),
            a40.get(be),
            by_id.get('nightsky_june16_2021.npy'),
            by_id.get('mount_st_helens_1.png'),
        ]
        for c_i, rec in enumerate(entries):
            if rec and rec.get('status') == 'SOLVED':
                mat[r_i, c_i] = 1.0
                err = rec.get('attitude_error_arcsec')
                txt_mat[r_i][c_i] = f'SOLVED\n{err:.1f}″' if err is not None else 'SOLVED'
            else:
                mat[r_i, c_i] = 0.0
                txt_mat[r_i][c_i] = 'LOST'

    cmap = matplotlib.colors.ListedColormap(['#FEE2E2', '#D1FAE5'])
    ax.imshow(mat, cmap=cmap, aspect='auto', vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(frame_names)))
    ax.set_xticklabels(frame_names, fontsize=8.2)
    ax.set_yticks(np.arange(len(be_list)))
    ax.set_yticklabels([f"{LABELS[b]}\n({int(mat[i].sum())}/4)" for i, b in enumerate(be_list)], fontsize=8.4, fontweight='bold')
    ax.grid(False)
    for r_i in range(len(be_list)):
        for c_i in range(len(frame_names)):
            ok = mat[r_i, c_i] > 0.5
            ax.text(c_i, r_i, txt_mat[r_i][c_i], ha='center', va='center', fontsize=8.0, fontweight='bold', color='#065F46' if ok else '#991B1B')
    for xline in np.arange(-0.5, len(frame_names), 1):
        ax.axvline(xline, color='#FFFFFF', linewidth=2.0)
    for yline in np.arange(-0.5, len(be_list), 1):
        ax.axhline(yline, color='#FFFFFF', linewidth=2.0)
    ax.set_title('C. 4 ảnh trời thật hiệu chuẩn (0% Khóa sai)', fontsize=10.5, fontweight='bold', color='#133E68', pad=8)

    plt.tight_layout(rect=(0.0, 0.0, 0.99, 0.93))
    out_p = FIG_DIR / 'fig10_4way_ablation_tetra3_hybrid.png'
    fig.savefig(out_p, dpi=240)
    plt.close(fig)
    print(f'wrote {out_p}')
    return out_p


def make_fig11() -> Path:
    sc_path = OUT_DIR / 'benchmark_stress_curves.json'
    d = json.loads(sc_path.read_text(encoding='utf-8'))
    be_list = [b for b in ('classical', 'tetra3', 'cnn', 'auto') if b in d.get('backends', [])]

    fig, axes = plt.subplots(1, 3, figsize=(16.5, 4.9), dpi=240)
    fig.suptitle(
        'Đường cong suy giảm hiệu năng dưới điều kiện khắc nghiệt (1024×683 · 10 khung/mức · 0% Khóa sai)',
        fontsize=12.5, fontweight='bold', color='#0F172A', y=0.98,
    )

    markers = {'classical': 'o', 'tetra3': 's', 'cnn': '^', 'auto': 'D'}
    styles = {'classical': '-', 'tetra3': '--', 'cnn': '-', 'auto': ':'}

    sweeps = [
        ('omega_sweep', 'A. Tỷ lệ giải theo vận tốc quay ω (motion blur)', 'Vận tốc quay ω (°/s, t_exp = 0,15 s)', 'solve_rate_pct', 'Tỷ lệ giải thành công (%)'),
        ('false_stars_sweep', 'B. Tỷ lệ giải khi tiêm sao giả / tia vũ trụ', 'Số sao giả tiêm vào khung hình', 'solve_rate_pct', 'Tỷ lệ giải thành công (%)'),
        ('glare_sweep', 'C. Sai số Δθ theo nền lóa (100% giải · 0% FL)', 'Đỉnh nền lóa (DN · halo σ = 180 px)', 'median_err_arcsec', 'Sai số trung vị Δθ (arcsec)'),
    ]

    for ax, (key, title, xlabel, metric, ylabel) in zip(axes, sweeps):
        pts = d[key]
        xs = [p['x'] for p in pts]
        for be in be_list:
            ys = [p['results'][be][metric] for p in pts]
            ax.plot(
                xs, ys,
                marker=markers[be], linestyle=styles[be], linewidth=2.3, markersize=6.5,
                color=COLORS[be], label=LABELS[be], alpha=0.92,
            )
            if metric == 'median_err_arcsec' and ys[-1] is not None:
                dy_map = {'tetra3': 0, 'cnn': 10, 'classical': 0, 'auto': -10}
                ax.annotate(
                    f'{ys[-1]:.1f}″',
                    xy=(xs[-1], ys[-1]),
                    xytext=(6, dy_map.get(be, 0)),
                    textcoords='offset points',
                    fontsize=8.0,
                    fontweight='bold',
                    color=COLORS[be],
                    va='center',
                )
        ax.set_title(title, fontsize=10.3, fontweight='bold', color='#133E68', pad=8)
        ax.set_xlabel(xlabel, fontsize=9.2, fontweight='bold', color='#1E293B')
        ax.set_ylabel(ylabel, fontsize=9.2, fontweight='bold', color='#1E293B')
        if metric == 'solve_rate_pct':
            ax.set_ylim(-4, 108)
            ax.legend(fontsize=8.2, loc='lower left', frameon=True, facecolor='#F8FAFC')
        else:
            ax.set_ylim(0, max(7.2, ax.get_ylim()[1] * 1.18))
            ax.set_xlim(min(xs) - 200, max(xs) + 750)
            ax.legend(fontsize=8.2, loc='upper left', frameon=True, facecolor='#F8FAFC')

    plt.tight_layout(rect=(0.0, 0.0, 1.0, 0.93))
    out_p = FIG_DIR / 'fig11_stress_degradation_curves.png'
    fig.savefig(out_p, dpi=240)
    plt.close(fig)
    print(f'wrote {out_p}')
    return out_p


if __name__ == '__main__':
    make_fig10()
    make_fig11()
