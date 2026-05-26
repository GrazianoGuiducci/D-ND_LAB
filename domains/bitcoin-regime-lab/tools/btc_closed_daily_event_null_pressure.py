#!/usr/bin/env python3
"""Pressure-test the closed-daily BTC event/null family."""
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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _round(value: float | int | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _variant_row(name: str, axis: str, **kwargs: Any) -> dict[str, Any]:
    payload = build_closed_daily_event_null(**kwargs)
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    return {
        "variant": name,
        "axis": axis,
        "decision": payload.get("decision"),
        "verdict": payload.get("verdict"),
        "next_test": payload.get("next_test"),
        "lookback": kwargs.get("lookback"),
        "forward_window": kwargs.get("forward_window"),
        "expansion_multiple": kwargs.get("expansion_multiple"),
        "close_location_threshold": kwargs.get("close_location_threshold"),
        "controls_per_event": kwargs.get("controls_per_event"),
        "events": metrics.get("events"),
        "null_rows": metrics.get("null_rows"),
        "event_median_directional_return_pct": metrics.get("event_median_directional_return_pct"),
        "null_median_directional_return_pct": metrics.get("null_median_directional_return_pct"),
        "edge_vs_matched_null_pct": metrics.get("edge_vs_matched_null_pct"),
        "event_positive_rate": metrics.get("event_positive_rate"),
        "null_positive_rate": metrics.get("null_positive_rate"),
        "matched_null_p_proxy": metrics.get("matched_null_p_proxy"),
    }


def build_pressure(
    *,
    input_path: Path = EXCHANGE_LATEST,
    lookback: int = 20,
    forward_window: int = 10,
    expansion_multiple: float = 1.5,
    close_location_threshold: float = 0.7,
    controls_per_event: int = 20,
    min_events: int = 8,
) -> dict[str, Any]:
    base = {
        "input_path": input_path,
        "lookback": lookback,
        "forward_window": forward_window,
        "expansion_multiple": expansion_multiple,
        "close_location_threshold": close_location_threshold,
        "controls_per_event": controls_per_event,
        "min_events": min_events,
    }
    specs = [
        ("baseline", "baseline", {}),
        ("forward_5", "forward_denominator", {"forward_window": 5}),
        ("forward_15", "forward_denominator", {"forward_window": 15}),
        ("forward_20", "forward_denominator", {"forward_window": 20}),
        ("null_10", "matched_null_density", {"controls_per_event": 10}),
        ("null_50", "matched_null_density", {"controls_per_event": 50}),
        ("loose_event", "event_threshold", {"expansion_multiple": 1.25}),
        ("strict_event", "event_threshold", {"expansion_multiple": 2.0}),
        ("strict_close", "event_threshold", {"close_location_threshold": 0.8}),
    ]
    variants = [
        _variant_row(name, axis, **{**base, **overrides})
        for name, axis, overrides in specs
    ]
    ready = [row for row in variants if int(row.get("events") or 0) >= min_events]
    positive = [
        row for row in ready
        if (row.get("edge_vs_matched_null_pct") is not None and float(row["edge_vs_matched_null_pct"]) > 0.0)
        and (row.get("matched_null_p_proxy") is not None and float(row["matched_null_p_proxy"]) <= 0.2)
    ]
    negative_or_neutral = [
        row for row in ready
        if row.get("edge_vs_matched_null_pct") is not None
        and float(row["edge_vs_matched_null_pct"]) <= 0.0
    ]
    best = max(
        ready,
        key=lambda row: float(row.get("edge_vs_matched_null_pct") if row.get("edge_vs_matched_null_pct") is not None else -9999),
        default=None,
    )
    if len(ready) < 4:
        decision = "observe"
        verdict = "CLOSED_DAILY_EVENT_NULL_PRESSURE_DENOMINATOR_LOW"
        next_test = "Do not decide this event/null family until enough variants have minimum event denominator."
    elif positive:
        decision = "test"
        verdict = "CLOSED_DAILY_EVENT_NULL_PRESSURE_POSITIVE_VARIANT"
        next_test = "Promote only the positive variant to paper-ledger simulation after closed-daily refresh."
    elif len(negative_or_neutral) == len(ready):
        decision = "redesign"
        verdict = "CLOSED_DAILY_EVENT_NULL_PRESSURE_NULL_NOT_BEATEN"
        next_test = "Matched-date null and tested denominators are strong enough to reject this family for now; choose another event source or null family."
    else:
        decision = "watch"
        verdict = "CLOSED_DAILY_EVENT_NULL_PRESSURE_MIXED"
        next_test = "Keep the family as watch and retest the unstable axis on the next closed-data refresh."

    result = {
        "decision": decision,
        "verdict": verdict,
        "ready_variants": [row["variant"] for row in ready],
        "positive_variants": [row["variant"] for row in positive],
        "best_variant": best.get("variant") if best else None,
        "best_axis": best.get("axis") if best else None,
        "best_edge_vs_matched_null_pct": best.get("edge_vs_matched_null_pct") if best else None,
        "forward_10_admissible": any(row["variant"] == "baseline" and row in ready for row in ready),
        "next_test": next_test,
    }
    return {
        "schema": "dndlab.bitcoin.closed_daily_event_null_pressure.v1",
        "generated_at": _utc_now(),
        "domain": DOMAIN,
        "version": VERSION,
        "intent": "Test whether matched-date directional null and forward-window denominator can decide the closed-daily range-expansion event family.",
        "input_artifacts": {
            "exchange_ohlcv": str(input_path),
            "event_null_builder": "domains/bitcoin-regime-lab/tools/btc_closed_daily_event_null.py",
        },
        "baseline_contract": {
            "event_family": "closed_daily_range_expansion_directional_close",
            "lookback_days": lookback,
            "forward_window_days": forward_window,
            "expansion_multiple": expansion_multiple,
            "close_location_threshold": close_location_threshold,
            "controls_per_event": controls_per_event,
            "min_events": min_events,
        },
        "variants": variants,
        "result": result,
        "decision": decision,
        "verdict": verdict,
        "next_test": next_test,
        "summary": {
            "observe": 1 if decision == "observe" else 0,
            "watch": 1 if decision == "watch" else 0,
            "test": 1 if decision == "test" else 0,
            "reject": 0,
            "redesign": 1 if decision == "redesign" else 0,
            "variants_checked": len(variants),
            "ready_variants": len(ready),
            "positive_variants": len(positive),
            "trading_signal": False,
        },
        "cards": [
            {
                "claim_id": "btc_closed_daily_event_null_pressure",
                "title": "BTC closed-daily event/null pressure",
                "decision": decision,
                "verdict": verdict,
                "evidence": (
                    f"{len(ready)}/{len(variants)} variants ready; "
                    f"positive={len(positive)}; best={result['best_variant']} "
                    f"edge={_round(result['best_edge_vs_matched_null_pct'])}."
                ),
                "next_test": next_test,
                "boundary": "Pressure artifact only: denominator/null admissibility for paper research, no advice, entries, exits, targets or real orders.",
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
    }


def write_artifact(payload: dict[str, Any]) -> dict[str, str]:
    return write_json_artifact(
        payload=payload,
        value_dir=VALUE_DIR,
        data_dir=DATA_DIR,
        repo_root=REPO_ROOT,
        tool_path=Path(__file__),
        artifact_prefix="btc_closed_daily_event_null_pressure",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Pressure-test BTC closed-daily event/null family.")
    parser.add_argument("--input", default=str(EXCHANGE_LATEST))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = build_pressure(input_path=Path(args.input))
    if args.write:
        payload["files"] = write_artifact(payload)
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"status": "OK", "files": payload.get("files"), "summary": payload["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
