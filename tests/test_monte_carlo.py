"""Monte Carlo campaign wrapper for automated regression testing."""
from __future__ import annotations
import json
import pytest

@pytest.mark.slow
def test_monte_carlo_fast_100(star_tracker_root: object) -> object:
    from benchmarks.monte_carlo import run_mc
    report: object = run_mc(100, 'fast', seed=1, catalog_kind='synthetic')
    target_file: object = star_tracker_root.joinpath('data', 'outputs', 'mc_fast_100.json')
    target_file.parent.mkdir(parents=True, exist_ok=True)
    compact: object = {key: val for key, val in report.items() if not isinstance(val, list)}
    target_file.write_text(json.dumps(compact, indent=2), encoding='utf-8')
    if float(report['solve_rate_pct']) < 80.0:
        raise AssertionError(f"Low solve rate: {report['solve_rate_pct']}")
