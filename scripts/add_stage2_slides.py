"""Idempotently add 3 Stage 2 Hackathon & Defense slides and sync cross-slide metrics in AI2026_SLIDE_THUYET_TRINH.pptx."""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor as PptxRGB
from pptx.enum.text import PP_ALIGN
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.opc.packuri import PackURI
from pptx.util import Inches

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))

import update_national_slides_and_docs as base  # noqa: E402

PPTX_PATH = ROOT / 'AI2026_Portfolio' / 'AI2026_SLIDE_THUYET_TRINH.pptx'
EV_DIR = ROOT / 'AI2026_Portfolio' / 'stage2_evidence'
STAGE2_MARKER = 'CHẶNG 2 · HACKATHON'


def _slide_has_marker(slide) -> bool:
    for sh in slide.shapes:
        if sh.has_text_frame and STAGE2_MARKER in sh.text_frame.text:
            return True
    return False


def _remove_slide(prs: Presentation, idx: int) -> None:
    sld_id = prs.slides._sldIdLst[idx]
    r_id = sld_id.rId
    prs.part.drop_rel(r_id)
    prs.slides._sldIdLst.remove(sld_id)


def _clear_slide(slide) -> None:
    """Remove all shapes and non-layout relationships from a slide so it can be cleanly rebuilt in-place."""
    sp_tree = slide.shapes._spTree
    for child in list(sp_tree):
        if child.tag.endswith('}nvGrpSpPr') or child.tag.endswith('}grpSpPr'):
            continue
        sp_tree.remove(child)
    for r_id, rel in list(slide.part.rels.items()):
        if rel.reltype != RT.SLIDE_LAYOUT:
            slide.part.drop_rel(r_id)


def _populate_slide_chrome(
    sl,
    badge_txt: str,
    title_txt: str,
    sub_txt: str,
    badge_bg: PptxRGB = base.P_BADGE_BG,
    badge_fg: PptxRGB = base.P_NAVY,
):
    base._add_rect(sl, 0.0, 0.0, 13.333, 7.5, base.P_BG)
    base._add_rect(sl, 0.0, 0.0, 13.333, 0.05, base.P_NAVY)
    base._add_badge(sl, 0.60, 0.18, 3.85, 0.26, badge_txt, bg=badge_bg, fg=badge_fg)

    tb_t = sl.shapes.add_textbox(Inches(0.60), Inches(0.49), Inches(12.13), Inches(0.42))
    base._set_single_text(tb_t, title_txt, size=22.0, color=base.P_NAVY, bold=True)

    tb_s = sl.shapes.add_textbox(Inches(0.60), Inches(0.90), Inches(12.13), Inches(0.28))
    base._set_single_text(tb_s, sub_txt, size=12.0, color=base.P_MUTED, bold=False)

    base._add_rect(sl, 0.60, 1.20, 12.13, 0.015, base.P_LINE)
    base._add_rect(sl, 0.60, 6.96, 12.13, 0.015, base.P_LINE)

    tb_f = sl.shapes.add_textbox(Inches(0.60), Inches(7.02), Inches(10.00), Inches(0.35))
    base._set_single_text(
        tb_f,
        'Trường Đại học Bách khoa, Đại học Đà Nẵng — Khoa Công nghệ thông tin',
        size=10.0,
        color=base.P_MUTED,
        bold=False,
    )

    tb_p = sl.shapes.add_textbox(Inches(10.73), Inches(7.02), Inches(2.00), Inches(0.35))
    tb_p.text_frame.paragraphs[0].alignment = PP_ALIGN.RIGHT
    base._set_single_text(tb_p, '0 / 0', size=10.0, color=base.P_NAVY, bold=True)
    return sl


def _patch_slide_text_replace(slide, replacements: list[tuple[str, str]]) -> None:
    """Replace exact substrings in text shapes and table cells while preserving paragraph/run styling."""
    for sh in slide.shapes:
        if sh.has_text_frame:
            for p in sh.text_frame.paragraphs:
                full = p.text
                new_full = full
                for old, new in replacements:
                    if old in new_full:
                        new_full = new_full.replace(old, new)
                if new_full != full:
                    if p.runs:
                        p.runs[0].text = new_full
                        for r in p.runs[1:]:
                            r.text = ''
                    else:
                        p.text = new_full
        if sh.has_table:
            for row in sh.table.rows:
                for cell in row.cells:
                    for p in cell.text_frame.paragraphs:
                        full = p.text
                        new_full = full
                        for old, new in replacements:
                            if old in new_full:
                                new_full = new_full.replace(old, new)
                        if new_full != full:
                            if p.runs:
                                p.runs[0].text = new_full
                                for r in p.runs[1:]:
                                    r.text = ''
                            else:
                                p.text = new_full


