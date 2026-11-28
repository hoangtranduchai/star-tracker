"""Generate high-resolution Stage 2 Pipeline & Image Data-Control Architecture diagram."""
from __future__ import annotations

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
    title_fs: float = 9.3,
    body_fs: float = 7.7,
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
        y + h - 0.18,
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
        y + h - 0.48,
        body,
        ha='left',
        va='top',
        fontsize=body_fs,
        color=body_color,
        linespacing=1.34,
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
            fontsize=7.4,
            fontweight='bold',
            color=label_color or color,
            bbox=dict(boxstyle='round,pad=0.18', facecolor='white', edgecolor='none', alpha=0.92),
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
        # Draw all segments except the last tip with plain line, then final segment with arrow
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
            fontsize=7.4,
            fontweight='bold',
            color=color,
            bbox=dict(boxstyle='round,pad=0.18', facecolor='white', edgecolor='none', alpha=0.94),
            zorder=7,
        )


def build_stage2_pipeline_diagram() -> list[Path]:
    plt.rcParams['font.family'] = 'DejaVu Sans'
    fig, ax = plt.subplots(figsize=(16.0, 10.6), dpi=200)
    ax.set_xlim(0.0, 16.0)
    ax.set_ylim(0.0, 10.6)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    # Header banner
    ax.add_patch(FancyBboxPatch(
        (0.25, 9.62), 15.5, 0.80,
        boxstyle='round,pad=0.04,rounding_size=0.14',
        facecolor='#0f294a', edgecolor='#0f294a', linewidth=1.2, zorder=2,
    ))
    ax.text(
        8.0, 10.14,
        'KIẾN TRÚC PIPELINE ĐỊNH HƯỚNG SAO J2000 & KIỂM SOÁT DỮ LIỆU ẢNH (CHẶNG 1 + CHẶNG 2)',
        ha='center', va='center', fontsize=12.4, fontweight='bold', color='white', zorder=3,
    )
    ax.text(
        8.0, 9.81,
        'DUT.StarTracker (AI26C0083) · Gói tái lập 13/13 SHA-256 (36,03 MB) · Auto-Router + Fallback CoG tường minh · 0% False Lock · Cô lập UUID4 / TTL / Quyền xóa',
        ha='center', va='center', fontsize=8.3, color='#bae6fd', zorder=3,
    )

    # ==================== BAND 1: REPRODUCIBILITY & DATA CONTROL ====================
    ax.add_patch(FancyBboxPatch(
        (0.25, 7.30), 15.05, 2.08,
        boxstyle='round,pad=0.04,rounding_size=0.14',
        facecolor='#f8fafc', edgecolor='#cbd5e1', linewidth=1.1, linestyle='--', zorder=1,
    ))
    ax.text(0.45, 9.20, 'TẦNG 1 — GÓI TÁI LẬP ĐỘC LẬP & KIỂM SOÁT DỮ LIỆU ẢNH TẢI LÊN (CẢI TIẾN CHẶNG 2)', fontsize=8.5, fontweight='bold', color='#0f4c81', zorder=2)

    _draw_box(
        ax, 0.45, 7.46, 4.65, 1.56,
        '1A. Gói tái lập độc lập (CHECKSUMS.sha256)',
        '• Checkpoint: MobileUNet_B10_50.pt (18,57 MB)\n'
        '• 6 ảnh trời thật hiệu chuẩn (ESA, Zhao, MSH, NTNU)\n'
        '• Manifest hiệu chuẩn, Config & Catalog BSC5/IAU\n'
        '• Xác thực 13/13 SHA-256 (verify_repro_bundle.py)',
        fc='#ecfeff', ec='#0891b2', title_color='#0e7490',
    )
    _draw_box(
        ax, 5.42, 7.46, 4.72, 1.56,
        '1B. Cô lập ảnh tải lên & Chống ghi đè',
        '• Ảnh tải lên + sidecar → data/user_uploads/<UUID4>/\n'
        '• mkdir(exist_ok=False): 0% ghi đè khi trùng tên tệp\n'
        '• Ảnh mẫu chỉ đọc tách riêng tại data/uploads/\n'
        '• Preview cách ly (inline base64 / preview UUID)',
        fc='#eef2ff', ec='#4f46e5', title_color='#3730a3',
    )
    _draw_box(
        ax, 10.46, 7.46, 4.64, 1.56,
        '1C. Thời gian lưu & Quyền xóa (upload_store.py)',
        '• Mặc định ephemeral (0s): xóa sạch trong finally:\n'
        '  (preview trả inline, verified_gone_on_disk=True)\n'
        '• Tùy chọn ttl: lưu tối đa 15 phút (900s), tự dọn\n'
        '• DELETE /api/uploads[/<id>] → xóa & preview 404',
        fc='#f0fdf4', ec='#16a34a', title_color='#166534',
    )
    _arrow(ax, (10.16, 8.24), (10.44, 8.24), color='#4f46e5', lw=1.6)

    # ==================== BAND 2: CORE PIPELINE + FALLBACK ====================
    ax.add_patch(FancyBboxPatch(
        (0.25, 2.75), 15.05, 4.18,
        boxstyle='round,pad=0.04,rounding_size=0.14',
        facecolor='#f0f9ff', edgecolor='#93c5fd', linewidth=1.2, zorder=1,
    ))
    ax.text(3.35, 6.75, 'TẦNG 2 — ĐƯỜNG ỐNG XỬ LÝ ẢNH SAO LOST-IN-SPACE & CHỐT CHẶN AN TOÀN (CHẶNG 1 + CHẶNG 2)', fontsize=8.5, fontweight='bold', color='#1e3a8a', zorder=2)

    _draw_box(
        ax, 0.45, 4.82, 3.25, 1.72,
        '2A. Quang học & Tiền xử lý',
        '• CameraModel (fx, cx, cy, k1, k2)\n'
        '• Khử méo Heikkilä 8 tham số\n'
        '  (ảnh 8-bit Zhao MT9V022)\n'
        '• GlareMasker: che chói lóa,\n'
        '  rìa Trái Đất & tiền cảnh sáng',
        fc='#ffffff', ec='#1d4ed8', title_color='#1e3a8a',
    )
    _draw_box(
        ax, 4.05, 4.82, 3.55, 1.72,
        '2B. Auto-Router tách tâm sao',
        '• Bước 1: CoG cổ điển (~85 ms,\n'
        '  0 FP trên trời sạch & SAA)\n'
        '• Bước 2 (khi LOST / nền khó):\n'
        '  nâng cấp tự động → CNN-Hybrid\n'
        '  (MobileUNet + Local CoG + SNR)',
        fc='#ffffff', ec='#0284c7', title_color='#0369a1',
    )
    _draw_box(
        ax, 7.95, 4.82, 3.30, 1.72,
        '2C. Nhận dạng sao J2000',
        '• Pyramid (Mortari) + K-vector\n'
        '• Tiền lọc 2 tầng BLAS float32\n'
        '  SGEMM (tăng tốc 5×–11×)\n'
        '• Danh mục Yale BSC5\n'
        '  (5.023 sao thực, V ≤ 6,0)',
        fc='#ffffff', ec='#1d4ed8', title_color='#1e3a8a',
    )
    _draw_box(
        ax, 11.60, 4.82, 3.50, 1.72,
        '2D. Wahba & Chốt chặn 0% FL',
        '• Wahba SVD / QUEST trọng số SNR\n'
        '• _refine_inliers trước & sau gán\n'
        '• Kiểm hạng SVD s_min ≥ 1e-6\n'
        '  (chặn hình học thẳng hàng)\n'
        '• Kiểm min_stars ≥ 4 & mật độ FOV',
        fc='#ffffff', ec='#7c3aed', title_color='#5b21b6',
    )

    # Explicit Fallback CoG Box neatly aligned under 2A–2B (leaves right side clean for 2D routing!)
    _draw_box(
        ax, 0.75, 2.94, 10.00, 1.38,
        'NHÁNH BÁO RÕ FALLBACK CNN → CoG (BẮT BUỘC CHẶNG 2)',
        '• Kích hoạt khi thiếu checkpoint, lệch tệp hoặc lỗi suy luận PyTorch (kiểm chứng bằng --simulate-cnn-fallback / nút Web).\n'
        '• Tự chuyển sang CoG cổ điển, phân biệt tường minh requested_backend → executed_backend (FALLBACK_TO_COG) + fallback_reason.\n'
        '• Bật dải cảnh báo màu cam trên Web UI, in cảnh báo CLI và ghi ngay sự kiện vào data/outputs/execution_log.jsonl.',
        fc='#fffbeb', ec='#d97706', title_color='#b45309', lw=1.8, body_fs=7.5,
    )

    # Clean orthogonal arrows Band 1 -> Band 2 (in corridor y=7.08)
    _ortho_arrow(
        ax, [(1.85, 7.44), (1.85, 6.56)],
        color='#0891b2', lw=1.6, label='Ảnh mẫu + Hiệu chuẩn', label_pos=(1.85, 7.12),
    )
    _ortho_arrow(
        ax, [(7.20, 7.44), (7.20, 7.12), (2.75, 7.12), (2.75, 6.56)],
        color='#4f46e5', lw=1.6, label='Ảnh tải lên (UUID)', label_pos=(5.20, 7.12),
    )

    # Arrows across Band 2
    _arrow(ax, (3.72, 5.68), (4.03, 5.68), color='#1d4ed8')
    _arrow(ax, (7.62, 5.68), (7.93, 5.68), color='#1d4ed8')
    _arrow(ax, (11.27, 5.68), (11.58, 5.68), color='#7c3aed')

    # Fallback arrows between 2B <-> Fallback Box -> 2C
    _ortho_arrow(
        ax, [(5.55, 4.80), (5.55, 4.35)],
        color='#d97706', lw=1.7, ls='--', label='Thiếu/lỗi .pt', label_pos=(4.60, 4.58),
    )
    _ortho_arrow(
        ax, [(9.20, 4.35), (9.20, 4.80)],
        color='#d97706', lw=1.7, ls='--', label='Tâm CoG dự phòng', label_pos=(10.22, 4.58),
    )

    # ==================== BAND 3: OUTPUTS & REAL-TIME AUDIT ====================
    ax.add_patch(FancyBboxPatch(
        (0.25, 0.38), 15.05, 1.88,
        boxstyle='round,pad=0.04,rounding_size=0.14',
        facecolor='#f8fafc', edgecolor='#cbd5e1', linewidth=1.1, linestyle='--', zorder=1,
    ))
    ax.text(2.90, 2.08, 'TẦNG 3 — ĐẦU RA ĐỊNH HƯỚNG AN TOÀN & NHẬT KÝ KIỂM TOÁN THỜI GIAN THỰC', fontsize=8.5, fontweight='bold', color='#334155', zorder=2)

    _draw_box(
        ax, 0.45, 0.54, 4.65, 1.38,
        '3A. Đầu ra hợp lệ: SOLVED',
        '• Quaternion J2000 [w, x, y, z] (16 byte float32)\n'
        '• Telemetry 32B + CRC-16-CCITT (bắt 100% SEU)\n'
        '• Đối chiếu trực quan 3D thiên cầu 5.023 sao thực',
        fc='#ecfdf5', ec='#059669', title_color='#065f46',
    )
    _draw_box(
        ax, 5.42, 0.54, 4.72, 1.38,
        '3B. Từ chối an toàn: LOST (0% False Lock)',
        '• Downlink 16 byte 0x00 (không xuất góc giả)\n'
        '• Trả reject_code tường minh (INSUFFICIENT_INLIERS,\n'
        '  COLLINEAR_DEGENERATE, LOW_FOV_CONSISTENCY)',
        fc='#fff1f2', ec='#e11d48', title_color='#9f1239',
    )
    _draw_box(
        ax, 10.46, 0.54, 4.64, 1.38,
        '3C. Nhật ký Kiểm toán (execution_log.jsonl)',
        '• PIPELINE_RUN: mode yêu cầu → thực thi, fallback\n'
        '• DATA_DELETION: upload_id, tệp xóa, verified_gone\n'
        '• Tra cứu live: GET /api/execution-log & /api/uploads',
        fc='#f5f3ff', ec='#6d28d9', title_color='#4c1d95',
    )

    # ==================== CLEAN ORTHOGONAL BUS ROUTING BAND 2 -> BAND 3 ====================
    # Corridor between Band 2 (y=2.75) and Band 3 (y=2.26) — ZERO box crossings!
    # 2D -> 3A (SOLVED): drop right of Fallback box (x=12.15), run along y=2.56 -> down into 3A (x=2.75)
    _ortho_arrow(
        ax, [(12.15, 4.80), (12.15, 2.56), (2.75, 2.56), (2.75, 1.95)],
        color='#059669', lw=1.7, label='Hợp lệ (inlier ≥ 4, RMS đạt)', label_pos=(5.10, 2.56),
    )
    # 2D -> 3B (LOST): drop at x=13.15, run along y=2.39 -> down into 3B (x=7.78)
    _ortho_arrow(
        ax, [(13.15, 4.80), (13.15, 2.39), (10.00, 2.39), (10.00, 1.95)],
        color='#e11d48', lw=1.7, label='Không đạt chốt chặn → LOST', label_pos=(11.55, 2.39),
    )
    # 2D -> 3C (Log PIPELINE_RUN): straight drop x=14.15 -> 3C
    _ortho_arrow(
        ax, [(14.15, 4.80), (14.15, 1.95)],
        color='#6d28d9', lw=1.5, ls='--', label='PIPELINE_RUN', label_pos=(14.15, 3.65),
    )
    # Fallback Box -> 3C (Log FALLBACK): exit bottom-right (x=10.75, y=3.35) -> x=11.35 -> down to 3C (x=11.35, y=1.95)
    _ortho_arrow(
        ax, [(10.77, 3.35), (11.35, 3.35), (11.35, 1.95)],
        color='#d97706', lw=1.5, ls='--', label='FALLBACK', label_pos=(11.35, 2.86),
    )
    # 1C -> 3C (Log DATA_DELETION): clean outer right gutter x=15.58 (ZERO crossing of any box!)
    _ortho_arrow(
        ax, [(15.12, 8.24), (15.62, 8.24), (15.62, 1.23), (15.12, 1.23)],
        color='#16a34a', lw=1.6, ls=':',
    )
    ax.text(
        15.62, 4.85,
        'Log DATA_DELETION',
        ha='center', va='center', rotation=90,
        fontsize=7.5, fontweight='bold', color='#16a34a',
        bbox=dict(boxstyle='round,pad=0.18', facecolor='white', edgecolor='none', alpha=0.95),
        zorder=7,
    )

    # Footer scope disclaimer
    ax.text(
        8.0, 0.14,
        'Phạm vi kỹ thuật: Phần mềm nghiên cứu & mô phỏng chạy trên PC / ARM64 (NASA TRL 3–4), không tuyên bố đạt chuẩn phần cứng bay hay vòng điều khiển ADCS thực tế.',
        ha='center', va='center', fontsize=7.6, style='italic', color='#64748b',
    )

    targets = [
        ROOT / 'data' / 'outputs' / 'ai2026_figures' / 'pipeline.png',
        ROOT / 'data' / 'outputs' / 'e2e_figures' / 'stage2_pipeline_architecture.png',
        ROOT / 'AI2026_Portfolio' / 'stage2_evidence' / 'stage2_pipeline_architecture.png',
    ]
    for p in targets:
        p.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(p, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return targets


if __name__ == '__main__':
    written = build_stage2_pipeline_diagram()
    for p in written:
        print(f'[OK] Wrote {p} ({p.stat().st_size:,} bytes)')
