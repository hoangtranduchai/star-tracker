"""Structured JSONL execution-mode, CoG-fallback, and data-deletion audit logger."""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOG_REL_PATH = Path('data') / 'outputs' / 'execution_log.jsonl'
MAX_LOG_ENTRIES = 250
_LOG_LOCK = threading.Lock()
_REPLACE_MAX_ATTEMPTS = 6
_WIN_ABS_PATH_RE = re.compile(r"""[A-Za-z]:[\\/][^\s'"(),;<>|]+""")
_UNIX_ABS_PATH_RE = re.compile(
    r"""(?<![A-Za-z0-9_:/])/(?:app|home|Users|tmp|var|opt|root|srv|etc|mnt|Volumes|usr)/[^\s'"(),;<>|]+"""
)


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def log_path(base: Path) -> Path:
    return Path(base) / LOG_REL_PATH


def hash_session_id(owner_sid: str | None) -> str | None:
    """Return an irreversible 16-hex SHA-256 prefix for a session ID (never persists raw cookies)."""
    if not owner_sid:
        return None
    cleaned = str(owner_sid).strip().lower()
    if not cleaned:
        return None
    return hashlib.sha256(cleaned.encode('utf-8')).hexdigest()[:16]


def _relativize_matched_path(raw_path: str, base: Path | None) -> str:
    norm = raw_path.replace('\\', '/')
    if base is not None:
        base_posix = str(Path(base).resolve()).replace('\\', '/').rstrip('/')
        if norm.lower().startswith(base_posix.lower() + '/'):
            return norm[len(base_posix) + 1 :]
    for anchor in ('third_party/', 'data/', 'config/', 'src/', 'scripts/', 'web/'):
        idx = norm.lower().find('/' + anchor)
        if idx != -1:
            return norm[idx + 1 :]
    leaf = norm.rstrip('/').rsplit('/', 1)[-1]
    return leaf or norm


def sanitize_log_text(text: str | None, base: Path | None = None) -> str | None:
    """Strip absolute host filesystem paths (Windows or Unix) before persisting to audit logs."""
    if text is None:
        return None
    s = str(text)
    if not s:
        return s
    if base is not None:
        resolved = Path(base).resolve()
        for prefix in (str(resolved) + os.sep, str(resolved).replace('\\', '/') + '/'):
            if prefix in s:
                s = s.replace(prefix, '')
    s = _WIN_ABS_PATH_RE.sub(lambda m: _relativize_matched_path(m.group(0), base), s)
    s = _UNIX_ABS_PATH_RE.sub(lambda m: _relativize_matched_path(m.group(0), base), s)
    return s


def infer_execution_summary(
    requested_backend: str,
    executed_backend: str,
    *,
    fallback_triggered: bool = False,
    auto_router_used: bool = False,
    auto_router_selected: str | None = None,
) -> str:
    req = str(requested_backend or 'classical').lower()
    exe = str(executed_backend or req).lower()
    if fallback_triggered:
        return f'{req} -> classical [FALLBACK_TO_COG]'
    if auto_router_used:
        sel = str(auto_router_selected or exe).lower()
        if 'cnn' in sel:
            return 'auto -> cnn_hybrid [AUTO_ESCALATED]'
        return 'auto -> classical [FAST_COG]'
    return f'{req} -> {exe} [DIRECT]'


def _replace_with_retry(src: Path, dst: Path) -> None:
    """Atomically replace `dst` with `src`, retrying briefly on Windows file-lock contention."""
    last_err: OSError | None = None
    for attempt in range(_REPLACE_MAX_ATTEMPTS):
        try:
            os.replace(str(src), str(dst))
            return
        except (PermissionError, OSError) as err:
            last_err = err
            if attempt + 1 < _REPLACE_MAX_ATTEMPTS:
                time.sleep(0.015 + random.uniform(0.0, 0.035))
    if last_err is not None:
        raise last_err


def _read_lines_with_retry(lp: Path) -> list[str]:
    for attempt in range(3):
        try:
            return lp.read_text(encoding='utf-8').splitlines()
        except (PermissionError, OSError):
            if attempt + 1 < 3:
                time.sleep(0.015)
        except Exception:
            return []
    return []


def append_audit_event(base: Path, event: dict[str, Any]) -> dict[str, Any]:
    """Append a structured execution or deletion audit record to `execution_log.jsonl`."""
    rec = dict(event)
    rec.setdefault('event_id', uuid.uuid4().hex[:12])
    rec.setdefault('timestamp_utc', _utc_now())
    rec.setdefault('timestamp_epoch', round(time.time(), 3))
    for text_key in ('fallback_reason', 'auto_router_reason', 'note', 'error'):
        if rec.get(text_key) is not None:
            rec[text_key] = sanitize_log_text(str(rec[text_key]), base)
    lp = log_path(base)
    lp.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(rec, ensure_ascii=False)
    with _LOG_LOCK:
        existing: list[str] = _read_lines_with_retry(lp) if lp.is_file() else []
        existing.append(line)
        if len(existing) > MAX_LOG_ENTRIES:
            existing = existing[-MAX_LOG_ENTRIES:]
        payload_txt = '\n'.join(existing) + '\n'
        tmp_p = lp.with_name(f'.{lp.name}.{uuid.uuid4().hex[:8]}.tmp')
        try:
            tmp_p.write_text(payload_txt, encoding='utf-8')
            _replace_with_retry(tmp_p, lp)
        finally:
            if tmp_p.exists():
                try:
                    tmp_p.unlink()
                except OSError:
                    pass
    return rec


