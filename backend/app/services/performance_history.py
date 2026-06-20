"""Time-series PnL snapshots for auto vs manual vs total (retain 4 weeks)."""
from __future__ import annotations

import asyncio
import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings

_lock = threading.Lock()
_history_path = Path(settings.performance_history_path)
_recorder_task: Optional[asyncio.Task] = None
_last_snapshot_at: Optional[datetime] = None

RETENTION_DAYS = 28


def _load_history() -> Dict[str, Any]:
    if _history_path.is_file():
        try:
            data = json.loads(_history_path.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                data.setdefault('snapshots', [])
                return data
        except (json.JSONDecodeError, OSError, TypeError):
            pass
    return {'snapshots': []}


def _save_history(data: Dict[str, Any]) -> None:
    _history_path.parent.mkdir(parents=True, exist_ok=True)
    _history_path.write_text(json.dumps(data, indent=2), encoding='utf-8')


def _parse_ts(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace('Z', '+00:00'))


def _prune(snapshots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    out = []
    for row in snapshots:
        try:
            if _parse_ts(row['at']) >= cutoff:
                out.append(row)
        except (KeyError, ValueError):
            continue
    return out


def record_snapshot(*, force: bool = False) -> Optional[Dict[str, Any]]:
    global _last_snapshot_at
    from app.services.paper_trading import compute_performance_breakdown

    now = datetime.now(timezone.utc)
    min_gap = timedelta(seconds=settings.performance_snapshot_min_seconds)
    if not force and _last_snapshot_at and now - _last_snapshot_at < min_gap:
        return None

    row = compute_performance_breakdown()
    row['at'] = now.isoformat()

    with _lock:
        data = _load_history()
        snapshots: List[Dict[str, Any]] = data.setdefault('snapshots', [])
        if snapshots:
            try:
                last = _parse_ts(snapshots[-1]['at'])
                if not force and now - last < min_gap:
                    return None
            except (KeyError, ValueError):
                pass
        snapshots.append(row)
        data['snapshots'] = _prune(snapshots)
        _save_history(data)

    _last_snapshot_at = now
    return row


def _filter_days(snapshots: List[Dict[str, Any]], days: int) -> List[Dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return [s for s in snapshots if _parse_ts(s['at']) >= cutoff]


def _zero_point(days_ago: int = 7) -> Dict[str, Any]:
    t = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {
        'at': t.isoformat(),
        'total_pnl_usd': 0.0,
        'total_pnl_pct': 0.0,
        'auto_pnl_usd': 0.0,
        'auto_pnl_pct': 0.0,
        'manual_pnl_usd': 0.0,
        'manual_pnl_pct': 0.0,
        'total_equity': settings.paper_trading_initial_balance,
        'auto_equity': settings.paper_trading_initial_balance / 2,
        'manual_equity': settings.paper_trading_initial_balance / 2,
    }


def _ensure_series(snapshots: List[Dict[str, Any]], days: int) -> List[Dict[str, Any]]:
    if not snapshots:
        return [_zero_point(days), _zero_point(0)]
    if len(snapshots) == 1:
        return [_zero_point(days), snapshots[0]]
    return snapshots


def _build_chart_payload(snapshots: List[Dict[str, Any]], days: int) -> Dict[str, Any]:
    series = _ensure_series(_filter_days(snapshots, days), days)

    def map_series(key_usd: str, key_pct: str) -> List[Dict[str, Any]]:
        return [
            {
                'at': s['at'],
                'label': _parse_ts(s['at']).strftime('%d/%m'),
                'pnl_usd': s.get(key_usd, 0),
                'pnl_pct': s.get(key_pct, 0),
            }
            for s in series
        ]

    return {
        'days': days,
        'retention_days': RETENTION_DAYS,
        'point_count': len(series),
        'auto': map_series('auto_pnl_usd', 'auto_pnl_pct'),
        'manual': map_series('manual_pnl_usd', 'manual_pnl_pct'),
        'total': map_series('total_pnl_usd', 'total_pnl_pct'),
        'latest': series[-1] if series else None,
    }


def get_performance_week() -> Dict[str, Any]:
    with _lock:
        data = _load_history()
    return _build_chart_payload(data.get('snapshots') or [], days=7)


def get_performance_month() -> Dict[str, Any]:
    with _lock:
        data = _load_history()
    return _build_chart_payload(data.get('snapshots') or [], days=28)


async def _recorder_loop() -> None:
    await asyncio.sleep(10)
    record_snapshot(force=True)
    while True:
        try:
            record_snapshot(force=False)
        except Exception:
            pass
        await asyncio.sleep(settings.performance_snapshot_min_seconds)


def start_performance_recorder() -> None:
    global _recorder_task
    if _recorder_task is None or _recorder_task.done():
        _recorder_task = asyncio.create_task(_recorder_loop())
