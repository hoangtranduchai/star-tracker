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


def test_api_repro_status_and_fallback_alert(star_tracker_root: Path, tmp_path: Path, monkeypatch) -> None:
    import app as web_app

    monkeypatch.setattr(web_app, 'BASE', tmp_path)
    client = web_app.app.test_client()

    r_repro = client.get('/api/repro-status')
    assert r_repro.status_code == 200
    j_repro = r_repro.get_json()
    assert j_repro['bundle']['ok'] is True
    assert j_repro['bundle']['n_verified'] == 13
    assert j_repro['storage_policy']['default_retention_mode'] == 'ephemeral'
    assert j_repro['storage_policy']['session_isolation'] is True
    assert j_repro['storage_policy']['error_rollback_cleanup'] is True

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


def test_auto_router_explicit_fallback_when_cnn_checkpoint_missing(star_tracker_root: Path, tmp_path: Path, monkeypatch) -> None:
    import app as web_app

    monkeypatch.setattr(web_app, 'BASE', tmp_path)
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


def test_tampered_checkpoint_blocked_before_torch_load_and_falls_back_to_cog(tmp_path: Path, monkeypatch) -> None:
    import torch
    from src.camera import demo_camera
    from src.centroid_cnn import CNNCentroidDetector

    # Create a >1MB fake/corrupted file named MobileUNet_B10_50.pt
    bad_ckpt = tmp_path / 'MobileUNet_B10_50.pt'
    bad_ckpt.write_bytes(b'\x00' * (1_100_000) + b'TAMPERED')

    torch_load_called = False

    def _forbid_torch_load(*args, **kwargs):
        nonlocal torch_load_called
        torch_load_called = True
        raise AssertionError('torch.load must NEVER be called when SHA-256 mismatches!')

    monkeypatch.setattr(torch, 'load', _forbid_torch_load)

    cam = demo_camera().downscaled(4)
    det = CNNCentroidDetector(cam, weights_path=bad_ckpt)
    img = np.full((128, 128), 64, dtype=np.uint16)
    det.detect(img)

    assert torch_load_called is False
    assert det.last_fallback is True
    assert det.last_backend == 'classical'
    assert det.last_error and 'CHECKPOINT_SHA256_MISMATCH' in det.last_error


def test_cli_accepts_custom_optics_flags_on_real_calibrated_frame(star_tracker_root: Path, tmp_path: Path, capsys) -> None:
    import demo_star_tracker

    alt60 = star_tracker_root / 'data' / 'tetra3' / '2019-07-29T204726_Alt60_Azi-135_Try1.tiff'
    assert alt60.is_file()
    rc = demo_star_tracker.main([
        '--image', str(alt60),
        '--focal-mm', '35.291113627236776',
        '--pixel-um', '6.9',
        '--k1', '0.10021753616812087',
        '--centroid', 'auto',
        '--no-show',
        '--out', str(tmp_path),
    ])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert 'Status      : SOLVED' in out
    assert 'att err' in out


def test_ttl_upload_error_rolls_back_with_zero_orphan_files(tmp_path: Path, monkeypatch) -> None:
    """Failed HTTP 400 upload in TTL mode must immediately delete its slot and leave 0 orphan files."""
    import app as web_app
    from src.upload_store import user_uploads_root

    monkeypatch.setattr(web_app, 'BASE', tmp_path)
    client = web_app.app.test_client()

    # Upload 128x128 image in TTL mode WITHOUT focal_mm/pixel_um -> triggers ValueError (HTTP 400)
    r = client.post(
        '/api/run-upload',
        data={
            'image': (io.BytesIO(_make_png_bytes(77)), 'orphan_check.png'),
            'retention_mode': 'ttl',
            'centroid_backend': 'classical',
        },
        content_type='multipart/form-data',
    )
    assert r.status_code == 400
    root = user_uploads_root(tmp_path)
    remaining = [p for p in root.iterdir() if p.is_dir()] if root.is_dir() else []
    assert remaining == [], f'Found orphan TTL slot after HTTP 400 error: {remaining}'

    # Confirm ERROR_ROLLBACK_DELETE was recorded in execution_log.jsonl
    entries = client.get('/api/execution-log?limit=10').get_json()['entries']
    assert any(
        e.get('event_type') == 'DATA_DELETION'
        and e.get('action') == 'ERROR_ROLLBACK_DELETE'
        and e.get('verified_gone') is True
        for e in entries
    )


