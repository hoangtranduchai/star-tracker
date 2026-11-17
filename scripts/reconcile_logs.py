"""Reconcile all Star Tracker benchmark JSONs and audit old PPTX/MD claims (Stage 3A).

Reads:
  - data/outputs/centroid_benchmark_hd1024_thr2.json
  - data/outputs/centroid_benchmark_hd1024_glare_sun_strong.json
  - data/outputs/benchmark_real_calibrated_e2e.json
  - data/outputs/benchmark_sim_hd1024_e2e.json
  - data/outputs/benchmark_sim_glare_e2e.json
  - data/outputs/benchmark_rejection_stress.json
  - data/outputs/seed42_cog_vs_cnn.json
  - data/outputs/mount_st_helens_centroid_compare.json
  - data/outputs/mount_st_helens_lost_compare.json
  - AI2026_Portfolio/AI2026_SLIDE_THUYET_TRINH.pptx (read-only audit)
  - AI2026_Ho-so-du-an_StarTracker.md & AI2026_Portfolio/*.md (read-only audit)

Writes:
  - data/outputs/log_reconciliation_audit.json
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from typing import Any

from pptx import Presentation

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.demo_session import _jsonable

OUT_DIR = ROOT / 'data' / 'outputs'
AUDIT_OUT = OUT_DIR / 'log_reconciliation_audit.json'
PPTX_PATH = ROOT / 'AI2026_Portfolio' / 'AI2026_SLIDE_THUYET_TRINH.pptx'
MD_DOCS = [
    ROOT / 'AI2026_Ho-so-du-an_StarTracker.md',
    ROOT / 'AI2026_Portfolio' / 'CAU_HOI_BGK.md',
    ROOT / 'AI2026_Portfolio' / 'KICH_BAN_THUYET_TRINH.md',
    ROOT / 'AI2026_Portfolio' / 'KICH_BAN_THUYET_TRINH 2.md',
    ROOT / 'AI2026_Portfolio' / 'KICH_BAN_QUAY_DEMO.md',
    ROOT / 'AI2026_Portfolio' / 'README_HOAN_THIEN_HO_SO.md',
]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f'Missing required benchmark JSON: {path}')
    return json.loads(path.read_text(encoding='utf-8'))


def _check_no_nan_inf(obj: Any, trail: str = '$') -> list[str]:
    bad: list[str] = []
    if isinstance(obj, float):
        if not math.isfinite(obj):
            bad.append(trail)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            bad.extend(_check_no_nan_inf(v, f'{trail}.{k}'))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            bad.extend(_check_no_nan_inf(v, f'{trail}[{i}]'))
    return bad


def _audit_thr2_precision_recall(thr2: dict[str, Any]) -> dict[str, Any]:
    """Compute exact matched/predicted/GT/FP/Precision/Recall from centroid_benchmark_hd1024_thr2.json."""
    frames = thr2['frames']
    n_frames = len(frames)
    gt_total = sum(int(f['n_gt']) for f in frames)
    cl_matched = sum(int(f['classical']['n_matched']) for f in frames)
    cl_pred = sum(int(f['classical']['n_pred']) for f in frames)
    nn_matched = sum(int(f['cnn']['n_matched']) for f in frames)
    nn_pred = sum(int(f['cnn']['n_pred']) for f in frames)
    nn_fp = nn_pred - nn_matched
    cl_fp = cl_pred - cl_matched
    return {
        'source_file': 'data/outputs/centroid_benchmark_hd1024_thr2.json',
        'n_frames': n_frames,
        'gt_stars_total': gt_total,
        'gt_stars_per_frame': gt_total / max(n_frames, 1),
        'classical': {
            'matched_stars_total': cl_matched,
            'predicted_stars_total': cl_pred,
            'false_positives_total': cl_fp,
            'false_positives_per_frame': cl_fp / max(n_frames, 1),
            'recall_pct': 100.0 * cl_matched / gt_total,
            'precision_pct': 100.0 * cl_matched / cl_pred,
            'rmse_px_mean': thr2['summary']['classical']['rmse_px_mean'],
            'rmse_px_median': thr2['summary']['classical']['rmse_px_median'],
            'time_ms_median': thr2['summary']['classical']['time_ms_median'],
            'vi_summary': f'{cl_matched:,} / {gt_total:,} = {100.0 * cl_matched / gt_total:.2f}% Recall; {cl_matched:,} / {cl_pred:,} = {100.0 * cl_matched / cl_pred:.2f}% Precision; {cl_fp} FP'.replace(',', '.'),
        },
        'cnn': {
            'matched_stars_total': nn_matched,
            'predicted_stars_total': nn_pred,
            'false_positives_total': nn_fp,
            'false_positives_per_frame': nn_fp / max(n_frames, 1),
            'recall_pct': 100.0 * nn_matched / gt_total,
            'precision_pct': 100.0 * nn_matched / nn_pred,
            'rmse_px_mean': thr2['summary']['cnn']['rmse_px_mean'],
            'rmse_px_median': thr2['summary']['cnn']['rmse_px_median'],
            'time_ms_median': thr2['summary']['cnn']['time_ms_median'],
            'vi_summary': f'{nn_matched:,} / {gt_total:,} = {100.0 * nn_matched / gt_total:.2f}% Recall; {nn_matched:,} / {nn_pred:,} = {100.0 * nn_matched / nn_pred:.2f}% Precision; {nn_fp:,} false detections ({nn_fp / n_frames:.3f}/frame)'.replace(',', '.'),
        },
    }


def _extract_pptx_text_by_slide(pptx_path: Path) -> dict[int, str]:
    prs = Presentation(str(pptx_path))
    out: dict[int, str] = {}
    for idx, slide in enumerate(prs.slides, 1):
        chunks: list[str] = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                chunks.append(shape.text_frame.text)
            if shape.has_table:
                for row in shape.table.rows:
                    chunks.append(' | '.join(cell.text.strip() for cell in row.cells))
        out[idx] = '\n'.join(chunks)
    return out


def _audit_portfolio_discrepancies(
    thr2_audit: dict[str, Any],
    seed42: dict[str, Any],
    msh_cent: dict[str, Any],
    msh_lost: dict[str, Any],
    hd_e2e: dict[str, Any],
) -> dict[str, Any]:
    """Scan existing PPTX and MD portfolio documents for exact numeric & claim discrepancies."""
    slide_texts = _extract_pptx_text_by_slide(PPTX_PATH) if PPTX_PATH.is_file() else {}
    pptx_findings: list[dict[str, Any]] = []

    s7 = slide_texts.get(7, '')
    if '25206/27017 (100%)' in s7 or '25050/27017 (98,4%)' in s7:
        pptx_findings.append({
            'file': 'AI2026_Portfolio/AI2026_SLIDE_THUYET_TRINH.pptx',
            'location': 'Slide 7 table',
            'old_claim': 'CoG: 25206/27017 (100%); CNN: 25050/27017 (98,4%)',
            'audited_truth': (
                f"CoG Recall = {thr2_audit['classical']['recall_pct']:.2f}% (25,206/27,017), Precision = 100.00% (25,206/25,206); "
                f"CNN Recall = {thr2_audit['cnn']['recall_pct']:.2f}% (25,050/27,017), Precision = {thr2_audit['cnn']['precision_pct']:.2f}% "
                f"(25,050/33,241) with 8,191 false detections omitted from the slide."
            ),
            'severity': 'HIGH_MATHEMATICAL_ERROR',
        })

    s12 = slide_texts.get(12, '')
    if '12.592/12.592' in s12 or 'tuyệt đối 100%' in s12:
        pptx_findings.append({
            'file': 'AI2026_Portfolio/AI2026_SLIDE_THUYET_TRINH.pptx',
            'location': 'Slide 12 FAQ 2',
            'old_claim': 'Tỷ lệ khớp sao CoG đạt tuyệt đối 100% (12.592/12.592 sao).',
            'audited_truth': (
                f"Stale/contradictory count: authoritative thr2 JSON has 27,017 GT stars across 500 frames and "
                f"CoG matched 25,206/27,017 ({thr2_audit['classical']['recall_pct']:.2f}% Recall, 100.00% Precision), NOT 12,592/12,592."
            ),
            'severity': 'HIGH_CONTRADICTION',
        })

    overclaim_checks = [
        (3, 'Xác định hướng vệ tinh thời gian thực', 'Laptop software demo only; not spacecraft flight hardware or ADCS-qualified.'),
        (3, 'chuẩn hóa cho ADCS', 'Downlink quaternion format follows 4xfloat32 J2000 convention for demo, not flight-qualified ADCS hardware.'),
        (4, 'độ tin cậy tuyệt đối', 'Pre-fix pipeline even had a break bug admitting <3 valid inliers; post-fix achieves 0% false lock on 100 stress trials and 500 sim frames, but real uncalibrated wide-angle frames cleanly return LOST.'),
        (4, 'Sai số góc đạt dưới 1 giây cung trên ảnh sạch', f"Only true on single FAST Seed 42 CoG ({seed42['classical']['attitude_error_arcsec']:.4f}\"); across 500 hd1024 frames median is {hd_e2e['classical']['attitude_error_arcsec']['median']:.2f}\" and P90 is {hd_e2e['classical']['attitude_error_arcsec']['p90']:.2f}\"."),
        (10, 'chuẩn hóa cho vệ tinh', 'Laptop demo output; not flight hardware.'),
        (11, 'được kiểm chứng trên một khung hình sạch tĩnh mẫu', 'Now resolved: full 500-frame hd1024 + 40-frame glare + real calibrated sky E2E benchmarks completed.'),
        (12, 'đảm bảo luôn chứa 10–30 sao định vị tại mọi vị trí bầu trời', 'Overclaim: BSC5 V<=6 star density varies across the celestial sphere (e.g., Alt40 11.4 deg FOV only has 3 BSC5 stars inside edge margin).'),
    ]
    for sl_num, pattern, correction in overclaim_checks:
        txt = slide_texts.get(sl_num, '')
        if pattern in txt:
            pptx_findings.append({
                'file': 'AI2026_Portfolio/AI2026_SLIDE_THUYET_TRINH.pptx',
                'location': f'Slide {sl_num}',
                'old_claim': pattern,
                'audited_truth': correction,
                'severity': 'OVERCLAIM_OR_STALE',
            })

    md_findings: list[dict[str, Any]] = []
    for doc_path in MD_DOCS:
        if not doc_path.is_file():
            continue
        rel = str(doc_path.relative_to(ROOT)).replace('\\', '/')
        content = doc_path.read_text(encoding='utf-8')
        if '1,65' in content or '1.65' in content:
            md_findings.append({
                'file': rel,
                'issue': 'unlogged_seed42_1_65_arcsec',
                'old_claim': 'Cited ~0.446" CoG vs ~1.65" CNN on clean sim without an archived JSON log.',
                'reconciled_to': (
                    f"Now logged in data/outputs/seed42_cog_vs_cnn.json: FAST Seed 42 CoG = {seed42['classical']['attitude_error_arcsec']:.4f}\" "
                    f"vs CNN = {seed42['cnn']['attitude_error_arcsec']:.4f}\" (valid pairs {seed42['classical']['n_valid_pairs']} vs {seed42['cnn']['n_valid_pairs']})."
                ),
            })
        if '111' in content and '106' in content:
            diff = msh_cent.get('pipeline_vs_standalone_diff', {})
            md_findings.append({
                'file': rel,
                'issue': 'unexplained_msh_111_vs_106_and_legacy_cog_solve',
                'old_claim': 'Cited CoG 111 points (centroid compare) vs 64/106 ~16.2s (web pipeline) without explaining the discrepancy.',
                'reconciled_to': (
                    f"Reconciled in mount_st_helens_centroid_compare.json & mount_st_helens_lost_compare.json: "
                    f"standalone CentroidDetector(bg_block=31, no mask)={diff.get('standalone_n_detected')} pts ({diff.get('standalone_time_ms', 0):.1f} ms) vs "
                    f"StarTrackerPipeline(GlareMasker + bg_block=32->33)={diff.get('pipeline_n_detected')} pts; "
                    f"and post-Wave-2 strict outlier gate cleanly rejects uncalibrated CoG as LOST [{msh_lost['modes']['classical']['reject_code']}] "
                    f"while CNN solves (sep={msh_lost['modes']['cnn']['sep_deg_from_LOST']:.4f} deg vs UW LOST)."
                ),
            })
        if 'chưa kiểm được' in content and ('attitude end-to-end' in content.lower() or 'độ chính xác' in content.lower() or 'bộ sim lớn' in content.lower()):
            md_findings.append({
                'file': rel,
                'issue': 'stale_untested_large_sim_e2e',
                'old_claim': 'Stated end-to-end attitude (Δθ) on large sim set was not yet verified.',
                'reconciled_to': (
                    f"Now audited across 500 hd1024 frames (benchmark_sim_hd1024_e2e.json: CoG {hd_e2e['classical']['true_solve_rate_pct']:.1f}%, "
                    f"CNN {hd_e2e['cnn']['true_solve_rate_pct']:.1f}%), 40 glare frames, and 6 real frames."
                ),
            })

    return {
        'pptx_discrepancies': pptx_findings,
        'markdown_portfolio_discrepancies': md_findings,
        'total_discrepancies_logged': len(pptx_findings) + len(md_findings),
    }


def main() -> int:
    thr2 = _load_json(OUT_DIR / 'centroid_benchmark_hd1024_thr2.json')
    glare_cent = _load_json(OUT_DIR / 'centroid_benchmark_hd1024_glare_sun_strong.json')
    real_e2e = _load_json(OUT_DIR / 'benchmark_real_calibrated_e2e.json')
    hd_e2e = _load_json(OUT_DIR / 'benchmark_sim_hd1024_e2e.json')
    glare_e2e = _load_json(OUT_DIR / 'benchmark_sim_glare_e2e.json')
    stress = _load_json(OUT_DIR / 'benchmark_rejection_stress.json')
    seed42 = _load_json(OUT_DIR / 'seed42_cog_vs_cnn.json')
    msh_cent = _load_json(OUT_DIR / 'mount_st_helens_centroid_compare.json')
    msh_lost = _load_json(OUT_DIR / 'mount_st_helens_lost_compare.json')

    loaded_files = {
        'centroid_benchmark_hd1024_thr2.json': thr2,
        'centroid_benchmark_hd1024_glare_sun_strong.json': glare_cent,
        'benchmark_real_calibrated_e2e.json': real_e2e,
        'benchmark_sim_hd1024_e2e.json': hd_e2e,
        'benchmark_sim_glare_e2e.json': glare_e2e,
        'benchmark_rejection_stress.json': stress,
        'seed42_cog_vs_cnn.json': seed42,
        'mount_st_helens_centroid_compare.json': msh_cent,
        'mount_st_helens_lost_compare.json': msh_lost,
    }
    nan_issues = {name: _check_no_nan_inf(data, name) for name, data in loaded_files.items()}
    nan_issues = {k: v for k, v in nan_issues.items() if v}

    thr2_audit = _audit_thr2_precision_recall(thr2)
    portfolio_audit = _audit_portfolio_discrepancies(thr2_audit, seed42, msh_cent, msh_lost, hd_e2e)

    required_pngs = [
        'data/outputs/e2e_figures/real_sky_e2e_summary.png',
        'data/outputs/e2e_figures/sim500_e2e_comparison.png',
        'data/outputs/e2e_figures/precision_recall_centroid.png',
        'data/outputs/e2e_figures/rejection_guard_before_after.png',
        'data/outputs/failure_cases/tetra3_alt40_nominal_vs_calibrated.png',
        'data/outputs/failure_cases/ntnu_0006_distortion_lost.png',
        'data/outputs/failure_cases/hd1024_cnn_false_positives_example.png',
        'data/outputs/failure_cases/invalid_match_rejection_case.png',
    ]
    png_check = {p: (ROOT / p).is_file() and (ROOT / p).stat().st_size > 5000 for p in required_pngs}

    audit = {
        'audit_version': 'stage3a_reconciliation_v1',
        'all_json_finite_check_passed': len(nan_issues) == 0,
        'non_finite_paths': nan_issues,
        'all_required_pngs_present': all(png_check.values()),
        'png_check': png_check,
        'thr2_centroid_precision_recall_audit': thr2_audit,
        'e2e_summary_reconciliation': {
            'real_calibrated': {
                'nominal': real_e2e['nominal']['summary'],
                'calibrated': real_e2e['calibrated']['summary'],
            },
            'sim_hd1024_500': {
                'classical': {k: hd_e2e['classical'][k] for k in ('n_frames', 'n_solved', 'solve_rate_pct', 'n_correct', 'true_solve_rate_pct', 'n_false_lock', 'false_lock_rate_pct', 'n_lost', 'attitude_error_arcsec', 'centroid_precision_micro', 'centroid_recall_micro', 'centroid_false_pos_5px_total', 'total_pipeline_ms')},
                'cnn': {k: hd_e2e['cnn'][k] for k in ('n_frames', 'n_solved', 'solve_rate_pct', 'n_correct', 'true_solve_rate_pct', 'n_false_lock', 'false_lock_rate_pct', 'n_lost', 'attitude_error_arcsec', 'centroid_precision_micro', 'centroid_recall_micro', 'centroid_false_pos_5px_total', 'total_pipeline_ms')},
            },
            'sim_hd1024_glare_40': {
                'classical': {k: glare_e2e['classical'][k] for k in ('n_frames', 'n_solved', 'solve_rate_pct', 'n_correct', 'true_solve_rate_pct', 'n_false_lock', 'false_lock_rate_pct', 'n_lost', 'attitude_error_arcsec', 'centroid_precision_micro', 'centroid_recall_micro', 'centroid_false_pos_5px_total', 'total_pipeline_ms')},
                'cnn': {k: glare_e2e['cnn'][k] for k in ('n_frames', 'n_solved', 'solve_rate_pct', 'n_correct', 'true_solve_rate_pct', 'n_false_lock', 'false_lock_rate_pct', 'n_lost', 'attitude_error_arcsec', 'centroid_precision_micro', 'centroid_recall_micro', 'centroid_false_pos_5px_total', 'total_pipeline_ms')},
            },
            'seed42_fast': {
                'classical_err_arcsec': seed42['classical']['attitude_error_arcsec'],
                'cnn_err_arcsec': seed42['cnn']['attitude_error_arcsec'],
                'classical_valid_pairs': seed42['classical']['n_valid_pairs'],
                'cnn_valid_pairs': seed42['cnn']['n_valid_pairs'],
                'classical_precision_recall': [seed42['classical']['centroid_precision'], seed42['classical']['centroid_recall']],
                'cnn_precision_recall': [seed42['cnn']['centroid_precision'], seed42['cnn']['centroid_recall']],
            },
            'rejection_stress_100': {
                'improved': stress['improved_pipeline'],
                'legacy': stress['legacy_prefixed_pipeline'],
                'by_category': stress['by_category'],
            },
            'mount_st_helens': {
                'standalone_vs_pipeline': msh_cent['pipeline_vs_standalone_diff'],
                'modes': msh_lost['modes'],
            },
        },
        'portfolio_discrepancies_audit': portfolio_audit,
    }
    clean = _jsonable(audit)
    AUDIT_OUT.write_text(json.dumps(clean, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    print(f'[*] wrote {AUDIT_OUT}')
    print(f"    thr2 CoG: {thr2_audit['classical']['vi_summary']}")
    print(f"    thr2 CNN: {thr2_audit['cnn']['vi_summary']}")
    print(f"    Discrepancies logged: {portfolio_audit['total_discrepancies_logged']}")
    print(f"    All JSON finite: {audit['all_json_finite_check_passed']} | All PNGs present: {audit['all_required_pngs_present']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
