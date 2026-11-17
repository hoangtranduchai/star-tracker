"""Integration tests for DemoEngine, RunRequest, and synthetic/external frame solving."""
from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from cv2 import imwrite
import demo_star_tracker
from src.demo_session import DemoEngine, RunRequest
from src.quaternion import parse_dec_deg, parse_ra_deg

def _ensure(ok: bool, info: str='') -> None:
    if not ok:
        raise AssertionError(info)

def test_engine_runs_fast_default(star_tracker_root: object, tmp_path: Path) -> object:
    engine: object = DemoEngine(star_tracker_root)
    req: object = RunRequest(mode='fast', seed=42, catalog='bsc5', max_mag=6.0, out_dir=tmp_path, save_png=False)
    outcome: object = engine.run(req)
    _ensure(bool(outcome.success), str(outcome.error))
    _ensure(float(outcome.metrics['attitude_error_arcsec']) < 40.0)
    p: object = outcome.payload
    _ensure(p['status'] == 'SOLVED', f"Expected SOLVED, got {p.get('status')}")
    _ensure(p['reject_code'] is None, f"Expected None reject_code, got {p.get('reject_code')}")
    ms: object = p['match_stats']
    for key in ('n_initial_matched', 'n_rejected_outliers', 'n_valid_pairs', 'min_pairs_required', 'rms_residual_arcsec', 'max_residual_arcsec'):
        _ensure(key in ms, f'Missing match_stats[{key}]')
    _ensure(int(ms['n_valid_pairs']) >= 4)
    _ensure(p['metrics']['status'] == 'SOLVED')
    _ensure(any((row['param'].startswith('Trạng thái') for row in p['compare'])))
    _ensure(any((row['param'].startswith('Cặp hợp lệ') for row in p['compare'])))
    _ensure(any(('RMS / Max' in row['param'] for row in p['compare'])))

def test_engine_supports_pointing_override(star_tracker_root: object, tmp_path: Path) -> object:
    engine: object = DemoEngine(star_tracker_root)
    ra_val: object = parse_ra_deg('18h 36m 56.3s')
    dec_val: object = parse_dec_deg('+38d 47m 01s')
    req: object = RunRequest(mode='fast', seed=10, catalog='bsc5', max_mag=6.0, ra_deg=ra_val, dec_deg=dec_val, out_dir=tmp_path, save_png=False)
    outcome: object = engine.run(req)
    _ensure(bool(outcome.success), str(outcome.error))

def test_engine_hr_pointing_vega(star_tracker_root: object, tmp_path: Path) -> object:
    engine: object = DemoEngine(star_tracker_root)
    req: object = RunRequest(mode='fast', seed=15, catalog='bsc5', max_mag=6.0, point_hr=7001, out_dir=tmp_path, save_png=False)
    outcome: object = engine.run(req)
    _ensure(bool(outcome.success), str(outcome.error))

def test_engine_surfaces_lost_on_empty_frame(star_tracker_root: object, tmp_path: Path) -> None:
    empty_path: Path = tmp_path / 'empty_1500x1000.tif'
    blank: np.ndarray = np.full((1000, 1500), 64, dtype=np.uint16)
    _ensure(bool(imwrite(str(empty_path), blank)), 'Failed to write blank tif')
    engine: DemoEngine = DemoEngine(star_tracker_root)
    outcome: object = engine.run(RunRequest(mode='fast', image=empty_path, out_dir=tmp_path, save_png=False))
    p: dict = outcome.payload
    _ensure(not outcome.success, 'Empty frame must not succeed')
    _ensure(p['status'] == 'LOST', f"Expected LOST, got {p.get('status')}")
    _ensure(p['q_est'] is None)
    _ensure(p['downlink_hex'] == '00' * 16)
    _ensure(int(p['match_stats']['n_valid_pairs']) == 0)
    _ensure(p['metrics']['status'] == 'LOST')

