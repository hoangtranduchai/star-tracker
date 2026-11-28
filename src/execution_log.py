"""Structured JSONL execution-mode, CoG-fallback, and data-deletion audit logger."""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOG_REL_PATH = Path('data') / 'outputs' / 'execution_log.jsonl'
MAX_LOG_ENTRIES = 250
_LOG_LOCK = threading.Lock()


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def log_path(base: Path) -> Path:
    return Path(base) / LOG_REL_PATH


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


def append_audit_event(base: Path, event: dict[str, Any]) -> dict[str, Any]:
    """Append a structured execution or deletion audit record to `execution_log.jsonl`."""
    rec = dict(event)
    rec.setdefault('event_id', uuid.uuid4().hex[:12])
    rec.setdefault('timestamp_utc', _utc_now())
    rec.setdefault('timestamp_epoch', round(time.time(), 3))
    lp = log_path(base)
    lp.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(rec, ensure_ascii=False)
    with _LOG_LOCK:
        existing: list[str] = []
        if lp.is_file():
            try:
                existing = lp.read_text(encoding='utf-8').splitlines()
            except Exception:
                existing = []
        existing.append(line)
        if len(existing) > MAX_LOG_ENTRIES:
            existing = existing[-MAX_LOG_ENTRIES:]
        payload_txt = '\n'.join(existing) + '\n'
        tmp_p = lp.with_name(f'.{lp.name}.{uuid.uuid4().hex[:8]}.tmp')
        try:
            tmp_p.write_text(payload_txt, encoding='utf-8')
            os.replace(str(tmp_p), str(lp))
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
    upload_id: str | None = None,
    retention_mode: str | None = None,
    deleted_immediately: bool | None = None,
) -> dict[str, Any]:
    summary = infer_execution_summary(
        requested_backend,
        executed_backend,
        fallback_triggered=fallback_triggered,
        auto_router_used=auto_router_used,
        auto_router_selected=auto_router_selected,
    )
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
            'status': status,
            'reject_code': reject_code,
            'n_valid_pairs': int(n_valid_pairs),
            'n_detected': int(n_detected),
            'latency_ms': None if latency_ms is None else round(float(latency_ms), 2),
            'upload_id': upload_id,
            'retention_mode': retention_mode,
            'deleted_immediately': deleted_immediately,
        },
    )


def record_data_deletion(
    base: Path,
    *,
    action: str,
    upload_id: str | None,
    deleted_files: list[str],
    verified_gone: bool,
    endpoint: str = 'DELETE /api/uploads',
) -> dict[str, Any]:
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
        },
    )


def read_execution_log(base: Path, *, limit: int = 50) -> list[dict[str, Any]]:
    """Return the most recent audit entries (newest first)."""
    lp = log_path(base)
    if not lp.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with _LOG_LOCK:
        lines = lp.read_text(encoding='utf-8').splitlines()
    for ln in reversed(lines):
        if not ln.strip():
            continue
        try:
            rows.append(json.loads(ln))
        except Exception:
            continue
        if len(rows) >= max(1, min(200, int(limit))):
            break
    return rows
