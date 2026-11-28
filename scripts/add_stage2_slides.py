"""Idempotently add 3 Stage 2 Hackathon & Defense slides to AI2026_SLIDE_THUYET_TRINH.pptx."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor as PptxRGB
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


def add_stage2_slides() -> int:
    prs = Presentation(str(PPTX_PATH))

    # Idempotent cleanup: remove any previously added Stage 2 slides
    for i in range(len(prs.slides) - 1, -1, -1):
        if _slide_has_marker(prs.slides[i]):
            _remove_slide(prs, i)

    base_count = len(prs.slides)

    # ---------- SLIDE S2-1: Full Pipeline & Image Data Control Architecture ----------
    s1 = base._add_slide_chrome(
        prs,
        f'{STAGE2_MARKER} · KIẾN TRÚC TỔNG THỂ',
        'Kiến trúc Pipeline J2000 & Kiểm soát Dữ liệu Ảnh (Chặng 2)',
        'Khép kín 3 tầng: Gói tái lập SHA-256 & Upload UUID4/TTL → Auto-Router + Fallback CoG tường minh → 0% False Lock & Nhật ký kiểm toán JSONL',
        badge_bg=base.P_OBADGE_BG,
        badge_fg=base.P_ORANGE,
    )
    arch_png = EV_DIR / 'stage2_pipeline_architecture.png'
    base._add_picture_fit(s1, arch_png, 0.45, 1.30, 12.43, 4.92)
    base._add_rect(s1, 0.45, 6.30, 12.43, 0.50, base.P_BADGE_BG, border=base.P_NAVY)
    tb_f1 = s1.shapes.add_textbox(Inches(0.60), Inches(6.35), Inches(12.13), Inches(0.40))
    base._set_single_text(
        tb_f1,
        'Điểm chốt Chặng 2: (1) Xác thực SHA-256 ngay trước torch.load (chặn tệp sửa đổi)  |  (2) Ảnh gốc + sidecar + preview cách ly 100% theo UUID4  |  (3) 141 pytest PASS (0 lỗi).',
        size=10.0,
        color=base.P_NAVY,
        bold=True,
    )

    # ---------- SLIDE S2-2: Standalone Reproducibility Bundle & Clean-Clone Proof ----------
    s2 = base._add_slide_chrome(
        prs,
        f'{STAGE2_MARKER} · GÓI TÁI LẬP ĐỘC LẬP',
        'Đóng gói 13/13 Tệp SHA-256 (36,03 MB) & Tái lập từ Bản Clone Sạch',
        'Chạy độc lập không cần tải thủ công ngoài kho · Đủ checkpoint, 6 ảnh thật hiệu chuẩn, manifest, catalog, CLI optics & lệnh benchmark',
        badge_bg=base.P_BADGE_BG,
        badge_fg=base.P_NAVY,
    )
    # Left table of clean-clone results
    rows_cc = [
        ['Kịch bản trên git clone sạch', 'Chế độ thực thi', 'Kết quả / Sai số 3-DOF'],
        ['verify_repro_bundle.py', 'SHA-256 (13/13 tệp)', 'PASS · 36,03 MB · ckpt verified'],
        ['Seed 42 FAST (Auto)', 'auto → classical', 'SOLVED · 36 sao · Δθ 0,45″ (93 ms)'],
        ['ESA Alt60 16-bit (Auto)', 'auto → classical', 'SOLVED · 9 sao · Δθ 2,26″ (66 ms)'],
        ['Zhao MT9V022 8-bit (Auto)', 'auto → cnn_hybrid', 'SOLVED · 8 sao · Δθ 48,26″'],
        ['Mount St. Helens (CNN)', 'cnn → cnn_hybrid', 'SOLVED · 72 sao · Δθ 71,13″'],
        ['Fallback (CNN & Auto)', '→ classical [FALLBACK]', 'Báo rõ lý do + ghi execution_log'],
        ['benchmark_3way --real-only', '5 pp × 6 ảnh thật + stress', 'PASS · 0,0% False Lock (41,9 s)'],
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
                base._set_table_cell(cell, val, size=9.0, bold=True, color=base.P_WHITE)
            else:
                cell.fill.solid()
                cell.fill.fore_color.rgb = base.P_WHITE if ri % 2 == 1 else PptxRGB(0xF8, 0xFA, 0xFC)
                base._set_table_cell(cell, val, size=8.6, bold=(ci == 0), color=base.P_NAVY if ci == 0 else base.P_DARK)

    base._add_card(
        s2, 0.45, 4.54, 6.25, 2.26, base.P_ORANGE,
        'CHẠY SẠCH 1 LỆNH & BẢO VỆ CHECKPOINT', base.P_OBADGE_BG, base.P_ORANGE,
        'Chặn tệp hỏng trước torch.load & CLI đủ tham số quang học',
        [
            '• requirements.txt đủ flask, Pillow, psutil, python-pptx (chạy sạch trên venv trống).',
            '• verify_checkpoint_integrity() đối chiếu SHA-256 trước torch.load → lệch 1 byte tự fallback CoG.',
            '• demo_star_tracker.py hỗ trợ đủ --focal-mm, --pixel-um, --k1, --k2, --sidecar & --simulate-cnn-fallback.',
        ],
        head_size=11.0, body_size=9.1,
    )

    ev1_png = EV_DIR / 'ev1_repro_checksums_and_audit_log.png'
    base._add_picture_fit(
        s2, ev1_png, 6.90, 1.30, 5.98, 5.45,
        caption='Giao diện live (startracker.agentlens.dpdns.org): đối soát 13/13 SHA-256 trực tuyến',
    )

    # ---------- SLIDE S2-3: Explicit CoG Fallback & Isolated Upload / Right-to-Delete Demo ----------
    s3 = base._add_slide_chrome(
        prs,
        f'{STAGE2_MARKER} · FALLBACK & KIỂM SOÁT DỮ LIỆU',
        'Minh bạch Fallback CoG · Chống ghi đè UUID4 · Quyền xóa tức thì',
        'Giải quyết triệt để mâu thuẫn cam kết lưu ảnh: mặc định 0s lưu đĩa (preview inline base64) hoặc TTL 15 phút (xóa trả 404 ngay)',
        badge_bg=base.P_OBADGE_BG,
        badge_fg=base.P_ORANGE,
    )
    ev2_png = EV_DIR / 'ev2_fallback_cog_banner.png'
    ev3_png = EV_DIR / 'ev3_upload_ttl_and_zero_overwrite.png'
    ev4_png = EV_DIR / 'ev4_delete_verified_empty.png'

    base._add_picture_fit(
        s3, ev2_png, 0.45, 1.30, 6.10, 3.06,
        caption='1) Cảnh báo cam FALLBACK → CoG + log JSONL ghi rõ lý do FileNotFoundError',
    )
    base._add_picture_fit(
        s3, ev3_png, 6.75, 1.30, 6.13, 3.06,
        caption='2) Tải 2 ảnh trùng tên mount_st_helens_1.png → 2 thư mục UUID4 (0% ghi đè)',
    )
    base._add_picture_fit(
        s3, ev4_png, 6.75, 4.50, 6.13, 2.30,
        caption='3) Bấm Xóa ngay / Xóa tất cả → 0 tệp sót đĩa, preview trả 404 & ghi DATA_DELETION',
    )
    base._add_card(
        s3, 0.45, 4.50, 6.10, 2.30, base.P_NAVY,
        'CHÍNH SÁCH DỮ LIỆU KHỚP 100% MÃ NGUỒN & HỒ SƠ', base.P_BADGE_BG, base.P_NAVY,
        'Cách ly hoàn toàn data/user_uploads/<UUID4>/ khỏi data/uploads/',
        [
            '• Mặc định ephemeral (0s): preview trả inline base64; finally xóa 100% ảnh gốc + sidecar + preview.',
            '• Tùy chọn ttl (15 phút): preview qua /api/uploads/<id>/preview/<name>; DELETE lập tức trả 404.',
            '• Đã đồng bộ P184 Hồ sơ DOCX, README, REPRODUCIBILITY & 0 byte NULL trên Link minh chứng.',
        ],
        head_size=10.8, body_size=9.0,
    )

    # Move the 3 newly appended slides right before the last 2 slides (FAQ & Closing)
    sld_lst = prs.slides._sldIdLst
    elems = list(sld_lst)
    # elems[:base_count-2] + elems[base_count:] (the 3 new slides) + elems[base_count-2:base_count]
    insert_pos = max(0, base_count - 2)
    new_order = elems[:insert_pos] + elems[base_count:] + elems[insert_pos:base_count]
    for el in elems:
        sld_lst.remove(el)
    for el in new_order:
        sld_lst.append(el)

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

    prs.save(str(PPTX_PATH))
    print(f'[OK] Updated {PPTX_PATH} -> {total_slides} slides (inserted 3 Stage 2 slides at #{insert_pos + 1}..#{insert_pos + 3})')
    return total_slides


if __name__ == '__main__':
    add_stage2_slides()
