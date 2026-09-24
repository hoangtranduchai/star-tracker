"""Static integrity checks for the Star Tracker web interface (HTML, JS, CSS)."""
from __future__ import annotations
import re

def _verify_ui(condition: bool, reason: str='UI check failed') -> None:
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
