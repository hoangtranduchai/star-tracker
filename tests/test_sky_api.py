"""Tests for `/api/sky-catalog`, headless browser guard, and deep-cosmos viewport rendering."""
from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace
import numpy as np
import pytest

import app as web_app
from src.visualize import _draw_starfield, plot_frame, save_input_png, save_output_png


def test_sky_catalog_default_bsc5_vectors_and_iau_names() -> None:
    client = web_app.app.test_client()
    res = client.get('/api/sky-catalog')
    assert res.status_code == 200
    data = res.get_json()
    assert isinstance(data, dict)
    assert 'BSC5' in str(data['source']).upper()
    assert data['synthetic'] is False

    n = int(data['n'])
    assert n >= 4500
    ids = data['ids']
    vx = data['vx']
    vy = data['vy']
    vz = data['vz']
    mag = data['mag']
    assert len(ids) == n
    assert len(vx) == n
    assert len(vy) == n
    assert len(vz) == n
    assert len(mag) == n

    norms_sq = np.square(vx) + np.square(vy) + np.square(vz)
    assert float(np.max(np.abs(norms_sq - 1.0))) < 1e-3

    names = data['names']
    assert isinstance(names, dict)
    assert names.get('2491') == 'Sirius'
    assert names.get('7001') == 'Vega'
    assert names.get('424') == 'Polaris'
    assert ('bsc5', 6.0) in web_app._SKY_CATALOG_CACHE


def test_sky_catalog_query_validation_and_mag_clamping(monkeypatch: pytest.MonkeyPatch) -> None:
    client = web_app.app.test_client()

    bad_cat = client.get('/api/sky-catalog?catalog=unknown')
    assert bad_cat.status_code == 400

    bad_mag = client.get('/api/sky-catalog?max_mag=not_a_number')
    assert bad_mag.status_code == 400

    observed_calls: list[tuple[str, float]] = []
    dummy_cat = SimpleNamespace(
        source='BSC5',
        num_stars=1,
        ids=np.array([2491], dtype=np.int32),
        vectors=np.array([[0.0, 0.0, 1.0]], dtype=np.float64),
        mags=np.array([-1.46], dtype=np.float32),
    )

    def _fake_stack(kind: str, max_mag: float, theta_max_deg: float = 30.5) -> tuple[object, bool, None]:
        observed_calls.append((str(kind), float(max_mag)))
        return (dummy_cat, False, None)

    monkeypatch.setattr(web_app.ENGINE, 'stack', _fake_stack)
    monkeypatch.setattr(web_app, '_SKY_CATALOG_CACHE', {})

    low_res = client.get('/api/sky-catalog?catalog=bsc5&max_mag=0.2')
    assert low_res.status_code == 200
    assert observed_calls[-1] == ('bsc5', 1.0)
    assert low_res.get_json()['names'].get('2491') == 'Sirius'

    high_res = client.get('/api/sky-catalog?catalog=hipparcos&max_mag=9.9')
    assert high_res.status_code == 200
    assert observed_calls[-1] == ('hipparcos', 7.5)

    cached_res = client.get('/api/sky-catalog?catalog=hipparcos&max_mag=9.9')
    assert cached_res.status_code == 200
    assert len(observed_calls) == 2


def test_main_no_browser_env_and_flag_suppress_open_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    opened_urls: list[str] = []
    started_timers: list[object] = []
    run_calls: list[dict[str, object]] = []

    class DummyTimer:
        def __init__(self, interval: float, fn: object) -> None:
            self.interval = interval
            self.fn = fn

        def start(self) -> None:
            started_timers.append(self)

    monkeypatch.setattr(web_app, 'open_browser', lambda url: opened_urls.append(str(url)))
    monkeypatch.setattr(web_app, 'Timer', DummyTimer)
    monkeypatch.setattr(web_app.app, 'run', lambda **kw: run_calls.append(kw))

    monkeypatch.setenv('STAR_TRACKER_NO_BROWSER', '1')
    monkeypatch.setenv('STAR_TRACKER_PORT', '8899')
    monkeypatch.setattr(sys, 'argv', ['app.py'])
    web_app.main()

    assert opened_urls == []
    assert started_timers == []
    assert len(run_calls) == 1
    assert run_calls[0]['port'] == 8899

    run_calls.clear()
    monkeypatch.delenv('STAR_TRACKER_NO_BROWSER', raising=False)
    monkeypatch.delenv('STAR_TRACKER_PORT', raising=False)
    monkeypatch.setattr(sys, 'argv', ['app.py', '--no-browser'])
    web_app.main()

    assert opened_urls == []
    assert started_timers == []
    assert len(run_calls) == 1
    assert run_calls[0]['port'] == 8765


def test_visualize_deep_cosmos_omits_unidentified_clutter_labels(tmp_path: Path) -> None:
    import matplotlib.pyplot as plt

    img = np.full((120, 160), 64, dtype=np.uint16)
    img[40, 50] = 2400
    img[80, 110] = 1800

    centroids = SimpleNamespace(
        uv=np.array([[50.0, 40.0], [110.0, 80.0], [25.0, 95.0]], dtype=np.float64),
        axis_ratio=np.array([1.0, 1.8, 1.1], dtype=np.float64),
        angle_rad=np.array([0.0, 0.4, 0.0], dtype=np.float64),
    )
    ident = SimpleNamespace(obs_idx=np.array([0]), cat_idx=np.array([0]))
    glare = np.zeros((120, 160), dtype=bool)
    glare[:10, :10] = True
    result = SimpleNamespace(
        success=True,
        status='SOLVED',
        centroids=centroids,
        ident=ident,
        glare_mask=glare,
        timing_ms={'centroiding_ms': 2.1, 'identification_ms': 0.8, 'attitude_ms': 0.1, 'total_pipeline_ms': 3.0},
    )
    catalog = SimpleNamespace(num_stars=1, ids=np.array([7001]), source='BSC5')

    fig, ax = plt.subplots()
    try:
        _draw_starfield(ax, img, result, catalog, lookup=True)
        texts = [t.get_text() for t in ax.texts]
        assert not any('chưa ID' in t for t in texts)
        assert any('Vega' in t or '7001' in t for t in texts)
    finally:
        plt.close(fig)

    in_png = save_input_png(img, tmp_path / 'demo_input.png')
    out_png = save_output_png(img, result, tmp_path / 'demo_output.png', catalog=catalog, lookup=True)
    res_png = plot_frame(
        img,
        result,
        truth=None,
        metrics={
            'status': 'SOLVED',
            'attitude_error_arcsec': 1.25,
            'boresight_est_ra_deg': 279.23,
            'boresight_est_dec_deg': 38.78,
            'boresight_est_ra_hms': '18h36m56s',
            'boresight_est_dec_dms': '+38°47\'01"',
            'n_truth': 3,
            'n_detected': 3,
            'n_matched': 1,
            'centroid_rms_px': 0.08,
            'limit_arcsec': 10.0,
            'verdict': 'PASS',
        },
        camera_label='Optics: f 50 mm',
        out_path=tmp_path / 'demo_result.png',
        show=False,
        catalog=catalog,
        lookup=True,
    )
    for p in (in_png, out_png, res_png):
        assert p.is_file() and p.stat().st_size > 1000
