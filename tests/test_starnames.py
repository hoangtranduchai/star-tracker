"""Tests for IAU Catalog of Star Names (CSN) parsing and HR cross-indexing."""
from __future__ import annotations
from src.starnames import find_iau_xlsx, label_hr, lookup_hr, n_iau_names, n_named_hr, parse_iau_txt, parse_iau_xlsx, rebuild_cache

def _check_iau(cond: bool, msg: str='starnames test failed') -> None:
    if not cond:
        raise AssertionError(msg)

def test_xlsx_is_the_csn_source(star_tracker_root: object) -> object:
    expected_xlsx: object = star_tracker_root.joinpath('data', 'IAU-Catalog of Star Names (always up to date).xlsx')
    _check_iau(expected_xlsx.exists() and find_iau_xlsx() == expected_xlsx)

def test_parse_xlsx_counts_and_spot_checks(star_tracker_root: object) -> object:
    expected_xlsx: object = star_tracker_root.joinpath('data', 'IAU-Catalog of Star Names (always up to date).xlsx')
    entries: object = parse_iau_xlsx(expected_xlsx)
    by_name: object = {item['name']: item['hr'] for item in entries}
    _check_iau(len(entries) == 640 and len(by_name) == 640 and ('Unurgunite' in by_name))
    for proper_name, hr_id in (('Sirius', 2491), ('Vega', 7001), ('Alkes', 4287), ('Rasalgethi', 6406)):
        _check_iau(by_name.get(proper_name) == hr_id)

def test_rebuild_uses_xlsx_not_2022_txt() -> object:
    rebuild_cache()
    for hr_id, proper_name in ((4287, 'Alkes'), (2491, 'Sirius'), (7001, 'Vega'), (6406, 'Rasalgethi')):
        record: object = lookup_hr(hr_id)
        _check_iau(record is not None and record['name'] == proper_name)
    _check_iau('Alkes' in label_hr(4287))
    _check_iau(lookup_hr(99999) is None)
    _check_iau(n_iau_names() == 640 and n_named_hr() > 333)

def test_parse_iau_txt_if_present(star_tracker_root: object) -> object:
    txt_file: object = star_tracker_root.joinpath('data', 'catalogs', 'IAU-CSN.txt')
    if txt_file.exists():
        mapping: object = parse_iau_txt(txt_file)
        _check_iau(4287 in mapping and mapping[4287]['name'] == 'Alkes')
