"""Static checks so demo buttons stay wired after HTML/JS edits."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "web" / "templates" / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "web" / "static" / "app.js").read_text(encoding="utf-8")


def test_app_js_binds_every_button_id():
    ids = re.findall(r'<button[^>]*\sid="([^"]+)"', HTML)
    assert "btn-run" in ids and "btn-load" in ids and "btn-seed42" in ids
    assert "btn-upload" in ids
    assert 'id="local-image"' in HTML
    assert 'id="local-sidecar"' in HTML
    for bid in ids:
        assert f'getElementById("{bid}")' in JS, f"app.js never binds #{bid}"


def test_html_has_two_radec_input_modes():
    assert 'name="ra_hms"' in HTML and 'type="text"' in HTML
    assert 'name="dec_dms"' in HTML
    assert 'name="ra_decimal"' in HTML
    assert 'name="dec_decimal"' in HTML
    assert 'id="radec-converted"' in HTML
    assert 'id="radec-line-ra"' in HTML
    assert 'id="radec-line-dec"' in HTML
    assert "setRadecSummary" in JS
    assert 'name="ra_decimal"' in HTML
    assert not re.search(r'name="ra_(deg|decimal|hms)"[^>]*type="number"', HTML)
    assert not re.search(r'name="dec_(deg|decimal|dms)"[^>]*type="number"', HTML)
    assert not re.search(r'name="radec_paste"[^>]*type="number"', HTML)
    assert "data.ra_deg = Number" not in JS
    assert 'name="radec_paste"' in HTML
    assert "splitRadecPaste" in JS
    assert 'value="moon"' in HTML
    assert 'value="earth"' in HTML
    assert "Number.isFinite(attErr)" in JS
    assert 'name="sky_clutter"' in HTML
    assert 'value="typical"' in HTML
    assert 'value="nebula"' in HTML
    assert "DOMContentLoaded" not in JS
    assert "fetchJson" in JS
    assert 'v=21' in HTML
    assert 'name="focal_mm"' in HTML and 'name="pixel_um"' in HTML
    assert 'name="optics"' in HTML and 'id="optics-readout"' in HTML
    assert "refreshOptics" in JS and "bodyNeedsWideTable" in JS
    assert "fmtCompareCell" in JS
    css = (ROOT / "web" / "static" / "app.css").read_text(encoding="utf-8")
    status = css.split(".status-banner {")[1].split(".status-banner.err")[0]
    assert "display: block" in status
    assert "display: flex" not in status
    nav = css.split(".tab-nav {")[1].split(".tab-btn {")[0]
    assert "flex-shrink: 0" in nav
    assert 'id="tab-telemetry" class="tab-pane" hidden' in HTML
    assert 'id="tab-catalog" class="tab-pane" hidden' in HTML
