"""Stage 2 verification tests: standalone reproducibility bundle, CoG fallback transparency,
overwrite-safe isolated uploads, TTL auto-cleanup, right-to-delete, session isolation, and audit logging."""
from __future__ import annotations

import io
import json
import re
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

    # Confirm structured audit log captured the fallback event without leaking absolute OS paths
    r_log = client.get('/api/execution-log?limit=15')
    assert r_log.status_code == 200
    entries = r_log.get_json()['entries']
    fb_entries = [
        e for e in entries
        if e.get('event_type') == 'PIPELINE_RUN'
        and e.get('fallback_triggered') is True
        and 'FALLBACK_TO_COG' in str(e.get('mode_summary', ''))
    ]
    assert fb_entries, 'Expected FALLBACK_TO_COG record in /api/execution-log'
    reason_logged = str(fb_entries[0].get('fallback_reason') or '')
    assert not re.search(r'[A-Za-z]:\\', reason_logged), f'Leaked Windows host path in audit log: {reason_logged}'
    assert '/app/' not in reason_logged


def test_upload_ephemeral_zero_retention_and_no_bundled_overwrite(
    star_tracker_root: Path, tmp_path: Path, monkeypatch
) -> None:
    import app as web_app
    from src.repro_bundle import sha256_file

    monkeypatch.setattr(web_app, 'BASE', tmp_path)
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
    assert sc['session_scoped'] is True
    assert sc['deleted_immediately'] is True
    assert sc['verified_gone_on_disk'] is True
    assert sc['storage_rel_dir'].startswith('data/user_uploads/')
    # Ephemeral previews must be returned inline as data URIs (0 bytes written to shared data/outputs)
    assert str(j['clean_url']).startswith('data:image/png;base64,')
    assert str(j['input_url']).startswith('data:image/png;base64,')
    assert j['clean_png'] is None

    # Verify slot is truly absent on disk and bundled mount_st_helens_1.png was NEVER overwritten
    slot_dir = tmp_path / sc['storage_rel_dir'].rstrip('/')
    assert not slot_dir.exists()
    assert sha256_file(bundled_msh) == sha_before


