#!/usr/bin/env python3
"""btc_policy_simulator.py - BTC Lab policy research simulator.

Manual-only research layer for evaluating declared historical policies against
controls. v0 starts from the existing LVN/Volume Profile proxy substrate and
adds value metrics, walk-forward stability and parameter sensitivity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from btc_volume_profile_lvn_proxy import _median_daily_candles, _zone_closed, build_lvn_proxy


VERSION = "0.1.2"
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


def _delta(rows: list[dict[str, Any]], control_key: str = "strict_control_closed") -> float | None:
    policy = _rate(rows, "policy_closed")
    strict = _rate(rows, control_key)
    if policy is None or strict is None:
        return None
    return policy - strict


def _pct_change(start: float, end: float) -> float | None:
    if start == 0.0:
        return None
    return ((end - start) / start) * 100.0


def _stable_seed(*parts: Any) -> int:
    text = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _matched_random_zones(event: dict[str, Any], *, count: int) -> list[dict[str, float]]:
    zone = event.get("lvn_zone") or {}
    event_close = float(event.get("event_close") or 0.0)
    lower = float(zone.get("lower") or 0.0)
    upper = float(zone.get("upper") or 0.0)
    if event_close <= 0.0 or upper <= lower:
        return []

    width = upper - lower
    midpoint = (lower + upper) / 2.0
    distance = abs(event_close - midpoint) or width
    rng = random.Random(_stable_seed("btc_policy_simulator_v0", event.get("event_date"), event_close, lower, upper))
    zones = []
    for _ in range(count):
        side = -1 if rng.random() < 0.5 else 1
        jitter = rng.uniform(-0.5, 0.5) * width
        random_mid = max(event_close + side * max(width / 2.0, distance + jitter), width / 2.0)
        zones.append({
            "lower": random_mid - width / 2.0,
            "upper": random_mid + width / 2.0,
            "width": width,
        })
    return zones


def _policy_events(
    proxy: dict[str, Any],
    *,
    candles: list[dict[str, Any]],
    forward_window: int,
    closure_rule: str,
    random_controls: int,
    exclude_latest_event: bool,
) -> list[dict[str, Any]]:
    raw_events = list(proxy.get("events") or [])
    if exclude_latest_event and raw_events:
        latest_event_date = max(str(event.get("event_date") or "") for event in raw_events)
        raw_events = [event for event in raw_events if str(event.get("event_date") or "") != latest_event_date]

    candle_index = {str(candle.get("date")): index for index, candle in enumerate(candles)}
    rows = []
    for event in raw_events:
        index = candle_index.get(str(event.get("event_date")))
        future = candles[index + 1:index + 1 + forward_window] if index is not None else []
        matched_zones = _matched_random_zones(event, count=random_controls) if future else []
        matched_fills = [_zone_closed(future, zone, closure_rule) for zone in matched_zones]
        random_matched_rate = (
            sum(1 for fill in matched_fills if fill.get("closed")) / len(matched_fills)
            if matched_fills else None
        )
        zone = event.get("lvn_zone") or {}
        bars = event.get("lvn_bars_to_close")
        event_close = float(event.get("event_close") or 0.0)
        future_close = float(future[-1]["close"]) if future else None
        future_high = max(float(candle["high"]) for candle in future) if future else None
        future_low = min(float(candle["low"]) for candle in future) if future else None
        rows.append({
            "event_date": event.get("event_date"),
            "event_close": event_close,
            "relation": zone.get("relation"),
            "distance_pct": zone.get("distance_pct"),
            "lvn_zone": {
                "lower": zone.get("lower"),
                "upper": zone.get("upper"),
            },
            "policy_closed": bool(event.get("lvn_closed")),
            "bars_to_close": bars if isinstance(bars, int) else None,
            "forward_close": _round(future_close, 2),
            "forward_return_pct": _round(_pct_change(event_close, future_close), 4) if future_close is not None else None,
            "forward_max_up_pct": _round(_pct_change(event_close, future_high), 4) if future_high is not None else None,
            "forward_max_down_pct": _round(_pct_change(event_close, future_low), 4) if future_low is not None else None,
            "adjacent_control_closed": bool(event.get("adjacent_control_closed")),
            "opposite_control_closed": bool(event.get("opposite_control_closed")),
            "shuffled_volume_control_closed": bool(event.get("shuffled_volume_control_closed")),
            "strict_control_closed": bool(event.get("strict_control_closed")),
            "random_matched_control_rate": _round(random_matched_rate),
            "random_matched_control_closed": bool(random_matched_rate is not None and random_matched_rate >= 0.5),
            "random_matched_controls": len(matched_fills),
        })
    return rows


def _rolling_forward_returns(
    candles: list[dict[str, Any]],
    *,
    forward_window: int,
    exclude_latest_event: bool,
) -> list[dict[str, Any]]:
    end = len(candles) - forward_window
    rows = []
    for index in range(0, max(end, 0)):
        if exclude_latest_event and index == end - 1:
            continue
        start_close = float(candles[index]["close"])
        future = candles[index + 1:index + 1 + forward_window]
        if not future:
            continue
        future_close = float(future[-1]["close"])
        future_high = max(float(candle["high"]) for candle in future)
        future_low = min(float(candle["low"]) for candle in future)
        rows.append({
            "event_date": candles[index]["date"],
            "event_close": _round(start_close, 2),
            "forward_close": _round(future_close, 2),
            "forward_return_pct": _round(_pct_change(start_close, future_close), 4),
            "forward_max_up_pct": _round(_pct_change(start_close, future_high), 4),
            "forward_max_down_pct": _round(_pct_change(start_close, future_low), 4),
        })
    return rows


def _normal_chart_comparison(
    candles: list[dict[str, Any]],
    events: list[dict[str, Any]],
    *,
    forward_window: int,
    exclude_latest_event: bool,
) -> dict[str, Any]:
    rolling = _rolling_forward_returns(candles, forward_window=forward_window, exclude_latest_event=exclude_latest_event)
    rolling_returns = [float(row["forward_return_pct"]) for row in rolling if row.get("forward_return_pct") is not None]
    event_returns = [float(row["forward_return_pct"]) for row in events if row.get("forward_return_pct") is not None]
    closed_returns = [float(row["forward_return_pct"]) for row in events if row.get("policy_closed") and row.get("forward_return_pct") is not None]
    unclosed_returns = [float(row["forward_return_pct"]) for row in events if not row.get("policy_closed") and row.get("forward_return_pct") is not None]
    first_close = float(candles[0]["close"]) if candles else None
    last_close = float(candles[-1]["close"]) if candles else None
    return {
        "normal_chart_window": {
            "first_date": candles[0]["date"] if candles else None,
            "last_date": candles[-1]["date"] if candles else None,
            "days": len(candles),
            "first_close": _round(first_close, 2),
            "last_close": _round(last_close, 2),
            "full_window_return_pct": _round(_pct_change(first_close, last_close), 4) if first_close is not None and last_close is not None else None,
        },
        "rolling_baseline": {
            "windows": len(rolling_returns),
            "forward_window_days": forward_window,
            "mean_forward_return_pct": _round(_mean(rolling_returns), 4),
            "median_forward_return_pct": _round(_median(rolling_returns), 4),
            "positive_forward_windows": sum(1 for value in rolling_returns if value > 0),
        },
        "event_windows": {
            "events": len(event_returns),
            "mean_forward_return_pct": _round(_mean(event_returns), 4),
            "median_forward_return_pct": _round(_median(event_returns), 4),
            "delta_vs_rolling_median_pct": _round((_median(event_returns) or 0.0) - (_median(rolling_returns) or 0.0), 4),
            "closed_event_median_forward_return_pct": _round(_median(closed_returns), 4),
            "unclosed_event_median_forward_return_pct": _round(_median(unclosed_returns), 4),
        },
        "chart_points": [
            {
                "date": row.get("event_date"),
                "close": row.get("event_close"),
                "relation": row.get("relation"),
                "lvn_lower": (row.get("lvn_zone") or {}).get("lower"),
                "lvn_upper": (row.get("lvn_zone") or {}).get("upper"),
                "policy_closed": row.get("policy_closed"),
                "forward_return_pct": row.get("forward_return_pct"),
                "forward_max_up_pct": row.get("forward_max_up_pct"),
                "forward_max_down_pct": row.get("forward_max_down_pct"),
            }
            for row in events
        ],
    }


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


def _sensitivity_grid(input_path: Path, *, random_controls: int, exclude_latest_event: bool) -> list[dict[str, Any]]:
    exchange = _read_json(input_path)
    candles = _median_daily_candles(exchange)
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
                events = _policy_events(
                    proxy,
                    candles=candles,
                    forward_window=forward_window,
                    closure_rule="close",
                    random_controls=random_controls,
                    exclude_latest_event=exclude_latest_event,
                )
                random_rates = [
                    float(event["random_matched_control_rate"])
                    for event in events
                    if event.get("random_matched_control_rate") is not None
                ]
                rows.append({
                    "window_days": window_days,
                    "bins": bins,
                    "forward_window": forward_window,
                    "events": len(events),
                    "policy_closure_rate": _round(_rate(events, "policy_closed")),
                    "strict_control_rate": _round(_rate(events, "strict_control_closed")),
                    "delta_vs_strict_control": _round(_delta(events)),
                    "random_matched_control_rate": _round(_mean(random_rates)),
                    "delta_vs_random_matched_control": _round((_rate(events, "policy_closed") or 0.0) - (_mean(random_rates) or 0.0)),
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
    random_controls: int = 20,
    exclude_latest_event: bool = True,
) -> dict[str, Any]:
    exchange = _read_json(input_path)
    latest_common_date = (((exchange.get("metrics") or {}).get("latest_common_date")) or None)
    candles = _median_daily_candles(exchange)
    base_proxy = build_lvn_proxy(
        input_path=input_path,
        bins=bins,
        window_days=window_days,
        forward_window=forward_window,
        stride=stride,
        closure_rule=closure_rule,
    )
    previous_lvn_proxy = _read_json(LVN_PROXY_LATEST) if LVN_PROXY_LATEST.exists() else {}
    events = _policy_events(
        base_proxy,
        candles=candles,
        forward_window=forward_window,
        closure_rule=closure_rule,
        random_controls=random_controls,
        exclude_latest_event=exclude_latest_event,
    )
    policy_rate = _rate(events, "policy_closed")
    strict_rate = _rate(events, "strict_control_closed")
    adjacent_rate = _rate(events, "adjacent_control_closed")
    opposite_rate = _rate(events, "opposite_control_closed")
    shuffled_rate = _rate(events, "shuffled_volume_control_closed")
    delta_vs_strict = _delta(events)
    random_rates = [
        float(event["random_matched_control_rate"])
        for event in events
        if event.get("random_matched_control_rate") is not None
    ]
    random_matched_rate = _mean(random_rates)
    delta_vs_random_matched = (policy_rate - random_matched_rate) if policy_rate is not None and random_matched_rate is not None else None
    closed_bars = [float(e["bars_to_close"]) for e in events if e.get("bars_to_close") is not None]
    normal_chart = _normal_chart_comparison(
        candles,
        events,
        forward_window=forward_window,
        exclude_latest_event=exclude_latest_event,
    )
    walk_forward = _split_walk_forward(events)
    fold_deltas = [float(row["delta_vs_strict_control"]) for row in walk_forward if row.get("delta_vs_strict_control") is not None]
    sensitivity = _sensitivity_grid(input_path, random_controls=random_controls, exclude_latest_event=exclude_latest_event)
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

    research_decision = "observe"
    if len(events) < 12:
        decision = "observe"
        verdict = "POLICY_SIMULATOR_DENOMINATOR_LOW"
    elif score["classification"] == "research_useful":
        if value_direction == "positive_vs_strict_control":
            decision = "test"
            research_decision = "advance"
            verdict = "POLICY_SIMULATOR_RESEARCH_VALUE_HIGH_POSITIVE_EDGE"
        elif value_direction == "negative_vs_strict_control":
            decision = "redesign"
            research_decision = "redesign"
            verdict = "POLICY_SIMULATOR_RESEARCH_VALUE_HIGH_NEGATIVE_EDGE_REDESIGN"
        else:
            decision = "watch"
            research_decision = "watch"
            verdict = "POLICY_SIMULATOR_RESEARCH_VALUE_HIGH_NEUTRAL"
    elif score["classification"] == "research_watch":
        decision = "watch"
        research_decision = "watch"
        verdict = "POLICY_SIMULATOR_RESEARCH_VALUE_WATCH"
    else:
        decision = "reject"
        research_decision = "reject"
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
            "random_matched_controls_per_event": random_controls,
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
            "deterministic random matched zones",
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
            "normal_chart_comparison": "compare event windows with the ordinary BTC daily chart path over the same forward horizon",
        },
        "policy_contract": primary_contract,
        "summary": {
            "observe": 1 if decision == "observe" else 0,
            "watch": 1 if decision == "watch" else 0,
            "test": 1 if decision == "test" else 0,
            "reject": 1 if decision == "reject" else 0,
            "redesign": 1 if decision == "redesign" else 0,
        },
        "card": {
            "claim_id": "btc_policy_simulator_lvn_close_policy",
            "title": "BTC LVN policy simulator v0",
            "decision": decision,
            "research_decision": research_decision,
            "verdict": verdict,
            "evidence": (
                f"{len(events)} closed-data events; policy closure {_round(policy_rate)}; "
                f"strict control {_round(strict_rate)}; delta {_round(delta_vs_strict)}; "
                f"random matched control {_round(random_matched_rate)}; "
                f"event median forward return {normal_chart['event_windows']['median_forward_return_pct']}% vs "
                f"normal rolling median {normal_chart['rolling_baseline']['median_forward_return_pct']}%; "
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
            "random_matched_control_rate": _round(random_matched_rate),
            "strict_control_rate": _round(strict_rate),
            "delta_vs_strict_control": _round(delta_vs_strict),
            "delta_vs_random_matched_control": _round(delta_vs_random_matched),
            "random_matched_controls_per_event": random_controls,
            "median_bars_to_close": _round(_median(closed_bars), 2),
            "mean_bars_to_close": _round(_mean(closed_bars), 2),
            "open_candle_exclusion_passed": exclude_latest_event,
            "latest_common_date": latest_common_date,
        },
        "normal_chart_comparison": normal_chart,
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
            "deterministic_random_matched_controls": True,
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
    parser.add_argument("--random-controls", type=int, default=20)
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
        random_controls=args.random_controls,
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
