"""Standalone reproducibility bundle verification and SHA-256 checksum utilities."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

CHECKSUM_FILE = 'CHECKSUMS.sha256'

# Canonical files required for clean-clone standalone reproducibility (checkpoint, calibrated
# real-sky samples, calibration manifests, catalog, and default pipeline/camera configs).
REPRO_BUNDLE_FILES: tuple[tuple[str, str], ...] = (
    ('checkpoint', 'third_party/cnn_star_centroid/saved_models/MobileUNet_B10_50.pt'),
    ('sample_real_sky', 'data/tetra3/2019-07-29T204726_Alt40_Azi-135_Try1.tiff'),
    ('sample_real_sky', 'data/tetra3/2019-07-29T204726_Alt60_Azi-135_Try1.tiff'),
    ('sample_real_sky', 'data/real_calibrated/zhao_mt9v022/nightsky_june16_2021.npy'),
    ('sample_real_sky', 'data/real_calibrated/zhao_mt9v022/verification_img.npy'),
    ('sample_real_sky', 'data/uploads/mount_st_helens_1.png'),
    ('sample_real_sky', 'data/uploads/real_sky/images/0006.png'),
    ('calibration', 'data/real_calibrated/manifest_real_calibrated.json'),
    ('calibration', 'data/uploads/real_sky/metadata.yaml'),
    ('calibration', 'config/camera_specs.json'),
    ('calibration', 'config/pipeline_default.json'),
    ('catalog', 'data/catalogs/BSC5'),
    ('catalog', 'data/catalogs/IAU-CSN.txt'),
)


def sha256_file(path: Path) -> str:
    """Compute hex SHA-256 digest of a file in streaming 1 MiB chunks."""
    h = hashlib.sha256()
    with path.open('rb') as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def parse_checksums_file(path: Path) -> dict[str, str]:
    """Parse GNU sha256sum format (`<hex>  <relpath>`) into {relpath: hex}."""
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            digest = parts[0].strip().lower()
            rel = parts[1].strip().lstrip('*').replace('\\', '/')
            out[rel] = digest
    return out


def generate_checksums_file(root: Path) -> Path:
    """Hash all canonical reproducibility files and write `CHECKSUMS.sha256`."""
    lines = [
        '# SHA-256 Checksums for DUT.StarTracker Standalone Reproducibility Bundle (Stage 2)',
        '# Verify with: python scripts/verify_repro_bundle.py  (or `sha256sum -c CHECKSUMS.sha256`)',
    ]
    for _cat, rel in REPRO_BUNDLE_FILES:
        fp = root / rel
        if not fp.is_file():
            raise FileNotFoundError(f'Missing required bundle artifact: {fp}')
        digest = sha256_file(fp)
        lines.append(f'{digest}  {rel}')
    out_p = root / CHECKSUM_FILE
    out_p.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return out_p


def verify_repro_bundle(root: Path) -> dict[str, Any]:
    """Verify every canonical artifact against `CHECKSUMS.sha256`."""
    cs_path = root / CHECKSUM_FILE
    expected = parse_checksums_file(cs_path)
    entries: list[dict[str, Any]] = []
    missing: list[str] = []
    mismatched: list[str] = []
    total_bytes = 0

    for category, rel in REPRO_BUNDLE_FILES:
        fp = root / rel
        exp_hash = expected.get(rel)
        exists = fp.is_file()
        size_b = int(fp.stat().st_size) if exists else 0
        total_bytes += size_b
        act_hash = sha256_file(fp) if exists else None
        if not exists:
            status = 'missing'
            missing.append(rel)
        elif exp_hash is None:
            status = 'unlisted_in_checksums'
            mismatched.append(rel)
        elif act_hash != exp_hash:
            status = 'checksum_mismatch'
            mismatched.append(rel)
        else:
            status = 'verified'
        entries.append({
            'category': category,
            'path': rel,
            'exists': exists,
            'size_bytes': size_b,
            'expected_sha256': exp_hash,
            'actual_sha256': act_hash,
            'status': status,
        })

    ckpt_entry = next((e for e in entries if e['category'] == 'checkpoint'), None)
    return {
        'ok': (len(missing) == 0 and len(mismatched) == 0 and cs_path.is_file()),
        'checksum_file': CHECKSUM_FILE,
        'checksum_file_exists': cs_path.is_file(),
        'n_total': len(entries),
        'n_verified': sum(1 for e in entries if e['status'] == 'verified'),
        'total_bundle_mb': round(total_bytes / (1024.0 * 1024.0), 2),
        'checkpoint_status': ckpt_entry['status'] if ckpt_entry else 'missing',
        'checkpoint_sha256': ckpt_entry['actual_sha256'] if ckpt_entry else None,
        'missing': missing,
        'mismatched': mismatched,
        'entries': entries,
    }
