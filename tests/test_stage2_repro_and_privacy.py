"""Stage 2 verification tests: standalone reproducibility bundle, CoG fallback transparency,
overwrite-safe isolated uploads, TTL auto-cleanup, right-to-delete, and audit logging."""
from __future__ import annotations

import io
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image


def _make_png_bytes(seed: int = 0) -> bytes:
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 40, size=(128, 128), dtype=np.uint8)
    # Stamp a few synthetic bright dots so detector executes cleanly
    for (r, c) in ((32, 32), (32, 96), (96, 32), (96, 96), (64, 64)):
        arr[r - 1 : r + 2, c - 1 : c + 2] = 240
    buf = io.BytesIO()
    Image.fromarray(arr, mode='L').save(buf, format='PNG')
    return buf.getvalue()


def test_repro_bundle_checksums_all_verified(star_tracker_root: Path) -> None:
    from src.repro_bundle import verify_repro_bundle

    res = verify_repro_bundle(star_tracker_root)
    assert res['checksum_file_exists'] is True
    assert res['ok'] is True, f"Bundle verification failed: missing={res['missing']} mismatched={res['mismatched']}"
    assert res['n_verified'] == res['n_total'] == 13
    assert res['checkpoint_status'] == 'verified'
    assert res['checkpoint_sha256'] and len(res['checkpoint_sha256']) == 64


def test_api_repro_status_and_fallback_alert(star_tracker_root: Path) -> None:
    import app as web_app

    client = web_app.app.test_client()

    r_repro = client.get('/api/repro-status')
    assert r_repro.status_code == 200
    j_repro = r_repro.get_json()
    assert j_repro['bundle']['ok'] is True
    assert j_repro['bundle']['n_verified'] == 13
    assert j_repro['storage_policy']['default_retention_mode'] == 'ephemeral'

    # Deliberately trigger real CNN -> CoG fallback via simulate_missing_weights=True
    r_fb = client.post(
        '/api/run',
        json={
            'mode': 'fast',
            'seed': 42,
            'centroid_backend': 'cnn',
            'simulate_missing_weights': True,
            'catalog': 'bsc5',
            'solver': 'svd',
        },
    )
    assert r_fb.status_code == 200
    j_fb = r_fb.get_json()
    assert j_fb['requested_backend'] == 'cnn'
    assert j_fb['executed_backend'] == 'classical'
    assert j_fb['centroid_fallback'] is True
    assert j_fb['fallback_reason'] and '__simulated_missing_checkpoint__' in j_fb['fallback_reason']
    assert 'FALLBACK_TO_COG' in j_fb['execution_mode_summary']
    assert j_fb['checkpoint_status'] == 'simulated_missing'

    # Confirm structured audit log captured the fallback event
    r_log = client.get('/api/execution-log?limit=15')
    assert r_log.status_code == 200
    entries = r_log.get_json()['entries']
    assert any(
        e.get('event_type') == 'PIPELINE_RUN'
        and e.get('fallback_triggered') is True
        and 'FALLBACK_TO_COG' in str(e.get('mode_summary', ''))
        for e in entries
    ), 'Expected FALLBACK_TO_COG record in /api/execution-log'


def test_upload_ephemeral_zero_retention_and_no_bundled_overwrite(star_tracker_root: Path) -> None:
    import app as web_app
    from src.repro_bundle import sha256_file

    bundled_msh = star_tracker_root / 'data' / 'uploads' / 'mount_st_helens_1.png'
    sha_before = sha256_file(bundled_msh)

    client = web_app.app.test_client()
    valid_sidecar = json.dumps({'q_gt': [1.0, 0.0, 0.0, 0.0], 'stars_in_fov': []}).encode('utf-8')
    r = client.post(
        '/api/run-upload',
        data={
            'image': (io.BytesIO(_make_png_bytes(1)), 'mount_st_helens_1.png'),
            'sidecar': (io.BytesIO(valid_sidecar), 'mount_st_helens_1.json'),
            'focal_mm': '50',
            'pixel_um': '14.88',
            'retention_mode': 'ephemeral',
            'centroid_backend': 'classical',
        },
        content_type='multipart/form-data',
    )
    assert r.status_code == 200
    j = r.get_json()
    sc = j['storage_control']
    assert sc['retention_mode'] == 'ephemeral'
    assert sc['overwrite_protected'] is True
    assert sc['previews_isolated'] is True
    assert sc['deleted_immediately'] is True
    assert sc['verified_gone_on_disk'] is True
    assert sc['storage_rel_dir'].startswith('data/user_uploads/')
    # Ephemeral previews must be returned inline as data URIs (0 bytes written to shared data/outputs)
    assert str(j['clean_url']).startswith('data:image/png;base64,')
    assert str(j['input_url']).startswith('data:image/png;base64,')
    assert j['clean_png'] is None

    # Verify slot is truly absent on disk and bundled mount_st_helens_1.png was NEVER overwritten
    slot_dir = star_tracker_root / sc['storage_rel_dir'].rstrip('/')
    assert not slot_dir.exists()
    assert sha256_file(bundled_msh) == sha_before


