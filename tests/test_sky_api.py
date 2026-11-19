"""Tests for `/api/sky-catalog`, headless browser guard, and deep-cosmos viewport rendering."""
from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace
import cv2
import numpy as np
import pytest

import app as web_app
from src.visualize import _draw_starfield, plot_frame, save_clean_png, save_input_png, save_output_png


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


def test_health_and_favicon_endpoints() -> None:
    client = web_app.app.test_client()

    health_res = client.get('/api/health')
    assert health_res.status_code == 200
    health_json = health_res.get_json()
    assert health_json == {'ok': True, 'service': 'star-tracker'}

    fav_res = client.get('/favicon.ico')
    assert fav_res.status_code in (200, 204)
    if fav_res.status_code == 200:
        assert 'svg' in fav_res.mimetype
        assert b'<svg' in fav_res.data


def test_save_clean_png_exact_aspect_and_deep_space_black(tmp_path: Path) -> None:
    rng = np.random.default_rng(7)
    sky = np.clip(64.0 + rng.normal(0.0, 5.0, size=(1000, 1500)), 0, 4095).astype(np.uint16)
    sky[250:253, 400:403] = 3200
    sky[710:712, 1120:1122] = 1800

    clean_p = save_clean_png(sky, tmp_path / 'clean_fast.png')
    assert clean_p.is_file()
    decoded = cv2.imread(str(clean_p), cv2.IMREAD_UNCHANGED)
    assert decoded is not None
    assert decoded.dtype == np.uint8
    assert decoded.shape == (1000, 1500)
    assert int(np.median(decoded)) == 0
    assert int(decoded.max()) >= 240

    large_sky = np.full((2000, 3000), 64, dtype=np.uint16)
    large_sky[500:506, 900:906] = 3800
    decimated_p = save_clean_png(large_sky, tmp_path / 'clean_decimated.png')
    dec_img = cv2.imread(str(decimated_p), cv2.IMREAD_UNCHANGED)
    assert dec_img is not None
    assert dec_img.shape == (1067, 1600)