def _sync_legacy_slides(prs: Presentation) -> None:
    """Keep Slides 2, 9, 12, 15, 21, and 22 100% consistent with the 22-slide hardened Stage 2 deck."""
    # Slide 2 (Mục lục): reflect Chặng 1 & Chặng 2 (22 slides)
    if len(prs.slides) >= 2:
        s_toc = prs.slides[1]
        for sh in s_toc.shapes:
            if not sh.has_text_frame:
                continue
            txt = sh.text_frame.text.strip()
            if txt.startswith('Cấu trúc báo cáo mở rộng'):
                base._set_single_text(
                    sh,
                    'Cấu trúc báo cáo mở rộng Vòng Chung kết · Chặng 1 & Chặng 2 (22 slide: Chốt chặn False Lock, CNN-Hybrid, CubeSat, Tái lập 13/13 SHA-256 & Kiểm soát Ảnh)',
                    size=11.0,
                    color=base.P_MUTED,
                    bold=False,
                )
            elif 'Đối soát Log–Slide' in txt or 'Chặng 2 (Slide 18–20' in txt:
                base._set_single_text(
                    sh,
                    'Chặng 2 (Slide 18–20: 13/13 SHA-256 LF, Fallback CoG, UUID4/TTL/st_sid, 151 test) & Hỏi đáp',
                    size=12.0,
                    color=base.P_DARK,
                    bold=False,
                )

    # Slide 9: nudge both top image captions down from y=3.90 to y=4.01 to eliminate 0.08" overlap with Picture 8 (bottom=3.98")
    if len(prs.slides) >= 9:
        s9 = prs.slides[8]
        for sh in s9.shapes:
            if sh.has_text_frame:
                txt = sh.text_frame.text.strip()
                if txt in ('Sơ đồ MobileUNet (Zhao et al.)', 'Ánh sáng lạc ban đêm (Stray Light)'):
                    sh.top = Inches(4.01)

    # Slide 12: update 133 passed -> 151 passed, 1 skipped (17 test Chặng 2)
    if len(prs.slides) >= 12:
        s12 = prs.slides[11]
        _patch_slide_text_replace(
            s12,
            [
                ('trong bộ 133 passed.', 'trong bộ 151 passed, 1 skipped (17 test Chặng 2).'),
                ('trong bộ 144 passed.', 'trong bộ 151 passed, 1 skipped (17 test Chặng 2).'),
            ],
        )

    # Slide 15: update 19 slide -> 22 slide in Table R6 and TextBox 13
    if len(prs.slides) >= 15:
        s15 = prs.slides[14]
        _patch_slide_text_replace(
            s15,
            [
                ('Toàn bộ 19 slide & .md/.docx', 'Toàn bộ 22 slide & .md/.docx'),
                ('hồ sơ và 19 slide.', 'hồ sơ và 22 slide.'),
            ],
        )

    # Slide 21 (Q3): add concise 1-line bridge note on Mount St. Helens CoG (nominal LOST vs calibrated SOLVED 83/106, 49.51″)
    if len(prs.slides) >= 21:
        s21 = prs.slides[20]
        for sh in s21.shapes:
            if sh.has_text_frame and 'Mạng CNN chứng minh giá trị ở đâu trên ảnh núi thật?' in sh.text_frame.text:
                base._set_card_paragraphs(
                    sh,
                    'Q: Mạng CNN chứng minh giá trị ở đâu trên ảnh núi thật?',
                    [
                        '• Mặt nạ địa hình độc lập: CNN chỉ 1 điểm trên núi/cây vs CoG 25 điểm.',
                        '• Quang học danh nghĩa (Chặng 1): CNN giải 54/79 (~2,76 s, Δ 0,034° vs LOST); CoG (106 điểm bị tạp địa hình & méo) bị chặn an toàn LOST [INSUFFICIENT_INLIER_PAIRS].',
                        '• Quang học hiệu chuẩn rộng k1/k2 & tìm rộng mới: CoG giải SOLVED 83/106 (49,51″), CNN-Hybrid giải 72/77 (71,13″).',
                    ],
                    head_size=11.5,
                    head_color=base.P_NAVY,
                    body_size=9.5,
                    body_color=base.P_DARK,
                )

    # Slide 22 (Tổng kết): add Chặng 2 summary bullet cleanly inside left technical card
    if len(prs.slides) >= 22:
        s22 = prs.slides[21]
        for sh in s22.shapes:
            if sh.has_text_frame and 'Kiến trúc lai tin cậy' in sh.text_frame.text:
                base._set_card_paragraphs(
                    sh,
                    'Kiến trúc lai tin cậy · Kiểm chứng minh bạch (Chặng 1 & 2)',
                    [
                        '• Bộ định tuyến Tự động (Auto: CoG → CNN-Hybrid) + đối chuẩn công bằng với ngưỡng truyền thống ESA tetra3 ngay trên Web UI.',
                        '• Chống khóa sai tuyệt đối: 0% False Lock trên 100 ca đối kháng (vs 41% cũ), 3.430 lượt E2E/Stress & 200 lượt mưa proton SAA.',
                        '• Kiểm toán nhúng CubeSat (TRL 3–4): 16,9 Hz trên 1 nhân ARM64, ONNX 4,8×, Telemetry 32B CRC-16 chặn 100% (10.512/10.512) lỗi SEU.',
                        '• Chặng 2 (Slide 18–20): 13/13 SHA-256 LF (36,02 MiB), chặn tệp hỏng trước torch.load, 0% fallback ngầm, UUID4/TTL/st_sid xóa trả 404 & 151/151 pytest PASS.',
                        '• Demo 24/7 tại startracker.agentlens.dpdns.org · Phạm vi PC/ARM64 TRL 3–4 (chưa kiểm chứng bay/ADCS).',
                    ],
                    head_size=12.0,
                    head_color=base.P_NAVY,
                    body_size=9.4,
                    body_color=base.P_DARK,
                )


