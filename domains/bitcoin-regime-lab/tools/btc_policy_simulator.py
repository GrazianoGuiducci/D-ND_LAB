#!/usr/bin/env python3
"""btc_policy_simulator.py - BTC Lab policy research simulator.

Manual-only research layer for evaluating declared historical policies against
controls. v0 starts from the existing LVN/Volume Profile proxy substrate and
adds value metrics, walk-forward stability and parameter sensitivity.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from btc_volume_profile_lvn_proxy import build_lvn_proxy


VERSION = "0.1.0"
DOMAIN_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = DOMAIN_DIR.parents[1]
DATA_ROOT = Path(os.environ.get("LAB_DATA_DIR", REPO_ROOT / "data")).resolve()
DATA_DIR = DATA_ROOT / "bitcoin-regime-lab"
VALUE_DIR = DATA_DIR / "value"
EXCHANGE_LATEST = VALUE_DIR / "btc_exchange_ohlcv_latest.json"
LVN_PROXY_LATEST = VALUE_DIR / "btc_volume_profile_lvn_proxy_latest.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing required artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _rate(rows: list[dict[str, Any]], key: str) -> float | None:
    if not rows:
        return None
    return sum(1 for row in rows if row.get(key)) / len(rows)


def _round(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.median(values))


def _stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return float(statistics.pstdev(values))


def _delta(rows: list[dict[str, Any]]) -> float | None:
    policy = _rate(rows, "policy_closed")
    strict = _rate(rows, "strict_control_closed")
    if policy is None or strict is None:
        return None
    return policy - strict


def _policy_events(proxy: dict[str, Any], *, exclude_latest_event: bool) -> list[dict[str, Any]]:
    raw_events = list(proxy.get("events") or [])
    if exclude_latest_event and raw_events:
        latest_event_date = max(str(event.get("event_date") or "") for event in raw_events)
        raw_events = [event for event in raw_events if str(event.get("event_date") or "") != latest_event_date]

    rows = []
    for event in raw_events:
        zone = event.get("lvn_zone") or {}
        bars = event.get("lvn_bars_to_close")
        rows.append({
            "event_date": event.get("event_date"),
            "event_close": event.get("event_close"),
            "relation": zone.get("relation"),
            "distance_pct": zone.get("distance_pct"),
            "policy_closed": bool(event.get("lvn_closed")),
            "bars_to_close": bars if isinstance(bars, int) else None,
            "adjacent_control_closed": bool(event.get("adjacent_control_closed")),
            "opposite_control_closed": bool(event.get("opposite_control_closed")),
            "shuffled_volume_control_closed": bool(event.get("shuffled_volume_control_closed")),
            "strict_control_closed": bool(event.get("strict_control_closed")),
        })
    return rows


def _split_walk_forward(events: list[dict[str, Any]], folds: int = 3) -> list[dict[str, Any]]:
    if not events:
        return []
    fold_size = max(1, len(events) // folds)
    out = []
    for index in range(folds):
        start = index * fold_size
        end = len(events) if index == folds - 1 else (index + 1) * fold_size
        subset = events[start:end]
        if not subset:
            continue
        policy_rate = _rate(subset, "policy_closed")
        strict_rate = _rate(subset, "strict_control_closed")
        delta = _delta(subset)
        out.append({
            "fold": index + 1,
            "events": len(subset),
            "first_event": subset[0].get("event_date"),
            "last_event": subset[-1].get("event_date"),
            "policy_closure_rate": _round(policy_rate),
            "strict_control_rate": _round(strict_rate),
            "delta_vs_strict_control": _round(delta),
        })
    return out


def _relation_slices(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for relation in sorted({str(e.get("relation")) for e in events if e.get("relation")}):
        subset = [e for e in events if e.get("relation") == relation]
        closed_bars = [float(e["bars_to_close"]) for e in subset if e.get("bars_to_close") is not None]
        out.append({
            "relation": relation,
            "events": len(subset),
            "policy_closure_rate": _round(_rate(subset, "policy_closed")),
            "strict_control_rate": _round(_rate(subset, "strict_control_closed")),
            "delta_vs_strict_control": _round(_delta(subset)),
            "median_bars_to_close": _round(_median(closed_bars), 2),
        })
    return out


def _sensitivity_grid(input_path: Path, *, exclude_latest_event: bool) -> list[dict[str, Any]]:
    rows = []
    for window_days in (30, 45, 60):
        for bins in (24, 36, 48):
            for forward_window in (5, 10, 15):
                proxy = build_lvn_proxy(
                    input_path=input_path,
                    bins=bins,
                    window_days=window_days,
                    forward_window=forward_window,
                    stride=3,
                    closure_rule="close",
                )
                events = _policy_events(proxy, exclude_latest_event=exclude_latest_event)
                rows.append({
                    "window_days": window_days,
                    "bins": bins,
                    "forward_window": forward_window,
                    "events": len(events),
                    "policy_closure_rate": _round(_rate(events, "policy_closed")),
                    "strict_control_rate": _round(_rate(events, "strict_control_closed")),
                    "delta_vs_strict_control": _round(_delta(events)),
                })
    return rows


def _score(
    *,
    event_count: int,
    delta_vs_strict: float | None,
    fold_deltas: list[float],
    sensitivity_deltas: list[float],
    open_candle_exclusion: bool,
) -> dict[str, Any]:
    denominator_score = min(event_count / 30.0, 1.0)
    discrimination_score = min(abs(delta_vs_strict or 0.0) / 0.25, 1.0)
    fold_std = _stdev(fold_deltas)
    stability_score = max(0.0, 1.0 - min(fold_std / 0.35, 1.0))
    sensitivity_range = (max(sensitivity_deltas) - min(sensitivity_deltas)) if sensitivity_deltas else 1.0
    sensitivity_score = max(0.0, 1.0 - min(sensitivity_range / 0.75, 1.0))
    open_candle_score = 1.0 if open_candle_exclusion else 0.0
    score = (
        0.25 * denominator_score
        + 0.25 * discrimination_score
        + 0.20 * stability_score
        + 0.20 * sensitivity_score
        + 0.10 * open_candle_score
    )
    if score >= 0.70:
        classification = "research_useful"
    elif score >= 0.45:
        classification = "research_watch"
    else:
        classification = "weak_research_value"
    return {
        "lab_value_score": round(score, 4),
        "classification": classification,
        "components": {
            "denominator_score": round(denominator_score, 4),
            "control_discrimination_score": round(discrimination_score, 4),
            "walk_forward_stability_score": round(stability_score, 4),
            "parameter_sensitivity_score": round(sensitivity_score, 4),
            "open_candle_exclusion_score": round(open_candle_score, 4),
        },
    }


def build_policy_simulator(
    *,
    input_path: Path = EXCHANGE_LATEST,
    bins: int = 36,
    window_days: int = 45,
    forward_window: int = 10,
    stride: int = 3,
    closure_rule: str = "close",
    exclude_latest_event: bool = True,
) -> dict[str, Any]:
    exchange = _read_json(input_path)
    latest_common_date = (((exchange.get("metrics") or {}).get("latest_common_date")) or None)
    base_proxy = build_lvn_proxy(
        input_path=input_path,
        bins=bins,
        window_days=window_days,
        forward_window=forward_window,
        stride=stride,
        closure_rule=closure_rule,
    )
    previous_lvn_proxy = _read_json(LVN_PROXY_LATEST) if LVN_PROXY_LATEST.exists() else {}
    events = _policy_events(base_proxy, exclude_latest_event=exclude_latest_event)
    policy_rate = _rate(events, "policy_closed")
    strict_rate = _rate(events, "strict_control_closed")
    adjacent_rate = _rate(events, "adjacent_control_closed")
    opposite_rate = _rate(events, "opposite_control_closed")
    shuffled_rate = _rate(events, "shuffled_volume_control_closed")
    delta_vs_strict = _delta(events)
    closed_bars = [float(e["bars_to_close"]) for e in events if e.get("bars_to_close") is not None]
    walk_forward = _split_walk_forward(events)
    fold_deltas = [float(row["delta_vs_strict_control"]) for row in walk_forward if row.get("delta_vs_strict_control") is not None]
    sensitivity = _sensitivity_grid(input_path, exclude_latest_event=exclude_latest_event)
    sensitivity_deltas = [float(row["delta_vs_strict_control"]) for row in sensitivity if row.get("delta_vs_strict_control") is not None]
    score = _score(
        event_count=len(events),
        delta_vs_strict=delta_vs_strict,
        fold_deltas=fold_deltas,
        sensitivity_deltas=sensitivity_deltas,
        open_candle_exclusion=exclude_latest_event,
    )

    value_direction = "neutral"
    if delta_vs_strict is not None and delta_vs_strict > 0.05:
        value_direction = "positive_vs_strict_control"
    elif delta_vs_strict is not None and delta_vs_strict < -0.05:
        value_direction = "negative_vs_strict_control"

    if len(events) < 12:
        decision = "observe"
        verdict = "POLICY_SIMULATOR_DENOMINATOR_LOW"
    elif score["classification"] == "research_useful":
        decision = "test"
        if value_direction == "positive_vs_strict_control":
            verdict = "POLICY_SIMULATOR_RESEARCH_VALUE_HIGH_POSITIVE_EDGE"
        elif value_direction == "negative_vs_strict_control":
            verdict = "POLICY_SIMULATOR_RESEARCH_VALUE_HIGH_NEGATIVE_EDGE"
        else:
            verdict = "POLICY_SIMULATOR_RESEARCH_VALUE_HIGH_NEUTRAL"
    elif score["classification"] == "research_watch":
        decision = "watch"
        verdict = "POLICY_SIMULATOR_RESEARCH_VALUE_WATCH"
    else:
        decision = "reject"
        verdict = "POLICY_SIMULATOR_RESEARCH_VALUE_WEAK"

    primary_contract = {
        "policy_id": "btc_policy_simulator_v0.lvn_close_policy",
        "method_id": "volume_profile_lvn_void",
        "policy_family": "zone_closure_research",
        "data_window": {
            "source": str(input_path),
            "latest_common_date": latest_common_date,
            "open_candle_exclusion": exclude_latest_event,
        },
        "event_builder": {
            "profile_type": "system_generated_daily_ohlcv_volume_profile_proxy",
            "profile_window_days": window_days,
            "bins": bins,
            "stride": stride,
            "nearest_zone": "nearest LVN bin to event close",
        },
        "activation_rule": "event close has a nearest LVN zone built from prior profile window",
        "closure_rule": f"future daily {closure_rule} enters LVN zone within forward window",
        "forward_window_days": forward_window,
        "invalidation_rule": "not defined in v0; measured as unclosed inside forward window",
        "cost_model": "not applied; closure policy is not a position-return model",
        "slippage_model": "not applied; closure policy is not a position-return model",
        "controls": [
            "adjacent equal-width zone",
            "opposite-distance zone",
            "shuffled-volume LVN proxy",
            "strict union of all controls",
        ],
        "no_lookahead": True,
    }

    return {
        "schema": "dndlab.bitcoin.policy_simulator.v1",
        "generated_at": _utc_now(),
        "domain": "bitcoin-regime-lab",
        "version": VERSION,
        "input_artifacts": {
            "exchange_ohlcv": str(input_path),
            "volume_profile_lvn_proxy_latest": str(LVN_PROXY_LATEST),
        },
        "research_frame": {
            "instrument": "BTC Lab policy research simulator",
            "purpose": "measure whether a declared method policy produces research value against controls and parameter perturbations",
            "not_primary_metric": "PnL alone",
        },
        "policy_contract": primary_contract,
        "summary": {
            "observe": 1 if decision == "observe" else 0,
            "watch": 1 if decision == "watch" else 0,
            "test": 1 if decision == "test" else 0,
            "reject": 1 if decision == "reject" else 0,
        },
        "card": {
            "claim_id": "btc_policy_simulator_lvn_close_policy",
            "title": "BTC LVN policy simulator v0",
            "decision": decision,
            "verdict": verdict,
            "evidence": (
                f"{len(events)} closed-data events; policy closure {_round(policy_rate)}; "
                f"strict control {_round(strict_rate)}; delta {_round(delta_vs_strict)}; "
                f"lab value score {score['lab_value_score']}."
            ),
            "interpretation": "Negative or positive separation from controls is useful when stable: it tells the Lab whether the method carries structure or should be redesigned.",
        },
        "metrics": {
            "event_count": len(events),
            "value_direction": value_direction,
            "policy_closure_rate": _round(policy_rate),
            "adjacent_control_rate": _round(adjacent_rate),
            "opposite_control_rate": _round(opposite_rate),
            "shuffled_volume_control_rate": _round(shuffled_rate),
            "strict_control_rate": _round(strict_rate),
            "delta_vs_strict_control": _round(delta_vs_strict),
            "median_bars_to_close": _round(_median(closed_bars), 2),
            "mean_bars_to_close": _round(_mean(closed_bars), 2),
            "open_candle_exclusion_passed": exclude_latest_event,
            "latest_common_date": latest_common_date,
        },
        "lab_value": score,
        "walk_forward": walk_forward,
        "relation_slices": _relation_slices(events),
        "parameter_sensitivity": {
            "grid": sensitivity,
            "median_delta_vs_strict": _round(_median(sensitivity_deltas)),
            "min_delta_vs_strict": _round(min(sensitivity_deltas), 4) if sensitivity_deltas else None,
            "max_delta_vs_strict": _round(max(sensitivity_deltas), 4) if sensitivity_deltas else None,
            "positive_delta_runs": sum(1 for value in sensitivity_deltas if value > 0),
            "runs": len(sensitivity_deltas),
        },
        "prior_proxy_comparison": {
            "schema": previous_lvn_proxy.get("schema"),
            "generated_at": previous_lvn_proxy.get("generated_at"),
            "decision": ((previous_lvn_proxy.get("cards") or [{}])[0] or {}).get("decision"),
            "verdict": ((previous_lvn_proxy.get("cards") or [{}])[0] or {}).get("verdict"),
            "delta_vs_strict_control": ((previous_lvn_proxy.get("metrics") or {}).get("delta_vs_strict_control")),
        },
        "research_controls": {
            "closed_data_only": True,
            "open_candle_exclusion": exclude_latest_event,
            "no_lookahead": True,
            "simulated_policy_declared": True,
            "historical_result": True,
            "research_metric": True,
        },
        "events": events,
    }


def write_artifact(payload: dict[str, Any]) -> dict[str, str]:
    VALUE_DIR.mkdir(parents=True, exist_ok=True)
    latest = VALUE_DIR / "btc_policy_simulator_latest.json"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stamped = VALUE_DIR / f"btc_policy_simulator_{stamp}.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    latest.write_text(text + "\n", encoding="utf-8")
    stamped.write_text(text + "\n", encoding="utf-8")
    return {"latest": str(latest), "stamped": str(stamped)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build BTC policy simulator research artifact.")
    parser.add_argument("--input", default=str(EXCHANGE_LATEST))
    parser.add_argument("--bins", type=int, default=36)
    parser.add_argument("--window-days", type=int, default=45)
    parser.add_argument("--forward-window", type=int, default=10)
    parser.add_argument("--stride", type=int, default=3)
    parser.add_argument("--closure-rule", choices=["wick", "close"], default="close")
    parser.add_argument("--include-latest-event", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = build_policy_simulator(
        input_path=Path(args.input),
        bins=args.bins,
        window_days=args.window_days,
        forward_window=args.forward_window,
        stride=args.stride,
        closure_rule=args.closure_rule,
        exclude_latest_event=not args.include_latest_event,
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
