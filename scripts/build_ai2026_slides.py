"""Build baseline AI2026 slides from audited Stage 3A benchmark JSONs (note: styled deck is updated via update_national_slides_and_docs.py)."""
from __future__ import annotations

import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, FancyBboxPatch, Rectangle
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'AI2026_Portfolio' / 'AI2026_SLIDE_THUYET_TRINH.pptx'
FIG = ROOT / 'data' / 'outputs' / 'ai2026_figures'
BENCH = ROOT / 'data' / 'outputs' / 'centroid_benchmark_hd1024_thr2.json'
GLARE = ROOT / 'data' / 'outputs' / 'centroid_benchmark_hd1024_glare_sun_strong.json'
AUDIT = ROOT / 'data' / 'outputs' / 'log_reconciliation_audit.json'
HD_E2E = ROOT / 'data' / 'outputs' / 'benchmark_sim_hd1024_e2e.json'
SEED42 = ROOT / 'data' / 'outputs' / 'seed42_cog_vs_cnn.json'
MOUNT = ROOT / 'data' / 'outputs' / 'mount_st_helens_centroid_compare.json'
MOUNT_LOST = ROOT / 'data' / 'outputs' / 'mount_st_helens_lost_compare.json'
MOUNT_OVERLAY = ROOT / 'data' / 'outputs' / 'mount_st_helens_cog_vs_cnn.png'
ZHAO_FLOW = ROOT / 'data' / 'outputs' / 'zhao_paper_figures' / 'project_00.png'
ZHAO_STRAY = ROOT / 'data' / 'outputs' / 'zhao_paper_figures' / 'project_03.png'
PREVIEW = ROOT / 'data' / 'sim_dataset' / 'hd1024' / '0001_preview.png'

NAVY = RGBColor(31, 78, 121)
DARK = RGBColor(34, 34, 34)
MUTED = RGBColor(85, 85, 85)
WHITE = RGBColor(255, 255, 255)


def _run(p: object, text: object, size: object = 18, bold: object = False, color: object = DARK) -> None:
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.color.rgb = color
    r.font.name = 'Calibri'


def title_bar(slide: object, title: object, subtitle: object = None) -> None:
    box = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(0.95))
    box.fill.solid()
    box.fill.fore_color.rgb = NAVY
    box.line.fill.background()
    tf = box.text_frame
    tf.clear()
    _run(tf.paragraphs[0], title, size=26, bold=True, color=WHITE)
    if subtitle:
        _run(tf.add_paragraph(), subtitle, size=12, color=RGBColor(214, 228, 240))


def bullets(slide: object, left: object, top: object, width: object, height: object, items: object, size: object = 16) -> None:
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = box.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(8)
        _run(p, '• ' + item, size=size, color=DARK)


def footer(slide: object, page: object, total: object) -> None:
    box = slide.shapes.add_textbox(Inches(0.4), Inches(7.1), Inches(12.5), Inches(0.35))
    _run(box.text_frame.paragraphs[0], f'Trường Đại học Bách khoa, Đại học Đà Nẵng — Khoa Công nghệ thông tin    |    {page}/{total}', size=10, color=MUTED)


def blank(prs: object) -> object:
    return prs.slides.add_slide(prs.slide_layouts[6])