def test_browser_session_isolation_prevents_cross_user_ttl_access_and_delete(tmp_path: Path, monkeypatch) -> None:
    """Browser B must NOT list, preview, or delete Browser A's TTL uploads."""
    import app as web_app
    from src.upload_store import user_uploads_root

    monkeypatch.setattr(web_app, 'BASE', tmp_path)
    client_a = web_app.app.test_client()
    client_b = web_app.app.test_client()

    # Each browser receives its own HttpOnly st_sid cookie on GET /
    assert client_a.get('/').status_code == 200
    assert client_b.get('/').status_code == 200

    # Browser A uploads in TTL mode
    r_a = client_a.post(
        '/api/run-upload',
        data={
            'image': (io.BytesIO(_make_png_bytes(31)), 'private_sky_a.png'),
            'focal_mm': '50',
            'pixel_um': '14.88',
            'retention_mode': 'ttl',
            'centroid_backend': 'classical',
        },
        content_type='multipart/form-data',
    )
    assert r_a.status_code == 200
    j_a = r_a.get_json()
    uid_a = j_a['storage_control']['upload_id']
    assert j_a['storage_control']['session_scoped'] is True
    prev_url_a = j_a['clean_url']

    # Browser A sees its upload & can fetch its preview
    assert len(client_a.get('/api/uploads').get_json()['uploads']) == 1
    assert client_a.get(prev_url_a).status_code == 200

    # Browser B sees 0 uploads, gets 404 on A's preview & single delete, and DELETE /api/uploads does not harm A
    assert client_b.get('/api/uploads').get_json()['uploads'] == []
    assert client_b.get(prev_url_a).status_code == 404
    assert client_b.delete(f'/api/uploads/{uid_a}').status_code == 404
    assert client_b.delete('/api/uploads').get_json()['n_deleted_sessions'] == 0
    assert (user_uploads_root(tmp_path) / uid_a).is_dir()

    # Browser A deletes its own upload -> 200 verified_gone & preview 404
    r_del = client_a.delete(f'/api/uploads/{uid_a}')
    assert r_del.status_code == 200 and r_del.get_json()['verified_gone'] is True
    assert client_a.get(prev_url_a).status_code == 404
    assert not (user_uploads_root(tmp_path) / uid_a).exists()


def test_compare_and_compare_upload_log_checkpoint_status_and_atomic_jsonl(tmp_path: Path, monkeypatch) -> None:
    """/api/compare and /api/compare-upload must log truthful checkpoint_status with zero leftover temp files."""
    import app as web_app

    monkeypatch.setattr(web_app, 'BASE', tmp_path)
    client = web_app.app.test_client()

    r_cmp = client.post('/api/compare', json={'seed': 42, 'mode': 'fast', 'backends': ['classical']})
    assert r_cmp.status_code == 200

    r_up = client.post(
        '/api/compare-upload',
        data={
            'image': (io.BytesIO(_make_png_bytes(55)), 'cmp_check.png'),
            'focal_mm': '50',
            'pixel_um': '14.88',
            'retention_mode': 'ephemeral',
        },
        content_type='multipart/form-data',
    )
    assert r_up.status_code == 200

    entries = client.get('/api/execution-log?limit=20').get_json()['entries']
    cmp_rows = [
        e for e in entries
        if e.get('event_type') == 'PIPELINE_RUN' and e.get('endpoint') in ('/api/compare', '/api/compare-upload')
    ]
    assert len(cmp_rows) >= 2
    for row in cmp_rows:
        assert row.get('checkpoint_status') in ('available', 'missing', 'simulated_missing')

    # Verify atomic write left zero .tmp files next to execution_log.jsonl
    out_dir = tmp_path / 'data' / 'outputs'
    assert not list(out_dir.glob('*.tmp'))