def test_upload_ttl_collision_isolation_and_right_to_delete(tmp_path: Path, monkeypatch) -> None:
    import app as web_app
    from src.upload_store import cleanup_expired_uploads, user_uploads_root

    monkeypatch.setattr(web_app, 'BASE', tmp_path)
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
    assert not (user_uploads_root(tmp_path) / sc1['upload_id']).exists()
    assert client.get(prev_url_1).status_code == 404
    assert (user_uploads_root(tmp_path) / sc2['upload_id']).exists()

    # Force-expire slot 2 metadata and confirm TTL auto-cleanup purges & audits it
    meta2_p = user_uploads_root(tmp_path) / sc2['upload_id'] / 'meta.json'
    meta2 = json.loads(meta2_p.read_text(encoding='utf-8'))
    meta2['expires_at_epoch'] = time.time() - 5.0
    meta2_p.write_text(json.dumps(meta2), encoding='utf-8')
    purged = cleanup_expired_uploads(tmp_path)
    assert sc2['upload_id'] in purged
    assert not (user_uploads_root(tmp_path) / sc2['upload_id']).exists()

    # Confirm DATA_DELETION audit events were logged for both single delete and TTL expiry
    r_log = client.get('/api/execution-log?limit=20')
    entries = r_log.get_json()['entries']
    assert any(
        e.get('event_type') == 'DATA_DELETION'
        and e.get('upload_id') == sc1['upload_id']
        and e.get('verified_gone') is True
        for e in entries
    )
    assert any(
        e.get('event_type') == 'DATA_DELETION'
        and e.get('action') == 'TTL_EXPIRED_AUTO_PURGE'
        and e.get('upload_id') == sc2['upload_id']
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


def test_cli_accepts_custom_optics_flags_on_real_calibrated_frame(
    star_tracker_root: Path, tmp_path: Path, capsys, monkeypatch
) -> None:
    import demo_star_tracker
    import src.execution_log as exec_log

    # Keep CLI execution log inside tmp_path so pytest never mutates workspace data/outputs/execution_log.jsonl
    monkeypatch.setattr(exec_log, 'log_path', lambda _base: tmp_path / 'execution_log.jsonl')

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
    assert (tmp_path / 'execution_log.jsonl').is_file()


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

    # Confirm ERROR_ROLLBACK_DELETE was recorded in execution_log.jsonl (visible to owning session)
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
    """/api/compare and /api/compare-upload must log truthful checkpoint_status & sha256 with zero leftover .tmp files."""
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
        assert row.get('checkpoint_status') in ('verified', 'checksum_mismatch', 'corrupted_truncated', 'missing', 'simulated_missing')
        if row.get('checkpoint_status') == 'verified':
            assert row.get('checkpoint_sha256') and len(row['checkpoint_sha256']) == 64

    # Verify atomic write left zero .tmp files next to execution_log.jsonl
    out_dir = tmp_path / 'data' / 'outputs'
    assert not list(out_dir.glob('*.tmp'))


def test_output_route_blocks_raw_jsonl_and_traversal_returns_404(tmp_path: Path, monkeypatch) -> None:
    """Raw execution_log.jsonl must NEVER be publicly downloadable via /output/, and traversal must return 404 (not 500)."""
    import app as web_app

    monkeypatch.setattr(web_app, 'BASE', tmp_path)
    out_dir = tmp_path / 'data' / 'outputs'
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'execution_log.jsonl').write_text('{"secret":"nope"}\n', encoding='utf-8')
    (out_dir / 'other_audit.jsonl').write_text('{"secret":"nope"}\n', encoding='utf-8')

    client = web_app.app.test_client()
    assert client.get('/output/execution_log.jsonl').status_code in (403, 404)
    assert client.get('/output/other_audit.jsonl').status_code in (403, 404)
    r_trav = client.get('/output/..%2f..%2fapp.py')
    assert r_trav.status_code == 404


def test_cross_session_execution_log_isolation_blocks_filename_leak(tmp_path: Path, monkeypatch) -> None:
    """Browser B must NEVER see Browser A's uploaded filenames, sidecars, or upload_ids in /api/execution-log."""
    import app as web_app

    monkeypatch.setattr(web_app, 'BASE', tmp_path)
    client_a = web_app.app.test_client()
    client_b = web_app.app.test_client()
    assert client_a.get('/').status_code == 200
    assert client_b.get('/').status_code == 200

    # Non-upload run should remain visible to all sessions
    r_pub = client_a.post('/api/run', json={'seed': 42, 'mode': 'fast', 'centroid_backend': 'classical'})
    assert r_pub.status_code == 200

    # Ephemeral private upload by Browser A
    valid_sidecar = json.dumps({'q_gt': [1.0, 0.0, 0.0, 0.0], 'stars_in_fov': []}).encode('utf-8')
    r_a = client_a.post(
        '/api/run-upload',
        data={
            'image': (io.BytesIO(_make_png_bytes(91)), 'very_private_user_a.png'),
            'sidecar': (io.BytesIO(valid_sidecar), 'secret_sidecar_a.json'),
            'focal_mm': '50',
            'pixel_um': '14.88',
            'retention_mode': 'ephemeral',
            'centroid_backend': 'classical',
        },
        content_type='multipart/form-data',
    )
    assert r_a.status_code == 200
    uid_a = r_a.get_json()['storage_control']['upload_id']

    # Browser A sees its own EPHEMERAL_AUTO_DELETE & upload run
    log_a = client_a.get('/api/execution-log?limit=30').get_json()['entries']
    assert any(e.get('action') == 'EPHEMERAL_AUTO_DELETE' and e.get('upload_id') == uid_a for e in log_a)
    assert any(e.get('source_name') == 'very_private_user_a.png' for e in log_a)

    # Browser B sees the non-upload preset run, but ZERO of Browser A's upload filenames/sidecars/upload_ids
    log_b = client_b.get('/api/execution-log?limit=30').get_json()['entries']
    assert any(e.get('endpoint') == '/api/run' and e.get('source_name') == 'seed=42' for e in log_b)
    blob_b = json.dumps(log_b)
    assert 'very_private_user_a' not in blob_b
    assert 'secret_sidecar_a' not in blob_b
    assert uid_a not in blob_b
    assert not any(e.get('event_type') == 'DATA_DELETION' for e in log_b)

    # Raw JSONL on disk must store hashed owner_sid_hash (16 hex), never raw st_sid cookie
    raw_log = (tmp_path / 'data' / 'outputs' / 'execution_log.jsonl').read_text(encoding='utf-8')
    cookie_a = client_a.get_cookie('st_sid')
    assert cookie_a is not None and cookie_a.value
    assert cookie_a.value not in raw_log


