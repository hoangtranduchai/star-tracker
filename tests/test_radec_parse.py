"""Tests for flexible RA/Dec coordinate parsing (Stellarium sexagesimal and decimal degrees)."""
from __future__ import annotations
import pytest
from src.quaternion import format_dec_both, format_ra_both, parse_dec_deg, parse_ra_deg, parse_radec_pair, split_radec_text
_VEGA_RA = (18.0 + 37.0 / 60.0 + 51.2 / 3600.0) * 15.0
_VEGA_DEC = 38.0 + 48.0 / 60.0 + 46.2 / 3600.0

def _assert_close(val: float, target: float, tol: float=1e-06) -> None:
    if abs(float(val) - float(target)) > tol:
        raise AssertionError(f'{val} != {target}')

def test_parse_vega_stellarium_sexagesimal() -> object:
    _assert_close(parse_ra_deg('18h 37m 51.2s'), _VEGA_RA)
    _assert_close(parse_dec_deg('+38° 48\' 46.2"'), _VEGA_DEC)

def test_parse_vega_explicit_sexagesimal_mode() -> object:
    _assert_close(parse_ra_deg('18h 37m 51.2s', fmt='sexagesimal'), _VEGA_RA)
    _assert_close(parse_dec_deg('+38° 48\' 46.2"', fmt='sexagesimal'), _VEGA_DEC)

def test_two_modes_bare_number_hours_vs_degrees() -> object:
    h_val: object = 18.629222
    _assert_close(parse_ra_deg(h_val, fmt='hms'), h_val * 15.0)
    _assert_close(parse_ra_deg(str(h_val), fmt='sexagesimal'), h_val * 15.0)
    _assert_close(parse_ra_deg(h_val, fmt='decimal'), h_val)
    _assert_close(parse_ra_deg('279.234', fmt='decimal'), 279.234)

def test_parse_ra_dec_decimal_degrees() -> object:
    _assert_close(parse_ra_deg('279.234'), 279.234)
    _assert_close(parse_dec_deg('-16.725'), -16.725)
    _assert_close(parse_dec_deg('−16.725', fmt='decimal'), -16.725)

def test_parse_ra_colon_hours_and_dec_colon() -> object:
    _assert_close(parse_ra_deg('18:37:51.2'), _VEGA_RA)
    _assert_close(parse_dec_deg('+38:48:46.2'), _VEGA_DEC)

def test_parse_rejects_glued_digits() -> object:
    for bad_ra, mode in (('183751.2', 'auto'), ('183751.2', 'decimal'), ('183751.2', 'sexagesimal')):
        with pytest.raises(ValueError):
            parse_ra_deg(bad_ra, fmt=mode)
    for bad_dec, mode in (('+384846.2', 'auto'), ('+384846.2', 'sexagesimal')):
        with pytest.raises(ValueError):
            parse_dec_deg(bad_dec, fmt=mode)

def test_parse_vega_compact_one_line_stellarium_paste() -> object:
    pasted: object = '18h 37m51.2s   +38°48\'46.2"'
    tokens: object = split_radec_text(pasted)
    if tokens is None or '18h' not in tokens[0]:
        raise AssertionError('Failed to split pasted Stellarium string')
    ra_out, dec_out = parse_radec_pair(pasted)
    _assert_close(ra_out, _VEGA_RA)
    _assert_close(dec_out, _VEGA_DEC)
    _assert_close(parse_radec_pair('18h 37m51.2s+38°48\'46.2"')[0], _VEGA_RA)

def test_format_both_hours_and_degrees() -> object:
    ra_sample: object = (3.0 + 8.0 / 60.0 + 2.0 / 3600.0) * 15.0
    dec_sample: object = 89.0 + 22.0 / 60.0 + 21.3 / 3600.0
    ra_str: object = format_ra_both(ra_sample)
    dec_str: object = format_dec_both(dec_sample)
    if not ('03h' in ra_str and '47.008' in ra_str and ('89°' in dec_str)):
        raise AssertionError(f'Unexpected formatted strings: {ra_str} | {dec_str}')
