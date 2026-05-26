#!/usr/bin/env python3
"""Strict-close paper ledger for the BTC closed-daily contract.

This tool consumes the predeclared strict-close contract and builds a paper
decision ledger from closed daily event/null rows. It is intentionally not wired
into refresh yet: run it after the night-run smoke confirms fresh closed-data
cycles. It does not fetch data, mutate policy, execute orders or publish advice.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
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
STRICT_CONTRACT_LATEST = VALUE_DIR / "btc_closed_daily_strict_close_contract_latest.json"
GATE_LATEST = VALUE_DIR / "btc_daily_closed_evidence_gate_latest.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
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
    return round(count / total, 4) if total else None


def _contract_params(contract: dict[str, Any]) -> dict[str, Any]:
    spec = contract.get("predeclared_contract") if isinstance(contract.get("predeclared_contract"), dict) else {}
    return {
        "lookback": int(spec.get("lookback_days") or 20),
        "forward_window": int(spec.get("forward_window_days") or 10),
        "expansion_multiple": float(spec.get("range_expansion_multiple") or 1.5),
        "close_location_threshold": float(spec.get("close_location_threshold") or 0.8),
        "controls_per_event": int(spec.get("controls_per_event") or 20),
        "min_events": int(spec.get("min_events") or 8),
    }


def _null_groups(null_rows: list[dict[str, Any]], round_trip_cost_pct: float) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[float]] = {}
    for row in null_rows:
        event_id = str(row.get("matched_event_id") or "")
        value = row.get("directional_forward_return_pct")
        if not event_id or value is None:
            continue
        grouped.setdefault(event_id, []).append(float(value) - round_trip_cost_pct)
    return {
        event_id: {
            "rows": len(values),
            "median_net_directional_return_pct": _round(_median(values)),
            "positive_rate": _pct(sum(1 for value in values if value > 0.0), len(values)),
            "p_proxy": None,
            "values": values,
        }
        for event_id, values in grouped.items()
    }


def _ledger_row(
    event: dict[str, Any],
    null_group: dict[str, Any],
    *,
    round_trip_cost_pct: float,
) -> dict[str, Any]:
    gross = _round(event.get("directional_forward_return_pct"))
    net = _round(float(gross) - round_trip_cost_pct) if gross is not None else None
    null_median = null_group.get("median_net_directional_return_pct")
    null_values = null_group.get("values") if isinstance(null_group.get("values"), list) else []
    p_proxy = None
    if net is not None and null_values:
        p_proxy = _round(sum(1 for value in null_values if value >= net) / len(null_values))
    edge_vs_null = _round(net - float(null_median)) if net is not None and null_median is not None else None
    direction = str(event.get("direction") or "")
    decision = "paper_long" if direction == "bullish" else "paper_short" if direction == "bearish" else "paper_watch"

    if net is None:
        outcome = "not_evaluable"
        verdict = "WATCH_NO_FORWARD_RESULT"
    elif net > 0.0 and edge_vs_null is not None and edge_vs_null > 0.0 and p_proxy is not None and p_proxy <= 0.4:
        outcome = "above_null_after_cost"
        verdict = "PAPER_EVENT_BEATS_MATCHED_NULL"
    elif net > 0.0:
        outcome = "positive_but_not_null_separated"
        verdict = "PAPER_EVENT_POSITIVE_AMBIGUOUS"
    else:
        outcome = "below_cost_or_negative"
        verdict = "PAPER_EVENT_NOT_BEATEN"

    return {
        "event_id": event.get("event_id"),
        "event_date": event.get("event_date"),
        "future_date": event.get("future_date"),
        "direction": direction,
        "paper_decision": decision,
        "entry_basis": "event_close_after_closed_daily_strict_close_event",
        "exit_basis": "forward_window_close",
        "invalidation_basis": "predeclared forward window; no intraday stop in v0",
        "event_close": event.get("event_close"),
        "future_close": event.get("future_close"),
        "gross_directional_return_pct": gross,
        "round_trip_cost_pct": _round(round_trip_cost_pct),
        "net_directional_return_pct": net,
        "matched_null_rows": null_group.get("rows", 0),
        "matched_null_median_net_return_pct": null_median,
        "edge_vs_matched_null_pct": edge_vs_null,
        "matched_null_p_proxy": p_proxy,
        "outcome": outcome,
        "verdict": verdict,
        "advice": False,
        "real_order_execution": False,
    }


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    nets = [float(row["net_directional_return_pct"]) for row in rows if row.get("net_directional_return_pct") is not None]
    edges = [float(row["edge_vs_matched_null_pct"]) for row in rows if row.get("edge_vs_matched_null_pct") is not None]
    beaten = [row for row in rows if row.get("verdict") == "PAPER_EVENT_BEATS_MATCHED_NULL"]
    positive = [row for row in rows if row.get("net_directional_return_pct") is not None and float(row["net_directional_return_pct"]) > 0.0]
    long_rows = [row for row in rows if row.get("paper_decision") == "paper_long"]
    short_rows = [row for row in rows if row.get("paper_decision") == "paper_short"]
    best = max(rows, key=lambda row: row.get("net_directional_return_pct") if row.get("net_directional_return_pct") is not None else -9999, default=None)
    worst = min(rows, key=lambda row: row.get("net_directional_return_pct") if row.get("net_directional_return_pct") is not None else 9999, default=None)
    return {
        "rows": len(rows),
        "paper_long": len(long_rows),
        "paper_short": len(short_rows),
        "positive_after_cost": len(positive),
        "beats_matched_null": len(beaten),
        "hit_rate_after_cost": _pct(len(positive), len(rows)),
        "null_beat_rate": _pct(len(beaten), len(rows)),
        "median_net_directional_return_pct": _round(_median(nets)),
        "mean_net_directional_return_pct": _round(_mean(nets)),
        "median_edge_vs_matched_null_pct": _round(_median(edges)),
        "best_event": {
            "event_date": best.get("event_date"),
            "direction": best.get("direction"),
            "net_directional_return_pct": best.get("net_directional_return_pct"),
            "edge_vs_matched_null_pct": best.get("edge_vs_matched_null_pct"),
        } if best else None,
        "worst_event": {
            "event_date": worst.get("event_date"),
            "direction": worst.get("direction"),
            "net_directional_return_pct": worst.get("net_directional_return_pct"),
            "edge_vs_matched_null_pct": worst.get("edge_vs_matched_null_pct"),
        } if worst else None,
    }


def build_ledger(
    *,
    input_path: Path = EXCHANGE_LATEST,
    contract_path: Path = STRICT_CONTRACT_LATEST,
    round_trip_cost_pct: float = 0.10,
) -> dict[str, Any]:
    contract = _read_json(contract_path)
    gate = _read_json(GATE_LATEST)
    data_card = contract.get("data_card") if isinstance(contract.get("data_card"), dict) else {}
    params = _contract_params(contract)
    source = build_closed_daily_event_null(
        input_path=input_path,
        lookback=params["lookback"],
        forward_window=params["forward_window"],
        expansion_multiple=params["expansion_multiple"],
        close_location_threshold=params["close_location_threshold"],
        controls_per_event=params["controls_per_event"],
        min_events=params["min_events"],
    )
    events = source.get("events") if isinstance(source.get("events"), list) else []
    null_rows = source.get("matched_null_rows") if isinstance(source.get("matched_null_rows"), list) else []
    null_groups = _null_groups(null_rows, round_trip_cost_pct)
    rows = [
        _ledger_row(
            event,
            null_groups.get(str(event.get("event_id") or ""), {}),
            round_trip_cost_pct=round_trip_cost_pct,
        )
        for event in events
    ]
    metrics = _aggregate(rows)
    contract_ready = bool(data_card.get("paper_decision_admissible") is True)
    if not contract_ready:
        decision = "watch"
        verdict = "STRICT_CLOSE_LEDGER_CONTRACT_NOT_ADMISSIBLE"
    elif metrics["rows"] < params["min_events"]:
        decision = "observe"
        verdict = "STRICT_CLOSE_LEDGER_DENOMINATOR_LOW"
    elif (metrics.get("median_edge_vs_matched_null_pct") or 0.0) > 0 and (metrics.get("null_beat_rate") or 0.0) >= 0.5:
        decision = "test"
        verdict = "STRICT_CLOSE_PAPER_LEDGER_POSITIVE"
    elif (metrics.get("median_net_directional_return_pct") or 0.0) > 0:
        decision = "watch"
        verdict = "STRICT_CLOSE_PAPER_LEDGER_POSITIVE_AMBIGUOUS"
    else:
        decision = "redesign"
        verdict = "STRICT_CLOSE_PAPER_LEDGER_NOT_BEATEN"

    return {
        "schema": "dndlab.bitcoin.strict_close_paper_ledger.v1",
        "generated_at": _utc_now(),
        "domain": DOMAIN,
        "version": VERSION,
        "intent": "Turn the predeclared strict_close closed-daily contract into a paper decision ledger before any method-policy mutation.",
        "input_artifacts": {
            "exchange_ohlcv": str(input_path),
            "strict_close_contract": str(contract_path),
            "daily_closed_evidence_gate": str(GATE_LATEST),
            "event_null_builder": "domains/bitcoin-regime-lab/tools/btc_closed_daily_event_null.py",
        },
        "paper_contract": {
            "contract_id": (contract.get("predeclared_contract") or {}).get("contract_id"),
            "variant": "strict_close",
            "entry_basis": "event close after a fully closed daily strict-close event",
            "exit_basis": f"{params['forward_window']}-closed-daily-candle forward close",
            "cost_model": {
                "round_trip_cost_pct": _round(round_trip_cost_pct),
                "includes": ["fees", "slippage_proxy"],
                "real_execution": False,
            },
            "control": "deterministic matched-date directional null after the same round-trip cost",
            "policy_mutation_allowed": False,
            "pre_activation_state": "prepared_not_wired_to_refresh",
        },
        "gate_readback": gate.get("gate") if isinstance(gate.get("gate"), dict) else {},
        "source_metrics": source.get("metrics") if isinstance(source.get("metrics"), dict) else {},
        "metrics": metrics,
        "decision": decision,
        "verdict": verdict,
        "summary": {
            "observe": 1 if decision == "observe" else 0,
            "watch": 1 if decision == "watch" else 0,
            "test": 1 if decision == "test" else 0,
            "reject": 0,
            "redesign": 1 if decision == "redesign" else 0,
            "trading_signal": False,
            "policy_mutation_allowed": False,
        },
        "cards": [
            {
                "claim_id": "btc_strict_close_paper_ledger",
                "title": "BTC strict-close paper ledger",
                "decision": decision,
                "verdict": verdict,
                "evidence": (
                    f"{metrics['rows']} paper rows; median net {metrics.get('median_net_directional_return_pct')}%; "
                    f"median edge vs matched null {metrics.get('median_edge_vs_matched_null_pct')}%; "
                    f"hit-rate {metrics.get('hit_rate_after_cost')}; null-beat-rate {metrics.get('null_beat_rate')}."
                ),
                "next_test": "After the night-run smoke passes, wire this ledger into refresh/health only if strict_close remains paper-admissible.",
                "boundary": "Paper ledger only: simulated decisions, no advice, no public signal, no real orders and no method-policy mutation.",
            }
        ],
        "rows": rows,
        "boundary": {
            "public_claim": False,
            "trading_signal": False,
            "operational": False,
            "advice": False,
            "price_target": False,
            "entry_exit_public": False,
            "real_order_execution": False,
            "method_policy_mutation": False,
        },
    }


def write_artifact(payload: dict[str, Any]) -> dict[str, str]:
    return write_json_artifact(
        payload=payload,
        value_dir=VALUE_DIR,
        data_dir=DATA_DIR,
        repo_root=REPO_ROOT,
        tool_path=Path(__file__),
        artifact_prefix="btc_strict_close_paper_ledger",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build BTC strict-close paper ledger.")
    parser.add_argument("--input", default=str(EXCHANGE_LATEST))
    parser.add_argument("--contract", default=str(STRICT_CONTRACT_LATEST))
    parser.add_argument("--round-trip-cost-pct", type=float, default=0.10)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = build_ledger(
        input_path=Path(args.input),
        contract_path=Path(args.contract),
        round_trip_cost_pct=args.round_trip_cost_pct,
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