def record_pipeline_run(
    base: Path,
    *,
    endpoint: str,
    source_type: str,
    source_name: str,
    requested_backend: str,
    executed_backend: str,
    fallback_triggered: bool,
    fallback_reason: str | None,
    auto_router_used: bool = False,
    auto_router_selected: str | None = None,
    auto_router_reason: str | None = None,
    status: str = 'LOST',
    reject_code: str | None = None,
    n_valid_pairs: int = 0,
    n_detected: int = 0,
    latency_ms: float | None = None,
    checkpoint_status: str | None = None,
    checkpoint_sha256: str | None = None,
    upload_id: str | None = None,
    retention_mode: str | None = None,
    deleted_immediately: bool | None = None,
    owner_sid: str | None = None,
    owner_sid_hash: str | None = None,
) -> dict[str, Any]:
    summary = infer_execution_summary(
        requested_backend,
        executed_backend,
        fallback_triggered=fallback_triggered,
        auto_router_used=auto_router_used,
        auto_router_selected=auto_router_selected,
    )
    sid_hash = owner_sid_hash if owner_sid_hash is not None else hash_session_id(owner_sid)
    return append_audit_event(
        base,
        {
            'event_type': 'PIPELINE_RUN',
            'endpoint': endpoint,
            'source_type': source_type,
            'source_name': source_name,
            'requested_backend': requested_backend,
            'executed_backend': executed_backend,
            'mode_summary': summary,
            'fallback_triggered': bool(fallback_triggered),
            'fallback_reason': fallback_reason,
            'auto_router_used': bool(auto_router_used),
            'auto_router_selected': auto_router_selected,
            'auto_router_reason': auto_router_reason,
            'checkpoint_status': checkpoint_status,
            'checkpoint_sha256': checkpoint_sha256,
            'status': status,
            'reject_code': reject_code,
            'n_valid_pairs': int(n_valid_pairs),
            'n_detected': int(n_detected),
            'latency_ms': None if latency_ms is None else round(float(latency_ms), 2),
            'upload_id': upload_id,
            'retention_mode': retention_mode,
            'deleted_immediately': deleted_immediately,
            'owner_sid_hash': sid_hash,
        },
    )


# Alias for callers referencing `record_pipeline_execution`
record_pipeline_execution = record_pipeline_run


def record_data_deletion(
    base: Path,
    *,
    action: str,
    upload_id: str | None,
    deleted_files: list[str],
    verified_gone: bool,
    endpoint: str = 'DELETE /api/uploads',
    owner_sid: str | None = None,
    owner_sid_hash: str | None = None,
) -> dict[str, Any]:
    sid_hash = owner_sid_hash if owner_sid_hash is not None else hash_session_id(owner_sid)
    return append_audit_event(
        base,
        {
            'event_type': 'DATA_DELETION',
            'action': action,
            'endpoint': endpoint,
            'upload_id': upload_id,
            'deleted_files': list(deleted_files),
            'n_deleted_files': len(deleted_files),
            'verified_gone': bool(verified_gone),
            'owner_sid_hash': sid_hash,
        },
    )


def _is_private_upload_entry(rec: dict[str, Any]) -> bool:
    if rec.get('event_type') == 'DATA_DELETION':
        return True
    if rec.get('source_type') == 'upload' or rec.get('upload_id') is not None:
        return True
    ep = str(rec.get('endpoint') or '')
    return ep in ('/api/run-upload', '/api/compare-upload') or ep.startswith('DELETE /api/uploads')


def read_execution_log(
    base: Path,
    *,
    limit: int = 50,
    owner_sid: str | None = None,
    scope_by_session: bool = False,
) -> list[dict[str, Any]]:
    """Return the most recent audit entries (newest first).

    When `scope_by_session=True`, upload and deletion records are filtered strictly to the
    caller's `owner_sid_hash` so one browser can never see another user's uploaded filenames,
    sidecars, or upload IDs (even for ephemeral runs), while non-upload preset/fallback runs
    remain visible.
    """
    lp = log_path(base)
    if not lp.is_file():
        return []
    caller_hash = hash_session_id(owner_sid)
    max_rows = max(1, min(200, int(limit)))
    rows: list[dict[str, Any]] = []
    with _LOG_LOCK:
        lines = _read_lines_with_retry(lp)
    for ln in reversed(lines):
        if not ln.strip():
            continue
        try:
            rec = json.loads(ln)
        except Exception:
            continue
        if scope_by_session and _is_private_upload_entry(rec):
            entry_hash = rec.get('owner_sid_hash')
            if not caller_hash or not entry_hash or entry_hash != caller_hash:
                continue
        rows.append(rec)
        if len(rows) >= max_rows:
            break
    return rows
