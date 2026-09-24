"""Integration tests for DemoEngine, RunRequest, and synthetic/external frame solving."""
from __future__ import annotations
from src.demo_session import DemoEngine, RunRequest
from src.quaternion import parse_dec_deg, parse_ra_deg

def _ensure(ok: bool, info: str='') -> None:
    if not ok:
        raise AssertionError(info)

def test_engine_runs_fast_default(star_tracker_root: object) -> object:
    engine: object = DemoEngine(star_tracker_root)
    req: object = RunRequest(mode='fast', seed=42, catalog='bsc5', max_mag=6.0, save_png=False)
    outcome: object = engine.run(req)
    _ensure(bool(outcome.success), str(outcome.error))
    _ensure(float(outcome.metrics['attitude_error_arcsec']) < 40.0)

def test_engine_supports_pointing_override(star_tracker_root: object) -> object:
    engine: object = DemoEngine(star_tracker_root)
    ra_val: object = parse_ra_deg('18h 36m 56.3s')
    dec_val: object = parse_dec_deg('+38d 47m 01s')
    req: object = RunRequest(mode='fast', seed=10, catalog='bsc5', max_mag=6.0, ra_deg=ra_val, dec_deg=dec_val, save_png=False)
    outcome: object = engine.run(req)
    _ensure(bool(outcome.success), str(outcome.error))

def test_engine_hr_pointing_vega(star_tracker_root: object) -> object:
    engine: object = DemoEngine(star_tracker_root)
    req: object = RunRequest(mode='fast', seed=15, catalog='bsc5', max_mag=6.0, point_hr=7001, save_png=False)
    outcome: object = engine.run(req)
    _ensure(bool(outcome.success), str(outcome.error))
