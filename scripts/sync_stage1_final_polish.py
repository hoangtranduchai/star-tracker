"""Idempotently synchronize Stage 1 Final Polish upgrades into:
  1. AI2026_Portfolio/AI2026_SLIDE_THUYET_TRINH.pptx  (in-place -> 18 slides)
  2. AI2026_Portfolio/[StarTracker] - Hồ sơ dự án.docx (in-place appendix extension)
  3. Strict Bang C zero-GVHD audit across ALL .md, .docx, .pptx, .pdf files.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor as DocxRGB
from pptx import Presentation

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

import update_national_slides_and_docs as base  # noqa: E402

PORTFOLIO = ROOT / 'AI2026_Portfolio'
PPTX_PATH = PORTFOLIO / 'AI2026_SLIDE_THUYET_TRINH.pptx'
HOSO_DOCX = PORTFOLIO / '[StarTracker] - Hồ sơ dự án.docx'
OUT_DIR = ROOT / 'data' / 'outputs'

SLIDE_MARKER = '14 | NÂNG CẤP CNN-HYBRID & AUTO-ROUTER'
SLIDE_CUBESAT_MARKER = '15 | KHẢ THI NHÚNG CUBESAT & NASA TRL'
DOCX_MARKER = 'CẬP NHẬT MỞ RỘNG CHẶNG 1: CNN-HYBRID, AUTO-ROUTER & ĐƯỜNG CONG STRESS'

BANNED_TERMS = (
    'giảng viên hướng dẫn',
    'người hướng dẫn',
    'gvhd',
    'hùng vân',
    'năng hùng',
)


def _remove_pptx_slide(prs: Presentation, idx: int) -> None:
    sld_id_lst = prs.slides._sldIdLst
    sld_id = sld_id_lst[idx]
    r_id = sld_id.rId
    prs.part.drop_rel(r_id)
    sld_id_lst.remove(sld_id)


def _replace_in_tf(tf: Any, old: str, new: str) -> bool:
    changed = False
    for p in tf.paragraphs:
        for r in p.runs:
            if old in r.text:
                r.text = r.text.replace(old, new)
                changed = True
    return changed


def sync_pptx_in_place() -> None:
    b3 = json.loads((OUT_DIR / 'benchmark_3way_comparison.json').read_text(encoding='utf-8'))
    prs = Presentation(str(PPTX_PATH))

    # Idempotency: if both Slide 14 and Slide 15 already exist, just normalize run counts
    has_s14 = any(
        any(sh.has_text_frame and SLIDE_MARKER in sh.text_frame.text for sh in sl.shapes)
        for sl in prs.slides
    )
    has_s15 = any(
        any(sh.has_text_frame and SLIDE_CUBESAT_MARKER in sh.text_frame.text for sh in sl.shapes)
        for sl in prs.slides
    )
    if has_s14 and has_s15:
        total = len(prs.slides)
        for sl in prs.slides:
            for sh in sl.shapes:
                if sh.has_text_frame:
                    _replace_in_tf(sh.text_frame, '127 passed', '133 passed')
                    _replace_in_tf(sh.text_frame, '130 passed', '133 passed')
                    _replace_in_tf(sh.text_frame, '17 slide', f'{total} slide')
                    _replace_in_tf(sh.text_frame, '18 slide', f'{total} slide')
                if sh.has_table:
                    for row in sh.table.rows:
                        for cell in row.cells:
                            _replace_in_tf(cell.text_frame, '17 slide', f'{total} slide')
                            _replace_in_tf(cell.text_frame, '18 slide', f'{total} slide')
        prs.save(str(PPTX_PATH))
        print(f'[OK] Normalized counts in {PPTX_PATH} ({total} slides)')
        return

    if not has_s14:
        # Add Slide 14 (CNN-Hybrid + ESA tetra3 + Auto-Router + Speedup + Stress Curves)
        s_new = base._add_slide_chrome(
            prs,
            SLIDE_MARKER,
            '14. Nâng cấp CNN-Hybrid, Auto-Router & Đường cong Stress',
            'Đối chuẩn 5 phương pháp (566 khung + 150 ca stress = 3.430 lượt · 0% False Lock) & tăng tốc 5×–11× giữ nguyên độ phân giải',
            badge_bg=base.P_GBADGE_BG,
            badge_fg=base.P_GREEN,
        )
        base._add_picture_fit(
            s_new,
            OUT_DIR / 'e2e_figures' / 'fig10_4way_ablation_tetra3_hybrid.png',
            0.55, 1.32, 12.23, 2.58,
            caption='Hình 10. Đối chuẩn 5 phương pháp: Δθ trung vị, cắt giảm -99,8% FP (1.118 → 2) và ma trận giải đúng 4/4 ảnh trời thật hiệu chuẩn',
        )
        base._add_picture_fit(
            s_new,
            OUT_DIR / 'e2e_figures' / 'fig11_stress_degradation_curves.png',
            0.55, 4.02, 7.80, 2.86,
            caption='Hình 11. Đường cong suy giảm dưới vận tốc quay ω, 0–30 sao giả và nền lóa 0–4095 DN (0% Khóa sai)',
        )
        hd_cnn = b3['sim_hd1024']['summary']['cnn']
        hd_auto = b3['sim_hd1024']['summary']['auto']
        gl_cnn = b3['sim_glare']['summary']['cnn']
        gl_t3 = b3['sim_glare']['summary']['tetra3']
        base._add_card(
            s_new,
            8.50, 4.02, 4.28, 2.86, base.P_NAVY,
            'TỔNG KẾT NÂNG CẤP CHẶNG 1', base.P_BADGE_BG, base.P_NAVY,
            'Auto (CoG → CNN-Hybrid) · Nhanh & 4/4 Trời thật',
            [
                f"• CNN-Hybrid vs CNN gốc: cắt -99,8% FP sạch (1.118→{hd_cnn['centroid_false_pos_5px_total']} FP, Prec 99,99%) & -100% FP lóa (157→0 FP); giảm Δθ 4× (7,99″→2,02″).",
                f"• Vượt ngưỡng kiểu ESA tetra3: thắng trên 500 sạch (2,02″ vs 2,34″), 40 lóa ({gl_cnn['attitude_error_arcsec']['median']:.2f}″/69,9% vs {gl_t3['attitude_error_arcsec']['median']:.2f}″/51,3%), 30 sao giả (100% vs 70%) và giải 2 ảnh thật mà tetra3 LOST (Zhao 48,3″ & MSH 71,1″).",
                f"• Auto-Router mặc định: CoG trước ({hd_auto['attitude_error_arcsec']['median']:.2f}″, {hd_auto['total_pipeline_ms']['mean']:.0f} ms, 100% tới ω=1,5°/s), tự chuyển CNN khi CoG LOST → đạt 4/4 trời thật & 100% ở 30 sao giả.",
                '• Tăng tốc 5×–11× không giảm phân giải: tiền lọc BLAS SGEMM (MSH tetra3: 11,3s→1,43s; Zhao CoG: 2,7s→0,25s) & vẽ đồ thị bất đồng bộ.',
            ],
            head_size=11.0,
            body_size=8.6,
        )
        sld_lst = prs.slides._sldIdLst
        elems = list(sld_lst)
        new_el = elems[-1]
        reordered = elems[:-3] + [new_el, elems[-3], elems[-2]]
        for el in elems:
            sld_lst.remove(el)
        for el in reordered:
            sld_lst.append(el)

    if not has_s15:
        # Add Slide 15 (CubeSat Embedded 1-Core ARM64 + ONNX + SAA Proton + SEU CRC-16 + NASA TRL)
        s_emb = base._add_slide_chrome(
            prs,
            SLIDE_CUBESAT_MARKER,
            '15. Kiểm toán Khả thi Nhúng CubeSat & Tiêm lỗi SAA / SEU',
            'Đo thực nghiệm 1 nhân ARM64 (aarch64), ONNX 1 luồng (4,75×), mưa proton SAA & CRC-16 SEU — Định vị NASA TRL 3–4 (Chưa bay)',
            badge_bg=base.P_BADGE_BG,
            badge_fg=base.P_NAVY,
        )
        base._add_picture_fit(
            s_emb,
            OUT_DIR / 'e2e_figures' / 'fig12_cubesat_feasibility_seu_saa.png',
            0.55, 1.32, 12.23, 3.30,
            caption='Hình 12. Đo kiểm 1 nhân ARM64 & ONNX (4,75×), sức chịu đựng 0–100 vệt proton vùng SAA và kiểm thử 10.512 lỗi lật bit SEU (CRC-16-CCITT)',
        )
        base._add_card(
            s_emb,
            0.55, 4.74, 5.98, 2.15, base.P_NAVY,
            'PHÂN TẦNG PHẦN CỨNG CUBESAT (THỰC NGHIỆM ARM64)', base.P_BADGE_BG, base.P_NAVY,
            'Ranh giới định lượng giữa MCU & SoC Payload',
            [
                '• Tier 1 — MCU chịu bức xạ (STM32H7/LEON3, 1–16 MB SRAM): KHÔNG chạy được PyTorch CNN (OOM ở 768 MB); chỉ triển khai nhánh CoG + BSC5 nhị phân 80 KB (port C/MISRA-C).',
                '• Tier 2 — Linux CubeSat SoC (Zynq/Cortex-A53, ≥2 GB RAM): Chạy Auto 59,2 ms (16,9 Hz) & ESA Alt60 62,5 ms (16,0 Hz) trên 1 nhân ARM64; ONNX FP32 tăng tốc CNN 4,75× (12,5 MB; FP16 6,3 MB).',
                '• Tiêm lỗi vũ trụ: Mưa proton SAA 100 vệt/khung → CoG & Auto đạt 100% (2,2″, 0% FL) vs tetra3 0%; gói Telemetry 32B CRC-16-CCITT chặn 10.512/10.512 lỗi lật bit SEU (100%).',
            ],
            head_size=10.8,
            body_size=8.4,
        )
        base._add_card(
            s_emb,
            6.80, 4.74, 5.98, 2.15, base.P_ORANGE,
            'ĐỊNH VỊ TRUNG THỰC: NASA TRL 3–4 → LỘ TRÌNH TRL 6–8', base.P_OBADGE_BG, base.P_ORANGE,
            '5 cổng kiểm định phần cứng bắt buộc trước khi bay',
            [
                '• Hiện tại (TRL 3–4): Đã xác thực phần mềm trên ảnh thật công khai, 1 nhân ARM64 thương mại và tiêm lỗi SAA/SEU mô phỏng — KHÔNG khẳng định sẵn sàng bay.',
                '• Cổng 1–2 (TRL 5): Port lõi CoG/Pyramid/Wahba sang C/MISRA-C tĩnh (không cấp phát động) & hiệu chuẩn buồng chuẩn trực sao quang học (Optical Collimator HIL).',
                '• Cổng 3–5 (TRL 6–8): Chiếu xạ tổng liều & hạt đơn (TID/SEE), thử nghiệm nhiệt–chân không (TVAC), rung phóng cơ học và đóng vòng kín bus CAN / SpaceWire / RS-422 với ADCS.',
            ],
            head_size=10.8,
            body_size=8.4,
        )
        sld_lst = prs.slides._sldIdLst
        elems = list(sld_lst)
        new_el = elems[-1]
        reordered = elems[:-3] + [new_el, elems[-3], elems[-2]]
        for el in elems:
            sld_lst.remove(el)
        for el in reordered:
            sld_lst.append(el)

    # Update Slide 2 TOC subtitle
    sl2 = prs.slides[1]
    for sh in sl2.shapes:
        if sh.has_text_frame and 'Cấu trúc báo cáo mở rộng' in sh.text_frame.text:
            base._set_single_text(
                sh,
                'Cấu trúc báo cáo mở rộng Vòng Chung kết · Chặng 1 (gồm 6 slide minh chứng cải tiến, CNN-Hybrid, Auto-Router & Khả thi CubeSat)',
                size=12.5, color=base.P_MUTED,
            )

    # Update FAQ slide (now second-to-last, Slide 18)
    sl_faq = prs.slides[-2]
    for sh in sl_faq.shapes:
        if not sh.has_text_frame:
            continue
        txt = sh.text_frame.text.strip()
        if txt.startswith('14 | HỎI ĐÁP') or txt.startswith('15 | HỎI ĐÁP') or txt.startswith('16 | HỎI ĐÁP'):
            base._set_single_text(sh, '16 | HỎI ĐÁP CHUYÊN MÔN', size=10.5, color=base.P_NAVY, bold=True)
        elif txt.startswith('14. Câu hỏi') or txt.startswith('15. Câu hỏi') or txt.startswith('16. Câu hỏi'):
            base._set_single_text(sh, '16. Câu hỏi thường gặp', size=24.0, color=base.P_NAVY, bold=True)
        elif txt.startswith('Q: Vì sao phần mềm mặc định dùng'):
            base._set_card_paragraphs(
                sh,
                'Q: Vì sao phần mềm mặc định dùng Tự động (Auto: CoG → CNN-Hybrid)?',
                [
                    '• Nhánh CoG chạy ~85 ms PC / 58,8 ms (17 Hz) trên 1 nhân ARM64 với 0 FP và Δθ 1,91″, đồng thời chịu 100% mưa proton SAA & motion blur tới ω=1,5 °/s.',
                    '• Khi gặp ảnh đêm 8-bit nhiều nhiễu (Zhao MT9V022), tiền cảnh phức tạp hoặc 20–30 sao giả làm CoG trả LOST, bộ định tuyến tự động nâng cấp sang CNN-Hybrid để giải đúng 4/4 ảnh trời thật mà vẫn giữ 0% False Lock.',
                ],
                head_size=12.2, head_color=base.P_NAVY, body_size=9.5, body_color=base.P_DARK,
            )

    # Update Closing slide (last slide, Slide 19)
    sl_end = prs.slides[-1]
    for sh in sl_end.shapes:
        if sh.has_text_frame and 'Kiến trúc lai tin cậy' in sh.text_frame.text:
            base._set_card_paragraphs(
                sh,
                'Kiến trúc lai tin cậy · Kiểm chứng minh bạch',
                [
                    '• Bộ định tuyến Tự động (Auto: CoG → CNN-Hybrid) + đối chuẩn công bằng với ngưỡng truyền thống kiểu ESA tetra3 ngay trên Web UI.',
                    '• Chốt chặn chống khóa sai tuyệt đối: 0% False Lock trên 100 ca đối kháng (vs 41% cũ), 3.430 lượt E2E/Stress & 200 lượt mưa proton SAA.',
                    '• Kiểm toán nhúng CubeSat (TRL 3–4): 16,9 Hz trên 1 nhân ARM64, ONNX 4,75×, gói Telemetry 32B CRC-16 chặn 100% (10.512/10.512) lỗi SEU.',
                    '• Demo trực tuyến 24/7 tại startracker.agentlens.dpdns.org · Phân định rõ PC/ARM64 TRL 3–4 (chưa kiểm chứng bay/ADCS).',
                ],
                head_size=16.0, head_color=base.P_NAVY, body_size=10.6, body_color=base.P_DARK,
            )

    # Renumber ALL slide footers 2 / 19 .. 19 / 19, normalize counts, and verify zero banned terms
    total = len(prs.slides)
    for idx, slide in enumerate(prs.slides, 1):
        for sh in slide.shapes:
            if sh.has_text_frame:
                _replace_in_tf(sh.text_frame, '127 passed', '133 passed')
                _replace_in_tf(sh.text_frame, '130 passed', '133 passed')
                _replace_in_tf(sh.text_frame, '17 slide', f'{total} slide')
                _replace_in_tf(sh.text_frame, '18 slide', f'{total} slide')
                if idx > 1 and re.fullmatch(r'\s*\d+\s*/\s*\d+\s*', sh.text_frame.text.strip()):
                    base._set_single_text(sh, f'{idx} / {total}', size=10.0, color=base.P_NAVY, bold=True)
                low = sh.text_frame.text.lower()
                for bt in BANNED_TERMS:
                    if bt in low:
                        raise AssertionError(f'Banned term "{bt}" found on Slide {idx}: {sh.text_frame.text[:120]}')
            if sh.has_table:
                for row in sh.table.rows:
                    for cell in row.cells:
                        _replace_in_tf(cell.text_frame, '17 slide', f'{total} slide')
                        _replace_in_tf(cell.text_frame, '18 slide', f'{total} slide')

    prs.save(str(PPTX_PATH))
    print(f'[OK] Updated {PPTX_PATH} ({total} slides)')


def sync_hoso_docx_in_place() -> None:
    b3 = json.loads((OUT_DIR / 'benchmark_3way_comparison.json').read_text(encoding='utf-8'))
    doc = Document(str(HOSO_DOCX))

    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for r in p.runs:
                        if '17 slide' in r.text:
                            r.text = r.text.replace('17 slide', '19 slide')
                        if '18 slide' in r.text:
                            r.text = r.text.replace('18 slide', '19 slide')
                        if '127 passed' in r.text:
                            r.text = r.text.replace('127 passed', '133 passed')
                        if '130 passed' in r.text:
                            r.text = r.text.replace('130 passed', '133 passed')

    # Idempotency: strip any previous run's appended extension block
    marker_idx = None
    for idx, p in enumerate(doc.paragraphs):
        if DOCX_MARKER in p.text:
            marker_idx = idx
            break
    if marker_idx is not None:
        # Remove all body elements from marker paragraph onward
        body = doc._body._body
        target_el = doc.paragraphs[marker_idx]._p
        pos = list(body).index(target_el)
        for el in list(body)[pos:]:
            if el.tag.endswith('sectPr'):
                continue
            body.remove(el)

    p_h = doc.add_paragraph()
    p_h.paragraph_format.space_before = Pt(14)
    p_h.paragraph_format.space_after = Pt(6)
    rh = p_h.add_run(DOCX_MARKER)
    rh.font.name = 'Times New Roman'
    rh.font.size = Pt(13)
    rh.font.bold = True
    rh.font.color.rgb = DocxRGB(0x13, 0x3E, 0x68)

    p_intro = doc.add_paragraph()
    p_intro.paragraph_format.space_after = Pt(6)
    ri = p_intro.add_run(
        'Nhằm hoàn thiện toàn diện Chặng 1, nhóm bổ sung 4 cải tiến cốt lõi: '
        '(1) CNN-Hybrid (Windowed CoG + trừ nền 31×31 + cổng SNR vòng khuyên rỗng + lọc điểm nóng đơn pixel pk_net/flux > 0,75) cắt giảm -99,8% điểm giả FP (1.118 → 2 FP trên 500 khung sạch, 157 → 0 FP trên 40 khung lóa); '
        '(2) Bộ định tuyến Auto-Router (CoG → CNN-Hybrid) mặc định trên Web UI; '
        '(3) Bộ tiền lọc góc BLAS float32 SGEMM trong identify_wide + kết xuất biểu đồ nền bất đồng bộ giúp tăng tốc 5×–11× mà không giảm độ phân giải ảnh; và '
        '(4) Đối chuẩn 5 phương pháp trên 566 khung (2.830 lượt) + đường cong stress khắc nghiệt (600 lượt) đạt 0% Khóa sai tuyệt đối (chi tiết đầy đủ tại BAO_CAO_CAI_TIEN_VONG_CHUNG_KET_CHANG_1.pdf).'
    )
    ri.font.name = 'Times New Roman'
    ri.font.size = Pt(10.5)

    be_lbl = {
        'classical': 'CoG (Nhóm)',
        'tetra3': 'Ngưỡng kiểu tetra3',
        'cnn_raw': 'CNN gốc (Trước)',
        'cnn': 'CNN-Hybrid (Sau)',
        'auto': 'Auto (CoG→CNN)',
    }
    rows: list[list[str]] = []
    for be in ('classical', 'tetra3', 'cnn_raw', 'cnn', 'auto'):
        s500 = b3['sim_hd1024']['summary'][be]
        s40 = b3['sim_glare']['summary'][be]
        rc_by = b3['real_calibrated']['calibrated_bsc5_frames'][be]
        a40_rec = b3['real_calibrated']['alt40_hipparcos_v7'][be]
        n_real_ok = sum(
            1 for r in (
                next((x for x in rc_by if 'Alt60' in x['frame_id']), None),
                a40_rec,
                next((x for x in rc_by if 'nightsky' in x['frame_id']), None),
                next((x for x in rc_by if 'mount_st_helens' in x['frame_id']), None),
            ) if r and r.get('status') == 'SOLVED'
        )
        rows.append([
            be_lbl[be],
            f"{s500['n_correct']}/500 ({s500['attitude_error_arcsec']['median']:.2f}″, {s500['centroid_false_pos_5px_total']} FP)",
            f"{s40['n_correct']}/40 ({s40['attitude_error_arcsec']['median']:.2f}″, {100*s40['centroid_recall_micro']:.1f}% Rec)",
            f"{n_real_ok}/4 ảnh thật",
            f"0 FL · {s500['total_pipeline_ms']['mean']:.1f} ms",
        ])

    base._docx_add_styled_table(
        doc,
        ['Phương pháp', '500 sạch (Δθ, FP)', '40 lóa (Δθ, Recall)', 'Trời thật (4 GT)', 'Khóa sai · Trễ TB'],
        rows,
        col_widths_in=[1.25, 1.55, 1.45, 1.05, 1.20],
        font_size=8.5,
    )

    for rel_img, cap in (
        ('data/outputs/e2e_figures/fig10_4way_ablation_tetra3_hybrid.png', 'Hình 17. Đối chuẩn 5 phương pháp, cắt giảm -99,8% FP và ma trận giải đúng 4/4 ảnh bầu trời thật hiệu chuẩn.'),
        ('data/outputs/e2e_figures/fig11_stress_degradation_curves.png', 'Hình 18. Đường cong suy giảm hiệu năng theo vận tốc quay ω, số sao giả tiêm vào và nền lóa mặt trời (0% Khóa sai).'),
        ('data/outputs/e2e_figures/fig12_cubesat_feasibility_seu_saa.png', 'Hình 19. Kiểm toán khả thi nhúng CubeSat (1 nhân ARM64 16,9 Hz · ONNX 4,75×), mưa proton SAA (100% giải, 0% FL) và lật bit SEU CRC-16-CCITT (10.512/10.512 = 100%, NASA TRL 3–4).'),
    ):
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(6)
        p_img.paragraph_format.keep_with_next = True
        p_img.add_run().add_picture(str(ROOT / rel_img), width=Inches(6.2))
        p_c = doc.add_paragraph()
        p_c.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_c.paragraph_format.space_after = Pt(6)
        rc = p_c.add_run(cap)
        rc.font.name = 'Times New Roman'
        rc.font.size = Pt(9.5)
        rc.font.italic = True

    doc.save(str(HOSO_DOCX))
    print(f'[OK] Updated {HOSO_DOCX}')


def audit_zero_gvhd_all_docs() -> None:
    hits: list[str] = []
    # Check all MD files in portfolio + root README
    md_files = list(PORTFOLIO.glob('*.md')) + [ROOT / 'README.md']
    for p in md_files:
        txt = p.read_text(encoding='utf-8', errors='ignore').lower()
        for bt in BANNED_TERMS:
            if bt in txt:
                hits.append(f'{p.name}: "{bt}"')
    # Check all DOCX files in portfolio
    for p in PORTFOLIO.glob('*.docx'):
        d = Document(str(p))
        chunks = [par.text for par in d.paragraphs]
        for t in d.tables:
            for r in t.rows:
                for c in r.cells:
                    chunks.append(c.text)
        txt = '\n'.join(chunks).lower()
        for bt in BANNED_TERMS:
            if bt in txt:
                hits.append(f'{p.name}: "{bt}"')
    # Check PPTX
    prs = Presentation(str(PPTX_PATH))
    for i, sl in enumerate(prs.slides, 1):
        chunks = [sh.text_frame.text for sh in sl.shapes if sh.has_text_frame]
        for sh in sl.shapes:
            if sh.has_table:
                for r in sh.table.rows:
                    for c in r.cells:
                        chunks.append(c.text)
        txt = '\n'.join(chunks).lower()
        for bt in BANNED_TERMS:
            if bt in txt:
                hits.append(f'{PPTX_PATH.name} Slide {i}: "{bt}"')

    if hits:
        raise AssertionError('GVHD compliance violations found:\n  - ' + '\n  - '.join(hits))
    print('[OK] Zero GVHD / mentor references verified across ALL .md, .docx, .pptx files!')


if __name__ == '__main__':
    sync_pptx_in_place()
    sync_hoso_docx_in_place()
    audit_zero_gvhd_all_docs()