def test_cookieless_upload_mints_session_writes_meta_and_blocks_idor(tmp_path: Path, monkeypatch) -> None:
    """Direct POST /api/run-upload without prior GET / must mint st_sid, write meta.json, preserve non-Latin ext, and block IDOR."""
    import app as web_app
    from src.upload_store import list_uploads, resolve_upload_preview, save_uploaded_files, user_uploads_root

    monkeypatch.setattr(web_app, 'BASE', tmp_path)
    c_direct = web_app.app.test_client()
    c_browser_b = web_app.app.test_client()
    c_nocookie = web_app.app.test_client()
    assert c_browser_b.get('/').status_code == 200

    # Direct upload without visiting GET / using non-Latin filename `星空.png`
    r_up = c_direct.post(
        '/api/run-upload',
        data={
            'image': (io.BytesIO(_make_png_bytes(101)), '星空.png'),
            'focal_mm': '50',
            'pixel_um': '14.88',
            'retention_mode': 'ttl',
            'centroid_backend': 'classical',
        },
        content_type='multipart/form-data',
    )
    assert r_up.status_code == 200
    set_cookies = r_up.headers.getlist('Set-Cookie')
    assert any('st_sid=' in c and 'HttpOnly' in c and 'SameSite=Lax' in c for c in set_cookies)
    j = r_up.get_json()
    uid = j['storage_control']['upload_id']
    prev_url = j['clean_url']
    assert j['storage_control']['session_scoped'] is True
    assert j['source_image'].endswith('.png')

    # meta.json MUST exist with non-None owner_sid and files list
    meta = json.loads((user_uploads_root(tmp_path) / uid / 'meta.json').read_text(encoding='utf-8'))
    assert meta['owner_sid'] and len(meta['owner_sid']) == 32
    assert meta['retention_mode'] == 'ttl'
    assert isinstance(meta.get('files'), list) and len(meta['files']) >= 1

    # Owning client can list & preview; Browser B and cookieless client get 0 / 404
    assert len(c_direct.get('/api/uploads').get_json()['uploads']) == 1
    assert c_direct.get(prev_url).status_code == 200
    assert c_browser_b.get('/api/uploads').get_json()['uploads'] == []
    assert c_browser_b.get(prev_url).status_code == 404
    assert c_browser_b.delete(f'/api/uploads/{uid}').status_code == 404
    assert c_nocookie.get('/api/uploads').get_json()['uploads'] == []
    assert c_nocookie.get(prev_url).status_code == 404
    assert c_nocookie.delete(f'/api/uploads/{uid}').status_code == 404

    # Verify ephemeral slots ALSO write meta.json immediately & cannot be previewed/listed by another browser
    class _Mem:
        def __init__(self, b: bytes):
            self._b = b
        def save(self, dst: Path):
            Path(dst).write_bytes(self._b)

    eph_slot = save_uploaded_files(
        tmp_path,
        _Mem(_make_png_bytes(102)),
        'inflight.png',
        retention_mode='ephemeral',
        owner_sid='a' * 32,
    )
    eph_dir = eph_slot['slot_dir']
    eph_meta_p = eph_dir / 'meta.json'
    assert eph_meta_p.is_file()
    eph_meta = json.loads(eph_meta_p.read_text(encoding='utf-8'))
    assert eph_meta['retention_mode'] == 'ephemeral'
    assert eph_meta['owner_sid'] == 'a' * 32
    (eph_dir / 'demo_clean.png').write_bytes(_make_png_bytes(103))
    assert resolve_upload_preview(tmp_path, eph_slot['upload_id'], 'demo_clean.png', owner_sid='b' * 32, require_session=True) is None
    assert resolve_upload_preview(tmp_path, eph_slot['upload_id'], 'demo_clean.png', owner_sid='a' * 32, require_session=True) is None
    assert list_uploads(tmp_path, owner_sid='a' * 32, require_session=True) == []

    # Verify owner_sid=None slot is NEVER readable/deletable by a web session with st_sid
    cli_slot = save_uploaded_files(tmp_path, _Mem(_make_png_bytes(104)), 'cli.png', retention_mode='ttl', owner_sid=None)
    (cli_slot['slot_dir'] / 'demo_clean.png').write_bytes(_make_png_bytes(105))
    assert c_browser_b.get(f"/api/uploads/{cli_slot['upload_id']}/preview/demo_clean.png").status_code == 404
    assert c_browser_b.delete(f"/api/uploads/{cli_slot['upload_id']}").status_code == 404


