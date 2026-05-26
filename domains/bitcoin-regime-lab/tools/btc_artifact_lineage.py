#!/usr/bin/env python3
"""Shared BTC value artifact writer with runtime lineage metadata."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LINEAGE_SCHEMA = "dndlab.bitcoin.runtime_lineage.v1"
BOUNDARY = (
    "Runtime lineage only: no market-data interpretation, no policy mutation, "
    "no trading signal."
)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _repo_relative(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path)


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _latest_match(directory: Path, pattern: str) -> Path | None:
    matches = sorted(directory.glob(pattern))
    return matches[-1] if matches else None


def _input_artifacts(payload: dict[str, Any], repo_root: Path) -> list[str]:
    values: list[Any] = []
    for key in ("input_artifacts", "input_paths", "source_artifacts"):
        raw = payload.get(key)
        if isinstance(raw, list):
            values.extend(raw)
        elif isinstance(raw, dict):
            values.extend(raw.values())
        elif isinstance(raw, str):
            values.append(raw)

    inputs: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value:
            continue
        path = Path(value)
        normalized = _repo_relative(path, repo_root) if path.is_absolute() else value
        if normalized not in seen:
            inputs.append(normalized)
            seen.add(normalized)
    return inputs


def _active_cycle_ts() -> str | None:
    active = os.environ.get("DND_LAB_ACTIVE_CYCLE_TS", "").strip()
    if re.fullmatch(r"\d{8}_\d{4,6}", active):
        return active
    return None


def _last_cycle_ts(data_dir: Path) -> str | None:
    trajectory = _read_json(data_dir / "trajectory_state.json")
    value = trajectory.get("cycle_ts") or trajectory.get("last_cycle_ts")
    return str(value) if value else None


def _env_path(name: str, repo_root: Path) -> Path | None:
    value = os.environ.get(name, "").strip()
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def _runtime_lineage(
    *,
    payload: dict[str, Any],
    tool_path: Path,
    repo_root: Path,
    data_dir: Path,
    latest: Path,
    stamped: Path,
) -> dict[str, Any]:
    cycle_ts = _active_cycle_ts()
    last_cycle_ts = _last_cycle_ts(data_dir)
    session = os.environ.get("DND_LAB_LINEAGE_SESSION", "btc_value_refresh").strip() or "btc_value_refresh"
    refresh_ts = os.environ.get("DND_LAB_VALUE_REFRESH_TS", "").strip()
    reports_dir = data_dir / "reports"

    trace = None
    log = None
    report = None
    if cycle_ts:
        trace_candidates = [
            data_dir / f"cycle_trace_{cycle_ts}.json",
            data_dir / "artifacts" / cycle_ts / "cycle_trace.json",
        ]
        report_candidate = reports_dir / f"agent_{cycle_ts}.md"
        trace = _first_existing(trace_candidates)
        log = _env_path("DND_LAB_ACTIVE_CYCLE_LOG", repo_root) or _latest_match(data_dir, f"cycle_{cycle_ts}*.log")
        report = _first_existing([report_candidate])
        trace = trace or trace_candidates[0]
        report = report or report_candidate

    lineage: dict[str, Any] = {
        "schema": LINEAGE_SCHEMA,
        "producer": tool_path.name,
        "tool_path": _repo_relative(tool_path, repo_root),
        "runtime": "python",
        "provider": "deterministic-python",
        "session": session,
        "cycle_ts": cycle_ts,
        "last_cycle_ref": last_cycle_ts,
        "input_artifacts": _input_artifacts(payload, repo_root),
        "output_artifact": _repo_relative(latest, repo_root),
        "output_artifact_stamped": _repo_relative(stamped, repo_root),
        "trajectory_state": _repo_relative(data_dir / "trajectory_state.json", repo_root),
        "boundary": BOUNDARY,
    }
    if refresh_ts:
        lineage["refresh_ts"] = refresh_ts
    if trace:
        lineage["raw_trace"] = _repo_relative(trace, repo_root)
    if log:
        lineage["raw_log"] = _repo_relative(log, repo_root)
    if report:
        lineage["report"] = _repo_relative(report, repo_root)
    if not cycle_ts and last_cycle_ts:
        last_trace = _latest_match(data_dir, f"cycle_trace_{last_cycle_ts}.json")
        last_log = _latest_match(data_dir, f"cycle_{last_cycle_ts}*.log")
        last_report = _first_existing([reports_dir / f"agent_{last_cycle_ts}.md"])
        if last_trace:
            lineage["last_cycle_trace"] = _repo_relative(last_trace, repo_root)
        if last_log:
            lineage["last_cycle_log"] = _repo_relative(last_log, repo_root)
        if last_report:
            lineage["last_cycle_report"] = _repo_relative(last_report, repo_root)
    return lineage


def write_json_artifact(
    *,
    payload: dict[str, Any],
    value_dir: Path,
    data_dir: Path,
    repo_root: Path,
    tool_path: Path,
    artifact_prefix: str,
) -> dict[str, str]:
    value_dir.mkdir(parents=True, exist_ok=True)
    latest = value_dir / f"{artifact_prefix}_latest.json"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stamped = value_dir / f"{artifact_prefix}_{stamp}.json"

    payload["runtime_lineage"] = _runtime_lineage(
        payload=payload,
        tool_path=tool_path,
        repo_root=repo_root,
        data_dir=data_dir,
        latest=latest,
        stamped=stamped,
    )
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    latest.write_text(text + "\n", encoding="utf-8")
    stamped.write_text(text + "\n", encoding="utf-8")
    return {"latest": str(latest), "stamped": str(stamped)}
