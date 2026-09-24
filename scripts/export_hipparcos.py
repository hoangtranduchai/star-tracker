"""Compile Hipparcos V<=6.0 catalog and K-vector table into compressed NPZ archives."""
from json import dumps as json_dumps
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.catalog import CatalogManager
from src.kvector import KVectorTable

def main() -> object:
    cat_dir: object = ROOT.joinpath('data', 'catalogs')
    search_names: object = ('hipparcos_v6.tsv', 'starcat.tsv', 'hip_main.dat')
    tsv_file: object = next((cat_dir / nm for nm in search_names if (cat_dir / nm).exists()), None)
    if tsv_file is None:
        report: object = dict(status='missing_tsv', note='bỏ qua — chưa có bảng TSV Hipparcos trong thư mục data/catalogs/')
    else:
        try:
            raw_cat: object = CatalogManager.load_hipparcos_tsv(tsv_file, max_mag=6.0, epoch_year=2026.7)
            pruned: object = CatalogManager.filter_close_pairs(raw_cat, 60.0)
            cat_npz: object = CatalogManager.save_npz(pruned, cat_dir / 'hipparcos_v6.npz')
            kv_tbl: object = KVectorTable.build(pruned)
            kv_npz: object = kv_tbl.save(cat_dir / 'hipparcos_v6_kvector.npz')
            report: object = dict(status='ok', source=pruned.source, n_stars=pruned.num_stars, npz_bytes=cat_npz.stat().st_size, kvector_pairs=kv_tbl.num_pairs, kvector_bytes=kv_npz.stat().st_size, tsv=str(tsv_file.name))
        except Exception as err:
            report: object = dict(status='error', error=str(err), tsv=str(tsv_file))
    out_json: object = ROOT.joinpath('data', 'outputs', 'hipparcos_export.json')
    out_json.parent.mkdir(parents=True, exist_ok=True)
    text_out: object = json_dumps(report, indent=2)
    out_json.write_text(text_out, encoding='utf-8')
    print(text_out)
    return 1 if report.get('status') == 'error' else 0
if __name__ == '__main__':
    raise SystemExit(main())