def test_startup_orphan_ephemeral_sweep_and_lazy_ttl_purge_audit(tmp_path: Path, monkeypatch) -> None:
    """Startup sweep must purge crash-orphaned ephemeral slots immediately, and lazy TTL sweep must log TTL_EXPIRED_AUTO_PURGE."""
    import app as web_app
    from src.upload_store import save_uploaded_files, user_uploads_root

    monkeypatch.setattr(web_app, 'BASE', tmp_path)

    class _Mem:
        def __init__(self, b: bytes):
            self._b = b
        def save(self, dst: Path):
            Path(dst).write_bytes(self._b)

    # 1. Crash-orphaned ephemeral slot (with meta.json mode='ephemeral') -> startup sweep purges immediately
    sid_a = '1' * 32
    orphan = save_uploaded_files(tmp_path, _Mem(_make_png_bytes(111)), 'crashed.png', retention_mode='ephemeral', owner_sid=sid_a)
    assert orphan['slot_dir'].is_dir()
    purged_boot = web_app._run_startup_sweep(tmp_path)
    assert orphan['upload_id'] in purged_boot
    assert not orphan['slot_dir'].exists()

    # 2. Expired TTL slot swept lazily by GET /api/uploads -> logs TTL_EXPIRED_AUTO_PURGE scoped to owner
    client_a = web_app.app.test_client()
    client_b = web_app.app.test_client()
    assert client_a.get('/').status_code == 200
    assert client_b.get('/').status_code == 200

    r_ttl = client_a.post(
        '/api/run-upload',
        data={
            'image': (io.BytesIO(_make_png_bytes(112)), 'lazy_expire.png'),
            'focal_mm': '50',
            'pixel_um': '14.88',
            'retention_mode': 'ttl',
            'centroid_backend': 'classical',
        },
        content_type='multipart/form-data',
    )
    assert r_ttl.status_code == 200
    uid_ttl = r_ttl.get_json()['storage_control']['upload_id']
    meta_p = user_uploads_root(tmp_path) / uid_ttl / 'meta.json'
    meta = json.loads(meta_p.read_text(encoding='utf-8'))
    meta['expires_at_epoch'] = time.time() - 10.0
    meta_p.write_text(json.dumps(meta), encoding='utf-8')

    # Trigger lazy sweep via GET /api/uploads
    assert client_a.get('/api/uploads').get_json()['uploads'] == []
    assert not (user_uploads_root(tmp_path) / uid_ttl).exists()

    log_a = client_a.get('/api/execution-log?limit=20').get_json()['entries']
    assert any(
        e.get('event_type') == 'DATA_DELETION'
        and e.get('action') == 'TTL_EXPIRED_AUTO_PURGE'
        and e.get('upload_id') == uid_ttl
        and e.get('verified_gone') is True
        for e in log_a
    )
    # Browser B must NOT see Browser A's purged upload_id
    log_b = client_b.get('/api/execution-log?limit=20').get_json()['entries']
    assert uid_ttl not in json.dumps(log_b)


