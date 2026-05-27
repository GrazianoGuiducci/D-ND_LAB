#!/usr/bin/env python3
"""Recurrence validation cycle for Finance candidate discovery.

Reads the latest window/universe scout candidates and tests them across rolling
windows. This is the gate between a local candidate and inactive paper-ledger
design; it never opens paper/live-sim by itself.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from finance_recurrence_diagnostic import classify as classify_symbol_recurrence  # noqa: E402
from finance_transfer_diagnostic import run_symbol  # noqa: E402


SCHEMA = "dndlab.finance.recurrence_validation_cycle.value.v1"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


ROOT = repo_root()
VALUE_DIR = ROOT / "data" / "finance" / "value"
VALIDATION_DIR = ROOT / "data" / "finance" / "recurrence_validation"
DIAGNOSTIC_DIR = ROOT / "data" / "finance" / "diagnostics"


def rel(path: Path | None) -> str | None:
    if not path:
        return None
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path | None) -> dict[str, Any] | None:
    if not path or not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def latest_scout_candidates(limit: int) -> list[dict[str, Any]]:
    scout = load_json(VALUE_DIR / "finance_window_universe_scout_latest.json") or {}
    summary = scout.get("summary") if isinstance(scout.get("summary"), dict) else {}
    candidates = summary.get("selected_for_crosscheck")
    if not isinstance(candidates, list):
        return []
    return [
        row for row in candidates[:limit]
        if isinstance(row, dict) and row.get("symbol") and row.get("start") and row.get("end")
    ]


def write_json_pair(payload: dict[str, Any]) -> dict[str, str]:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    VALUE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    artifact = VALIDATION_DIR / f"finance_recurrence_validation_cycle_{stamp}.json"
    value_path = VALUE_DIR / f"finance_recurrence_validation_cycle_{stamp}.json"
    latest = VALUE_DIR / "finance_recurrence_validation_cycle_latest.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    artifact.write_text(text, encoding="utf-8")
    value_path.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    return {
        "artifact": rel(artifact) or str(artifact),
        "stamped": rel(value_path) or str(value_path),
        "latest": rel(latest) or str(latest),
    }


def rolling_windows(anchor_start: str, anchor_end: str, *, step_days: int, count: int) -> list[dict[str, str]]:
    start_dt = datetime.fromisoformat(anchor_start).date()
    end_dt = datetime.fromisoformat(anchor_end).date()
    width = (end_dt - start_dt).days
    windows = []
    for idx in range(count):
        shifted_end = end_dt - timedelta(days=idx * step_days)
        shifted_start = shifted_end - timedelta(days=width)
        label = "anchor" if idx == 0 else f"prev_step_{idx}"
        windows.append({"label": label, "start": shifted_start.isoformat(), "end": shifted_end.isoformat()})
    return windows


def validate_candidate(candidate: dict[str, Any], *, step_days: int, count: int, seed: int, shuffles: int) -> dict[str, Any]:
    symbol = str(candidate["symbol"]).upper()
    windows = rolling_windows(str(candidate["start"]), str(candidate["end"]), step_days=step_days, count=count)
    rows = []
    for idx, spec in enumerate(windows):
        row = run_symbol(
            symbol,
            start=spec["start"],
            end=spec["end"],
            seed=seed + idx,
            shuffles=shuffles,
        )
        row["label"] = spec["label"]
        row["window_start"] = spec["start"]
        row["window_end"] = spec["end"]
        rows.append(row)
    classification = classify_symbol_recurrence(rows)
    robust_count = len(classification.get("robust_all_null_windows") or [])
    return {
        "symbol": symbol,
        "asset_class": candidate.get("asset_class"),
        "source_scout": candidate,
        "windows": windows,
        "rows": rows,
        "classification": classification,
        "promotable_to_paper_design": classification.get("label") == "recurring_candidate",
        "robust_window_count": robust_count,
    }


def classify_cycle(candidate_results: list[dict[str, Any]]) -> dict[str, Any]:
    recurring = [row for row in candidate_results if row.get("classification", {}).get("label") == "recurring_candidate"]
    single = [row for row in candidate_results if row.get("classification", {}).get("label") == "single_robust_window"]
    review = [
        row for row in candidate_results
        if row.get("classification", {}).get("review_required_windows")
    ]
    if recurring:
        label = "recurrence_candidate_found"
        decision = "prepare_inactive_paper_ledger_design"
        reason = "At least one candidate has two or more robust rolling windows."
    elif single:
        label = "local_candidate_not_recurring"
        decision = "redesign_window_or_universe"
        reason = "Candidates are robust in one window only; recurrence is not established."
    elif review:
        label = "recurrence_review_required"
        decision = "repair_data_before_next_validation"
        reason = "At least one candidate/window needs data review."
    else:
        label = "no_recurrence_candidate"
        decision = "redesign_window_or_universe"
        reason = "No candidate survived rolling-window recurrence."
    return {
        "label": label,
        "decision": decision,
        "reason": reason,
        "recurring_symbols": [row["symbol"] for row in recurring],
        "single_window_symbols": [row["symbol"] for row in single],
        "review_symbols": [row["symbol"] for row in review],
        "paper_live_sim_allowed": False,
        "broker_sandbox_allowed": False,
        "real_execution_allowed": False,
    }


def build_payload(candidates: list[dict[str, Any]], *, step_days: int, count: int, seed: int, shuffles: int) -> dict[str, Any]:
    results = [
        validate_candidate(candidate, step_days=step_days, count=count, seed=seed, shuffles=shuffles)
        for candidate in candidates
    ]
    classification = classify_cycle(results)
    if not candidates:
        classification = {
            "label": "no_scout_candidates",
            "decision": "run_window_universe_scout",
            "reason": "No latest scout candidates were available.",
            "recurring_symbols": [],
            "single_window_symbols": [],
            "review_symbols": [],
            "paper_live_sim_allowed": False,
            "broker_sandbox_allowed": False,
            "real_execution_allowed": False,
        }
    payload = {
        "schema": SCHEMA,
        "generated_at": datetime.now(UTC).isoformat(),
        "domain": "finance",
        "intent": "Validate scout-nominated Finance candidates across rolling windows before paper-ledger design.",
        "parameters": {
            "step_days": step_days,
            "window_count": count,
            "seed": seed,
            "shuffles": shuffles,
        },
        "classification": classification,
        "summary": {
            "decision": classification["decision"],
            "label": classification["label"],
            "reason": classification["reason"],
            "candidates": [row.get("symbol") for row in candidates],
            "recurring_symbols": classification["recurring_symbols"],
            "single_window_symbols": classification["single_window_symbols"],
            "review_symbols": classification["review_symbols"],
            "paper_live_sim_allowed": False,
            "broker_sandbox_allowed": False,
            "real_execution_allowed": False,
            "next_gate": (
                "Prepare inactive paper ledger only if recurring_symbols is non-empty; otherwise redesign window/universe."
            ),
        },
        "candidate_results": results,
        "sources": {
            "window_universe_scout": rel(VALUE_DIR / "finance_window_universe_scout_latest.json"),
        },
        "boundary": {
            "operational": False,
            "public_claim": False,
            "trading_signal": False,
            "paper_live_sim": False,
        },
        "cards": [
            {
                "claim_id": "finance_recurrence_validation_cycle",
                "title": "Finance recurrence validation cycle",
                "decision": classification["decision"],
                "evidence": f"label={classification['label']}; recurring={len(classification['recurring_symbols'])}; single={len(classification['single_window_symbols'])}",
                "boundary": "No paper/live-sim or execution is authorized by recurrence validation alone.",
            }
        ],
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", help="comma-separated symbols; default latest scout selected rows")
    parser.add_argument("--step-days", type=int, default=45)
    parser.add_argument("--window-count", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--shuffles", type=int, default=1024)
    parser.add_argument("--candidate-limit", type=int, default=4)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    candidates = latest_scout_candidates(args.candidate_limit)
    if args.symbols:
        wanted = {item.strip().upper() for item in args.symbols.split(",") if item.strip()}
        candidates = [row for row in candidates if str(row.get("symbol", "")).upper() in wanted]
    payload = build_payload(
        candidates,
        step_days=args.step_days,
        count=args.window_count,
        seed=args.seed,
        shuffles=args.shuffles,
    )
    if args.write:
        payload["written"] = write_json_pair(payload)
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"status": "ok", "written": payload.get("written")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
