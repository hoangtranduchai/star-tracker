"""Isolated, overwrite-safe temporary storage, TTL auto-cleanup, and right-to-delete for user uploads.

Design invariants (Stage 2 data-control compliance):
  1. Bundled sample images live in read-only `data/uploads/` and are NEVER modified or deleted here.
  2. User-uploaded images and optional sidecar JSON files live exclusively under
     `data/user_uploads/<upload_id>/` where `<upload_id>` is a unique 16-hex UUID4 token.
     Two uploads with identical filenames (even `mount_st_helens_1.png`) NEVER collide or overwrite.
  3. Two explicit retention modes:
     - `ephemeral` (default): file + sidecar are removed unconditionally in `finally:` immediately
       after pipeline execution completes (0 seconds retained on disk), verified with `not exists()`.
     - `ttl`: file + sidecar are retained temporarily for `ttl_seconds` (default 900s = 15 minutes),
       auto-purged on expiration, and deletable immediately by the user via DELETE `/api/uploads/<id>`
       or DELETE `/api/uploads`.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_TTL_SECONDS: int = int(os.environ.get('STAR_TRACKER_UPLOAD_TTL_S', '900') or '900')
DEFAULT_SWEEP_INTERVAL_S: int = max(10, int(os.environ.get('STAR_TRACKER_SWEEP_INTERVAL_S', '60') or '60'))
DEFAULT_RETENTION_MODE: str = 'ephemeral'
VALID_RETENTION_MODES: tuple[str, ...] = ('ephemeral', 'ttl')
USER_UPLOADS_REL: str = 'data/user_uploads'
SESSION_COOKIE_NAME: str = 'st_sid'
PREVIEW_FILENAMES: tuple[str, ...] = (
    'demo_clean.png',
    'demo_input.png',
    'demo_output.png',
    'demo_result.png',
    'demo_compare_clean.png',
)

_UPLOAD_ID_RE = re.compile(r'^[0-9a-f]{16}$')
_SESSION_ID_RE = re.compile(r'^[0-9a-f]{32}$')


def normalize_session_id(raw: Any) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip().lower()
    return s if _SESSION_ID_RE.match(s) else None


def _utc_iso(ts: float | None = None) -> str:
    dt = datetime.fromtimestamp(time.time() if ts is None else float(ts), tz=timezone.utc)
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def user_uploads_root(base: Path) -> Path:
    return Path(base) / 'data' / 'user_uploads'


def normalize_retention_mode(raw: Any) -> str:
    s = str(raw or DEFAULT_RETENTION_MODE).strip().lower()
    if s in ('ephemeral', 'delete_immediately', 'immediate', 'none', '0'):
        return 'ephemeral'
    if s in ('ttl', 'temporary', 'temp', '15m'):
        return 'ttl'
    return DEFAULT_RETENTION_MODE


def storage_policy_summary(base: Path, *, owner_sid: str | None = None) -> dict[str, Any]:
    """Return transparent machine-readable disclosure of upload storage location, TTL & delete rights."""
    active = list_uploads(base, owner_sid=owner_sid)
    return {
        'storage_dir': f'{USER_UPLOADS_REL}/<upload_id>/',
        'bundled_samples_dir': 'data/uploads/ (read-only, separated from user uploads)',
        'default_retention_mode': DEFAULT_RETENTION_MODE,
        'supported_retention_modes': {
            'ephemeral': 'Xóa vĩnh viễn ảnh gốc, sidecar.json và toàn bộ ảnh xem trước tạm ngay sau khi xử lý xong (0 giây lưu đĩa trong khối finally; xem trước trả trực tiếp dạng inline data URI).',
            'ttl': f'Lưu tạm ảnh gốc, sidecar và ảnh xem trước tối đa {DEFAULT_TTL_SECONDS // 60} phút ({DEFAULT_TTL_SECONDS}s) trong thư mục UUID riêng theo phiên trình duyệt; tự động dọn nền mỗi {DEFAULT_SWEEP_INTERVAL_S}s khi hết hạn, rollback ngay nếu lỗi xử lý, hoặc xóa toàn bộ cùng lúc khi bấm Xóa ngay (URL preview trả 404).',
        },
        'ttl_seconds': DEFAULT_TTL_SECONDS,
        'background_ttl_sweeper_interval_s': DEFAULT_SWEEP_INTERVAL_S,
        'overwrite_protection': 'Mỗi lượt tải lên sinh thư mục UUID4 16 ký tự độc lập cho cả ảnh gốc, sidecar và ảnh xem trước — tuyệt đối không ghi đè tệp trùng tên, ảnh mẫu hay data/outputs/demo_*.png.',
        'preview_isolation': True,
        'session_isolation': True,
        'session_cookie': f'{SESSION_COOKIE_NAME} (HttpOnly, SameSite=Lax)',
        'error_rollback_cleanup': True,
        'right_to_delete_endpoints': [
            'GET /api/uploads',
            'GET /api/uploads/<upload_id>/preview/<filename>',
            'DELETE /api/uploads/<upload_id>',
            'DELETE /api/uploads',
        ],
        'active_temporary_uploads': len(active),
    }


def _sha256_bytes(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def cleanup_expired_uploads(base: Path) -> list[str]:
    """Remove any TTL upload directories whose `expires_at_epoch` has passed."""
    root = user_uploads_root(base)
    if not root.is_dir():
        return []
    now = time.time()
    purged: list[str] = []
    for item in list(root.iterdir()):
        if not item.is_dir():
            continue
        meta_p = item / 'meta.json'
        expired = False
        if meta_p.is_file():
            try:
                meta = json.loads(meta_p.read_text(encoding='utf-8'))
                exp_ts = float(meta.get('expires_at_epoch') or 0.0)
                if exp_ts > 0.0 and now >= exp_ts:
                    expired = True
            except Exception:
                # Corrupt metadata older than TTL -> clean up
                if now - item.stat().st_mtime >= DEFAULT_TTL_SECONDS:
                    expired = True
        else:
            if now - item.stat().st_mtime >= DEFAULT_TTL_SECONDS:
                expired = True
        if expired:
            shutil.rmtree(item, ignore_errors=True)
            purged.append(item.name)
    return purged


def save_uploaded_files(
    base: Path,
    image_storage: Any,
    safe_image_name: str,
    *,
    sidecar_storage: Any = None,
    safe_sidecar_name: str | None = None,
    retention_mode: str = DEFAULT_RETENTION_MODE,
    ttl_seconds: int | None = None,
    endpoint: str = '/api/run-upload',
    owner_sid: str | None = None,
) -> dict[str, Any]:
    """Save uploaded image (+ optional sidecar) into a collision-proof UUID4 directory."""
    cleanup_expired_uploads(base)
    mode = normalize_retention_mode(retention_mode)
    ttl = DEFAULT_TTL_SECONDS if ttl_seconds is None else max(30, min(86400, int(ttl_seconds)))
    norm_sid = normalize_session_id(owner_sid)

    upload_id = uuid.uuid4().hex[:16]
    root = user_uploads_root(base)
    slot_dir = root / upload_id
    slot_dir.mkdir(parents=True, exist_ok=False)

    try:
        img_stem = Path(safe_image_name).stem[:64] or 'upload'
        img_ext = Path(safe_image_name).suffix.lower()
        stored_img_name = f'img_{img_stem}{img_ext}'
        saved_img = slot_dir / stored_img_name
        image_storage.save(saved_img)

        saved_sidecar: Path | None = None
        stored_sc_name: str | None = None
        sidecar_size = 0
        if sidecar_storage is not None and safe_sidecar_name:
            sc_stem = Path(safe_sidecar_name).stem[:64] or 'sidecar'
            stored_sc_name = f'sidecar_{sc_stem}.json'
            saved_sidecar = slot_dir / stored_sc_name
            sidecar_storage.save(saved_sidecar)
            sidecar_size = int(saved_sidecar.stat().st_size)

        now = time.time()
        exp_ts = now if mode == 'ephemeral' else now + ttl
        img_size = int(saved_img.stat().st_size)
        img_sha = _sha256_bytes(saved_img)

        meta = {
            'upload_id': upload_id,
            'endpoint': endpoint,
            'owner_sid': norm_sid,
            'retention_mode': mode,
            'storage_rel_dir': f'{USER_UPLOADS_REL}/{upload_id}/',
            'original_image_name': safe_image_name,
            'stored_image_name': stored_img_name,
            'image_size_bytes': img_size,
            'image_sha256': img_sha,
            'original_sidecar_name': safe_sidecar_name if saved_sidecar is not None else None,
            'stored_sidecar_name': stored_sc_name,
            'sidecar_size_bytes': sidecar_size,
            'total_size_bytes': img_size + sidecar_size,
            'created_at_epoch': now,
            'created_at_utc': _utc_iso(now),
            'ttl_seconds': 0 if mode == 'ephemeral' else ttl,
            'expires_at_epoch': exp_ts,
            'expires_at_utc': _utc_iso(exp_ts),
        }
        if mode == 'ttl':
            (slot_dir / 'meta.json').write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding='utf-8')
    except Exception:
        shutil.rmtree(slot_dir, ignore_errors=True)
        raise

    return {
        'upload_id': upload_id,
        'slot_dir': slot_dir,
        'image_path': saved_img,
        'sidecar_path': saved_sidecar,
        'meta': meta,
    }


def _read_slot_owner(slot_dir: Path) -> str | None:
    meta_p = slot_dir / 'meta.json'
    if not meta_p.is_file():
        return None
    try:
        m = json.loads(meta_p.read_text(encoding='utf-8'))
        return normalize_session_id(m.get('owner_sid'))
    except Exception:
        return None


def list_uploads(base: Path, *, owner_sid: str | None = None, include_all: bool = False) -> list[dict[str, Any]]:
    """List active temporary user uploads scoped to `owner_sid` (never exposes bundled sample frames or other browsers' uploads)."""
    cleanup_expired_uploads(base)
    root = user_uploads_root(base)
    if not root.is_dir():
        return []
    caller_sid = normalize_session_id(owner_sid)
    now = time.time()
    rows: list[dict[str, Any]] = []
    for item in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not item.is_dir() or not _UPLOAD_ID_RE.match(item.name):
            continue
        meta_p = item / 'meta.json'
        if meta_p.is_file():
            try:
                m = json.loads(meta_p.read_text(encoding='utf-8'))
            except Exception:
                m = {'upload_id': item.name, 'storage_rel_dir': f'{USER_UPLOADS_REL}/{item.name}/'}
        else:
            files = [f.name for f in item.iterdir() if f.is_file()]
            m = {
                'upload_id': item.name,
                'storage_rel_dir': f'{USER_UPLOADS_REL}/{item.name}/',
                'original_image_name': files[0] if files else '(unknown)',
                'created_at_utc': _utc_iso(item.stat().st_mtime),
                'expires_at_epoch': item.stat().st_mtime + DEFAULT_TTL_SECONDS,
                'expires_at_utc': _utc_iso(item.stat().st_mtime + DEFAULT_TTL_SECONDS),
                'total_size_bytes': sum(f.stat().st_size for f in item.iterdir() if f.is_file()),
            }
        slot_owner = normalize_session_id(m.get('owner_sid'))
        if not include_all and slot_owner != caller_sid:
            continue
        m.pop('owner_sid', None)
        rem = max(0, int(round(float(m.get('expires_at_epoch') or now) - now)))
        m['remaining_seconds'] = rem
        m['files_on_disk'] = sorted(f.name for f in item.iterdir() if f.is_file() and f.name != 'meta.json')
        m['session_scoped'] = slot_owner is not None
        rows.append(m)
    return rows


def encode_png_data_uri(path: Path) -> str | None:
    """Encode a PNG file on disk as an inline base64 data URI so ephemeral mode leaves 0 bytes on disk."""
    p = Path(path)
    if not p.is_file():
        return None
    b64 = base64.b64encode(p.read_bytes()).decode('ascii')
    return f'data:image/png;base64,{b64}'


def resolve_upload_preview(base: Path, upload_id: str, filename: str, *, owner_sid: str | None = None) -> Path | None:
    """Resolve an allowlisted preview PNG inside an active TTL upload slot (enforces owner session isolation)."""
    cleanup_expired_uploads(base)
    uid = str(upload_id or '').strip().lower()
    fname = str(filename or '').strip()
    if not _UPLOAD_ID_RE.match(uid) or fname not in PREVIEW_FILENAMES:
        return None
    root = user_uploads_root(base).resolve()
    slot_dir = (root / uid).resolve()
    target = (slot_dir / fname).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    if not slot_dir.is_dir():
        return None
    slot_owner = _read_slot_owner(slot_dir)
    if slot_owner is not None and slot_owner != normalize_session_id(owner_sid):
        return None
    return target if target.is_file() else None


def delete_upload(
    base: Path,
    upload_id: str,
    *,
    owner_sid: str | None = None,
    ignore_owner: bool = False,
) -> dict[str, Any]:
    """Immediately and permanently delete a specific user upload directory (image + sidecar + previews)."""
    uid = str(upload_id or '').strip().lower()
    if not _UPLOAD_ID_RE.match(uid):
        return {'deleted': False, 'upload_id': uid, 'error': 'Mã upload_id không hợp lệ.', 'verified_gone': False}
    root = user_uploads_root(base).resolve()
    target = (root / uid).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return {'deleted': False, 'upload_id': uid, 'error': 'Đường dẫn ngoài phạm vi cho phép.', 'verified_gone': False}
    if not target.exists():
        return {
            'deleted': False,
            'upload_id': uid,
            'error': 'Không tìm thấy phiên tải lên (có thể đã được xóa trước đó).',
            'deleted_files': [],
            'verified_gone': True,
        }
    if not ignore_owner:
        slot_owner = _read_slot_owner(target)
        if slot_owner is not None and slot_owner != normalize_session_id(owner_sid):
            return {
                'deleted': False,
                'upload_id': uid,
                'error': 'Không tìm thấy phiên tải lên thuộc trình duyệt hiện tại.',
                'deleted_files': [],
                'verified_gone': False,
                'not_found_or_denied': True,
            }
    files_before = sorted(f.name for f in target.iterdir() if f.is_file())
    shutil.rmtree(target, ignore_errors=False)
    gone = not target.exists()
    return {
        'deleted': gone,
        'upload_id': uid,
        'storage_rel_dir': f'{USER_UPLOADS_REL}/{uid}/',
        'deleted_files': files_before,
        'verified_gone': gone,
        'deleted_at_utc': _utc_iso(),
    }


def delete_all_uploads(base: Path, *, owner_sid: str | None = None, force_all: bool = False) -> dict[str, Any]:
    """Delete temporary user uploads in `owner_sid` scope (never touches bundled samples or other browsers' sessions)."""
    root = user_uploads_root(base)
    caller_sid = normalize_session_id(owner_sid)
    deleted_ids: list[str] = []
    deleted_files: list[str] = []
    if root.is_dir():
        for item in list(root.iterdir()):
            if item.is_dir() and _UPLOAD_ID_RE.match(item.name):
                if not force_all and _read_slot_owner(item) != caller_sid:
                    continue
                deleted_ids.append(item.name)
                deleted_files.extend(f'{item.name}/{f.name}' for f in sorted(item.iterdir()) if f.is_file())
                shutil.rmtree(item, ignore_errors=False)
    remaining = list_uploads(base, owner_sid=caller_sid, include_all=force_all)
    return {
        'deleted': True,
        'n_deleted_sessions': len(deleted_ids),
        'deleted_count': len(deleted_ids),
        'deleted_upload_ids': deleted_ids,
        'deleted_files': deleted_files,
        'remaining_sessions': len(remaining),
        'verified_empty': len(remaining) == 0,
        'deleted_at_utc': _utc_iso(),
    }
