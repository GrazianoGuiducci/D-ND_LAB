#!/usr/bin/env python3
"""btc_paper_simulation_ledger.py - BTC paper simulation ledger.

This tool reads the BTC policy simulator and turns its event windows into a
compact research ledger: simulated decision, outcome, error against the normal
BTC baseline and the next adjustment hint. It does not fetch data and does not
place orders.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VERSION = "0.1.0"
DOMAIN = "bitcoin-regime-lab"
DOMAIN_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = DOMAIN_DIR.parents[1]
DATA_ROOT = Path(os.environ.get("LAB_DATA_DIR", REPO_ROOT / "data")).resolve()
DATA_DIR = DATA_ROOT / DOMAIN
VALUE_DIR = DATA_DIR / "value"

POLICY_SIMULATOR_LATEST = VALUE_DIR / "btc_policy_simulator_latest.json"
EXCHANGE_LATEST = VALUE_DIR / "btc_exchange_ohlcv_latest.json"
DAILY_CLOSED_GATE_LATEST = VALUE_DIR / "btc_daily_closed_evidence_gate_latest.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _round(value: float | int | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _median(values: list[float]) -> float | None:
    return float(statistics.median(values)) if values else None


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _pct(count: int, total: int) -> float | None:
    if total <= 0:
        return None
    return round(count / total, 4)


def _normal_baseline(policy: dict[str, Any]) -> float | None:
    normal = policy.get("normal_chart_comparison")
    if not isinstance(normal, dict):
        return None
    rolling = normal.get("rolling_baseline")
    if not isinstance(rolling, dict):
        return None
    return _round(rolling.get("median_forward_return_pct"))


def _decision_for_event(event: dict[str, Any], *, baseline: float | None) -> dict[str, Any]:
    event_return = _round(event.get("forward_return_pct"))
    max_up = _round(event.get("forward_max_up_pct"))
    max_down = _round(event.get("forward_max_down_pct"))
    strict_closed = bool(event.get("strict_control_closed"))
    random_rate = _round(event.get("random_matched_control_rate"))
    policy_closed = bool(event.get("policy_closed"))
    relation = str(event.get("relation") or "")
    error = _round((event_return - baseline), 4) if event_return is not None and baseline is not None else None
    fragile = bool(max_down is not None and max_down <= -8.0)
    strong_random = bool(random_rate is not None and random_rate >= 0.55)
    positive_edge = bool(error is not None and error > 0.0)
    strong_edge = bool(error is not None and error >= 0.75)
    negative_edge = bool(error is not None and error < 0.0)

    if positive_edge and not fragile and not strict_closed and not strong_random:
        decision = "candidate_accept"
    elif strong_edge and policy_closed and not fragile and not strict_closed:
        decision = "candidate_accept"
    elif negative_edge or fragile or strict_closed:
        decision = "candidate_reject"
    else:
        decision = "ambiguous_watch"

    if positive_edge and not fragile:
        outcome = "above_normal"
    elif positive_edge and fragile:
        outcome = "fragile_above_normal"
    elif negative_edge:
        outcome = "below_normal"
    else:
        outcome = "near_normal"

    if strict_closed:
        control_state = "strict_control_dominates"
    elif strong_random:
        control_state = "random_matched_high"
    elif policy_closed:
        control_state = "policy_closed"
    else:
        control_state = "policy_open"

    confidence_parts = []
    if error is not None:
        confidence_parts.append(min(abs(error) / 4.0, 1.0))
    if strict_closed:
        confidence_parts.append(0.75)
    if fragile:
        confidence_parts.append(0.70)
    if random_rate is not None:
        confidence_parts.append(min(abs(0.5 - random_rate) * 2.0, 1.0))
    confidence = _round(_mean(confidence_parts), 3) if confidence_parts else None

    if decision == "candidate_accept":
        lesson = "event window beats the normal baseline without current fragility/control dominance"
        next_adjustment = "retain acceptance rule and retest on the next closed-data run"
    elif decision == "candidate_reject":
        lesson = "event window is below normal, fragile or explained by stricter controls"
        next_adjustment = "tighten event filter or redesign the policy contract"
    else:
        lesson = "event window does not separate enough from normal BTC movement"
        next_adjustment = "keep as watch and wait for cleaner closed-data evidence"

    return {
        "event_date": event.get("event_date"),
        "relation": relation or None,
        "event_close": _round(event.get("event_close"), 2),
        "decision": decision,
        "confidence": confidence,
        "outcome": outcome,
        "control_state": control_state,
        "normal_baseline_return_pct": baseline,
        "simulated_forward_return_pct": event_return,
        "error_vs_baseline_pct": error,
        "forward_max_up_pct": max_up,
        "forward_max_down_pct": max_down,
        "fragile": fragile,
        "policy_closed": policy_closed,
        "strict_control_closed": strict_closed,
        "random_matched_control_rate": random_rate,
        "lesson": lesson,
        "next_adjustment": next_adjustment,
    }


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors = [float(row["error_vs_baseline_pct"]) for row in rows if row.get("error_vs_baseline_pct") is not None]
    accepted = [row for row in rows if row.get("decision") == "candidate_accept"]
    rejected = [row for row in rows if row.get("decision") == "candidate_reject"]
    watch = [row for row in rows if row.get("decision") == "ambiguous_watch"]
    above = [row for row in rows if (row.get("error_vs_baseline_pct") is not None and float(row["error_vs_baseline_pct"]) > 0)]
    fragile = [row for row in rows if row.get("fragile")]
    false_accept = [
        row for row in accepted
        if row.get("error_vs_baseline_pct") is not None and float(row["error_vs_baseline_pct"]) <= 0
    ]
    missed_positive = [
        row for row in rejected
        if row.get("error_vs_baseline_pct") is not None
        and float(row["error_vs_baseline_pct"]) > 0
        and not row.get("fragile")
    ]
    worst = min(rows, key=lambda row: row.get("error_vs_baseline_pct") if row.get("error_vs_baseline_pct") is not None else 9999, default=None)
    best = max(rows, key=lambda row: row.get("error_vs_baseline_pct") if row.get("error_vs_baseline_pct") is not None else -9999, default=None)
    return {
        "rows": len(rows),
        "candidate_accept": len(accepted),
        "candidate_reject": len(rejected),
        "ambiguous_watch": len(watch),
        "above_normal": len(above),
        "fragile": len(fragile),
        "false_accept": len(false_accept),
        "missed_positive": len(missed_positive),
        "hit_rate_vs_baseline": _pct(len(above), len(rows)),
        "median_error_vs_baseline_pct": _round(_median(errors)),
        "mean_error_vs_baseline_pct": _round(_mean(errors)),
        "best_event": {
            "event_date": best.get("event_date"),
            "error_vs_baseline_pct": best.get("error_vs_baseline_pct"),
            "decision": best.get("decision"),
        } if best else None,
        "worst_event": {
            "event_date": worst.get("event_date"),
            "error_vs_baseline_pct": worst.get("error_vs_baseline_pct"),
            "decision": worst.get("decision"),
        } if worst else None,
    }


def build_ledger(
    *,
    policy_path: Path = POLICY_SIMULATOR_LATEST,
    exchange_path: Path = EXCHANGE_LATEST,
    gate_path: Path = DAILY_CLOSED_GATE_LATEST,
    limit: int | None = None,
) -> dict[str, Any]:
    policy = _read_json(policy_path)
    exchange = _read_json(exchange_path)
    gate = _read_json(gate_path)
    events = policy.get("events") if isinstance(policy.get("events"), list) else []
    baseline = _normal_baseline(policy)
    rows = [_decision_for_event(event, baseline=baseline) for event in events]
    rows = [row for row in rows if row.get("event_date")]
    if limit and limit > 0:
        rows = rows[-limit:]
    metrics = _aggregate(rows)
    gate_payload = gate.get("gate") if isinstance(gate.get("gate"), dict) else {}
    normal = policy.get("normal_chart_comparison") if isinstance(policy.get("normal_chart_comparison"), dict) else {}
    chart = normal.get("normal_chart_window") if isinstance(normal.get("normal_chart_window"), dict) else {}

    if metrics["rows"] == 0:
        decision = "observe"
        verdict = "PAPER_SIMULATION_LEDGER_EMPTY"
    elif (metrics.get("median_error_vs_baseline_pct") or 0.0) > 0 and metrics.get("false_accept", 0) == 0:
        decision = "watch"
        verdict = "PAPER_SIMULATION_LEDGER_POSITIVE_BUT_UNPROMOTED"
    elif metrics.get("false_accept", 0) or metrics.get("missed_positive", 0):
        decision = "redesign"
        verdict = "PAPER_SIMULATION_LEDGER_ERROR_VISIBLE"
    else:
        decision = "watch"
        verdict = "PAPER_SIMULATION_LEDGER_BASELINE_COMPARISON_READY"

    return {
        "schema": "dndlab.bitcoin.paper_simulation_ledger.v1",
        "generated_at": _utc_now(),
        "domain": DOMAIN,
        "version": VERSION,
        "input_artifacts": {
            "policy_simulator": str(policy_path),
            "exchange_ohlcv": str(exchange_path),
            "daily_closed_evidence_gate": str(gate_path),
        },
        "frame": {
            "purpose": "measure simulated event decisions against the normal BTC chart baseline",
            "source_policy": (policy.get("policy_contract") or {}).get("policy_id"),
            "normal_baseline_return_pct": baseline,
            "forward_window_days": ((policy.get("policy_contract") or {}).get("forward_window_days")),
            "chart_window": {
                "first_date": chart.get("first_date"),
                "last_date": chart.get("last_date"),
                "days": chart.get("days"),
            },
            "closed_data": {
                "latest_common_date": ((exchange.get("metrics") or {}).get("latest_common_date")),
                "latest_closed_common_date": gate_payload.get("latest_closed_common_date"),
                "mutation_allowed": gate_payload.get("mutation_allowed"),
            },
        },
        "summary": {
            "observe": 1 if decision == "observe" else 0,
            "watch": 1 if decision == "watch" else 0,
            "test": 0,
            "reject": 0,
            "redesign": 1 if decision == "redesign" else 0,
        },
        "card": {
            "claim_id": "btc_paper_simulation_ledger_v0",
            "title": "BTC paper simulation ledger v0",
            "decision": decision,
            "verdict": verdict,
            "evidence": (
                f"{metrics['rows']} simulated rows; median error vs normal baseline "
                f"{metrics.get('median_error_vs_baseline_pct')}%; hit-rate "
                f"{metrics.get('hit_rate_vs_baseline')}; accept/reject/watch "
                f"{metrics.get('candidate_accept')}/{metrics.get('candidate_reject')}/"
                f"{metrics.get('ambiguous_watch')}."
            ),
            "interpretation": "The ledger measures where simulated method decisions diverge from the normal BTC chart path.",
            "boundary": "Paper simulation ledger: simulated research decisions, outcome, error and baseline comparison.",
        },
        "metrics": metrics,
        "rows": rows,
    }


def write_artifact(payload: dict[str, Any]) -> dict[str, str]:
    VALUE_DIR.mkdir(parents=True, exist_ok=True)
    latest = VALUE_DIR / "btc_paper_simulation_ledger_latest.json"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stamped = VALUE_DIR / f"btc_paper_simulation_ledger_{stamp}.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    latest.write_text(text + "\n", encoding="utf-8")
    stamped.write_text(text + "\n", encoding="utf-8")
    return {"latest": str(latest), "stamped": str(stamped)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build BTC paper simulation ledger.")
    parser.add_argument("--policy", default=str(POLICY_SIMULATOR_LATEST))
    parser.add_argument("--exchange", default=str(EXCHANGE_LATEST))
    parser.add_argument("--gate", default=str(DAILY_CLOSED_GATE_LATEST))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = build_ledger(
        policy_path=Path(args.policy),
        exchange_path=Path(args.exchange),
        gate_path=Path(args.gate),
        limit=args.limit or None,
    )
    if args.write:
        payload["files"] = write_artifact(payload)
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"status": "OK", "files": payload.get("files"), "summary": payload["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
