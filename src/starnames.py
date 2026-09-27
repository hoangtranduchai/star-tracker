"""IAU proper-name overlay for bright stars (HR and Hipparcos identifiers)."""
from functools import lru_cache
from json import dumps as json_dumps, loads as json_loads
from pathlib import Path
from re import IGNORECASE, compile as re_compile, search as re_search
from numpy import degrees
from .catalog import vectors_to_ra_dec
ROOT = Path(__file__).resolve().parents[1]
IAU_TXT = ROOT.joinpath('data', 'catalogs', 'IAU-CSN.txt')
IAU_JSON = ROOT.joinpath('data', 'catalogs', 'iau_hr_names.json')
IAU_XLSX_NAME = 'IAU-Catalog of Star Names (always up to date).xlsx'
HR_PAT = re_compile('HR\\s*(\\d+)\\b', IGNORECASE)
_HR_SPACE_PAT = re_compile('\\sHR\\s+(\\d+)\\b')
JSON_FORMAT = 'iau_csn_v2'

def find_iau_xlsx() -> object:
    direct: object = ROOT.joinpath('data', IAU_XLSX_NAME)
    if direct.is_file():
        return direct
    matches: object = sorted(ROOT.joinpath('data').rglob('*Star Names*.xlsx'))
    return matches[0] if matches else None

def _iter_clean_txt_lines(path: object) -> object:
    if not Path(path).is_file():
        return ()
    raw_content: object = Path(path).read_text(encoding='utf-8', errors='replace')
    return (ln.strip() for ln in raw_content.splitlines() if ln.strip() and ln.strip()[0] not in '#$')

def _hip_to_hr_from_txt(path: object) -> object:
    mapping: object = {}
    for cleaned in _iter_clean_txt_lines(path):
        hit: object = _HR_SPACE_PAT.search(' ' + cleaned)
        if hit is not None:
            hr_num: object = int(hit.group(1))
            tokens: object = cleaned[hit.end():].split()
            for pos in range(len(tokens) - 1):
                if tokens[pos] in ('V', 'G') and tokens[pos + 1].isdigit():
                    mapping[int(tokens[pos + 1])] = hr_num
                    break
    return mapping

def _dedup_repeated_phrase(words: object, default_label: object) -> object:
    if not words:
        return default_label
    total: object = len(words)
    half: object = total // 2
    if total % 2 == 0 and words[:half] == words[half:]:
        return ' '.join(words[:half])
    return words[0]

def parse_iau_txt(path: object) -> object:
    records: object = {}
    for cleaned in _iter_clean_txt_lines(path):
        hit: object = _HR_SPACE_PAT.search(' ' + cleaned)
        if hit is None:
            continue
        hr_num: object = int(hit.group(1))
        prefix_words: object = cleaned[:hit.start()].strip().split()
        star_name: object = _dedup_repeated_phrase(prefix_words, f'HR{hr_num}')
        tail_tokens: object = cleaned[hit.end():].strip().split()
        raw_desig: object = tail_tokens[0] if tail_tokens else ''
        desig: object = '' if raw_desig in ('_', '-') else raw_desig
        records[hr_num] = dict(name=star_name, designation=desig, hr=hr_num)
    return records

def _as_int(value: object) -> object:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    s_val: object = str(value).strip()
    if not s_val or s_val in ('_', '-'):
        return None
    try:
        return int(float(s_val.split()[0]))
    except (TypeError, ValueError):
        return None

def _cell_str(row: object, col_map: object, key: object) -> object:
    idx: object = col_map.get(key)
    if idx is None or idx >= len(row) or row[idx] is None:
        return ''
    return str(row[idx]).strip()

def parse_iau_xlsx(path: object=None) -> object:
    """Parse WGSN Excel star name table and cross-match HR numbers."""
    from openpyxl import load_workbook
    target: object = Path(path) if path is not None else find_iau_xlsx()
    if target is None or not target.is_file():
        raise FileNotFoundError('IAU CSN xlsx not found under star_tracker/data')
    book: object = load_workbook(target, read_only=True, data_only=True)
    ws: object = book[book.sheetnames[0]]
    all_rows: object = list(ws.iter_rows(values_only=True))
    if len(all_rows) < 3:
        return []
    hdr_pos: object = next((idx for idx, r in enumerate(all_rows) if r and r[0] == 'proper names'))
    col_map: object = {str(cell).strip() if cell is not None else '': idx for idx, cell in enumerate(all_rows[hdr_pos])}
    fallback_txt: object = parse_iau_txt(IAU_TXT) if IAU_TXT.is_file() else {}
    by_lower_name: object = {entry['name'].lower(): hr_id for hr_id, entry in fallback_txt.items()}
    hip_bridge: object = _hip_to_hr_from_txt(IAU_TXT)
    parsed_rows: object = []
    for r_tuple in all_rows[hdr_pos + 1:]:
        if not r_tuple or r_tuple[0] is None or (not str(r_tuple[0]).strip()):
            continue
        proper: object = _cell_str(r_tuple, col_map, 'proper names')
        desig: object = _cell_str(r_tuple, col_map, 'Designation')
        bayer: object = _cell_str(r_tuple, col_map, 'Bayer ID')
        hip_idx: object = col_map.get('HIP')
        hip_val: object = _as_int(r_tuple[hip_idx]) if hip_idx is not None and hip_idx < len(r_tuple) else None
        hr_match: object = HR_PAT.search(desig)
        if hr_match is not None:
            hr_val: object = int(hr_match.group(1))
        elif hip_val is not None and hip_val in hip_bridge:
            hr_val: object = hip_bridge[hip_val]
        else:
            hr_val: object = by_lower_name.get(proper.lower())
        parsed_rows.append(dict(name=proper, designation=desig or bayer, hr=hr_val, hip=hip_val))
    return parsed_rows