def test_failed_ephemeral_logs_error_rollback_and_windows_replace_safety(tmp_path: Path, monkeypatch) -> None:
    """Failed ephemeral uploads must log ERROR_ROLLBACK_DELETE, and os.replace errors must retry / never HTTP 500."""
    import os
    import app as web_app
    import src.execution_log as exec_log
    from src.upload_store import user_uploads_root

    monkeypatch.setattr(web_app, 'BASE', tmp_path)
    client = web_app.app.test_client()

    # 1. Failed ephemeral upload (missing optics for 128x128) -> 400 + ERROR_ROLLBACK_DELETE (not EPHEMERAL_AUTO_DELETE)
    r_err = client.post(
        '/api/run-upload',
        data={
            'image': (io.BytesIO(_make_png_bytes(121)), 'bad_eph.png'),
            'retention_mode': 'ephemeral',
            'centroid_backend': 'classical',
        },
        content_type='multipart/form-data',
    )
    assert r_err.status_code == 400
    root = user_uploads_root(tmp_path)
    assert not root.is_dir() or not [p for p in root.iterdir() if p.is_dir()]
    entries = client.get('/api/execution-log?limit=10').get_json()['entries']
    assert any(e.get('event_type') == 'DATA_DELETION' and e.get('action') == 'ERROR_ROLLBACK_DELETE' for e in entries)

    # 2. Transient Windows PermissionError on os.replace -> retry succeeds with zero temp files left
    real_replace = os.replace
    calls = {'n': 0}

    def _flaky_replace(src, dst):
        calls['n'] += 1
        if calls['n'] <= 2:
            raise PermissionError('simulated Windows AV lock')
        return real_replace(src, dst)

    monkeypatch.setattr(exec_log.os, 'replace', _flaky_replace)
    rec = exec_log.record_data_deletion(tmp_path, action='USER_DELETE_SINGLE', upload_id='a' * 16, deleted_files=['x.png'], verified_gone=True)
    assert rec['verified_gone'] is True
    assert calls['n'] == 3
    assert not list((tmp_path / 'data' / 'outputs').glob('*.tmp'))

    # 3. Persistent PermissionError on os.replace -> _safe_record_data_deletion catches cleanly, DELETE never returns 500
    def _always_locked(src, dst):
        raise PermissionError('persistent lock')

    monkeypatch.setattr(exec_log.os, 'replace', _always_locked)
    r_ttl = client.post(
        '/api/run-upload',
        data={
            'image': (io.BytesIO(_make_png_bytes(122)), 'lock_resilient.png'),
            'focal_mm': '50',
            'pixel_um': '14.88',
            'retention_mode': 'ttl',
            'centroid_backend': 'classical',
        },
        content_type='multipart/form-data',
    )
    assert r_ttl.status_code == 200
    uid = r_ttl.get_json()['storage_control']['upload_id']
    r_del = client.delete(f'/api/uploads/{uid}')
    assert r_del.status_code == 200
    assert r_del.get_json()['verified_gone'] is True
    assert not list((tmp_path / 'data' / 'outputs').glob('*.tmp'))


