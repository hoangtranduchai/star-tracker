"""Download and verify the Yale Bright Star Catalog (BSC5) binary file."""
from hashlib import sha256
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.catalog import BSC5_SIZE, CatalogManager

def main() -> object:
    target: object = ROOT.joinpath('data', 'catalogs', 'BSC5')
    fetched: object = CatalogManager.fetch_bsc5(target)
    raw_bytes: object = fetched.read_bytes()
    hdr_info: object = CatalogManager.parse_bsc5_header(fetched)
    rows: object = (('BSC5 path     ', fetched), ('size          ', f'{len(raw_bytes)} bytes (expected {BSC5_SIZE})'), ('sha256        ', sha256(raw_bytes).hexdigest()), ('endian        ', hdr_info['endian']), ('STARN         ', hdr_info['STARN']), ('NBENT         ', hdr_info['NBENT']), ('J2000 flag    ', hdr_info['j2000']))
    print('\n'.join((f'{k}: {v}' for k, v in rows)))
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
