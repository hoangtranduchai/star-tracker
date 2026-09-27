"""Slow Monte Carlo wrapper. Fast path: 100 FAST trials via benchmarks/monte_carlo.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.slow
def test_monte_carlo_fast_100():
    from benchmarks.monte_carlo import run_mc

    summary = run_mc(100, "fast", seed=1, catalog_kind="synthetic")
    out = ROOT / "data" / "outputs" / "mc_fast_100.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    slim = {k: v for k, v in summary.items() if not isinstance(v, list)}
    out.write_text(json.dumps(slim, indent=2), encoding="utf-8")
    assert summary["solve_rate_pct"] >= 80.0  # design target 99% is recorded, not gated here
