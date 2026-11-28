"""Isolated, overwrite-safe temporary storage, TTL auto-cleanup, and right-to-delete for user uploads.

Design invariants (Stage 2 data-control compliance):
  1. Bundled sample images live in read-only `data/uploads/` and are NEVER modified or deleted here.
  2. User-uploaded images, optional sidecar JSON files, and `meta.json` live exclusively under
     `data/user_uploads/<upload_id>/` where `<upload_id>` is a unique 16-hex UUID4 token.
     Two uploads with identical filenames (even `mount_st_helens_1.png`) NEVER collide or overwrite.
  3. Two explicit retention modes (both write `meta.json` with `owner_sid` immediately on creation):
     - `ephemeral` (default): file + sidecar + preview are removed unconditionally in `finally:`
       immediately after pipeline execution completes (0 seconds retained post-request), verified
       with `not exists()`. Any crash-orphaned ephemeral slot is purged on startup sweep or after grace.
     - `ttl`: file + sidecar + previews are retained temporarily for `ttl_seconds` (default 900s = 15 min),
       scoped strictly to `owner_sid`, auto-purged on expiration with `TTL_EXPIRED_AUTO_PURGE` audit log,
       and deletable immediately by the owning session via DELETE `/api/uploads/<id>` or DELETE `/api/uploads`.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS: int = int(os.environ.get('STAR_TRACKER_UPLOAD_TTL_S', '900') or '900')
DEFAULT_SWEEP_INTERVAL_S: int = max(10, int(os.environ.get('STAR_TRACKER_SWEEP_INTERVAL_S', '60') or '60'))
DEFAULT_EPHEMERAL_ORPHAN_GRACE_S: float = float(os.environ.get('STAR_TRACKER_EPHEMERAL_GRACE_S', '60') or '60')
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
_EXT_RE = re.compile(r'^\.[a-z0-9]{1,10}$')


def normalize_session_id(raw: Any) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip().lower()
    return s if _SESSION_ID_RE.match(s) else None


def sanitize_upload_filename(raw_filename: Any, *, fallback_stem: str = 'upload') -> str:
    """Sanitize uploaded filename while preserving valid ASCII extensions for non-Latin names (e.g. `星空.png`)."""
    raw = str(raw_filename or '').strip()
    if not raw:
        return ''
    base = raw.replace('\\', '/').rsplit('/', 1)[-1].strip()
    if not base or base in ('.', '..'):
        return ''
    p = Path(base)
    raw_ext = p.suffix.lower()
    ext = raw_ext if _EXT_RE.match(raw_ext) else ''
    stem_raw = base[: -len(raw_ext)] if raw_ext else base
    try:
        from werkzeug.utils import secure_filename as _wz_secure

        clean_stem = _wz_secure(stem_raw)
    except Exception:
        clean_stem = re.sub(r'[^A-Za-z0-9_.-]+', '_', stem_raw)
    clean_stem = clean_stem.strip('._-')[:64]
    if not clean_stem:
        clean_stem = fallback_stem
    return f'{clean_stem}{ext}'


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


def _owner_matches(slot_owner: str | None, caller_sid: str | None, *, require_session: bool = False) -> bool:
    """Strict owner check: never allow a web session to access `slot_owner=None` or another session's slot."""
    if require_session and caller_sid is None:
        return False
    if caller_sid is not None:
        return slot_owner is not None and slot_owner == caller_sid
    # Unauthenticated local CLI mode (`require_session=False` and `caller_sid is None`):
    # only slots explicitly created without a session (`slot_owner is None`) match.
    return slot_owner is None


