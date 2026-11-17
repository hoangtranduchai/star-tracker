"""Static integrity checks for the Star Tracker web interface (HTML, JS, CSS)."""
from __future__ import annotations
import re


def _verify_ui(condition: bool, reason: str = 'UI check failed') -> None:
    if not condition:
        raise AssertionError(reason)


def test_every_html_button_id_is_wired_in_js(star_tracker_root: object) -> object:
    html_src: object = (star_tracker_root / 'web' / 'templates' / 'index.html').read_text(encoding='utf-8')
    js_src: object = (star_tracker_root / 'web' / 'static' / 'app.js').read_text(encoding='utf-8')
    btn_ids: object = re.findall('<button\\b[^>]*\\bid="([^"]+)"', html_src)
    _verify_ui(len(btn_ids) >= 6, f'Expected >=6 buttons, found {btn_ids}')
    missing: object = [bid for bid in btn_ids if f'getElementById("{bid}")' not in js_src]
    _verify_ui(not missing, f'Unwired buttons in app.js: {missing}')


def test_scripts_do_not_wait_for_never_firing_domcontentloaded(star_tracker_root: object) -> object:
    js_src: object = (star_tracker_root / 'web' / 'static' / 'app.js').read_text(encoding='utf-8')
    _verify_ui('DOMContentLoaded' not in js_src)


def test_sexagesimal_inputs_are_preserved_as_strings(star_tracker_root: object) -> object:
    html_src: object = (star_tracker_root / 'web' / 'templates' / 'index.html').read_text(encoding='utf-8')
    js_src: object = (star_tracker_root / 'web' / 'static' / 'app.js').read_text(encoding='utf-8')
    field_names: object = set(re.findall('\\bname="([^"]+)"', html_src))
    for req_name in ('ra_hms', 'dec_dms', 'ra_decimal', 'dec_decimal', 'radec_paste'):
        _verify_ui(req_name in field_names, f'Missing input name={req_name}')
    _verify_ui('data.ra_deg = Number' not in js_src)
    _verify_ui('setRadecSummary' in js_src)
    _verify_ui('splitRadecPaste' in js_src)


def test_null_attitude_error_is_guarded_in_js(star_tracker_root: object) -> object:
    js_src: object = (star_tracker_root / 'web' / 'static' / 'app.js').read_text(encoding='utf-8')
    _verify_ui('Number.isFinite(attErr)' in js_src)
    _verify_ui('fetchJson' in js_src)


def test_status_banner_allows_inline_code_flowing(star_tracker_root: object) -> object:
    css_src: object = (star_tracker_root / 'web' / 'static' / 'app.css').read_text(encoding='utf-8')
    start_idx: object = css_src.find('.status-banner {')
    _verify_ui(start_idx != -1, 'Missing .status-banner rule')
    end_idx: object = css_src.find('.status-banner.err', start_idx)
    snippet: object = css_src[start_idx:end_idx]
    _verify_ui('display: block' in snippet)
    _verify_ui('display: flex' not in snippet)


def test_tab_strip_never_clips_horizontally(star_tracker_root: object) -> object:
    css_src: object = (star_tracker_root / 'web' / 'static' / 'app.css').read_text(encoding='utf-8')
    nav_idx: object = css_src.find('.tab-nav {')
    _verify_ui(nav_idx != -1, 'Missing .tab-nav rule')
    btn_idx: object = css_src.find('.tab-btn {', nav_idx)
    snippet: object = css_src[nav_idx:btn_idx]
    _verify_ui('flex-shrink: 0' in snippet)


def test_optics_readout_and_comparison_helpers_exist(star_tracker_root: object) -> object:
    js_src: object = (star_tracker_root / 'web' / 'static' / 'app.js').read_text(encoding='utf-8')
    for token in ('refreshOptics', 'bodyNeedsWideTable', 'fmtCompareCell'):
        _verify_ui(token in js_src, f'Missing JS symbol: {token}')