def fig_pipeline() -> Path:
    FIG.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12.5, 3.4), dpi=160)
    ax.set_xlim(0, 12.5)
    ax.set_ylim(0, 3.4)
    ax.axis('off')
    boxes = [
        (0.3, 1.0, 2.0, 1.4, 'Ảnh sao\n1024×683'),
        (2.6, 1.0, 2.0, 1.4, 'Centroid\nCoG | CNN*'),
        (4.9, 1.0, 2.2, 1.4, 'Pyramid +\nK-vector'),
        (7.4, 1.0, 2.0, 1.4, 'Wahba + Guard\nSVD/QUEST'),
        (9.7, 1.0, 2.4, 1.4, 'Quaternion\n16B (0x00=LOST)'),
    ]
    for x, y, w, h, label in boxes:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.04,rounding_size=0.12', facecolor='#e8f1fb', edgecolor='#1f4e79', lw=1.6))
        ax.text(x + w / 2, y + h / 2, label, ha='center', va='center', fontsize=11)
    for x0, x1 in [(2.3, 2.6), (4.6, 4.9), (7.1, 7.4), (9.4, 9.7)]:
        ax.annotate('', xy=(x1, 1.7), xytext=(x0, 1.7), arrowprops=dict(arrowstyle='->', color='#1f4e79', lw=1.8))
    ax.text(6.25, 0.3, '* CNN MobileUNet công khai · d_th=2 (public) · không huấn luyện lại', ha='center', fontsize=8.5, color='#444')
    ax.set_title('Đường ống star tracker (demo laptop)', fontsize=13, color='#1f4e79')
    path = FIG / 'pipeline.png'
    fig.tight_layout()
    fig.savefig(path, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return path


def fig_camera() -> Path:
    fig, ax = plt.subplots(figsize=(10, 5.0), dpi=160)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5.0)
    ax.axis('off')
    ax.add_patch(Rectangle((0.6, 1.5), 2.4, 1.5, fill=False, lw=2, edgecolor='#1f4e79'))
    ax.text(1.8, 2.25, 'APS-C demo\n6000×4000\np=3,72 µm', ha='center', va='center', fontsize=9)
    ax.add_patch(Ellipse((4.0, 2.25), 0.55, 1.4, fill=False, lw=2, edgecolor='#c45c26'))
    ax.text(4.0, 0.7, 'f = 50 mm', ha='center', fontsize=10, color='#c45c26')
    ax.plot([4.3, 8.8], [3.0, 4.4], color='#1f4e79', lw=1.2)
    ax.plot([4.3, 8.8], [1.5, 0.5], color='#1f4e79', lw=1.2)
    ax.plot([4.3, 8.8], [2.25, 2.25], color='#888', lw=1.0, ls='--')
    ax.text(7.0, 4.6, 'FOV ≈ 25,16° × 16,93°', fontsize=10, color='#1f4e79')
    ax.add_patch(FancyBboxPatch((0.5, 3.4), 3.2, 1.3, boxstyle='round,pad=0.05', facecolor='#fff4e8', edgecolor='#c45c26', lw=1.4))
    ax.text(2.1, 4.05, 'Benchmark hd1024\n1024×683\n(cùng lớp FOV demo)', ha='center', va='center', fontsize=9)
    ax.add_patch(FancyBboxPatch((5.4, 1.4), 4.1, 2.2, boxstyle='round,pad=0.05', facecolor='#f3f7fb', edgecolor='#1f4e79', lw=1.2))
    ax.text(7.45, 2.5, 'Demo đầy đủ: 15,35″/pixel\nTâm: u₀=2999,5  v₀=1999,5\n\nhd1024 = tỷ lệ cạnh dài ~1024\nkhông phải cảm biến bay mới', ha='center', va='center', fontsize=9)
    ax.set_title('Hình học camera demo / bộ đo 1024', fontsize=12, color='#1f4e79')
    path = FIG / 'camera_geometry.png'
    fig.tight_layout()
    fig.savefig(path, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return path


def fig_starfield() -> Path | None:
    path = FIG / 'starfield_hd1024.png'
    src = PREVIEW if PREVIEW.is_file() else None
    if src is None:
        cands = sorted((ROOT / 'data' / 'sim_dataset' / 'hd1024').glob('*_preview.png'))
        src = cands[1] if len(cands) > 1 else cands[0] if cands else None
    if src is None:
        return None
    img = plt.imread(str(src))
    fig, ax = plt.subplots(figsize=(10, 5.0), dpi=150)
    ax.imshow(img, cmap='gray' if getattr(img, 'ndim', 2) == 2 else None)
    ax.set_title('Ảnh sao benchmark 1024×683 (preview từ data/sim_dataset/hd1024)')
    ax.axis('off')
    fig.tight_layout()
    fig.savefig(path, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return path


def fig_comparison(s: dict, t2: dict) -> Path:
    cl, nn = s['classical'], s['cnn']
    t2_cl, t2_nn = t2['classical'], t2['cnn']
    thr = s.get('distance_map_threshold', 2.0)
    rows = [
        ['Phương án', 'RMSE tb', 'RMSE tv', 'Recall · Precision (Khớp)', 'ms tv'],
        [
            'CoG cổ điển',
            f"{cl['rmse_px_mean']:.4f}",
            f"{cl['rmse_px_median']:.4f}",
            f"{t2_cl['recall_pct']:.1f}% · {t2_cl['precision_pct']:.1f}% ({t2_cl['matched_stars_total']}/{t2['gt_stars_total']})",
            f"{cl['time_ms_median']:.2f}",
        ],
        [
            f'CNN MobileUNet (d_th={thr:g})',
            f"{nn['rmse_px_mean']:.4f}",
            f"{nn['rmse_px_median']:.4f}",
            f"{t2_nn['recall_pct']:.1f}% · {t2_nn['precision_pct']:.1f}% ({t2_nn['matched_stars_total']}/{t2_nn['predicted_stars_total']}, {t2_nn['false_positives_total']} FP)",
            f"{nn['time_ms_median']:.2f}",
        ],
    ]
    fig, ax = plt.subplots(figsize=(12, 2.7), dpi=160)
    ax.axis('off')
    table = ax.table(cellText=rows, loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(9.5)
    table.scale(1.15, 1.7)
    for j in range(5):
        table[0, j].set_facecolor('#1f4e79')
        table[0, j].set_text_props(color='white', weight='bold')
    ax.set_title('So sánh centroid — 500 khung 1024×683 · d_th=2 · RTX 5070 (số liệu đã kiểm toán)', fontsize=11, pad=10, color='#1f4e79')
    path = FIG / 'comparison_table.png'
    fig.tight_layout()
    fig.savefig(path, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return path


def build() -> None:
    s = json.loads(BENCH.read_text(encoding='utf-8')).get('summary')
    t2 = json.loads(AUDIT.read_text(encoding='utf-8'))['thr2_centroid_precision_recall_audit']
    hd = json.loads(HD_E2E.read_text(encoding='utf-8'))
    s42 = json.loads(SEED42.read_text(encoding='utf-8'))
    if not s or s.get('classical', {}).get('n_frames') != 500:
        raise SystemExit('thr2 JSON incomplete')
    cl, nn, cam = s['classical'], s['cnn'], s['camera']
    thr = s.get('distance_map_threshold', 2.0)
    m = json.loads(MOUNT.read_text(encoding='utf-8'))
    lost = json.loads(MOUNT_LOST.read_text(encoding='utf-8'))
    g = json.loads(GLARE.read_text(encoding='utf-8')).get('summary')
    fig_pipeline()
    fig_camera()
    fig_starfield()
    fig_comparison(s, t2)

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    total = 13

    sl = blank(prs)
    bg = sl.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(7.5))
    bg.fill.solid()
    bg.fill.fore_color.rgb = NAVY
    bg.line.fill.background()
    tb = sl.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(11.5), Inches(4.5))
    tf = tb.text_frame
    tf.word_wrap = True
    _run(tf.paragraphs[0], 'STAR TRACKER — DEMO LAPTOP', size=34, bold=True, color=WHITE)
    _run(tf.add_paragraph(), 'Centroid → Pyramid / K-vector → Wahba + Guard → Quaternion 16 byte', size=18, color=RGBColor(214, 228, 240))
    p = tf.add_paragraph()
    p.space_before = Pt(20)
    _run(p, 'Cuộc thi Sáng tạo trẻ Quốc gia — Trí tuệ nhân tạo 2026 (Bảng C)', size=15, color=WHITE)
    p = tf.add_paragraph()
    p.space_before = Pt(16)
    _run(p, 'Trường Đại học Bách khoa, Đại học Đà Nẵng\nKhoa Công nghệ thông tin', size=18, bold=True, color=WHITE)
    p = tf.add_paragraph()
    p.space_before = Pt(12)
    _run(p, 'Đội: Hoàng Trần Đức Hải · Nguyễn Tiến · Mai Tạ Trúc Vy', size=12, color=RGBColor(184, 201, 220))

    sl = blank(prs)
    title_bar(sl, 'Nội dung thuyết trình')
    bullets(sl, 0.7, 1.3, 11.5, 5.5, ['Bài toán lost-in-space và quaternion 16 byte (demo PC)', 'Pipeline cổ điển + CNN centroid tùy chọn (d_th=2)', 'Kết quả đo hd1024 (Centroid & E2E): CoG thắng trên bộ sạch', 'Điểm sáng tạo: ảnh núi thật LOST — CoG bị chặn ngoại lai / CNN giải đúng', 'Trích dẫn Zhao et al. (arXiv:2404.19108) — tách khỏi số đo nhóm', 'Giới hạn PC Demo & FAQ'], size=18)
    footer(sl, 2, total)

    sl = blank(prs)
    title_bar(sl, '1. Bài toán lost-in-space')
    bullets(sl, 0.7, 1.3, 11.5, 5.5, ['Không biết hướng nhìn ban đầu trên bầu trời.', 'Đầu ra: quaternion J2000 — 4×float32 = 16 byte (0x00 khi LOST).', 'Giải bằng hình học góc giữa các sao.', 'Demo trên laptop; chưa kiểm chứng phần cứng bay hay ADCS vệ tinh.'], size=18)
    footer(sl, 3, total)

    sl = blank(prs)
    title_bar(sl, '2. Đường ống thuật toán')
    sl.shapes.add_picture(str(FIG / 'pipeline.png'), Inches(0.5), Inches(1.25), width=Inches(12.3))
    bullets(sl, 0.7, 5.0, 12, 1.8, ['Pyramid (Mortari) + K-vector · Yale BSC5 V ≤ 6.', 'Wahba SVD/QUEST + hậu kiểm dư góc & SVD thẳng hàng → quaternion.', f'CNN: MobileUNet công khai, d_th={thr:g} (public), không huấn luyện lại.'], size=14)
    footer(sl, 4, total)

    sl = blank(prs)
    title_bar(sl, '3. Hình học camera / bộ đo 1024')
    sl.shapes.add_picture(str(FIG / 'camera_geometry.png'), Inches(1.0), Inches(1.15), width=Inches(11.2))
    footer(sl, 5, total)

    sl = blank(prs)
    title_bar(sl, '4. Ảnh sao benchmark hd1024')
    sf = FIG / 'starfield_hd1024.png'
    if sf.is_file():
        sl.shapes.add_picture(str(sf), Inches(1.5), Inches(1.2), width=Inches(10.3))
    footer(sl, 6, total)

    sl = blank(prs)
    title_bar(sl, '5. Kết quả đo tâm sao & E2E (d_th=2)', 'log_reconciliation_audit.json & benchmark_sim_hd1024_e2e.json')
    sl.shapes.add_picture(str(FIG / 'comparison_table.png'), Inches(0.5), Inches(1.15), width=Inches(12.2))
    bullets(sl, 0.7, 4.4, 12, 2.4, [
        f"500 khung {cam['width']}×{cam['height']}, GPU {s.get('device')}.",
        f"CoG: RMSE tb {cl['rmse_px_mean']:.4f} px · Recall {t2['classical']['recall_pct']:.1f}% · Precision {t2['classical']['precision_pct']:.1f}% · E2E 500/500 <40″ (tv {hd['classical']['attitude_error_arcsec']['median']:.2f}″, {hd['classical']['total_pipeline_ms']['median']:.1f} ms).",
        f"CNN: RMSE tb {nn['rmse_px_mean']:.4f} px · Recall {t2['cnn']['recall_pct']:.1f}% · Precision {t2['cnn']['precision_pct']:.1f}% ({t2['cnn']['false_positives_total']} FP) · E2E 498/500 <40″ (tv {hd['cnn']['attitude_error_arcsec']['median']:.2f}″, {hd['cnn']['total_pipeline_ms']['median']:.1f} ms).",
        f"Lóa mạnh {g['classical']['n_frames']} khung: CoG RMSE {g['classical']['rmse_px_mean']:.4f} px vs CNN {g['cnn']['rmse_px_mean']:.4f} px.",
    ], size=12)
    footer(sl, 7, total)

    sl = blank(prs)
    title_bar(sl, '6. Điểm sáng tạo — ảnh núi thật LOST', 'mount_st_helens_1.png · 4,2 mm · 4,1 µm · không phải ảnh nhóm chụp')
    if MOUNT_OVERLAY.is_file():
        sl.shapes.add_picture(str(MOUNT_OVERLAY), Inches(0.4), Inches(1.15), height=Inches(5.5))
    cnn_a = lost['modes']['cnn']
    cog_a = lost['modes']['classical']
    bullets(sl, 7.6, 1.3, 5.3, 5.5, [
        f"Đo centroid độc lập (bg_block=31): CoG {m['classical']['n_total']} điểm ({m['classical']['n_on_terrain']} núi/cây) vs CNN {m['cnn']['n_total']} ({m['cnn']['n_on_terrain']} núi/cây).",
        f"Pipeline (GlareMasker + bg_block=32→33): CoG tách {cog_a['n_detected']} điểm và bị chặn an toàn {cog_a['status']} [{cog_a['reject_code']}] (0% khóa sai).",
        f"CNN pipeline: {cnn_a['status']} ({cnn_a['n_matched']}/{cnn_a['n_detected']}, Δ {cnn_a['sep_deg_from_LOST']:.3f}° vs LOST, ~{cnn_a['pipeline_ms']/1000:.2f} s).",
        f"Seed 42 FAST: CoG {s42['classical']['attitude_error_arcsec']:.3f}″ vs CNN {s42['cnn']['attitude_error_arcsec']:.3f}″ — trên sim sạch CoG vẫn chính xác hơn.",
    ], size=12)
    footer(sl, 8, total)

    sl = blank(prs)
    title_bar(sl, '7. Trích dẫn Zhao et al.', 'arXiv:2404.19108 — số liệu TÁC GIẢ, không phải đo nhóm')
    if ZHAO_FLOW.is_file():
        sl.shapes.add_picture(str(ZHAO_FLOW), Inches(0.4), Inches(1.2), width=Inches(6.2))
    if ZHAO_STRAY.is_file():
        sl.shapes.add_picture(str(ZHAO_STRAY), Inches(6.9), Inches(1.2), width=Inches(5.8))
    bullets(sl, 0.5, 5.0, 12.3, 2.0, [
        'Nguồn: Zhao et al., arXiv:2404.19108 — flowchart (trái) · night+stray (phải).',
        'Table V: MobileUNet ≈ 0,020 s (~20 ms) trên RTX 2060M @ 640×480; Table VI: Coral TPU ≈ 266 ms.',
        'Table III: RMSE MobileUNet ≈ 0,1695 px vs CoG ≈ 0,6966 px (ảnh tổng hợp của tác giả).',
        f"Đo nhóm (RTX 5070, 1024×683, d_th=2): CoG {cl['rmse_px_mean']:.4f} px · CNN {nn['rmse_px_mean']:.4f} px.",
    ], size=11)
    footer(sl, 9, total)

    sl = blank(prs)
    title_bar(sl, '8. Kiến trúc & chạy thử')
    bullets(sl, 0.7, 1.3, 11.5, 5.5, [
        'camera → GlareMasker → centroid (CoG|CNN) → Pyramid/K-vector → _refine_inliers + SVD → quaternion 16 byte (0x00=LOST)',
        'CLI: python demo_star_tracker.py --mode fast --seed 42 --lookup --no-show',
        'Web: python app.py → UI tối giản + đối chiếu 3D bầu trời sao thực J2000 (BSC5) với ảnh gốc (mô phỏng trực quan trên PC)',
        'Benchmark: python scripts/benchmark_end_to_end.py --suites all && python scripts/reconcile_logs.py',
    ], size=15)
    footer(sl, 10, total)

    sl = blank(prs)
    title_bar(sl, '9. Giới hạn')
    bullets(sl, 0.7, 1.3, 11.5, 5.5, [
        'Demo laptop (RTX 5070 / CPU) — chưa kiểm chứng phần cứng bay, bức xạ hay ADCS vệ tinh.',
        f"Trên hd1024 sạch: CNN lệch miền (RMSE {nn['rmse_px_mean']:.4f} px, Precision {t2['cnn']['precision_pct']:.1f}%, {t2['cnn']['false_positives_total']} FP ở thr2).",
        'Mặt nạ núi/cây là heuristic; ảnh góc siêu rộng chưa hiệu chuẩn (NTNU 0006.png) trả về LOST an toàn.',
        f"E2E đã kiểm chứng trên 500 khung hd1024 (CoG tv {hd['classical']['attitude_error_arcsec']['median']:.2f}″) & 6 khung ảnh thật.",
    ], size=15)
    footer(sl, 11, total)

    sl = blank(prs)
    title_bar(sl, '10. FAQ')
    bullets(sl, 0.7, 1.3, 11.5, 5.5, [
        'Có AI không? — Mặc định CoG; CNN centroid tùy chọn công khai, không huấn luyện lại.',
        f"500 khung hd1024? — CoG 25.206/27.017 (Rec {t2['classical']['recall_pct']:.1f}%, Prec 100,0%, E2E 500/500 <40″) vs CNN 25.050/27.017 (Rec {t2['cnn']['recall_pct']:.1f}%, Prec {t2['cnn']['precision_pct']:.1f}%, E2E 498/500 <40″).",
        f"Ảnh núi LOST? — CNN giải {cnn_a['n_matched']}/{cnn_a['n_detected']} (Δ {cnn_a['sep_deg_from_LOST']:.3f}°); CoG bị chốt chặn từ chối an toàn LOST [{cog_a['reject_code']}].",
        'Đầu ra? — Quaternion J2000 16 byte (0x00 khi LOST). Catalog mặc định: Yale BSC5 V≤6.',
    ], size=14)
    footer(sl, 12, total)

    sl = blank(prs)
    title_bar(sl, 'Kết · Cảm ơn quý thầy cô')
    bullets(sl, 0.7, 1.4, 11.5, 5, [
        'Chốt chặn 0% False Lock · Đánh giá E2E 540 khung mô phỏng & ảnh thật hiệu chuẩn · Đối soát Log–Tài liệu–Slide.',
        'Hồ sơ & Báo cáo: AI2026_Ho-so-du-an_StarTracker.docx / BAO_CAO_CAI_TIEN_VONG_CHUNG_KET_CHANG_1.{md,docx,pdf}',
        'Đội: Hoàng Trần Đức Hải · Nguyễn Tiến · Mai Tạ Trúc Vy · Khoa Công nghệ thông tin — Trường Đại học Bách khoa, Đại học Đà Nẵng',
    ], size=15)
    footer(sl, 13, total)
    print(f'Reference baseline builder checked ({OUT.name}); run scripts/update_national_slides_and_docs.py for the full styled 17-slide deck.')


if __name__ == '__main__':
    build()