def test_upload_ttl_collision_isolation_and_right_to_delete(star_tracker_root: Path) -> None:
    import app as web_app
    from src.upload_store import cleanup_expired_uploads, user_uploads_root

    client = web_app.app.test_client()

    # Clean start
    client.delete('/api/uploads')

    valid_sidecar = json.dumps({'q_gt': [1.0, 0.0, 0.0, 0.0], 'stars_in_fov': []}).encode('utf-8')
    # Upload TWO files with the exact same filename in TTL mode -> must get 2 distinct UUID dirs
    r1 = client.post(
        '/api/run-upload',
        data={
            'image': (io.BytesIO(_make_png_bytes(10)), 'same_sky_frame.png'),
            'sidecar': (io.BytesIO(valid_sidecar), 'same_sky_frame.json'),
            'focal_mm': '50',
            'pixel_um': '14.88',
            'retention_mode': 'ttl',
            'centroid_backend': 'classical',
        },
        content_type='multipart/form-data',
    )
    r2 = client.post(
        '/api/run-upload',
        data={
            'image': (io.BytesIO(_make_png_bytes(20)), 'same_sky_frame.png'),
            'focal_mm': '50',
            'pixel_um': '14.88',
            'retention_mode': 'ttl',
            'centroid_backend': 'classical',
        },
        content_type='multipart/form-data',
    )
    assert r1.status_code == 200 and r2.status_code == 200
    sc1 = r1.get_json()['storage_control']
    sc2 = r2.get_json()['storage_control']
    assert sc1['upload_id'] != sc2['upload_id']
    assert sc1['storage_rel_dir'] != sc2['storage_rel_dir']
    assert sc1['deleted_immediately'] is False
    assert sc2['deleted_immediately'] is False

    # Both slots must appear in GET /api/uploads and serve isolated previews until deleted
    r_list = client.get('/api/uploads')
    assert r_list.status_code == 200
    ids = {u['upload_id'] for u in r_list.get_json()['uploads']}
    assert sc1['upload_id'] in ids and sc2['upload_id'] in ids
    prev_url_1 = r1.get_json()['clean_url']
    assert prev_url_1 == f"/api/uploads/{sc1['upload_id']}/preview/demo_clean.png"
    assert client.get(prev_url_1).status_code == 200

    # Delete slot 1 individually -> verified gone on disk, preview returns 404, slot 2 still present
    r_del1 = client.delete(f"/api/uploads/{sc1['upload_id']}")
    assert r_del1.status_code == 200
    j_del1 = r_del1.get_json()
    assert j_del1['deleted'] is True and j_del1['verified_gone'] is True
    assert not (user_uploads_root(star_tracker_root) / sc1['upload_id']).exists()
    assert client.get(prev_url_1).status_code == 404
    assert (user_uploads_root(star_tracker_root) / sc2['upload_id']).exists()

    # Force-expire slot 2 metadata and confirm TTL auto-cleanup purges it
    meta2_p = user_uploads_root(star_tracker_root) / sc2['upload_id'] / 'meta.json'
    meta2 = json.loads(meta2_p.read_text(encoding='utf-8'))
    meta2['expires_at_epoch'] = time.time() - 5.0
    meta2_p.write_text(json.dumps(meta2), encoding='utf-8')
    purged = cleanup_expired_uploads(star_tracker_root)
    assert sc2['upload_id'] in purged
    assert not (user_uploads_root(star_tracker_root) / sc2['upload_id']).exists()

    # Confirm DATA_DELETION audit event was logged
    r_log = client.get('/api/execution-log?limit=15')
    entries = r_log.get_json()['entries']
    assert any(
        e.get('event_type') == 'DATA_DELETION'
        and e.get('upload_id') == sc1['upload_id']
        and e.get('verified_gone') is True
        for e in entries
    )

    # Final cleanup leaves data/user_uploads clean
    r_clr = client.delete('/api/uploads')
    assert r_clr.status_code == 200
    assert r_clr.get_json()['verified_empty'] is True


def test_auto_router_explicit_fallback_when_cnn_checkpoint_missing(star_tracker_root: Path) -> None:
    import app as web_app

    zhao_p = star_tracker_root / 'data' / 'real_calibrated' / 'zhao_mt9v022' / 'nightsky_june16_2021.npy'
    assert zhao_p.is_file()
    client = web_app.app.test_client()
    r = client.post(
        '/api/run',
        json={
            'image': 'real_calibrated/zhao_mt9v022/nightsky_june16_2021.npy',
            'centroid_backend': 'auto',
            'simulate_missing_weights': True,
        },
    )
    assert r.status_code == 200
    j = r.get_json()
    assert j['requested_backend'] == 'auto'
    assert j['executed_backend'] == 'classical'
    assert j['centroid_fallback'] is True
    assert 'FALLBACK_TO_COG' in j['execution_mode_summary']
    assert j['fallback_reason'] and '__simulated_missing_checkpoint__' in j['fallback_reason']
    # On Zhao nightsky with CoG only, safety guard must still return LOST (0% False Lock)
    assert j['status'] == 'LOST'


def test_stage2_evidence_markdown_has_zero_null_bytes(star_tracker_root: Path) -> None:
    for rel in (
        'AI2026_Portfolio/MINH_CHUNG_CAI_TIEN_CHANG_2.md',
        'AI2026_Portfolio/BAO_CAO_CAI_TIEN_VONG_CHUNG_KET_CHANG_2.md',
        'AI2026_Portfolio/stage2_evidence/vps_deploy_and_smoke.txt',
        'REPRODUCIBILITY.md',
        'CHECKSUMS.sha256',
    ):
        fp = star_tracker_root / rel
        if fp.is_file():
            raw = fp.read_bytes()
            assert raw.count(0) == 0, f'Found NUL bytes in {rel} (UTF-16 corruption)'
            raw.decode('utf-8')
