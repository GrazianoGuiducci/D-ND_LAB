"""Shared trajectory state emission.

The append-only trajectory log is the historical ledger. This state file is the
current pointer: it tells downstream audits whether the last trajectory is
pending, applied, skipped, or only informational.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import paths


def trajectory_state_path(domain: str) -> Path:
    return paths.domain_data_dir(domain) / "trajectory_state.json"


def direction_from_entry(entry: dict[str, Any]) -> str | None:
    action = entry.get("action") or {}
    if not isinstance(action, dict):
        return None
    detail = action.get("detail") or {}
    if not isinstance(detail, dict):
        return None
    for key in ("new_value", "direction", "seed_change", "directive", "instruction", "next_focus"):
        value = detail.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def write_trajectory_state(
    domain: str,
    *,
    status: str,
    source: str,
    cycle_ts: str | None = None,
    entry: dict[str, Any] | None = None,
    direction: str | None = None,
    reason: str | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    entry = entry or {}
    action = entry.get("action") or {}
    if not isinstance(action, dict):
        action = {}

    payload: dict[str, Any] = {
        "schema": "trajectory_state.v1",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "domain": domain,
        "status": status,
        "source": source,
        "cycle_ts": cycle_ts,
        "entry_ts": entry.get("ts"),
        "entry_cycle_ref": entry.get("cycle_ref"),
        "decision": entry.get("decision"),
        "confidence": entry.get("confidence"),
        "action_type": action.get("type"),
        "executed": entry.get("executed"),
        "direction": direction if direction is not None else direction_from_entry(entry),
        "reason": reason,
    }
    if extra:
        payload["extra"] = extra

    path = trajectory_state_path(domain)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def read_trajectory_state(domain: str) -> dict[str, Any] | None:
    path = trajectory_state_path(domain)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