def add_stage2_slides() -> int:
    prs = Presentation(str(PPTX_PATH))

    existing_s2 = [i for i, sl in enumerate(prs.slides) if _slide_has_marker(sl)]
    if len(existing_s2) == 3:
        # Rebuild the 3 existing Stage 2 slides in-place: zero partname collisions, zero orphan rels.
        s1, s2, s3 = (prs.slides[i] for i in existing_s2)
        for sl in (s1, s2, s3):
            _clear_slide(sl)
        reordered = False
        insert_pos = existing_s2[0]
    else:
        for i in reversed(existing_s2):
            _remove_slide(prs, i)
        # Compact remaining slide partnames so add_slide() never collides with slide21/slide22
        for k, sl in enumerate(prs.slides, 1):
            sl.part.partname = PackURI(f'/ppt/slides/slide{k}.xml')
        base_count = len(prs.slides)
        s1 = prs.slides.add_slide(prs.slide_layouts[6])
        s2 = prs.slides.add_slide(prs.slide_layouts[6])
        s3 = prs.slides.add_slide(prs.slide_layouts[6])
        reordered = True
        insert_pos = max(0, base_count - 2)

    # ---------- SLIDE S2-1 (Slide 18): Full Pipeline & Image Data Control Architecture ----------
    _populate_slide_chrome(
        s1,
        f'{STAGE2_MARKER} · KIẾN TRÚC TỔNG THỂ',
        'Kiến trúc Pipeline J2000 & Kiểm soát Dữ liệu Ảnh (Chặng 2)',
        'Khép kín 3 tầng: Gói 13/13 SHA-256 LF & Upload UUID4/st_sid → Auto-Router + Chặn tệp hỏng trước torch.load → 0% False Lock & Nhật ký JSONL',
        badge_bg=base.P_OBADGE_BG,
        badge_fg=base.P_ORANGE,
    )
    arch_png = EV_DIR / 'stage2_pipeline_architecture.png'
    base._add_picture_fit(s1, arch_png, 0.45, 1.30, 12.43, 4.92)
    base._add_rect(s1, 0.45, 6.30, 12.43, 0.50, base.P_BADGE_BG, border=base.P_NAVY)
    tb_f1 = s1.shapes.add_textbox(Inches(0.60), Inches(6.35), Inches(12.13), Inches(0.40))
    base._set_single_text(
        tb_f1,
        'Điểm chốt Chặng 2: (1) 13/13 SHA-256 LF (Linux/macOS/Win) & chặn tệp hỏng trước torch.load  |  (2) UUID4 + meta.json + st_sid & chặn /output/*.jsonl  |  (3) 151 pytest PASS (17 test Chặng 2).',
        size=9.6,
        color=base.P_NAVY,
        bold=True,
    )

    # ---------- SLIDE S2-2 (Slide 19): Standalone Reproducibility Bundle & Clean-Clone Proof ----------
    _populate_slide_chrome(
        s2,
        f'{STAGE2_MARKER} · GÓI TÁI LẬP ĐỘC LẬP',
        'Đóng gói 13/13 Tệp SHA-256 (36,02 MiB) & Tái lập Bản Clone Sạch',
        'Chuẩn hóa .gitattributes LF (PASS 13/13 Linux/macOS/Windows) · Đủ checkpoint (17,71 MiB / 18,57 MB), 6 ảnh thật hiệu chuẩn, catalog & benchmark',
        badge_bg=base.P_BADGE_BG,
        badge_fg=base.P_NAVY,
    )
    rows_cc = [
        ['Kịch bản trên git clone sạch', 'Chế độ thực thi', 'Kết quả / Sai số 3-DOF'],
        ['verify_repro_bundle / sha256sum', 'SHA-256 LF (Linux/Win)', 'PASS 13/13 · 36,02 MiB (37,77 MB)'],
        ['Seed 42 FAST (Auto)', 'auto → classical', 'SOLVED · 36 sao · Δθ 0,45″ (93,6 ms)'],
        ['ESA Alt60 16-bit (Auto)', 'auto → classical', 'SOLVED · 9 sao · Δθ 2,26″ (72,4 ms)'],
        ['Zhao MT9V022 8-bit (Auto)', 'auto → cnn_hybrid', 'SOLVED · 8 sao · Δθ 48,26″'],
        ['Mount St. Helens (CNN)', 'cnn → cnn_hybrid', 'SOLVED · 72 sao · Δθ 71,13″'],
        ['Fallback (CNN/Auto/Compare)', '→ classical [FALLBACK]', 'Chặn 1-byte lệch & ghi execution_log'],
        ['benchmark_3way --real-only', '5 pp × 6 ảnh thật + 20 stress', 'PASS · 0,0% False Lock (86,5 s)'],
    ]
    tbl_shape = s2.shapes.add_table(len(rows_cc), 3, Inches(0.45), Inches(1.30), Inches(6.25), Inches(3.10))
    tbl = tbl_shape.table
    col_ws = (2.15, 1.85, 2.25)
    for ci, cw in enumerate(col_ws):
        tbl.columns[ci].width = Inches(cw)
    for ri, rvals in enumerate(rows_cc):
        for ci, val in enumerate(rvals):
            cell = tbl.cell(ri, ci)
            if ri == 0:
                cell.fill.solid()
                cell.fill.fore_color.rgb = base.P_NAVY
                base._set_table_cell(cell, val, size=8.8, bold=True, color=base.P_WHITE)
            else:
                cell.fill.solid()
                cell.fill.fore_color.rgb = base.P_WHITE if ri % 2 == 1 else PptxRGB(0xF8, 0xFA, 0xFC)
                base._set_table_cell(cell, val, size=8.4, bold=(ci == 0), color=base.P_NAVY if ci == 0 else base.P_DARK)

    base._add_card(
        s2, 0.45, 4.52, 6.25, 2.30, base.P_ORANGE,
        'CHẠY SẠCH ĐA NỀN TẢNG & CHỐT CHẶN CHECKPOINT', base.P_OBADGE_BG, base.P_ORANGE,
        'Chặn tệp hỏng trước torch.load & CLI đủ tham số quang học',
        [
            '• .gitattributes chuẩn LF: verify_repro_bundle.py & sha256sum -c đều PASS 13/13 trên Linux/macOS/Windows.',
            '• verify_checkpoint_integrity() chặn CHECKPOINT_SHA256_MISMATCH / CHECKPOINT_TRUNCATED trước torch.load → 0% fallback ngầm (cả /api/compare).',
            '• demo_star_tracker.py đủ --focal-mm, --pixel-um, --k1, --k2, --sidecar & --simulate-cnn-fallback · 151 passed (17 test Chặng 2).',
        ],
        head_size=10.6, body_size=8.7,
    )

    ev1_png = EV_DIR / 'ev1_repro_checksums_and_audit_log.png'
    base._add_picture_fit(
        s2, ev1_png, 6.90, 1.30, 5.98, 5.52,
        caption='Giao diện live: đối soát 13/13 SHA-256 (36,02 MiB) & bảng Nhật ký thực thi thời gian thực',
    )

    # ---------- SLIDE S2-3 (Slide 20): Explicit CoG Fallback & Isolated Upload / Right-to-Delete Demo ----------
    # Asymmetric hero layout: ev4 enlarged to 6.08 x 3.80 in (3.3x larger area) for crisp projector legibility!
    _populate_slide_chrome(
        s3,
        f'{STAGE2_MARKER} · FALLBACK & KIỂM SOÁT DỮ LIỆU',
        'Minh bạch Fallback CoG · Chống ghi đè UUID4 · Quyền xóa tức thì',
        'Mặc định xóa ngay trong finally: (0s sau xử lý, preview base64) hoặc TTL 15 phút (cô lập st_sid + meta.json, startup+60s sweeper, DELETE→404)',
        badge_bg=base.P_OBADGE_BG,
        badge_fg=base.P_ORANGE,
    )
    ev2_png = EV_DIR / 'ev2_fallback_cog_banner.png'
    ev3_png = EV_DIR / 'ev3_upload_ttl_and_zero_overwrite.png'
    ev4_png = EV_DIR / 'ev4_delete_verified_empty.png'

    base._add_picture_fit(
        s3, ev2_png, 0.42, 1.28, 5.62, 2.74,
        caption='1) Cảnh báo cam FALLBACK → CoG & log JSONL (đường dẫn tương đối an toàn)',
    )
    base._add_picture_fit(
        s3, ev3_png, 0.42, 4.12, 5.62, 2.74,
        caption='2) Tải 2 ảnh trùng tên mount_st_helens_1.png → 2 thư mục UUID4 độc lập (0% ghi đè)',
    )
    base._add_picture_fit(
        s3, ev4_png, 6.18, 1.28, 6.73, 4.16,
        caption='3) Sau bấm Xóa ngay / Xóa tất cả: 0 ảnh tạm trên đĩa, preview trả 404 & log DATA_DELETION đầy đủ',
    )
    base._add_card(
        s3, 6.18, 5.54, 6.73, 1.32, base.P_NAVY,
        'CHÍNH SÁCH DỮ LIỆU KHỚP 100% MÃ NGUỒN & HỒ SƠ', base.P_BADGE_BG, base.P_NAVY,
        'Cách ly hoàn toàn data/user_uploads/<UUID4>/ khỏi data/uploads/',
        [
            '• Ephemeral (mặc định): preview inline base64; finally: xóa trọn thư mục tạm (0s sau xử lý).',
            '• TTL (15 phút): st_sid + meta.json chống IDOR, startup+60s sweeper, chặn /output/*.jsonl (404), rollback 400/409.',
        ],
        head_size=9.8, body_size=8.3,
    )

    if reordered:
        # Move the 3 newly appended slides right before the last 2 slides (FAQ & Closing)
        sld_lst = prs.slides._sldIdLst
        elems = list(sld_lst)
        new_order = elems[:insert_pos] + elems[base_count:] + elems[insert_pos:base_count]
        for el in elems:
            sld_lst.remove(el)
        for el in new_order:
            sld_lst.append(el)

    # Sync cross-slide consistency on Slides 2, 9, 12, 15, 21, and 22
    _sync_legacy_slides(prs)

    # Renumber slide footers cleanly & enforce Zero-GVHD
    total_slides = len(prs.slides)
    banned = ('giảng viên hướng dẫn', 'người hướng dẫn', 'gvhd', 'hùng vân', 'năng hùng')
    for idx, slide in enumerate(prs.slides, 1):
        for sh in slide.shapes:
            if sh.has_text_frame:
                txt = sh.text_frame.text.strip()
                if idx > 1 and re.fullmatch(r'\d+\s*/\s*\d+', txt):
                    base._set_single_text(sh, f'{idx} / {total_slides}', size=10.0, color=base.P_NAVY, bold=True)
                low = txt.lower()
                for bt in banned:
                    if bt in low:
                        raise AssertionError(f'Banned term "{bt}" found in Slide {idx}')

    tmp_out = PPTX_PATH.with_name(PPTX_PATH.stem + '.tmp.pptx')
    prs.save(str(tmp_out))

    # Integrity check: zero duplicate zip entries and intact Slides 21 & 22
    with zipfile.ZipFile(tmp_out) as zf:
        names = zf.namelist()
        if len(names) != len(set(names)):
            dups = sorted({n for n in names if names.count(n) > 1})
            tmp_out.unlink(missing_ok=True)
            raise RuntimeError(f'Duplicate ZIP entries detected in PPTX: {dups}')

    tmp_out.replace(PPTX_PATH)
    print(f'[OK] Updated {PPTX_PATH} -> {total_slides} slides (Stage 2 slides at #{insert_pos + 1}..#{insert_pos + 3})')
    return total_slides


if __name__ == '__main__':
    add_stage2_slides()
