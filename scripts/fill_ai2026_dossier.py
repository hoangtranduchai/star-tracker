"""Fill AI2026 Bang C dossier from audited JSON logs (Stage 3B)."""
from __future__ import annotations

import json
from pathlib import Path
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / 'data' / 'outputs'
TEMPLATE = ROOT / 'AI2026_Mẫu-hồ-sơ-gốc.docx'
ORIGINAL = ROOT / 'AI2026_Mẫu-hồ-sơ.docx'
OUT = ROOT / 'AI2026_Ho-so-du-an_StarTracker.docx'
OUT_MD = ROOT / 'AI2026_Ho-so-du-an_StarTracker.md'

BENCH = OUT_DIR / 'centroid_benchmark_hd1024_thr2.json'
GLARE_CENT = OUT_DIR / 'centroid_benchmark_hd1024_glare_sun_strong.json'
AUDIT_JSON = OUT_DIR / 'log_reconciliation_audit.json'
REAL_E2E_JSON = OUT_DIR / 'benchmark_real_calibrated_e2e.json'
HD_E2E_JSON = OUT_DIR / 'benchmark_sim_hd1024_e2e.json'
GLARE_E2E_JSON = OUT_DIR / 'benchmark_sim_glare_e2e.json'
STRESS_JSON = OUT_DIR / 'benchmark_rejection_stress.json'
SEED42_JSON = OUT_DIR / 'seed42_cog_vs_cnn.json'
MOUNT = OUT_DIR / 'mount_st_helens_centroid_compare.json'
MOUNT_LOST = OUT_DIR / 'mount_st_helens_lost_compare.json'
GITHUB_TXT = ROOT / 'AI2026_Portfolio' / '00_LINK_MA_NGUON_GITHUB.txt'

MOUNT_OVERLAY = OUT_DIR / 'mount_st_helens_cog_vs_cnn.png'
DEMO_FIELD = ROOT / 'data' / 'sim_dataset' / 'hd1024' / '0001_preview.png'
ZHAO_FLOW = OUT_DIR / 'zhao_paper_figures' / 'project_00.png'
ZHAO_STRAY = OUT_DIR / 'zhao_paper_figures' / 'project_03.png'
ZHAO_ATT = OUT_DIR / 'zhao_paper_figures' / 'project_05.png'

STAGE1_FIGS = (
    ('data/outputs/e2e_figures/rejection_guard_before_after.png', 'Chốt chặn từ chối khớp sao không hợp lệ trên 100 ca stress đối kháng (0% vs 41% False Lock)'),
    ('data/outputs/e2e_figures/real_sky_e2e_summary.png', 'Đánh giá End-to-End trên tập ảnh trời thật (Danh nghĩa vs Hiệu chuẩn, 0% False Lock)'),
    ('data/outputs/e2e_figures/sim500_e2e_comparison.png', 'Đánh giá End-to-End 500 khung hd1024 sạch và 40 khung lóa mạnh (CoG vs CNN d_th=2.0)'),
    ('data/outputs/e2e_figures/precision_recall_centroid.png', 'Đối soát Precision / Recall / Đốm giả (FP) của CoG và CNN trên thr2 & E2E'),
    ('data/outputs/failure_cases/tetra3_alt40_nominal_vs_calibrated.png', 'Ca lỗi ảnh thật: ESA tetra3 Alt40 (BSC5 V≤6 danh nghĩa LOST vs hiệu chuẩn + Hipparcos V≤7 SOLVED)'),
    ('data/outputs/failure_cases/ntnu_0006_distortion_lost.png', 'Ca lỗi ảnh thật: NTNU 0006.png góc siêu rộng 77,5° chưa hiệu chuẩn méo — trả về LOST an toàn (0% False Lock)'),
    ('data/outputs/failure_cases/hd1024_cnn_false_positives_example.png', 'Ca phân tích đốm giả CNN trên hd1024/0299.tif (6 FP do lệch miền 12-bit, Wahba vẫn giải đúng sau lọc ngoại lai)'),
    ('data/outputs/failure_cases/invalid_match_rejection_case.png', 'Đối chứng ca lỗi: Khớp ngoại lai (<3 inlier) và 3 sao thẳng hàng bị từ chối LOST sau cải tiến'),
)

IDENTITY_VALUE_ROWS = (2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20, 21)