def test_compare_auto_tampered_and_truncated_checkpoint_truthful_logging(
    star_tracker_root: Path, tmp_path: Path, monkeypatch
) -> None:
    """Verify /api/compare with backends=['auto'] + tampered .pt logs FALLBACK_TO_COG & checksum_mismatch,
    and truncated .pt logs corrupted_truncated (never 'available' or 'missing')."""
    import torch
    import app as web_app
    import src.centroid_cnn as cnn_mod

    monkeypatch.setattr(web_app, 'BASE', tmp_path)
    monkeypatch.setattr(web_app.ENGINE, '_cnn_cache', None)

    def _forbid_torch_load(*args, **kwargs):
        raise AssertionError('torch.load must NEVER be called for tampered or truncated checkpoints!')

    monkeypatch.setattr(torch, 'load', _forbid_torch_load)
    client = web_app.app.test_client()

    # Case A: Tampered 1-byte-modified (>1 MB) checkpoint on /api/compare backends=['auto'] (Zhao nightsky)
    tampered_pt = tmp_path / 'MobileUNet_B10_50.pt'
    tampered_pt.write_bytes(b'\x00' * 1_100_000 + b'X')
    monkeypatch.setattr(cnn_mod, '_DEFAULT_WEIGHTS', tampered_pt)
    monkeypatch.setattr(cnn_mod, 'DEFAULT_WEIGHTS_PATH', tampered_pt)

    r_cmp = client.post(
        '/api/compare',
        json={
            'image': 'real_calibrated/zhao_mt9v022/nightsky_june16_2021.npy',
            'backends': ['auto'],
        },
    )
    assert r_cmp.status_code == 200
    j_cmp = r_cmp.get_json()
    m_auto = j_cmp['methods']['auto']
    assert m_auto['centroid_fallback'] is True
    assert m_auto['executed_backend'] == 'classical'
    assert m_auto['checkpoint_status'] == 'checksum_mismatch'
    assert m_auto['fallback_reason'] and 'CHECKPOINT_SHA256_MISMATCH' in m_auto['fallback_reason']

    log_rows = client.get('/api/execution-log?limit=15').get_json()['entries']
    assert any(
        e.get('endpoint') == '/api/compare'
        and e.get('requested_backend') == 'auto'
        and e.get('executed_backend') == 'classical'
        and e.get('fallback_triggered') is True
        and 'FALLBACK_TO_COG' in str(e.get('mode_summary', ''))
        and e.get('checkpoint_status') == 'checksum_mismatch'
        for e in log_rows
    ), f'Expected truthful checksum_mismatch FALLBACK_TO_COG entry in log, got: {log_rows}'

    # Case B: Truncated (<1 MB) checkpoint -> must report corrupted_truncated (NOT 'missing')
    trunc_pt = tmp_path / 'MobileUNet_B10_50.pt'
    trunc_pt.write_bytes(b'TRUNCATED_BYTES')
    monkeypatch.setattr(web_app.ENGINE, '_cnn_cache', None)

    r_trunc = client.post(
        '/api/run',
        json={'mode': 'fast', 'seed': 42, 'centroid_backend': 'cnn', 'catalog': 'bsc5', 'solver': 'svd'},
    )
    assert r_trunc.status_code == 200
    j_trunc = r_trunc.get_json()
    assert j_trunc['centroid_fallback'] is True
    assert j_trunc['checkpoint_status'] == 'corrupted_truncated'

    log_rows2 = client.get('/api/execution-log?limit=15').get_json()['entries']
    assert any(
        e.get('endpoint') == '/api/run'
        and e.get('fallback_triggered') is True
        and e.get('checkpoint_status') == 'corrupted_truncated'
        for e in log_rows2
    ), f'Expected corrupted_truncated audit entry, got: {log_rows2}'
