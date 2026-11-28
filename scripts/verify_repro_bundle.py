"""Verify (or generate) SHA-256 checksums for the standalone reproducibility bundle."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.repro_bundle import generate_checksums_file, verify_repro_bundle


def main() -> int:
    ap = argparse.ArgumentParser(description='Verify or regenerate CHECKSUMS.sha256 for StarTracker.')
    ap.add_argument('--generate', action='store_true', help='Regenerate CHECKSUMS.sha256 from workspace files.')
    ap.add_argument('--json-out', type=str, default=None, help='Optional path to save JSON verification report.')
    args = ap.parse_args()

    if args.generate:
        out_p = generate_checksums_file(ROOT)
        # Ensure pure LF line endings for GNU sha256sum compatibility across Linux, macOS, and Windows
        out_p.write_bytes(out_p.read_bytes().replace(b'\r\n', b'\n'))
        print(f'[OK] Generated {out_p}')

    report = verify_repro_bundle(ROOT)
    for e in report['entries']:
        mark = 'PASS' if e['status'] == 'verified' else 'FAIL'
        h_short = (e['actual_sha256'] or 'missing')[:16]
        print(f"  [{mark}] {e['category']:15s} {e['path']:62s} ({e['size_bytes']/1024:8.1f} KB) sha256={h_short}...")

    print(
        f"\n[SUMMARY] verified={report['n_verified']}/{report['n_total']} "
        f"({report['total_bundle_mb']:.2f} MB) | checkpoint={report['checkpoint_status']} | ok={report['ok']}"
    )
    if args.json_out:
        jp = Path(args.json_out)
        jp.parent.mkdir(parents=True, exist_ok=True)
        jp.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f'[OK] Saved JSON report to {jp}')

    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
