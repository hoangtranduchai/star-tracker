"""Parse RA/Dec typed like Stellarium, not only decimal degrees."""

import pytest

from src.quaternion import parse_dec_deg, parse_ra_deg, parse_radec_pair, split_radec_text, format_dec_both, format_ra_both

VEGA_RA_DEG = (18 + 37 / 60 + 51.2 / 3600) * 15
VEGA_DEC_DEG = 38 + 48 / 60 + 46.2 / 3600


def test_parse_vega_stellarium_sexagesimal():
    ra = parse_ra_deg("18h 37m 51.2s")
    dec = parse_dec_deg("+38° 48' 46.2\"")
    assert ra == pytest.approx(VEGA_RA_DEG)
    assert dec == pytest.approx(VEGA_DEC_DEG)


def test_parse_vega_explicit_sexagesimal_mode():
    ra = parse_ra_deg("18h 37m 51.2s", fmt="sexagesimal")
    dec = parse_dec_deg("+38° 48' 46.2\"", fmt="sexagesimal")
    assert ra == pytest.approx(VEGA_RA_DEG)
    assert dec == pytest.approx(VEGA_DEC_DEG)


def test_two_modes_bare_number_hours_vs_degrees():
    hours = 18.629222
    assert parse_ra_deg(hours, fmt="hms") == pytest.approx(hours * 15)
    assert parse_ra_deg(str(hours), fmt="sexagesimal") == pytest.approx(hours * 15)
    assert parse_ra_deg(hours, fmt="decimal") == pytest.approx(hours)
    assert parse_ra_deg("279.234", fmt="decimal") == pytest.approx(279.234)


def test_parse_ra_dec_decimal_degrees():
    assert parse_ra_deg("279.234") == pytest.approx(279.234)
    assert parse_dec_deg("-16.725") == pytest.approx(-16.725)
    assert parse_dec_deg("−16.725", fmt="decimal") == pytest.approx(-16.725)


def test_parse_ra_colon_hours_and_dec_colon():
    assert parse_ra_deg("18:37:51.2") == pytest.approx(VEGA_RA_DEG)
    assert parse_dec_deg("+38:48:46.2") == pytest.approx(VEGA_DEC_DEG)


def test_parse_rejects_glued_digits():
    with pytest.raises(ValueError, match="183751"):
        parse_ra_deg("183751.2")
    with pytest.raises(ValueError, match="384846"):
        parse_dec_deg("+384846.2")
    with pytest.raises(ValueError):
        parse_ra_deg("183751.2", fmt="decimal")
    with pytest.raises(ValueError):
        parse_ra_deg("183751.2", fmt="sexagesimal")
    with pytest.raises(ValueError):
        parse_dec_deg("+384846.2", fmt="sexagesimal")


def test_parse_vega_compact_one_line_stellarium_paste():
    line = "18h 37m51.2s   +38°48'46.2\""
    parts = split_radec_text(line)
    assert parts is not None
    assert "18h" in parts[0] and "37m51.2s" in parts[0].replace(" ", "")
    ra, dec = parse_radec_pair(line)
    assert ra == pytest.approx(VEGA_RA_DEG)
    assert dec == pytest.approx(VEGA_DEC_DEG)
    assert parse_ra_deg("18h 37m51.2s") == pytest.approx(VEGA_RA_DEG)
    assert parse_dec_deg("+38°48'46.2\"") == pytest.approx(VEGA_DEC_DEG)
    assert parse_ra_deg(line) == pytest.approx(VEGA_RA_DEG)
    assert parse_dec_deg(line) == pytest.approx(VEGA_DEC_DEG)
    assert parse_radec_pair("18h 37m51.2s+38°48'46.2\"")[0] == pytest.approx(VEGA_RA_DEG)


def test_format_both_hours_and_degrees():
    ra = (3 + 8 / 60 + 2.0 / 3600) * 15
    dec = 89 + 22 / 60 + 21.3 / 3600
    both_ra = format_ra_both(ra)
    both_dec = format_dec_both(dec)
    assert "03h" in both_ra and "47.008" in both_ra and "°" in both_ra
    assert "89°" in both_dec and "89.372" in both_dec