def _read_slot_meta(slot_dir: Path) -> dict[str, Any] | None:
    meta_p = slot_dir / 'meta.json'
    try:
        if not meta_p.is_file():
            return None
        data = json.loads(meta_p.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _read_slot_owner(slot_dir: Path) -> str | None:
    meta = _read_slot_meta(slot_dir)
    if meta is None:
        return None
    return normalize_session_id(meta.get('owner_sid'))


def _safe_audit_purge(
    base: Path,
    *,
    action: str,
    upload_id: str,
    deleted_files: list[str],
    owner_sid: str | None,
    endpoint: str,
) -> None:
    try:
        from .execution_log import record_data_deletion

        record_data_deletion(
            base,
            action=action,
            upload_id=upload_id,
            deleted_files=deleted_files,
            verified_gone=True,
            endpoint=endpoint,
            owner_sid=owner_sid,
        )
    except Exception as err:
        _LOGGER.warning('Failed to record TTL/orphan purge audit (%s): %s', upload_id, err)


def storage_policy_summary(
    base: Path,
    *,
    owner_sid: str | None = None,
    require_session: bool = False,
) -> dict[str, Any]:
    """Return transparent machine-readable disclosure of upload storage location, TTL & delete rights."""
    active = list_uploads(base, owner_sid=owner_sid, require_session=require_session)
    return {
        'storage_dir': f'{USER_UPLOADS_REL}/<upload_id>/',
        'bundled_samples_dir': 'data/uploads/ (read-only, separated from user uploads)',
        'default_retention_mode': DEFAULT_RETENTION_MODE,
        'supported_retention_modes': {
            'ephemeral': 'Xóa vĩnh viễn ảnh gốc, sidecar.json và toàn bộ ảnh xem trước tạm ngay sau khi xử lý xong (0 giây lưu sau xử lý trong khối finally; xem trước trả trực tiếp dạng inline data URI).',
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


def cleanup_expired_uploads(
    base: Path,
    *,
    purge_orphaned_ephemeral: bool = False,
    ephemeral_orphan_grace_s: float = DEFAULT_EPHEMERAL_ORPHAN_GRACE_S,
    record_audit: bool = True,
    audit_endpoint: str = 'LAZY:ttl_cleanup',
) -> list[str]:
    """Remove expired TTL upload directories (and crash-orphaned ephemeral slots), verifying removal."""
    root = user_uploads_root(base)
    if not root.is_dir():
        return []
    now = time.time()
    purged: list[str] = []
    try:
        candidates = list(root.iterdir())
    except OSError:
        return []

    for item in candidates:
        try:
            if not item.is_dir():
                continue
            item_mtime = item.stat().st_mtime
        except (FileNotFoundError, OSError):
            continue

        meta = _read_slot_meta(item)
        expired = False
        purge_action = 'TTL_EXPIRED_AUTO_PURGE'
        slot_owner: str | None = None

        if meta is not None:
            slot_owner = normalize_session_id(meta.get('owner_sid'))
            ret_mode = str(meta.get('retention_mode') or 'ttl').strip().lower()
            if ret_mode == 'ephemeral':
                created_ts = float(meta.get('created_at_epoch') or item_mtime)
                if purge_orphaned_ephemeral or (now - created_ts >= float(ephemeral_orphan_grace_s)):
                    expired = True
                    purge_action = 'TTL_EXPIRED_AUTO_PURGE'
            else:
                exp_ts = float(meta.get('expires_at_epoch') or 0.0)
                if exp_ts > 0.0 and now >= exp_ts:
                    expired = True
        else:
            # Missing or corrupt meta.json -> crash orphan
            if purge_orphaned_ephemeral or (now - item_mtime >= DEFAULT_TTL_SECONDS):
                expired = True

        if not expired:
            continue

        try:
            files_before = sorted(f.name for f in item.iterdir() if f.is_file())
        except (FileNotFoundError, OSError):
            files_before = []

        shutil.rmtree(item, ignore_errors=True)
        # Verify deletion actually succeeded before reporting purged / verified_gone=True
        if not item.exists():
            purged.append(item.name)
            if record_audit:
                _safe_audit_purge(
                    base,
                    action=purge_action,
                    upload_id=item.name,
                    deleted_files=files_before or [item.name],
                    owner_sid=slot_owner,
                    endpoint=audit_endpoint,
                )
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
    """Save uploaded image (+ optional sidecar + `meta.json`) into a collision-proof UUID4 directory."""
    cleanup_expired_uploads(base, audit_endpoint='LAZY:save_uploaded_files')
    mode = normalize_retention_mode(retention_mode)
    ttl = DEFAULT_TTL_SECONDS if ttl_seconds is None else max(30, min(86400, int(ttl_seconds)))
    norm_sid = normalize_session_id(owner_sid)

    upload_id = uuid.uuid4().hex[:16]
    root = user_uploads_root(base)
    slot_dir = root / upload_id
    slot_dir.mkdir(parents=True, exist_ok=False)

    try:
        clean_img_name = sanitize_upload_filename(safe_image_name, fallback_stem='upload') or 'upload.bin'
        img_stem = Path(clean_img_name).stem[:64] or 'upload'
        img_ext = Path(clean_img_name).suffix.lower()
        stored_img_name = f'img_{img_stem}{img_ext}'
        saved_img = slot_dir / stored_img_name
        image_storage.save(saved_img)

        saved_sidecar: Path | None = None
        stored_sc_name: str | None = None
        sidecar_size = 0
        if sidecar_storage is not None and safe_sidecar_name:
            clean_sc_name = sanitize_upload_filename(safe_sidecar_name, fallback_stem='sidecar') or 'sidecar.json'
            sc_stem = Path(clean_sc_name).stem[:64] or 'sidecar'
            stored_sc_name = f'sidecar_{sc_stem}.json'
            saved_sidecar = slot_dir / stored_sc_name
            sidecar_storage.save(saved_sidecar)
            sidecar_size = int(saved_sidecar.stat().st_size)

        now = time.time()
        exp_ts = now if mode == 'ephemeral' else now + ttl
        img_size = int(saved_img.stat().st_size)
        img_sha = _sha256_bytes(saved_img)
        stored_files = [stored_img_name] + ([stored_sc_name] if stored_sc_name else [])

        meta = {
            'upload_id': upload_id,
            'endpoint': endpoint,
            'owner_sid': norm_sid,
            'retention_mode': mode,
            'storage_rel_dir': f'{USER_UPLOADS_REL}/{upload_id}/',
            'original_image_name': clean_img_name,
            'stored_image_name': stored_img_name,
            'image_size_bytes': img_size,
            'image_sha256': img_sha,
            'original_sidecar_name': safe_sidecar_name if saved_sidecar is not None else None,
            'stored_sidecar_name': stored_sc_name,
            'sidecar_size_bytes': sidecar_size,
            'total_size_bytes': img_size + sidecar_size,
            'files': stored_files,
            'created_at_epoch': now,
            'created_at_utc': _utc_iso(now),
            'ttl_seconds': 0 if mode == 'ephemeral' else ttl,
            'expires_at_epoch': exp_ts,
            'expires_at_utc': _utc_iso(exp_ts),
        }
        # ALWAYS write meta.json (including for ephemeral slots) to enforce owner_sid & crash-orphan tracking.
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


def list_uploads(
    base: Path,
    *,
    owner_sid: str | None = None,
    include_all: bool = False,
    require_session: bool = False,
) -> list[dict[str, Any]]:
    """List active TTL user uploads scoped to `owner_sid` (never exposes bundled samples, ephemeral slots, or other browsers' uploads)."""
    cleanup_expired_uploads(base, audit_endpoint='LAZY:list_uploads')
    root = user_uploads_root(base)
    if not root.is_dir():
        return []
    caller_sid = normalize_session_id(owner_sid)
    if not include_all and require_session and caller_sid is None:
        return []
    now = time.time()
    sortable_rows: list[tuple[float, dict[str, Any]]] = []
    try:
        items = list(root.iterdir())
    except OSError:
        return []

    for item in items:
        try:
            if not item.is_dir() or not _UPLOAD_ID_RE.match(item.name):
                continue
            item_mtime = item.stat().st_mtime
        except (FileNotFoundError, OSError):
            continue

        meta = _read_slot_meta(item)
        if meta is None:
            # Never expose meta-less/corrupt/in-flight slots to users
            continue
        if str(meta.get('retention_mode') or 'ttl').strip().lower() == 'ephemeral':
            # In-flight ephemeral slots are auto-deleted in finally: and never listed as retained TTL slots
            continue

        slot_owner = normalize_session_id(meta.get('owner_sid'))
        if not include_all and not _owner_matches(slot_owner, caller_sid, require_session=require_session):
            continue

        m = dict(meta)
        m.pop('owner_sid', None)
        try:
            files_on_disk = sorted(f.name for f in item.iterdir() if f.is_file() and f.name != 'meta.json')
        except (FileNotFoundError, OSError):
            continue
        rem = max(0, int(round(float(m.get('expires_at_epoch') or now) - now)))
        m['remaining_seconds'] = rem
        m['files_on_disk'] = files_on_disk
        m['session_scoped'] = slot_owner is not None
        sort_key = float(m.get('created_at_epoch') or item_mtime)
        sortable_rows.append((sort_key, m))

    sortable_rows.sort(key=lambda pair: pair[0], reverse=True)
    return [row for _, row in sortable_rows]


def encode_png_data_uri(path: Path) -> str | None:
    """Encode a PNG file on disk as an inline base64 data URI so ephemeral mode leaves 0 bytes post-request."""
    p = Path(path)
    if not p.is_file():
        return None
    b64 = base64.b64encode(p.read_bytes()).decode('ascii')
    return f'data:image/png;base64,{b64}'


def resolve_upload_preview(
    base: Path,
    upload_id: str,
    filename: str,
    *,
    owner_sid: str | None = None,
    require_session: bool = False,
) -> Path | None:
    """Resolve an allowlisted preview PNG inside an active TTL upload slot (strictly enforces owner session isolation)."""
    cleanup_expired_uploads(base, audit_endpoint='LAZY:resolve_preview')
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
    meta = _read_slot_meta(slot_dir)
    if meta is None:
        # Fail closed when meta.json is missing or unreadable
        return None
    if str(meta.get('retention_mode') or 'ttl').strip().lower() == 'ephemeral':
        # Ephemeral previews are served inline as data URIs only, never via preview route
        return None
    slot_owner = normalize_session_id(meta.get('owner_sid'))
    caller_sid = normalize_session_id(owner_sid)
    if not _owner_matches(slot_owner, caller_sid, require_session=require_session):
        return None
    return target if target.is_file() else None


def delete_upload(
    base: Path,
    upload_id: str,
    *,
    owner_sid: str | None = None,
    ignore_owner: bool = False,
    require_session: bool = False,
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
        meta = _read_slot_meta(target)
        caller_sid = normalize_session_id(owner_sid)
        slot_owner = None if meta is None else normalize_session_id(meta.get('owner_sid'))
        if meta is None or not _owner_matches(slot_owner, caller_sid, require_session=require_session):
            return {
                'deleted': False,
                'upload_id': uid,
                'error': 'Không tìm thấy phiên tải lên thuộc trình duyệt hiện tại.',
                'deleted_files': [],
                'verified_gone': False,
                'not_found_or_denied': True,
            }
    try:
        files_before = sorted(f.name for f in target.iterdir() if f.is_file())
    except (FileNotFoundError, OSError):
        files_before = []
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


def delete_all_uploads(
    base: Path,
    *,
    owner_sid: str | None = None,
    force_all: bool = False,
    require_session: bool = False,
) -> dict[str, Any]:
    """Delete temporary user uploads in `owner_sid` scope (never touches bundled samples or other browsers' sessions)."""
    root = user_uploads_root(base)
    caller_sid = normalize_session_id(owner_sid)
    deleted_ids: list[str] = []
    deleted_files: list[str] = []
    if root.is_dir() and (force_all or not (require_session and caller_sid is None)):
        try:
            items = list(root.iterdir())
        except OSError:
            items = []
        for item in items:
            try:
                if not item.is_dir() or not _UPLOAD_ID_RE.match(item.name):
                    continue
                if not force_all:
                    meta = _read_slot_meta(item)
                    if meta is None:
                        continue
                    if str(meta.get('retention_mode') or 'ttl').strip().lower() == 'ephemeral':
                        continue
                    slot_owner = normalize_session_id(meta.get('owner_sid'))
                    if not _owner_matches(slot_owner, caller_sid, require_session=require_session):
                        continue
                item_files = sorted(f.name for f in item.iterdir() if f.is_file())
                shutil.rmtree(item, ignore_errors=False)
                if not item.exists():
                    deleted_ids.append(item.name)
                    deleted_files.extend(f'{item.name}/{fn}' for fn in item_files)
            except FileNotFoundError:
                continue
    remaining = list_uploads(base, owner_sid=caller_sid, include_all=force_all, require_session=require_session)
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