def test_api_run_clean_url_borderless_png_and_detected_uv(
    star_tracker_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(web_app, 'BASE', tmp_path)
    client = web_app.app.test_client()

    run_res = client.post('/api/run', json={'seed': 42, 'mode': 'fast'})
    assert run_res.status_code == 200
    payload = run_res.get_json()
    assert isinstance(payload, dict)
    assert payload['status'] == 'SOLVED'
    assert payload['clean_url'] == '/output/demo_clean.png'
    assert payload['clean_png'] == 'data/outputs/demo_clean.png'

    detected_uv = payload['detected_uv']
    assert isinstance(detected_uv, list)
    assert len(detected_uv) >= 30
    cam_w = float(payload['camera']['width'])
    cam_h = float(payload['camera']['height'])
    assert (cam_w, cam_h) == (1500.0, 1000.0)
    for pair in detected_uv:
        assert isinstance(pair, list) and len(pair) == 2
        assert 0.0 <= float(pair[0]) <= cam_w
        assert 0.0 <= float(pair[1]) <= cam_h

    id_stars = payload['identified_stars']
    assert len(id_stars) >= 4
    for s_row in id_stars:
        assert 'u_px' in s_row and 'v_px' in s_row
        assert 0 <= int(s_row['obs_idx']) < len(detected_uv)

    png_res = client.get('/output/demo_clean.png')
    assert png_res.status_code == 200
    assert png_res.mimetype == 'image/png'
    buf = np.frombuffer(png_res.data, dtype=np.uint8)
    clean_img = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
    assert clean_img is not None
    assert clean_img.dtype == np.uint8
    h_px, w_px = clean_img.shape[:2]
    assert (w_px, h_px) == (1500, 1000)
    assert w_px * 2 == h_px * 3
    assert int(np.median(clean_img)) == 0
    assert int(np.median(clean_img)) <= 15
    assert int(clean_img.max()) >= 220
    star_peaks = [
        int(
            clean_img[
                max(0, int(round(float(v))) - 3) : min(h_px, int(round(float(v))) + 4),
                max(0, int(round(float(u))) - 3) : min(w_px, int(round(float(u))) + 4),
            ].max()
        )
        for u, v in detected_uv
    ]
    assert max(star_peaks) >= 210
    assert min(star_peaks) >= 210

    # Downsampled to 650px CSS width: stars must remain bright and unmistakable
    css_h = int(round(h_px * (650.0 / float(w_px))))
    s42_css = cv2.resize(clean_img, (650, css_h), interpolation=cv2.INTER_AREA)
    s42_css_peaks = [
        int(
            s42_css[
                max(0, int(round(float(v) * css_h / h_px)) - 2) : min(css_h, int(round(float(v) * css_h / h_px)) + 3),
                max(0, int(round(float(u) * 650.0 / w_px)) - 2) : min(650, int(round(float(u) * 650.0 / w_px)) + 3),
            ].max()
        )
        for u, v in detected_uv
    ]
    assert max(s42_css_peaks) >= 210
    assert float(np.median(s42_css_peaks)) >= 210.0

    # Real 16-bit ESA tetra3 Alt60 sky frame (1024x768) & extended glare/silhouette scenes
    from src.demo_session import DemoEngine, RunRequest

    engine = DemoEngine(star_tracker_root)
    alt60_path = star_tracker_root / 'data' / 'tetra3' / '2019-07-29T204726_Alt60_Azi-135_Try1.tiff'
    if alt60_path.is_file():
        t3_dir = tmp_path / 'tetra3_alt60'
        t3_out = engine.run(RunRequest(image=alt60_path, out_dir=t3_dir, save_png=True))
        assert t3_out.success
        t3_png = cv2.imread(str(t3_dir / 'demo_clean.png'), cv2.IMREAD_UNCHANGED)
        assert t3_png is not None and t3_png.dtype == np.uint8
        assert float(np.median(t3_png)) <= 15.0
        t3_h, t3_w = t3_png.shape[:2]
        t3_peaks = [
            int(
                t3_png[
                    max(0, int(round(float(v))) - 3) : min(t3_h, int(round(float(v))) + 4),
                    max(0, int(round(float(u))) - 3) : min(t3_w, int(round(float(u))) + 4),
                ].max()
            )
            for u, v in t3_out.payload['detected_uv']
        ]
        assert len(t3_peaks) >= 8
        assert min(t3_peaks) >= 210

    msh_path = star_tracker_root / 'data' / 'uploads' / 'mount_st_helens_1.png'
    if msh_path.is_file():
        msh_clean = save_clean_png(cv2.imread(str(msh_path), cv2.IMREAD_GRAYSCALE), tmp_path / 'msh_clean.png')
        msh_png = cv2.imread(str(msh_clean), cv2.IMREAD_UNCHANGED)
        assert msh_png is not None
        assert float(np.median(msh_png)) <= 15.0
        assert int(msh_png.max()) >= 210


def test_api_compare_and_benchmark_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web_app, 'BASE', tmp_path)
    client = web_app.app.test_client()

    cmp_res = client.post(
        '/api/compare',
        json={'seed': 42, 'mode': 'fast', 'backends': ['classical', 'tetra3']},
    )
    assert cmp_res.status_code == 200
    payload = cmp_res.get_json()
    assert payload['clean_url'] == '/output/demo_compare_clean.png'
    assert payload['have_gt'] is True
    assert set(payload['methods'].keys()) == {'classical', 'tetra3'}
    for k in ('classical', 'tetra3'):
        m = payload['methods'][k]
        assert m['status'] == 'SOLVED'
        assert m['attitude_error_arcsec'] is not None and m['attitude_error_arcsec'] < 15.0
        assert m['n_valid_pairs'] >= 15
        assert len(m['detected_uv']) >= 15

    png_res = client.get('/output/demo_compare_clean.png')
    assert png_res.status_code == 200
    assert len(png_res.data) > 500

    bench_res = client.get('/api/benchmark-summary')
    assert bench_res.status_code == 200
    bench_json = bench_res.get_json()
    assert 'available' in bench_json and 'evaluation_scope' in bench_json



