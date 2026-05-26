#!/usr/bin/env python3
"""Predeclare the strict-close closed-daily BTC event contract.

This artifact turns the best pressure-test axis into an explicit next-cycle
paper contract. It does not promote or mutate method policy.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from btc_artifact_lineage import write_json_artifact
from btc_closed_daily_event_null import EXCHANGE_LATEST, build_closed_daily_event_null


VERSION = "0.1.0"
DOMAIN = "bitcoin-regime-lab"
DOMAIN_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = DOMAIN_DIR.parents[1]
DATA_ROOT = Path(os.environ.get("LAB_DATA_DIR", REPO_ROOT / "data")).resolve()
DATA_DIR = DATA_ROOT / DOMAIN
VALUE_DIR = DATA_DIR / "value"
PRESSURE_LATEST = VALUE_DIR / "btc_closed_daily_event_null_pressure_latest.json"
GATE_LATEST = VALUE_DIR / "btc_daily_closed_evidence_gate_latest.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _variant_by_name(pressure: dict[str, Any], name: str) -> dict[str, Any]:
    variants = pressure.get("variants") if isinstance(pressure.get("variants"), list) else []
    for row in variants:
        if isinstance(row, dict) and row.get("variant") == name:
            return row
    return {}


def _round(value: float | int | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def build_contract(
    *,
    input_path: Path = EXCHANGE_LATEST,
    lookback: int = 20,
    forward_window: int = 10,
    expansion_multiple: float = 1.5,
    close_location_threshold: float = 0.8,
    controls_per_event: int = 20,
    min_events: int = 8,
) -> dict[str, Any]:
    pressure = _read_json(PRESSURE_LATEST)
    gate = _read_json(GATE_LATEST)
    pressure_result = pressure.get("result") if isinstance(pressure.get("result"), dict) else {}
    strict_pressure = _variant_by_name(pressure, "strict_close")
    strict_payload = build_closed_daily_event_null(
        input_path=input_path,
        lookback=lookback,
        forward_window=forward_window,
        expansion_multiple=expansion_multiple,
        close_location_threshold=close_location_threshold,
        controls_per_event=controls_per_event,
        min_events=min_events,
    )
    metrics = strict_payload.get("metrics") if isinstance(strict_payload.get("metrics"), dict) else {}
    events = int(metrics.get("events") or 0)
    null_rows = int(metrics.get("null_rows") or 0)
    p_proxy = metrics.get("matched_null_p_proxy")
    edge = metrics.get("edge_vs_matched_null_pct")
    pressure_selects_strict = pressure_result.get("best_variant") == "strict_close"
    denominator_ready = events >= min_events and null_rows >= events * controls_per_event
    null_readable = p_proxy is not None and null_rows > 0
    paper_decision_admissible = bool(pressure_selects_strict and denominator_ready and null_readable)
    policy_mutation_allowed = False

    checks = [
        {
            "check": "pressure_selected_strict_close",
            "passed": pressure_selects_strict,
            "evidence": f"best_variant={pressure_result.get('best_variant')}",
        },
        {
            "check": "forward_10_denominator_ready",
            "passed": denominator_ready,
            "evidence": f"events={events}; null_rows={null_rows}; min_events={min_events}; controls_per_event={controls_per_event}",
        },
        {
            "check": "matched_date_null_readable",
            "passed": null_readable,
            "evidence": f"p_proxy={p_proxy}; edge={edge}",
        },
        {
            "check": "paper_decision_admissible",
            "passed": paper_decision_admissible,
            "evidence": "strict_close can be re-tested as a paper contract; no policy mutation is authorized.",
        },
    ]
    decision = "test" if paper_decision_admissible else "watch"
    verdict = "STRICT_CLOSE_PREDECLARED_PAPER_CONTRACT" if paper_decision_admissible else "STRICT_CLOSE_CONTRACT_NOT_READY"
    next_test = (
        "Run the next closed-daily cycle with strict_close predeclared; compare its paper outcome against matched-date null and ledger before any mutation."
        if paper_decision_admissible
        else "Keep pressure testing until strict_close has readable denominator and null evidence."
    )

    return {
        "schema": "dndlab.bitcoin.closed_daily_strict_close_contract.v1",
        "generated_at": _utc_now(),
        "domain": DOMAIN,
        "version": VERSION,
        "intent": "Predeclare strict_close as the next paper-test contract after closed-daily event/null pressure selected it as the best axis.",
        "input_artifacts": {
            "exchange_ohlcv": str(input_path),
            "daily_closed_evidence_gate": str(GATE_LATEST),
            "closed_daily_event_null_pressure": str(PRESSURE_LATEST),
            "event_null_builder": "domains/bitcoin-regime-lab/tools/btc_closed_daily_event_null.py",
        },
        "predeclared_contract": {
            "contract_id": "closed_daily_range_expansion_directional_close.strict_close.v1",
            "event_family": "closed_daily_range_expansion_directional_close",
            "variant": "strict_close",
            "lookback_days": lookback,
            "forward_window_days": forward_window,
            "range_expansion_multiple": expansion_multiple,
            "close_location_threshold": close_location_threshold,
            "controls_per_event": controls_per_event,
            "min_events": min_events,
            "price_source": "median OHLC across available exchange-native daily feeds",
            "null_family": "deterministic_matched_date_directional_null",
            "predeclared": True,
        },
        "data_card": {
            "events": events,
            "null_rows": null_rows,
            "event_median_directional_return_pct": metrics.get("event_median_directional_return_pct"),
            "null_median_directional_return_pct": metrics.get("null_median_directional_return_pct"),
            "edge_vs_matched_null_pct": edge,
            "matched_null_p_proxy": p_proxy,
            "best_pressure_edge_vs_matched_null_pct": strict_pressure.get("edge_vs_matched_null_pct"),
            "forward_denominator_admissible": denominator_ready,
            "matched_null_admissible": null_readable,
            "paper_decision_admissible": paper_decision_admissible,
            "policy_mutation_allowed": policy_mutation_allowed,
        },
        "checks": checks,
        "decision": decision,
        "verdict": verdict,
        "next_test": next_test,
        "summary": {
            "observe": 0,
            "watch": 0 if decision == "test" else 1,
            "test": 1 if decision == "test" else 0,
            "reject": 0,
            "redesign": 0,
            "events": events,
            "null_rows": null_rows,
            "paper_decision_admissible": paper_decision_admissible,
            "policy_mutation_allowed": policy_mutation_allowed,
            "trading_signal": False,
        },
        "cards": [
            {
                "claim_id": "btc_closed_daily_strict_close_contract",
                "title": "BTC strict-close paper contract",
                "decision": decision,
                "verdict": verdict,
                "evidence": (
                    f"events={events}; null_rows={null_rows}; edge={_round(edge)}; "
                    f"p_proxy={p_proxy}; paper_admissible={paper_decision_admissible}."
                ),
                "next_test": next_test,
                "boundary": "Predeclared paper contract only: no entries, exits, price targets, advice, real orders or method-policy mutation.",
            }
        ],
        "boundary": {
            "public_claim": False,
            "trading_signal": False,
            "operational": False,
            "advice": False,
            "price_target": False,
            "entry_exit": False,
            "real_order_execution": False,
        },
        "gate_readback": gate.get("gate") if isinstance(gate.get("gate"), dict) else {},
    }


def write_artifact(payload: dict[str, Any]) -> dict[str, str]:
    return write_json_artifact(
        payload=payload,
        value_dir=VALUE_DIR,
        data_dir=DATA_DIR,
        repo_root=REPO_ROOT,
        tool_path=Path(__file__),
        artifact_prefix="btc_closed_daily_strict_close_contract",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Predeclare BTC strict-close paper contract.")
    parser.add_argument("--input", default=str(EXCHANGE_LATEST))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = build_contract(input_path=Path(args.input))
    if args.write:
        payload["files"] = write_artifact(payload)
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"status": "OK", "files": payload.get("files"), "summary": payload["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