def test_tetra3_preset_and_verification_fields_wired(star_tracker_root: object) -> object:
    html_src: object = (star_tracker_root / 'web' / 'templates' / 'index.html').read_text(encoding='utf-8')
    js_src: object = (star_tracker_root / 'web' / 'static' / 'app.js').read_text(encoding='utf-8')
    _verify_ui('id="btn-tetra3-preset"' in html_src, 'Missing btn-tetra3-preset in index.html')
    _verify_ui('id="kpi-status-badge"' in html_src, 'Missing kpi-status-badge in index.html')
    _verify_ui('tetra3/2019-07-29T204726_Alt60_Azi-135_Try1.tiff' in js_src, 'Missing tetra3 Alt60 path in app.js')
    for token in ('match_stats', 'reject_code', 'n_valid_pairs', 'n_rejected_outliers', 'rms_residual_arcsec', 'max_residual_arcsec', 'SOLVED', 'LOST'):
        _verify_ui(token in js_src, f'Missing verification token in app.js: {token}')
    lower_html: str = html_src.lower()
    for overclaim in ('sóng vô tuyến', 'đóng vòng adcs', 'mục tiêu onboard', '16 mp'):
        _verify_ui(overclaim not in lower_html, f'Found PC/satellite overclaim in index.html: {overclaim}')


def test_orbit3d_stage_and_single_webgl_root_wired(star_tracker_root: object) -> None:
    html_src: str = (star_tracker_root / 'web' / 'templates' / 'index.html').read_text(encoding='utf-8')
    js_src: str = (star_tracker_root / 'web' / 'static' / 'app.js').read_text(encoding='utf-8')
    css_src: str = (star_tracker_root / 'web' / 'static' / 'app.css').read_text(encoding='utf-8')

    _verify_ui(html_src.count('id="orbit3d-root"') == 1, 'Expected exactly one #orbit3d-root container in index.html')
    _verify_ui("filename='orbit3d.css'" in html_src, 'Missing orbit3d.css stylesheet link in index.html')
    _verify_ui("filename='vendor/three.min.js'" in html_src, 'Missing vendored three.min.js script in index.html')
    _verify_ui("filename='orbit3d.js'" in html_src, 'Missing orbit3d.js script in index.html')

    orbit_pos = html_src.find("filename='orbit3d.js'")
    app_pos = html_src.find("filename='app.js'")
    _verify_ui(0 < orbit_pos < app_pos, 'orbit3d.js must load before app.js')

    for mode in ('compare3d', 'orbit3d', 'split', 'hud'):
        _verify_ui(f'data-mode="{mode}"' in html_src, f'Missing view-mode button data-mode="{mode}"')

    _verify_ui('StarTrackerOrbit3D' in js_src, 'Missing StarTrackerOrbit3D integration in app.js')
    _verify_ui('updateFromPayload' in js_src, 'Missing StarTrackerOrbit3D.updateFromPayload call in app.js')
    _verify_ui('.stage-grid.is-compare3d' in css_src and '.stage-grid.is-orbit3d' in css_src, 'Missing stage-grid layout modes in app.css')


def test_human_copy_free_of_robotic_disclaimers(star_tracker_root: object) -> None:
    html_src: str = (star_tracker_root / 'web' / 'templates' / 'index.html').read_text(encoding='utf-8')
    js_src: str = (star_tracker_root / 'web' / 'static' / 'app.js').read_text(encoding='utf-8')
    combined = f'{html_src}\n{js_src}'
    forbidden_phrases = (
        'Radio vẫn đổi tay được',
        'không liệt kê từng DSO',
        'Không ghi tên cảm biến hay tên ống kính',
        'xem hồ sơ',
        'Cùng mảng pixel, trích xuất tâm sao sub-pixel và định danh',
        'Lớp extended, DN giả định',
    )
    for phrase in forbidden_phrases:
        _verify_ui(phrase not in combined, f'Found robotic disclaimer phrase: {phrase}')


def test_flask_index_and_frames_route() -> None:
    import app as web_app
    client = web_app.app.test_client()
    res = client.get('/')
    _verify_ui(res.status_code == 200, f'Unexpected status {res.status_code}')
    body: str = res.get_data(as_text=True)
    _verify_ui('btn-tetra3-preset' in body)
    _verify_ui('id="orbit3d-root"' in body)
    frames_res = client.get('/api/frames')
    _verify_ui(frames_res.status_code == 200)
    frames = frames_res.get_json()['frames']
    _verify_ui(any((f['file'].startswith('tetra3/') for f in frames)), 'Expected tetra3 frames in /api/frames')
