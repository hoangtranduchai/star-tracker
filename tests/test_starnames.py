from pathlib import Path

from src.starnames import (
    find_iau_xlsx,
    label_hr,
    lookup_hr,
    n_iau_names,
    n_named_hr,
    parse_iau_txt,
    parse_iau_xlsx,
    rebuild_cache,
)

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "data" / "IAU-Catalog of Star Names (always up to date).xlsx"


def test_xlsx_is_the_csn_source():
    assert XLSX.exists(), "missing user-downloaded IAU CSN xlsx under star_tracker/data"
    assert find_iau_xlsx() == XLSX


def test_parse_xlsx_counts_and_spot_checks():
    rows = parse_iau_xlsx(XLSX)
    names = [r["name"] for r in rows]
    assert len(rows) == 640
    assert len(set(names)) == 640
    assert "Unurgunite" in names
    sirius = next(r for r in rows if r["name"] == "Sirius")
    assert sirius["hr"] == 2491
    vega = next(r for r in rows if r["name"] == "Vega")
    assert vega["hr"] == 7001
    alkes = next(r for r in rows if r["name"] == "Alkes")
    assert alkes["hr"] == 4287
    rasal = next(r for r in rows if r["name"] == "Rasalgethi")
    assert rasal["hr"] == 6406


def test_rebuild_uses_xlsx_not_2022_txt():
    rebuild_cache()
    assert lookup_hr(4287)["name"] == "Alkes"
    assert lookup_hr(2491)["name"] == "Sirius"
    assert lookup_hr(7001)["name"] == "Vega"
    assert lookup_hr(6406)["name"] == "Rasalgethi"
    assert "Alkes" in label_hr(4287)
    assert lookup_hr(99999) is None
    assert n_iau_names() == 640
    assert n_named_hr() == sum(1 for r in parse_iau_xlsx(XLSX) if r.get("hr") is not None)
    assert n_named_hr() > 333


def test_parse_iau_txt_if_present():
    path = ROOT / "data" / "catalogs" / "IAU-CSN.txt"
    if not path.exists():
        return
    table = parse_iau_txt(path)
    assert 4287 in table
    assert table[4287]["name"] == "Alkes"