def test_engine_surfaces_rejected_match_contract(star_tracker_root: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from src.pipeline import StarTrackerPipeline
    fake_stats = dict(
        status='LOST',
        reject_code='INSUFFICIENT_INLIER_PAIRS',
        n_detected=6,
        n_initial_matched=4,
        n_rejected_outliers=2,
        n_valid_pairs=2,
        min_pairs_required=4,
        rms_residual_arcsec=None,
        max_residual_arcsec=None,
        fov_expected_stars=10,
    )
    def _fake_process(self: object, image: object) -> object:
        return SimpleNamespace(
            success=False,
            status='LOST',
            reject_code='INSUFFICIENT_INLIER_PAIRS',
            match_stats=fake_stats,
            q=None,
            a=None,
            centroids=None,
            ident=None,
            residuals_arcsec=None,
            cov_rad2=None,
            timing_ms={'total_pipeline_ms': 3.5},
            quality=fake_stats,
            error='LOST [INSUFFICIENT_INLIER_PAIRS]: only 2 inliers',
            glare_mask=None,
            to_downlink_bytes=lambda: b'\x00' * 16,
        )
    monkeypatch.setattr(StarTrackerPipeline, 'process_frame', _fake_process)
    engine: DemoEngine = DemoEngine(star_tracker_root)
    outcome: object = engine.run(RunRequest(mode='fast', seed=42, out_dir=tmp_path, save_png=False))
    p: dict = outcome.payload
    _ensure(not outcome.success)
    _ensure(p['status'] == 'LOST')
    _ensure(p['reject_code'] == 'INSUFFICIENT_INLIER_PAIRS')
    _ensure(p['match_stats']['n_initial_matched'] == 4)
    _ensure(p['match_stats']['n_rejected_outliers'] == 2)
    _ensure(p['match_stats']['n_valid_pairs'] == 2)
    _ensure(p['metrics']['status'] == 'LOST')
    _ensure(p['metrics']['reject_code'] == 'INSUFFICIENT_INLIER_PAIRS')
    _ensure(p['downlink_hex'] == '00' * 16)
    status_rows = [r for r in p['compare'] if r['param'].startswith('Trạng thái')]
    _ensure(len(status_rows) == 1 and status_rows[0]['est'] == 'LOST' and status_rows[0]['delta'] == 'INSUFFICIENT_INLIER_PAIRS')

def test_engine_lists_and_solves_tetra3_real_sky(star_tracker_root: object, tmp_path: Path) -> None:
    engine: DemoEngine = DemoEngine(star_tracker_root)
    alt60_rel = 'tetra3/2019-07-29T204726_Alt60_Azi-135_Try1.tiff'
    img_path: Path = engine.resolve_dataset_image(alt60_rel)
    if not img_path.is_file():
        pytest.skip('ESA tetra3 Alt60 frame not present')
    with pytest.raises(ValueError):
        engine.resolve_dataset_image('tetra3/../catalogs/bsc5_v6.0.npz')
    frames = engine.list_dataset_frames()
    _ensure(any((f['file'] == alt60_rel for f in frames)), 'Missing tetra3 frame in list_dataset_frames')
    outcome = engine.run(RunRequest(image=img_path, focal_mm=35.2911, pixel_um=6.9, out_dir=tmp_path, save_png=False))
    p = outcome.payload
    _ensure(outcome.success, str(outcome.error))
    _ensure(p['status'] == 'SOLVED')
    _ensure(p['reject_code'] is None)
    _ensure(int(p['match_stats']['n_valid_pairs']) >= 4)
    _ensure((p['camera']['width'], p['camera']['height']) == (1024, 768))
    bore = p['boresight_est']
    _ensure(bore is not None and abs(bore['ra_deg'] - 240.464) < 0.5 and abs(bore['dec_deg'] - 28.940) < 0.5, str(bore))
    auto_out = engine.run(RunRequest(image=img_path, out_dir=tmp_path, save_png=False))
    _ensure(auto_out.success and auto_out.payload['status'] == 'SOLVED', str(auto_out.error))

def test_cli_prints_verification_status_and_residuals(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc: int = demo_star_tracker.main(['--mode', 'fast', '--seed', '42', '--no-show', '--out', str(tmp_path)])
    out: str = capsys.readouterr().out
    _ensure(rc == 0, out)
    _ensure('Status      : SOLVED' in out, out)
    _ensure('Valid pairs :' in out, out)
    _ensure('Rejected outliers' in out, out)
    _ensure('Post-fit residual RMS/Max (arcsec):' in out, out)
    _ensure((tmp_path / 'demo_result.json').is_file())