def _records_to_bundle(rows: object, source: object) -> object:
    hr_map: object = {str(int(r['hr'])): r for r in rows if r.get('hr') is not None}
    hip_map: object = {str(int(r['hip'])): r for r in rows if r.get('hip') is not None}
    return dict(format=JSON_FORMAT, source=source, n_names=len(rows), by_hr=hr_map, by_hip=hip_map)

def _legacy_bundle(raw: object) -> object:
    hr_map: object = {str(int(k)): v for k, v in raw.items()}
    return dict(format=JSON_FORMAT, source='legacy-json', n_names=len(hr_map), by_hr=hr_map, by_hip={})

def _write_bundle(txt: object=None) -> object:
    xlsx_file: object = find_iau_xlsx()
    if xlsx_file is not None:
        payload: object = _records_to_bundle(parse_iau_xlsx(xlsx_file), xlsx_file.name)
    else:
        txt_file: object = txt or IAU_TXT
        txt_dict: object = parse_iau_txt(txt_file)
        items: object = [dict(name=info['name'], designation=info.get('designation') or '', hr=hr_id, hip=None) for hr_id, info in txt_dict.items()]
        payload: object = _records_to_bundle(items, Path(txt_file).name)
    IAU_JSON.parent.mkdir(parents=True, exist_ok=True)
    IAU_JSON.write_text(json_dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    return payload

def rebuild_cache(txt: object=None) -> object:
    _write_bundle(txt)
    _bundle.cache_clear()
    return IAU_JSON

def _xlsx_newer_than_json() -> object:
    xlsx_file: object = find_iau_xlsx()
    if xlsx_file is None or not IAU_JSON.exists():
        return xlsx_file is not None
    return xlsx_file.stat().st_mtime > IAU_JSON.stat().st_mtime

@lru_cache(maxsize=1)
def _bundle() -> object:
    if _xlsx_newer_than_json() or not IAU_JSON.exists():
        return _write_bundle()
    loaded: object = json_loads(IAU_JSON.read_text(encoding='utf-8'))
    if isinstance(loaded, dict):
        if loaded.get('format') == JSON_FORMAT:
            return loaded
        if 'by_hr' not in loaded:
            return _legacy_bundle(loaded)
    return loaded

def _table() -> object:
    return {int(k): v for k, v in _bundle()['by_hr'].items()}

def lookup_hr(hr: object) -> object:
    return _table().get(int(hr))

def lookup_hip(hip: object) -> object:
    return _bundle()['by_hip'].get(str(int(hip)))

def n_named_hr() -> object:
    return len(_bundle()['by_hr'])

def n_iau_names() -> object:
    return int(_bundle()['n_names'])

def label_hr(hr: object, compact: object=True) -> object:
    hr_i: object = int(hr)
    entry: object = lookup_hr(hr_i)
    if entry and entry.get('name'):
        star_n: object = entry['name']
        if compact:
            return f'{star_n} HR{hr_i}'
        desig: object = entry.get('designation') or ''
        suffix: object = f' ({desig})' if desig else ''
        return f'{star_n}{suffix}  HR {hr_i}'
    return f'HR {hr_i}'

def id_scheme(catalog_source: object) -> object:
    upper_src: object = str(catalog_source).upper()
    if 'BSC5' in upper_src or 'BRIGHT STAR' in upper_src:
        return 'HR'
    return 'HIP' if 'HIP' in upper_src else 'ID'

def describe_index(catalog: object, idx: object) -> object:
    """Build display dictionary for catalog entry `idx`."""
    pos: object = int(idx)
    cat_id: object = int(catalog.ids[pos])
    kind: object = id_scheme(catalog.source)
    entry: object = None
    if kind == 'HR':
        entry: object = lookup_hr(cat_id)
        disp: object = label_hr(cat_id, compact=False) if entry and entry.get('name') else f'HR {cat_id}'
    elif kind == 'HIP':
        entry: object = lookup_hip(cat_id)
        if entry and entry.get('name'):
            disp: object = f"{entry['name']}  HIP {cat_id}"
        else:
            entry, disp = (None, f'HIP {cat_id}')
    else:
        disp: object = f'{kind} {cat_id}'
    ra_arr, dec_arr = vectors_to_ra_dec(catalog.vectors[pos:pos + 1])
    return dict(catalog_idx=pos, id=cat_id, id_scheme=kind, iau_name=entry.get('name') if entry else None, designation=entry.get('designation') or None if entry else None, label=disp, mag=float(catalog.mags[pos]), ra_deg=float(degrees(ra_arr[0])), dec_deg=float(degrees(dec_arr[0])))

def compact_tag(catalog: object, idx: object, lookup: object) -> object:
    cat_id: object = int(catalog.ids[int(idx)])
    kind: object = id_scheme(catalog.source)
    if lookup:
        if kind == 'HR':
            return label_hr(cat_id, compact=True)
        if kind == 'HIP':
            entry: object = lookup_hip(cat_id)
            if entry and entry.get('name'):
                return f"{entry['name']} HIP{cat_id}"
    return f'{kind} {cat_id}'