def _read_json(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(f'Missing required audited JSON: {path}')
    return json.loads(path.read_text(encoding='utf-8'))


def _fmt_vi(val: float, decimals: int = 2) -> str:
    return f'{val:.{decimals}f}'.replace('.', ',')


def _fmt_int(val: int) -> str:
    return f'{int(val):,}'.replace(',', '.')


def _github_url() -> str:
    if not GITHUB_TXT.is_file():
        return 'https://github.com/hoangtranduchai/star-tracker'
    txt = GITHUB_TXT.read_text(encoding='utf-8')
    for token in txt.split():
        if token.startswith('http://') or token.startswith('https://'):
            return token.strip()
    return 'https://github.com/hoangtranduchai/star-tracker'


def _lost_attitude_sentence(lost: dict | None) -> str:
    """Audited post-fix pipeline outcome on Mount St. Helens vs UW LOST."""
    if lost is None:
        return 'Attitude vs LOST (RA 310,446° · Dec +36,0229°): thiếu mount_st_helens_lost_compare.json.'
    ref = lost.get('LOST_ref') or {}
    modes = lost.get('modes') or {}
    cnn_m = modes.get('cnn') or {}
    cog_m = modes.get('classical') or {}
    leg = (lost.get('legacy_pre_fix_reference') or {}).get('classical') or {}
    diff = lost.get('pipeline_vs_standalone_diff') or {}

    cnn_str = (
        f"CNN {cnn_m.get('status')}: RA {cnn_m['ra_deg']:.2f}° Dec {cnn_m['dec_deg']:+.2f}° "
        f"(Δ {cnn_m['sep_deg_from_LOST']:.3f}° vs UW LOST; 3-DOF vs manifest {cnn_m['attitude_error_arcsec_vs_manifest']:.2f}″) · "
        f"khớp {cnn_m.get('n_matched')}/{cnn_m.get('n_detected')} · ~{float(cnn_m.get('pipeline_ms') or 0)/1000.0:.2f} s"
    )
    cog_str = (
        f"CoG hậu kiểm (sau siết chốt chặn ngoại lai): {cog_m.get('status')} [{cog_m.get('reject_code')}] "
        f"(tách {cog_m.get('n_detected')} điểm với GlareMasker + bg_block={diff.get('pipeline_cfg_bg_block')}→{diff.get('pipeline_effective_odd_bg_block')}, "
        f"chỉ còn {cog_m.get('n_valid_pairs')} inlier < 3 nên từ chối an toàn, 0% khóa sai; "
        f"trước sửa giải {leg.get('n_matched')}/{leg.get('n_detected')} ~{float(leg.get('pipeline_ms') or 0)/1000.0:.1f} s lệch {leg.get('sep_deg_from_LOST', 0):.3f}°)"
    )
    return (
        f"Attitude sau cải tiến vs UW LOST (RA {float(ref.get('ra_deg', 310.446)):.3f}° · Dec {float(ref.get('dec_deg', 36.0229)):+.4f}°): "
        f"{cnn_str}; {cog_str}. Đối soát 111 vs 106 điểm: CentroidDetector độc lập (bg_block={diff.get('standalone_bg_block')}, không mask) tách "
        f"{diff.get('standalone_n_detected')} điểm ({diff.get('standalone_time_ms', 0):.1f} ms), còn StarTrackerPipeline (GlareMasker + bg_block={diff.get('pipeline_effective_odd_bg_block')}) tách {diff.get('pipeline_n_detected')} điểm."
    )


def _cell_val(row: object) -> str:
    if len(row.cells) < 2:
        return ''
    return row.cells[1].text.strip().replace('\n', ' ')


def load_identity_from_original() -> dict[int, str]:
    """Copy only non-empty identity values from the user's original Bang C dossier."""
    src_path = ORIGINAL
    if not src_path.is_file():
        cands = [p for p in ROOT.glob('AI2026*Mẫu*.docx') if 'gốc' not in p.name and 'goc' not in p.name and p.stat().st_size > 1000000]
        if not cands:
            raise SystemExit(f'missing original dossier {ORIGINAL}')
        src_path = cands[0]
    src = Document(str(src_path))
    table = src.tables[0]
    out: dict[int, str] = {}
    for ri in IDENTITY_VALUE_ROWS:
        if ri >= len(table.rows):
            continue
        val = _cell_val(table.rows[ri])
        if val:
            out[ri] = val
    out[-1] = '3'
    return out


def _dots(paragraph: object, text: str) -> bool:
    raw = paragraph.text.strip()
    if not raw:
        return False
    if set(raw) <= {'.', ' ', '…', '\xa0'} or raw.startswith('....'):
        paragraph.text = text
        for run in paragraph.runs:
            run.font.size = Pt(11)
        return True
    return False


def sections(
    bench: dict,
    glare_c: dict,
    audit: dict,
    real_e2e: dict,
    hd_e2e: dict,
    glare_e2e: dict,
    stress: dict,
    seed42: dict,
    m: dict,
    lost: dict,
) -> dict[int, str]:
    s = bench.get('summary', bench)
    cam, cl, nn = s['camera'], s['classical'], s['cnn']
    thr = s.get('distance_map_threshold', 2.0)
    t2_audit = audit['thr2_centroid_precision_recall_audit']
    t2_cl, t2_nn = t2_audit['classical'], t2_audit['cnn']
    gl_s = glare_c.get('summary', glare_c)
    s42_cl, s42_nn = seed42['classical'], seed42['cnn']
    hd_cl, hd_nn = hd_e2e['classical'], hd_e2e['cnn']
    gl_cl, gl_nn = glare_e2e['classical'], glare_e2e['cnn']
    real_nom_cl, real_nom_nn = real_e2e['nominal']['summary']['classical'], real_e2e['nominal']['summary']['cnn']
    real_cal_cl, real_cal_nn = real_e2e['calibrated']['summary']['classical'], real_e2e['calibrated']['summary']['cnn']
    cal_cl_frames = {r['frame_id']: r for r in real_e2e['calibrated']['frames']['classical']}
    cal_nn_frames = {r['frame_id']: r for r in real_e2e['calibrated']['frames']['cnn']}
    supp_alt40_cl = next(r for r in real_e2e['supplementary_hipparcos'] if 'Alt40' in r['frame_id'] and r['catalog'] == 'hipparcos_v7.0' and r['centroid_detector'] == 'classical')
    supp_alt40_nn = next(r for r in real_e2e['supplementary_hipparcos'] if 'Alt40' in r['frame_id'] and r['catalog'] == 'hipparcos_v7.0' and r['centroid_detector'] != 'classical')

    st_imp = stress['improved_pipeline']
    st_leg = stress['legacy_prefixed_pipeline']
    lost_sent = _lost_attitude_sentence(lost)

    creativity = (
        f"Điểm sáng tạo: (1) hệ lai CoG|CNN trên cùng pipeline Pyramid→Wahba kèm chốt chặn từ chối khớp sai (0% vs {_fmt_vi(st_leg['false_lock_rate_pct'], 0)}% legacy False Lock); "
        f"(2) so sánh công khai MobileUNet (Zhao et al.) không huấn luyện lại và đối soát E2E trên 540 khung mô phỏng + ảnh thật hiệu chuẩn; "
        f"(3) ca khó ảnh núi thật LOST — CoG tách {m['classical']['n_total']} điểm ({m['classical']['n_on_terrain']} núi/cây) nên bị chặn LOST an toàn, trong khi CNN tách {m['cnn']['n_total']} điểm (chỉ {m['cnn']['n_on_terrain']} núi/cây) và giải đúng."
    )
    zhao_cite = (
        'Trích dẫn Zhao et al., arXiv:2404.19108 (không phải số đo của nhóm): MobileUNet ≈ 0,020 s/khung trên RTX 2060M (Table V; ~20 ms @ 640×480); '
        'MobileUNet trên Google Coral Edge TPU ≈ 266 ms (Table VI; số tác giả ≈ 265,5 ms); RMSE centroid tổng hợp MobileUNet ≈ 0,1695 px vs CoG ≈ 0,6966 px trên ảnh tổng hợp sạch (Table III). '
        'Hình minh họa nguồn tác giả: data/outputs/zhao_paper_figures/ — chú thích «Nguồn: Zhao et al., arXiv:2404.19108».'
    )

    s1 = (
        'Bài toán thực tiễn: từ ảnh bầu trời sao xác định hướng (attitude) của trục máy ảnh trong hệ J2000 khi không có tư thế ban đầu (lost-in-space). '
        'Ba bước: ước lượng tâm sao dưới mức một pixel; nhận dạng sao bằng hình học góc và catalog; giải Wahba ra quaternion. '
        'Đầu ra gọn (4×float32 = 16 byte; hoặc 16 byte 0x00 khi LOST), chạy hoàn toàn trên phần mềm demo laptop cho sinh viên CNTT (chưa kiểm chứng trên phần cứng vệ tinh/ADCS bay). '
        'Attitude là góc/hướng, không dùng GSD mét mặt đất. ' + creativity
    )
    s2 = (
        f"Mục tiêu: (1) phát hiện và ước lượng tâm sao; (2) Pyramid/Mortari + K-vector trên Yale BSC5 (V ≤ 6, 5.023 sao) kèm chốt chặn từ chối khớp không hợp lệ (`LOST` + `reject_code`); "
        f"(3) quaternion J2000 16 byte (Wahba SVD/QUEST) và kiểm chứng End-to-End 3-DOF trên ảnh thật hiệu chuẩn lẫn mô phỏng. "
        f"Phạm vi: phần mềm demo nghiên cứu chạy trên máy tính cá nhân (Laptop RTX 5070 / CPU) — KHÔNG phải sản phẩm bay, chưa thử bức xạ hay phần cứng ADCS vệ tinh. "
        f"Camera demo: máy ảnh tĩnh APS-C 24 MP (6000×4000, pixel 3,72 µm, f=50 mm, FOV ≈ 25,16°×16,93°). "
        f"Bộ đo benchmark: {cam['width']}×{cam['height']} (pixel {cam['pixel_um']} µm, f={cam['focal_mm']} mm) cùng lớp FOV demo. "
        f"Đơn vị: Trường Đại học Bách khoa, Đại học Đà Nẵng — Khoa Công nghệ thông tin."
    )
    s3 = (
        f"Dữ liệu: (a) catalog Yale BSC5 công khai (5.023 sao V≤6 sau lọc cặp gần <60″) và Hipparcos I/239 (dự phòng/đối chiếu Alt40 V≤7); "
        f"(b) 500 khung mô phỏng sẵn data/sim_dataset/hd1024 và 40 khung lóa data/sim_dataset/hd1024_glare (1024×683, không sinh lại ảnh); "
        f"(c) trọng số MobileUNet_B10_50.pt công khai, không huấn luyện lại; "
        f"(d) bộ ảnh thật hiệu chuẩn (data/real_calibrated/manifest_real_calibrated.json): ESA tetra3 FLIR Blackfly S (Alt40, Alt60), Zhao MT9V022 (nightsky_june16_2021.npy, verification_img.npy), "
        f"UW LOST Mount St. Helens (mount_st_helens_1.png, 4,2 mm / 4,1 µm), NTNU góc rộng 77,5° chưa hiệu chuẩn (0006.png); "
        f"(e) hình minh họa bài báo Zhao (chỉ trích dẫn). Không thu thập dữ liệu cá nhân."
    )
    s4 = (
        f"Tiền xử lý CoG: nền cục bộ (bg_block=32→33 ở chế độ fast trong pipeline, 64 ở full), ngưỡng MAD, opening 3×3, connected components, trọng tâm cường độ. "
        f"Nhánh CNN: chuẩn hóa mean/std tác giả, chia thang bit (8-bit, 12-bit /16, 16-bit thực /256), pad chia hết 32, segmentation + distance map d_th={thr:g} (public run_neural_net); "
        f"trên ảnh 8-bit/16-bit thực xếp hạng hạt giống theo độ tương phản cục bộ (outdoor_seed_scores). Catalog: K-vector theo FOV đường chéo."
    )
    s5 = (
        'Mặc định không học máy: CoG → Pyramid/Mortari + K-vector → Wahba SVD/QUEST + hậu kiểm ngoại lai & suy biến thẳng hàng SVD (`s_min >= 1e-6`). '
        'Tùy chọn AI: MobileUNet công khai chỉ thay bước centroid (Zhao et al.). '
        'Công cụ: Python, NumPy, SciPy, OpenCV, PyTorch CUDA, pytest, app.py, demo_star_tracker.py. ' + zhao_cite
    )
    s6 = (
        f"Không huấn luyện lại CNN. Suy luận trên {s.get('device')}, cnn_torch_device={s.get('cnn_torch_device')}, torch {s.get('torch_version', '2.11.0+cu128')}. "
        f"Ngưỡng distance-map công khai = {thr:g}. Đã bổ sung hỗ trợ ảnh 16-bit từ camera thật (`img/256.0` + xếp hạng contrast SNR) trong `src/centroid_cnn.py` "
        f"và mô hình tâm quang học `(cx, cy)` hiệu chuẩn trong `src/camera.py`. Lần đo cũ sai ngưỡng ~0,707 đã bị loại bỏ hoàn toàn."
    )
    s7 = (
        'Chỉ số đánh giá End-to-End (đã triển khai đầy đủ trong `src/metrics.py` và `scripts/benchmark_end_to_end.py`): '
        '(1) Solve Rate, True Solve Rate (3-DOF Δθ < giới hạn, ví dụ 40″ trên hd1024), False Lock Rate (giải được nhưng Δθ > 300″), LOST Rate và phân rã `reject_code`; '
        '(2) Sai số quaternion 3-DOF Δθ (arcsec) kèm phân rã Cross-Boresight (`hypot(dx, dy)`) và Roll (`|dz|`); '
        '(3) Centroid Precision, Recall, F1, False Positives và RMSE (≤3 px & ≤5 px); '
        '(4) Độ trễ toàn pipeline (`mask_ms`, `centroiding_ms`, `identification_ms`, `attitude_ms`, `total_pipeline_ms`).'
    )
    alt60_cl = cal_cl_frames['2019-07-29T204726_Alt60_Azi-135_Try1.tiff']
    alt60_nn = cal_nn_frames['2019-07-29T204726_Alt60_Azi-135_Try1.tiff']
    zhao_nn = cal_nn_frames['nightsky_june16_2021.npy']
    s8 = (
        f"KẾT QUẢ KIỂM TOÁN & END-TO-END (VÒNG CHUNG KẾT · CHẶNG 1, trên {s.get('device')}):\n"
        f"1) Chốt chặn từ chối khớp sai (`benchmark_rejection_stress.json`, {stress['n_trials_total']} ca đối kháng): "
        f"Sau cải tiến False Lock = {st_imp['false_lock_count']}/{stress['n_trials_total']} ({_fmt_vi(st_imp['false_lock_rate_pct'], 1)}%, 100/100 downlink 16 byte 0x00) "
        f"so với Legacy trước sửa = {st_leg['false_lock_count']}/{stress['n_trials_total']} ({_fmt_vi(st_leg['false_lock_rate_pct'], 1)}% False Lock: 16/25 ca ngoại lai <3 inlier và 25/25 ca 3 sao thẳng hàng).\n"
        f"2) Benchmark Centroid 500 khung hd1024 (`centroid_benchmark_hd1024_thr2.json`, d_th={thr:g}, {_fmt_int(t2_audit['gt_stars_total'])} sao GT): "
        f"CoG RMSE tb {_fmt_vi(t2_cl['rmse_px_mean'], 4)} px · {_fmt_vi(t2_cl['time_ms_median'], 2)} ms tv · {_fmt_int(t2_cl['matched_stars_total'])}/{_fmt_int(t2_audit['gt_stars_total'])} (Recall {_fmt_vi(t2_cl['recall_pct'], 1)}% · Precision {_fmt_vi(t2_cl['precision_pct'], 1)}% · 0 FP); "
        f"CNN RMSE tb {_fmt_vi(t2_nn['rmse_px_mean'], 4)} px · {_fmt_vi(t2_nn['time_ms_median'], 2)} ms tv · {_fmt_int(t2_nn['matched_stars_total'])}/{_fmt_int(t2_audit['gt_stars_total'])} (Recall {_fmt_vi(t2_nn['recall_pct'], 1)}% · Precision {_fmt_vi(t2_nn['precision_pct'], 1)}% [{_fmt_int(t2_nn['matched_stars_total'])}/{_fmt_int(t2_nn['predicted_stars_total'])} · {_fmt_int(t2_nn['false_positives_total'])} sao giả]). "
        f"Lóa mạnh 40 khung: CoG RMSE {_fmt_vi(gl_s['classical']['rmse_px_mean'], 4)} px vs CNN {_fmt_vi(gl_s['cnn']['rmse_px_mean'], 4)} px.\n"
        f"3) Đánh giá End-to-End 500 khung hd1024 & 40 khung lóa (`benchmark_sim_hd1024_e2e.json`, `benchmark_sim_glare_e2e.json`): "
        f"500 khung sạch — CoG giải đúng {hd_cl['n_correct']}/{hd_cl['n_frames']} (<40″: {_fmt_vi(hd_cl['true_solve_rate_pct'], 1)}%, 0% False Lock, Δθ trung vị {_fmt_vi(hd_cl['attitude_error_arcsec']['median'], 2)}″, P90 {_fmt_vi(hd_cl['attitude_error_arcsec']['p90'], 2)}″, tổng pipeline {_fmt_vi(hd_cl['total_pipeline_ms']['median'], 1)} ms); "
        f"CNN giải {hd_nn['n_solved']}/{hd_nn['n_frames']}, đạt <40″ {hd_nn['n_correct']}/{hd_nn['n_frames']} ({_fmt_vi(hd_nn['true_solve_rate_pct'], 1)}%, 0% False Lock, Δθ trung vị {_fmt_vi(hd_nn['attitude_error_arcsec']['median'], 2)}″, P90 {_fmt_vi(hd_nn['attitude_error_arcsec']['p90'], 2)}″, {_fmt_vi(hd_nn['total_pipeline_ms']['median'], 1)} ms, Precision {_fmt_vi(100*hd_nn['centroid_precision_micro'], 1)}%, Recall {_fmt_vi(100*hd_nn['centroid_recall_micro'], 1)}%, {_fmt_int(hd_nn['centroid_false_pos_5px_total'])} FP). "
        f"40 khung lóa — CoG {gl_cl['n_correct']}/40 (<40″, tv {_fmt_vi(gl_cl['attitude_error_arcsec']['median'], 2)}″, {_fmt_vi(gl_cl['total_pipeline_ms']['median'], 1)} ms); CNN {gl_nn['n_correct']}/40 (<40″, tv {_fmt_vi(gl_nn['attitude_error_arcsec']['median'], 2)}″, {_fmt_vi(gl_nn['total_pipeline_ms']['median'], 1)} ms), 0% False Lock. "
        f"Khung đơn Seed 42 FAST (`seed42_cog_vs_cnn.json`): CoG {_fmt_vi(s42_cl['attitude_error_arcsec'], 3)}″ ({s42_cl['n_valid_pairs']}/{s42_cl['n_gt_stars']}, Prec/Rec 100%) vs CNN {_fmt_vi(s42_nn['attitude_error_arcsec'], 3)}″ ({s42_nn['n_valid_pairs']}/{s42_nn['n_gt_stars']}, Prec {_fmt_vi(100*s42_nn['centroid_precision'], 1)}%, Rec {_fmt_vi(100*s42_nn['centroid_recall'], 1)}%).\n"
        f"4) Đánh giá End-to-End trên ảnh trời thật (`benchmark_real_calibrated_e2e.json`, 0% False Lock): "
        f"Quang học danh nghĩa (6 khung BSC5) CoG {real_nom_cl['n_solved']}/6, CNN {real_nom_nn['n_solved']}/6 (MSH). Quang học hiệu chuẩn (5 khung BSC5) CoG {real_cal_cl['n_solved']}/5 (Alt60 {_fmt_vi(alt60_cl['attitude_error_arcsec'], 2)}″), "
        f"CNN {real_cal_nn['n_solved']}/5 (Alt60 {_fmt_vi(alt60_nn['attitude_error_arcsec'], 2)}″, Zhao MT9V022 {_fmt_vi(zhao_nn['attitude_error_arcsec'], 2)}″, MSH {_fmt_vi(cal_nn_frames['mount_st_helens_1.png']['attitude_error_arcsec'], 2)}″). "
        f"Ca bổ sung Hipparcos V≤7 giải Alt40 đạt CoG {_fmt_vi(supp_alt40_cl['attitude_error_arcsec'], 2)}″ / CNN {_fmt_vi(supp_alt40_nn['attitude_error_arcsec'], 2)}″. NTNU 0006.png (FOV 77,5° chưa hiệu chuẩn méo) và Zhao verification_img.npy (4 đốm) đều trả về LOST an toàn. "
        f"{lost_sent} {zhao_cite} Không claim phần cứng bay/ADCS."
    )
    s9 = (
        f"Baseline CoG + Pyramid + K-vector + Wahba. Trên 500 khung hd1024 (d_th={thr:g}): CoG thắng cả về RMSE ({_fmt_vi(t2_cl['rmse_px_mean'], 4)} vs {_fmt_vi(t2_nn['rmse_px_mean'], 4)} px), Precision (100,0% vs 75,4%), độ trễ E2E ({_fmt_vi(hd_cl['total_pipeline_ms']['median'], 1)} vs {_fmt_vi(hd_nn['total_pipeline_ms']['median'], 1)} ms) và Δθ ({_fmt_vi(hd_cl['attitude_error_arcsec']['median'], 2)}″ vs {_fmt_vi(hd_nn['attitude_error_arcsec']['median'], 2)}″). "
        f"Đóng góp cải tiến Chặng 1: (1) chốt chặn 0% False Lock trước & sau `_associate_remaining` + SVD rank check; (2) mở rộng CNN cho ảnh 16-bit camera thật + giải 3-DOF trên tập ảnh hiệu chuẩn ESA tetra3 & Zhao; (3) đối soát triệt để log–tài liệu–slide."
    )
    s10 = (
        'Kiến trúc: camera model (có tâm cx, cy & Brown-Conrady) → GlareMasker → centroid (CoG | CNN 8/12/16-bit) → Pyramid/K-vector → _refine_inliers (tiền/hậu _associate_remaining + SVD rank) → FOV consistency → quaternion 16 byte (0x00 khi LOST). '
        'Chạy kiểm thử & benchmark: `pytest -v`; `python scripts/benchmark_end_to_end.py --suites all`; `python scripts/reconcile_logs.py`; `python demo_star_tracker.py --mode fast --seed 42 --lookup`; `python app.py` (giao diện Web tối giản kèm API `GET /api/sky-catalog` dựng không gian 3D quỹ đạo Trái Đất & thiên cầu thực J2000 5.023 sao Yale BSC5 để đối chiếu trực quan tư thế vệ tinh 3D với khung ảnh gốc, có kịch bản nhanh `Mẫu chuẩn Seed 42`, `Bầu trời thật ESA`, `Núi St. Helens`, `Ngược nắng lóa mạnh` — mô phỏng trực quan trên PC, chưa kiểm chứng phần cứng bay/ADCS).'
    )
    s11 = (
        'Rủi ro & kiểm soát: (1) Khớp sai hoặc hình học thẳng hàng → đã chặn bằng `_refine_inliers`, SVD `s_min >= 1e-6` và `LOW_FOV_CONSISTENCY` (0% False Lock trên 100 ca đối kháng & 540 khung sim); '
        '(2) Ảnh thiếu sao sáng BSC5 (Alt40) hoặc méo ống kính rộng chưa hiệu chuẩn (NTNU 0006.png) → hệ thống trả LOST an toàn; '
        '(3) CNN lệch miền 12-bit trên ảnh mô phỏng → mặc định Auto-Router chạy CoG trước, xác thực SHA-256 trước `torch.load` và báo tường minh khi xảy ra Fallback CNN → CoG trong nhật ký nguyên tử `data/outputs/execution_log.jsonl` + dải cảnh báo Web UI; '
        '(4) Kiểm soát dữ liệu ảnh tải lên (`src/upload_store.py`): giao diện không có tài khoản người dùng; ảnh tải lên, nhãn JSON sidecar và 4 ảnh xem trước được cách ly vào thư mục UUID4 riêng `data/user_uploads/<upload_id>/` gắn cookie phiên `st_sid` (`HttpOnly`, `SameSite=Lax`, 0% ghi đè tệp trùng tên hay ảnh mẫu `data/uploads/`, rollback xóa sạch khi lỗi HTTP 400/409), chế độ mặc định `ephemeral` xóa vĩnh viễn 0 giây trong khối `finally:` (preview trả inline base64), chế độ tùy chọn `ttl` lưu tối đa 15 phút (900s, luồng nền tự dọn mỗi 60s) và hỗ trợ xóa tức thì qua `DELETE /api/uploads[/<id>]` (ghi dấu `DATA_DELETION`); '
        '(5) Phạm vi: toàn bộ số liệu đo trên PC Laptop (RTX 5070 / CPU / ARM64 TRL 3–4) — KHÔNG chứng minh khả năng chịu bức xạ hay sẵn sàng phần cứng vệ tinh/ADCS.'
    )
    s12 = (
        'Phân định rõ phạm vi: hiện tại đã hoàn thành kiểm thử chốt chặn False Lock, đánh giá E2E trên 540 khung mô phỏng và 6 khung ảnh thật hiệu chuẩn/stress trên PC. '
        'Kỳ vọng phát triển tương lai (chưa kiểm chứng bay): (1) tinh chỉnh có kiểm soát MobileUNet cho miền 12-bit; (2) mở rộng tập ảnh bầu trời thật đa quang học; (3) tối ưu C++/nhúng và thử nghiệm phần cứng/HIL hướng tới ứng dụng học thuật hoặc payload vệ tinh cỡ nhỏ sau này.'
    )
    s13 = (
        f"Minh chứng đã khóa: `data/outputs/log_reconciliation_audit.json`, `data/outputs/benchmark_real_calibrated_e2e.json`, `data/outputs/benchmark_sim_hd1024_e2e.json`, "
        f"`data/outputs/benchmark_sim_glare_e2e.json`, `data/outputs/benchmark_rejection_stress.json`, `data/outputs/seed42_cog_vs_cnn.json`, "
        f"`data/outputs/centroid_benchmark_hd1024_thr2.json`, `data/outputs/mount_st_helens_{{centroid,lost}}_compare.json`, `data/outputs/e2e_figures/*.png`, `data/outputs/failure_cases/*.png`, "
        f"`AI2026_Portfolio/BAO_CAO_CAI_TIEN_VONG_CHUNG_KET_CHANG_1.{{md,docx,pdf}}`, `AI2026_Portfolio/AI2026_SLIDE_THUYET_TRINH.pptx`. "
        f"Mã nguồn GitHub: {_github_url()} (nhánh `feat/national-round-stage1`). Video minh chứng: cập nhật khi quay bản hoàn thiện."
    )
    return {19: s1, 22: s2, 26: s3, 30: s4, 34: s5, 38: s6, 42: s7, 46: s8, 50: s9, 54: s10, 58: s11, 62: s12, 66: s13}


def write_md(bench: dict, bodies: dict[int, str], identity: dict[int, str], m: dict, lost: dict) -> None:
    s = bench.get('summary', bench)
    titles = [
        (19, '1. Bài toán hoặc vấn đề thực tiễn cần giải quyết'),
        (22, '2. Mục tiêu, phạm vi và đối tượng ứng dụng của sản phẩm'),
        (26, '3. Dữ liệu sử dụng, nguồn dữ liệu và tính hợp lệ của dữ liệu'),
        (30, '4. Quy trình tiền xử lý, làm sạch, chuẩn hóa hoặc tổ chức dữ liệu'),
        (34, '5. Thuật toán, mô hình, phương pháp hoặc công cụ trí tuệ nhân tạo được sử dụng'),
        (38, '6. Quy trình huấn luyện, tinh chỉnh, tích hợp hoặc khai thác mô hình (nếu có)'),
        (42, '7. Chỉ số, phương pháp hoặc tiêu chí đánh giá kết quả'),
        (46, '8. Kết quả thử nghiệm, phân tích ưu điểm, hạn chế và khả năng mở rộng'),
        (50, '9. So sánh với phương án hoặc mô hình cơ sở, phân tích đóng góp của các thành phần trong hệ thống (nếu có)'),
        (54, '10. Kiến trúc hệ thống và phương án triển khai'),
        (58, '11. Phân tích rủi ro, yêu cầu bảo mật, đạo đức trí tuệ nhân tạo và an toàn dữ liệu'),
        (62, '12. Hướng phát triển, hoàn thiện và khả năng ứng dụng trong thực tiễn'),
        (66, '13. Lịch sử câu lệnh và hình ảnh minh chứng quá trình phát triển sản phẩm từ bản nháp đến khi hoàn thiện'),
    ]
    g = identity.get
    lines = [
        '# HỒ SƠ DỰ ÁN DỰ THI BẢNG C',
        'Cuộc thi Sáng tạo trẻ Quốc gia trong lĩnh vực Trí tuệ nhân tạo năm 2026 (Đội `DUT.StarTracker` · Mã dự thi `AI26C0083`)',
        '',
        '## Thông tin đội thi',
        f"- Số lượng thí sinh: {g(-1, '')} người (theo hồ sơ gốc)",
        f"- Thí sinh 1 (đội trưởng): {g(2, '')} — {g(3, '')} — {g(6, '')} — {g(7, '')}",
        f"  - {g(4, '')}",
        f"  - Địa chỉ: {g(5, '')}",
        f"- Thí sinh 2: {g(9, '')} — {g(10, '')} — {g(13, '')} — {g(14, '')}",
        f"  - {g(11, '')}",
        f"  - Địa chỉ: {g(12, '')}",
        f"- Thí sinh 3: {g(16, '')} — {g(17, '')} — {g(20, '')} — {g(21, '')}",
        f"  - {g(18, '')}",
        f"  - Địa chỉ: {g(19, '')}",
        '- Trường: Trường Đại học Bách khoa, Đại học Đà Nẵng',
        '- Khoa: Khoa Công nghệ thông tin',
        f'- Mã nguồn: {_github_url()} (nhánh `feat/national-round-stage1`)',
        '',
        '## NỘI DUNG HỒ SƠ DỰ ÁN',
        '',
    ]
    for idx, title in titles:
        lines += [f'### {title}', '', bodies[idx], '']

    lines += [
        '## Hình minh chứng',
        '',
        '### Demo nhóm — ảnh núi thật LOST (CoG cam vs CNN xanh)',
        '',
        '![Overlay CoG vs CNN trên mount_st_helens_1.png](data/outputs/mount_st_helens_cog_vs_cnn.png)',
        '',
        '*Chú thích: ảnh thật công bố kèm LOST, không phải ảnh của nhóm chụp; thông số 4,2 mm và 4,1 µm. Cam = CoG; xanh = CNN MobileUNet (d_th=2). Đỏ nhạt = mặt nạ núi/cây heuristic.*',
        '',
        f"- Đo centroid độc lập (`bg_block=31`, không mask): CoG tổng {m['classical']['n_total']} (núi/cây {m['classical']['n_on_terrain']}, trời {m['classical']['n_on_sky']}); CNN tổng {m['cnn']['n_total']} (núi/cây {m['cnn']['n_on_terrain']}, trời {m['cnn']['n_on_sky']}).",
        f"- {_lost_attitude_sentence(lost)}",
        '',
    ]
    if DEMO_FIELD.is_file():
        lines += [
            '### Demo nhóm — khung sim hd1024 (1024×683)',
            '',
            '![Khung sao giả lập hd1024](data/sim_dataset/hd1024/0001_preview.png)',
            '',
            '*Chú thích: demo của nhóm, 1024×683 — không phải số liệu bài báo.*',
            '',
        ]
    lines += ['### Minh chứng cải tiến Vòng Chung kết · Chặng 1', '']
    for rel, cap in STAGE1_FIGS:
        if (ROOT / rel).is_file():
            lines += [f'![{cap}]({rel})', '', f'*{cap}*', '']
    lines += ['### Nguồn Zhao et al., arXiv:2404.19108 (không phải đo của nhóm)', '']
    for rel, cap in (
        ('data/outputs/zhao_paper_figures/project_00.png', 'Flowchart phương pháp — Nguồn: Zhao et al., arXiv:2404.19108'),
        ('data/outputs/zhao_paper_figures/project_03.png', 'Night sky + stray light — Nguồn: Zhao et al., arXiv:2404.19108'),
        ('data/outputs/zhao_paper_figures/project_05.png', 'Attitude so sánh — Nguồn: Zhao et al., arXiv:2404.19108'),
    ):
        if (ROOT / rel).is_file():
            lines += [f'![{cap}]({rel})', '', f'*{cap}*', '']
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')


def _add_caption(doc: Document, text: str) -> None:
    p = doc.add_paragraph(text)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in p.runs:
        run.font.size = Pt(10)
        run.font.italic = True


def _append_figures(doc: Document) -> None:
    doc.add_heading('Hình minh chứng (bổ sung)', level=2)
    if MOUNT_OVERLAY.is_file():
        doc.add_paragraph('Ảnh núi thật LOST — overlay CoG (cam) vs CNN (xanh)')
        doc.add_picture(str(MOUNT_OVERLAY), width=Inches(5.8))
        _add_caption(doc, 'Chú thích: ảnh thật công bố kèm LOST, không phải ảnh của nhóm chụp; thông số 4,2 mm và 4,1 µm. File: data/outputs/mount_st_helens_cog_vs_cnn.png')
    if DEMO_FIELD.is_file():
        doc.add_paragraph('Khung sao giả lập hd1024 (demo của nhóm, 1024×683)')
        doc.add_picture(str(DEMO_FIELD), width=Inches(5.2))
        _add_caption(doc, 'Chú thích: demo của nhóm, 1024×683 — không phải số liệu bài báo.')
    doc.add_paragraph('Minh chứng cải tiến Vòng Chung kết · Chặng 1 (E2E & Chốt chặn False Lock)')
    for rel, cap in STAGE1_FIGS:
        p = ROOT / rel
        if p.is_file():
            doc.add_picture(str(p), width=Inches(5.8))
            _add_caption(doc, cap)
    doc.add_paragraph('Hình từ Zhao et al. (chỉ trích dẫn nguồn)')
    for path, cap in (
        (ZHAO_FLOW, 'Nguồn: Zhao et al., arXiv:2404.19108 — flowchart phương pháp'),
        (ZHAO_STRAY, 'Nguồn: Zhao et al., arXiv:2404.19108 — night sky + stray light'),
        (ZHAO_ATT, 'Nguồn: Zhao et al., arXiv:2404.19108 — attitude comparison'),
    ):
        if path.is_file():
            doc.add_picture(str(path), width=Inches(5.5))
            _add_caption(doc, cap)


def main() -> None:
    template = TEMPLATE
    if not template.is_file():
        cands = list(ROOT.glob('AI2026*gốc*.docx')) + list(ROOT.glob('AI2026*goc*.docx'))
        if not cands:
            raise SystemExit(f'missing {TEMPLATE}')
        template = cands[0]
    bench = _read_json(BENCH)
    glare_c = _read_json(GLARE_CENT)
    audit = _read_json(AUDIT_JSON)
    real_e2e = _read_json(REAL_E2E_JSON)
    hd_e2e = _read_json(HD_E2E_JSON)
    glare_e2e = _read_json(GLARE_E2E_JSON)
    stress = _read_json(STRESS_JSON)
    seed42 = _read_json(SEED42_JSON)
    m = _read_json(MOUNT)
    lost = _read_json(MOUNT_LOST)

    bodies = sections(bench, glare_c, audit, real_e2e, hd_e2e, glare_e2e, stress, seed42, m, lost)
    identity = load_identity_from_original()
    write_md(bench, bodies, identity, m, lost)

    doc = Document(str(template))
    table = doc.tables[0]
    if len(table.rows[0].cells) >= 4:
        table.rows[0].cells[1].text = '1 người ☐'
        table.rows[0].cells[2].text = '2 người ☐'
        table.rows[0].cells[3].text = '3 người ☑'
    for ri in IDENTITY_VALUE_ROWS:
        val = identity.get(ri, '')
        if ri < len(table.rows) and len(table.rows[ri].cells) >= 2:
            table.rows[ri].cells[1].text = val
    filled: set[int] = set()
    for i, para in enumerate(doc.paragraphs):
        if i in bodies and _dots(para, bodies[i]):
            filled.add(i)
            continue
        if set(para.text.strip()) <= {'.', ' ', '…', '\xa0'} and para.text.strip().startswith('...'):
            if any(i - k in filled for k in range(1, 4)):
                para.text = ''
    _append_figures(doc)
    doc.save(str(OUT))
    print(f'wrote {OUT}')
    print(f'wrote {OUT_MD}')


if __name__ == '__main__':
    main()
