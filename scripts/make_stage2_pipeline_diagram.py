"""Generate high-resolution Stage 2 Pipeline & Image Data-Control Architecture diagram."""
from __future__ import annotations

import argparse
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = Path(__file__).resolve().parent.parent


def _draw_box(
    ax: plt.Axes,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    body: str,
    *,
    fc: str,
    ec: str,
    title_color: str,
    body_color: str = '#1e293b',
    lw: float = 1.6,
    title_fs: float = 9.2,
    body_fs: float = 7.6,
) -> None:
    box = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle='round,pad=0.04,rounding_size=0.14',
        facecolor=fc,
        edgecolor=ec,
        linewidth=lw,
        zorder=3,
    )
    ax.add_patch(box)
    ax.text(
        x + w / 2.0,
        y + h - 0.16,
        title,
        ha='center',
        va='top',
        fontsize=title_fs,
        fontweight='bold',
        color=title_color,
        zorder=4,
    )
    ax.text(
        x + 0.14,
        y + h - 0.45,
        body,
        ha='left',
        va='top',
        fontsize=body_fs,
        color=body_color,
        linespacing=1.35,
        zorder=4,
    )


def _arrow(
    ax: plt.Axes,
    p0: tuple[float, float],
    p1: tuple[float, float],
    *,
    color: str = '#1e3a8a',
    lw: float = 1.7,
    ls: str = '-',
    rad: float = 0.0,
    label: str = '',
    label_pos: tuple[float, float] | None = None,
    label_color: str | None = None,
) -> None:
    arr = FancyArrowPatch(
        p0,
        p1,
        connectionstyle=f'arc3,rad={rad}',
        arrowstyle='-|>,head_length=6.2,head_width=3.8',
        color=color,
        linewidth=lw,
        linestyle=ls,
        zorder=6,
    )
    ax.add_patch(arr)
    if label:
        mx, my = label_pos if label_pos is not None else ((p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0)
        ax.text(
            mx,
            my,
            label,
            ha='center',
            va='center',
            fontsize=7.3,
            fontweight='bold',
            color=label_color or color,
            bbox=dict(boxstyle='round,pad=0.18', facecolor='white', edgecolor='none', alpha=0.94),
            zorder=7,
        )


def _ortho_arrow(
    ax: plt.Axes,
    pts: list[tuple[float, float]],
    *,
    color: str,
    lw: float = 1.7,
    ls: str = '-',
    label: str = '',
    label_pos: tuple[float, float] | None = None,
) -> None:
    """Draw a clean orthogonal polyline ending in an arrowhead (zero diagonal clutter)."""
    xs = [p[0] for p in pts[:-1]]
    ys = [p[1] for p in pts[:-1]]
    if len(pts) >= 2:
        if len(pts) > 2:
            ax.plot(xs, ys, color=color, linewidth=lw, linestyle=ls, solid_capstyle='round', solid_joinstyle='round', zorder=5)
        arr = FancyArrowPatch(
            pts[-2],
            pts[-1],
            arrowstyle='-|>,head_length=6.2,head_width=3.8',
            color=color,
            linewidth=lw,
            linestyle=ls,
            zorder=6,
        )
        ax.add_patch(arr)
    if label and label_pos is not None:
        ax.text(
            label_pos[0],
            label_pos[1],
            label,
            ha='center',
            va='center',
            fontsize=7.3,
            fontweight='bold',
            color=color,
            bbox=dict(boxstyle='round,pad=0.18', facecolor='white', edgecolor='none', alpha=0.95),
            zorder=7,
        )


def build_stage2_pipeline_diagram(*, sync_outputs: bool = False) -> list[Path]:
    plt.rcParams['font.family'] = 'DejaVu Sans'
    fig, ax = plt.subplots(figsize=(16.0, 11.4), dpi=200)
    ax.set_xlim(0.0, 16.0)
    ax.set_ylim(0.0, 11.4)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    # Header banner
    ax.add_patch(FancyBboxPatch(
        (0.25, 10.42), 15.5, 0.80,
        boxstyle='round,pad=0.04,rounding_size=0.14',
        facecolor='#0f294a', edgecolor='#0f294a', linewidth=1.2, zorder=2,
    ))
    ax.text(
        8.0, 10.95,
        'KIẾN TRÚC PIPELINE ĐỊNH HƯỚNG SAO J2000 & KIỂM SOÁT DỮ LIỆU ẢNH (CHẶNG 1 + CHẶNG 2)',
        ha='center', va='center', fontsize=12.2, fontweight='bold', color='white', zorder=3,
    )
    ax.text(
        8.0, 10.61,
        'DUT.StarTracker (AI26C0083) · 13/13 SHA-256 (36,02 MiB / 37,77 MB) · Runtime Guard trước torch.load · Fallback CoG tường minh · Cô lập st_sid / UUID4 / TTL / 404',
        ha='center', va='center', fontsize=8.0, color='#bae6fd', zorder=3,
    )

    # ==================== BAND 1: REPRODUCIBILITY & IMAGE DATA GOVERNANCE ====================
    ax.add_patch(FancyBboxPatch(
        (0.25, 7.90), 15.05, 2.30,
        boxstyle='round,pad=0.04,rounding_size=0.14',
        facecolor='#f8fafc', edgecolor='#cbd5e1', linewidth=1.1, linestyle='--', zorder=1,
    ))
    ax.text(
        0.45, 10.02,
        'TẦNG 1 — GÓI TÁI LẬP ĐỘC LẬP, TOÀN VẸN SHA-256 & KIỂM SOÁT DỮ LIỆU ẢNH (CẢI TIẾN CHẶNG 2)',
        fontsize=8.4, fontweight='bold', color='#0f4c81', zorder=2,
    )

    _draw_box(
        ax, 0.45, 8.06, 4.65, 1.74,
        '1A. Tái lập Độc lập & SHA-256 (13/13)',
        '• Checkpoint: MobileUNet_B10_50.pt (17,71 MiB / 18,57 MB)\n'
        '• 6 ảnh trời thật hiệu chuẩn + Manifest + Config + BSC5/IAU\n'
        '• Gói 36,02 MiB / 37,77 MB · .gitattributes LF (Linux/Win)\n'
        '• Guard trước torch.load: chặn MISMATCH / TRUNCATED',
        fc='#ecfeff', ec='#0891b2', title_color='#0e7490', body_fs=7.35,
    )
    _draw_box(
        ax, 5.42, 8.06, 4.72, 1.74,
        '1B. Cô lập Ảnh Tải lên & Phiên st_sid',
        '• Lưu data/user_uploads/<UUID4>/ + meta.json (0% ghi đè)\n'
        '• Cookie phiên st_sid (HttpOnly, SameSite=Lax) → chống IDOR\n'
        '• Ảnh mẫu chỉ đọc tách riêng tại data/uploads/ (bất biến)\n'
        '• Preview cách ly: inline base64 (ephemeral) / URL UUID (ttl)',
        fc='#eef2ff', ec='#4f46e5', title_color='#3730a3', body_fs=7.35,
    )
    _draw_box(
        ax, 10.46, 8.06, 4.64, 1.74,
        '1C. Thời gian Lưu, Rollback & Quyền Xóa',
        '• Mặc định ephemeral (0s): xóa ngay trong finally: (0 B sót)\n'
        '• Tùy chọn ttl (15p/900s): quét lúc khởi động + nền mỗi 60s\n'
        '• Lỗi HTTP 400/409 → rollback xóa tức thì (0 tệp mồ côi)\n'
        '• DELETE /api/uploads[/<id>] → xóa vĩnh viễn & preview 404',
        fc='#f0fdf4', ec='#16a34a', title_color='#166534', body_fs=7.35,
    )
    _arrow(ax, (10.16, 8.93), (10.44, 8.93), color='#4f46e5', lw=1.6)

    # ==================== BAND 2: CORE PIPELINE + EXPLICIT COG FALLBACK ====================
    ax.add_patch(FancyBboxPatch(
        (0.25, 2.98), 15.05, 4.44,
        boxstyle='round,pad=0.04,rounding_size=0.14',
        facecolor='#f0f9ff', edgecolor='#93c5fd', linewidth=1.2, zorder=1,
    ))
    ax.text(
        3.25, 7.23,
        'TẦNG 2 — ĐƯỜNG ỐNG XỬ LÝ ẢNH SAO LOST-IN-SPACE, FALLBACK CoG & CHỐT CHẶN 0% FL',
        fontsize=8.4, fontweight='bold', color='#1e3a8a', zorder=2,
    )

    _draw_box(
        ax, 0.45, 5.22, 3.25, 1.82,
        '2A. Quang học & Tiền xử lý',
        '• CameraModel (fx, cx, cy, k1, k2)\n'
        '• Khử méo Heikkilä 8 tham số\n'
        '  (ảnh 8-bit Zhao MT9V022)\n'
        '• GlareMasker: che chói lóa,\n'
        '  rìa Trái Đất & tiền cảnh sáng',
        fc='#ffffff', ec='#1d4ed8', title_color='#1e3a8a',
    )
    _draw_box(
        ax, 4.05, 5.22, 3.55, 1.82,
        '2B. Auto-Router & Guard .pt',
        '• Bước 1: CoG cổ điển (~85 ms, 0 FP)\n'
        '• Bước 2 (LOST / nền khó):\n'
        '  xác thực SHA-256 trước torch.load\n'
        '  → CNN-Hybrid (MobileUNet + CoG)\n'
        '• Lệch 1B / tệp cụt → chặn & Fallback',
        fc='#ffffff', ec='#0284c7', title_color='#0369a1',
    )
    _draw_box(
        ax, 7.95, 5.22, 3.30, 1.82,
        '2C. Nhận dạng sao J2000',
        '• Pyramid (Mortari) + K-vector\n'
        '• Tiền lọc 2 tầng BLAS float32\n'
        '  SGEMM (tăng tốc 5×–11×)\n'
        '• Danh mục Yale BSC5\n'
        '  (5.023 sao thực, V ≤ 6,0)',
        fc='#ffffff', ec='#1d4ed8', title_color='#1e3a8a',
    )
    _draw_box(
        ax, 11.60, 5.22, 3.50, 1.82,
        '2D. Wahba & Chốt chặn 0% FL',
        '• Wahba SVD / QUEST trọng số SNR\n'
        '• _refine_inliers trước & sau gán\n'
        '• Kiểm hạng SVD s_min ≥ 1e-6\n'
        '  (chặn hình học thẳng hàng)\n'
        '• Kiểm min_stars ≥ 4 & mật độ FOV',
        fc='#ffffff', ec='#7c3aed', title_color='#5b21b6',
    )

    # Explicit Fallback Box (aligned cleanly on left so right corridor handles 2D->3A/3B/3C bus)
    _draw_box(
        ax, 0.45, 3.16, 9.95, 1.48,
        'NHÁNH BÁO RÕ FALLBACK CNN → CoG (0% FALLBACK NGẦM · CHẶNG 2)',
        '• Kích hoạt trên mọi nhánh (cnn, auto, /api/compare) khi thiếu .pt, CHECKPOINT_SHA256_MISMATCH, CHECKPOINT_TRUNCATED hoặc lỗi PyTorch.\n'
        '• Báo tường minh requested → executed (FALLBACK_TO_COG), checkpoint_status, checkpoint_sha256 & bật bit FLAG_FALLBACK_USED (0x08).\n'
        '• Hiện dải cảnh báo màu cam trên Web UI, cảnh báo CLI (đường dẫn tương đối, không lộ path OS) & ghi nguyên tử vào execution_log.jsonl.',
        fc='#fffbeb', ec='#d97706', title_color='#b45309', lw=1.8, body_fs=7.25,
    )

    # Clean orthogonal arrows Band 1 -> Band 2 (in corridor y=7.66)
    _ortho_arrow(
        ax, [(1.60, 8.04), (1.60, 7.06)],
        color='#0891b2', lw=1.6, label='Ảnh mẫu + Hiệu chuẩn', label_pos=(1.60, 7.66),
    )
    _ortho_arrow(
        ax, [(7.40, 8.04), (7.40, 7.66), (2.75, 7.66), (2.75, 7.06)],
        color='#4f46e5', lw=1.6, label='Ảnh tải lên (UUID + st_sid)', label_pos=(5.35, 7.66),
    )

    # Arrows across Band 2
    _arrow(ax, (3.72, 6.13), (4.03, 6.13), color='#1d4ed8')
    _arrow(ax, (7.62, 6.13), (7.93, 6.13), color='#1d4ed8')
    _arrow(ax, (11.27, 6.13), (11.58, 6.13), color='#7c3aed')

    # Fallback arrows between 2B <-> Fallback Box -> 2C
    _ortho_arrow(
        ax, [(5.55, 5.20), (5.55, 4.68)],
        color='#d97706', lw=1.7, ls='--', label='Guard chặn / lỗi .pt', label_pos=(4.25, 4.94),
    )
    _ortho_arrow(
        ax, [(9.05, 4.68), (9.05, 5.20)],
        color='#d97706', lw=1.7, ls='--', label='Tâm CoG dự phòng', label_pos=(10.22, 4.94),
    )

    # ==================== BAND 3: OUTPUTS & REAL-TIME AUDIT ====================
    ax.add_patch(FancyBboxPatch(
        (0.25, 0.40), 15.05, 1.92,
        boxstyle='round,pad=0.04,rounding_size=0.14',
        facecolor='#f8fafc', edgecolor='#cbd5e1', linewidth=1.1, linestyle='--', zorder=1,
    ))
    # Header spans x=[1.55 .. ~7.95], leaving wide clear lanes at x=1.05 (green) and x=9.65 (red)!
    ax.text(
        1.55, 2.13,
        'TẦNG 3 — ĐẦU RA AN TOÀN & NHẬT KÝ KIỂM TOÁN THỜI GIAN THỰC',
        fontsize=8.3, fontweight='bold', color='#334155', zorder=2,
    )

    _draw_box(
        ax, 0.45, 0.56, 4.65, 1.42,
        '3A. Đầu ra hợp lệ: SOLVED',
        '• Quaternion J2000 [w, x, y, z] (16 byte float32)\n'
        '• Telemetry 32B + CRC-16 + FLAG_FALLBACK_USED (0x08)\n'
        '• Đối chiếu trực quan 3D thiên cầu 5.023 sao thực',
        fc='#ecfdf5', ec='#059669', title_color='#065f46',
    )
    _draw_box(
        ax, 5.42, 0.56, 4.72, 1.42,
        '3B. Từ chối an toàn: LOST (0% False Lock)',
        '• Downlink 16 byte 0x00 (không xuất góc giả)\n'
        '• Trả reject_code tường minh (INSUFFICIENT_INLIERS,\n'
        '  COLLINEAR_DEGENERATE, LOW_FOV_CONSISTENCY)',
        fc='#fff1f2', ec='#e11d48', title_color='#9f1239',
    )
    _draw_box(
        ax, 10.46, 0.56, 4.64, 1.42,
        '3C. Nhật ký Kiểm toán (execution_log.jsonl)',
        '• Ghi nguyên tử os.replace + retry; chặn /output/*.jsonl\n'
        '• PIPELINE_RUN: mode, fallback, checkpoint_status & SHA\n'
        '• DATA_DELETION: cô lập st_sid (owner_sid_hash), verified',
        fc='#f5f3ff', ec='#6d28d9', title_color='#4c1d95',
    )

    # ==================== CLEAN ORTHOGONAL BUS ROUTING BAND 2 -> BAND 3 ====================
    # Corridor between Band 2 (y=2.98) and Band 3 (y=2.32) — ZERO header or text crossings!
    # 2D -> 3A (SOLVED): drop at x=12.15 to y=2.78, run left to x=1.05 (left of Tier 3 header), drop into 3A
    _ortho_arrow(
        ax, [(12.15, 5.20), (12.15, 2.78), (1.05, 2.78), (1.05, 2.00)],
        color='#059669', lw=1.7, label='Hợp lệ (inlier ≥ 4, RMS đạt)', label_pos=(5.25, 2.78),
    )
    # 2D -> 3B (LOST): drop at x=13.55 to y=2.48, run left to x=9.65 (well right of Tier 3 header!), drop into 3B
    _ortho_arrow(
        ax, [(13.55, 5.20), (13.55, 2.48), (9.65, 2.48), (9.65, 2.00)],
        color='#e11d48', lw=1.7, label='Không đạt chốt chặn → LOST', label_pos=(12.28, 2.48),
    )
    # 2D -> 3C (Log PIPELINE_RUN): straight drop x=14.48 -> 3C
    _ortho_arrow(
        ax, [(14.48, 5.20), (14.48, 2.00)],
        color='#6d28d9', lw=1.5, ls='--', label='PIPELINE_RUN', label_pos=(14.48, 3.88),
    )
    # Fallback Box -> 3C (Log FALLBACK): exit right edge (10.42, 3.88) -> x=11.02 -> down into 3C
    _ortho_arrow(
        ax, [(10.42, 3.88), (11.02, 3.88), (11.02, 2.00)],
        color='#d97706', lw=1.5, ls='--', label='FALLBACK', label_pos=(11.02, 3.36),
    )
    # 1C -> 3C (Log DATA_DELETION): clean outer right gutter x=15.62 (ZERO crossing of any box!)
    _ortho_arrow(
        ax, [(15.12, 8.93), (15.62, 8.93), (15.62, 1.27), (15.12, 1.27)],
        color='#16a34a', lw=1.6, ls=':',
    )
    ax.text(
        15.62, 5.20,
        'Log DATA_DELETION (st_sid)',
        ha='center', va='center', rotation=90,
        fontsize=7.4, fontweight='bold', color='#16a34a',
        bbox=dict(boxstyle='round,pad=0.18', facecolor='white', edgecolor='none', alpha=0.95),
        zorder=7,
    )

    # Footer scope disclaimer
    ax.text(
        8.0, 0.16,
        'Phạm vi kỹ thuật: Phần mềm nghiên cứu & mô phỏng chạy trên PC / ARM64 (NASA TRL 3–4), không tuyên bố đạt chuẩn phần cứng bay hay vòng điều khiển ADCS thực tế.',
        ha='center', va='center', fontsize=7.6, style='italic', color='#64748b',
    )

    targets = [ROOT / 'AI2026_Portfolio' / 'stage2_evidence' / 'stage2_pipeline_architecture.png']
    if sync_outputs:
        targets.extend([
            ROOT / 'data' / 'outputs' / 'ai2026_figures' / 'pipeline.png',
            ROOT / 'data' / 'outputs' / 'e2e_figures' / 'stage2_pipeline_architecture.png',
        ])
    for p in targets:
        p.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(p, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return targets


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Generate Stage 2 pipeline architecture diagram PNG.')
    ap.add_argument(
        '--sync-outputs',
        action='store_true',
        help='Also mirror diagram to data/outputs/e2e_figures and data/outputs/ai2026_figures.',
    )
    args = ap.parse_args()
    written = build_stage2_pipeline_diagram(sync_outputs=bool(args.sync_outputs))
    for p in written:
        print(f'[OK] Wrote {p} ({p.stat().st_size:,} bytes)')
