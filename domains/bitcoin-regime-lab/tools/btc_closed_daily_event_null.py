#!/usr/bin/env python3
"""Closed-daily BTC event/null family.

This artifact is the first redesign after the daily FVG/inefficiency proxy
failed strict-null pressure. It tests a different daily event family:
range-expansion candles with directional close-location, compared against a
deterministic matched-date null. It is paper/lab evidence only.
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

from btc_artifact_lineage import write_json_artifact


VERSION = "0.1.0"
DOMAIN = "bitcoin-regime-lab"
DOMAIN_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = DOMAIN_DIR.parents[1]
DATA_ROOT = Path(os.environ.get("LAB_DATA_DIR", REPO_ROOT / "data")).resolve()
DATA_DIR = DATA_ROOT / DOMAIN
VALUE_DIR = DATA_DIR / "value"
EXCHANGE_LATEST = VALUE_DIR / "btc_exchange_ohlcv_latest.json"
CLOSED_GATE_LATEST = VALUE_DIR / "btc_daily_closed_evidence_gate_latest.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing required artifact: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _read_json_optional(path: Path) -> dict[str, Any]:
    try:
        return _read_json(path)
    except Exception:
        return {}


def _round(value: float | int | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _median(values: list[float]) -> float | None:
    return float(statistics.median(values)) if values else None


def _pct_change(start: float, end: float) -> float | None:
    if start == 0.0:
        return None
    return ((end - start) / start) * 100.0


def _stable_seed(*parts: Any) -> int:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _median_daily_candles(exchange: dict[str, Any]) -> list[dict[str, Any]]:
    by_date: dict[str, list[dict[str, Any]]] = {}
    for feed in exchange.get("series") or []:
        candles = feed.get("candles") if isinstance(feed, dict) else None
        if not isinstance(candles, list):
            continue
        for candle in candles:
            if isinstance(candle, dict) and candle.get("date"):
                by_date.setdefault(str(candle["date"]), []).append(candle)

    rows: list[dict[str, Any]] = []
    for date in sorted(by_date):
        candles = by_date[date]
        if len(candles) < 2:
            continue
        rows.append({
            "date": date,
            "providers": len(candles),
            "open": float(statistics.median(float(c["open"]) for c in candles)),
            "high": float(statistics.median(float(c["high"]) for c in candles)),
            "low": float(statistics.median(float(c["low"]) for c in candles)),
            "close": float(statistics.median(float(c["close"]) for c in candles)),
            "volume": float(statistics.median(float(c.get("volume") or 0.0) for c in candles)),
        })
    return rows


def _closed_gate_state() -> dict[str, Any]:
    gate = _read_json_optional(CLOSED_GATE_LATEST)
    state = gate.get("gate") if isinstance(gate.get("gate"), dict) else {}
    return {
        "available": bool(gate),
        "decision": state.get("decision"),
        "mutation_allowed": state.get("mutation_allowed"),
        "latest_closed_common_date": state.get("latest_closed_common_date"),
        "open_daily_date": state.get("open_daily_date"),
    }


def _directional_return(start_close: float, future_close: float, direction: str) -> float | None:
    raw = _pct_change(start_close, future_close)
    if raw is None:
        return None
    return raw if direction == "bullish" else -raw


def _event_row(
    candles: list[dict[str, Any]],
    index: int,
    *,
    lookback: int,
    forward_window: int,
    expansion_multiple: float,
    close_location_threshold: float,
) -> dict[str, Any] | None:
    current = candles[index]
    future_index = index + forward_window
    if future_index >= len(candles):
        return None
    high = float(current["high"])
    low = float(current["low"])
    close = float(current["close"])
    open_ = float(current["open"])
    width = max(high - low, 0.0)
    if close <= 0.0 or width <= 0.0:
        return None
    prior = candles[index - lookback:index]
    prior_ranges = [
        ((float(row["high"]) - float(row["low"])) / float(row["close"])) * 100.0
        for row in prior
        if float(row["close"]) > 0.0 and float(row["high"]) > float(row["low"])
    ]
    median_range = _median(prior_ranges)
    if median_range is None or median_range <= 0.0:
        return None
    range_pct = (width / close) * 100.0
    close_location = (close - low) / width
    if range_pct < median_range * expansion_multiple:
        return None
    if close_location >= close_location_threshold and close > open_:
        direction = "bullish"
    elif close_location <= (1.0 - close_location_threshold) and close < open_:
        direction = "bearish"
    else:
        return None
    future_close = float(candles[future_index]["close"])
    directional = _directional_return(close, future_close, direction)
    return {
        "event_id": f"btc_closed_daily_range_expansion_{current['date']}_{direction}",
        "event_date": current["date"],
        "direction": direction,
        "event_close": _round(close, 2),
        "future_date": candles[future_index]["date"],
        "future_close": _round(future_close, 2),
        "range_pct_of_close": _round(range_pct),
        "median_prior_range_pct": _round(median_range),
        "range_expansion_multiple": _round(range_pct / median_range),
        "close_location": _round(close_location),
        "forward_window_days": forward_window,
        "directional_forward_return_pct": _round(directional),
        "outcome": "above_zero" if directional is not None and directional > 0.0 else "below_or_equal_zero",
    }


def _matched_null_rows(
    candles: list[dict[str, Any]],
    event: dict[str, Any],
    *,
    lookback: int,
    forward_window: int,
    controls_per_event: int,
) -> list[dict[str, Any]]:
    event_date = str(event.get("event_date"))
    direction = str(event.get("direction") or "bullish")
    eligible = [
        index for index in range(lookback, len(candles) - forward_window)
        if str(candles[index].get("date")) != event_date
    ]
    if not eligible:
        return []
    rng = random.Random(_stable_seed("btc_closed_daily_event_null", event_date, direction, controls_per_event))
    sampled = [eligible[rng.randrange(len(eligible))] for _ in range(controls_per_event)]
    rows = []
    for index in sampled:
        current = candles[index]
        future = candles[index + forward_window]
        start_close = float(current["close"])
        future_close = float(future["close"])
        directional = _directional_return(start_close, future_close, direction)
        rows.append({
            "matched_event_id": event.get("event_id"),
            "control_date": current["date"],
            "direction": direction,
            "event_close": _round(start_close, 2),
            "future_date": future["date"],
            "future_close": _round(future_close, 2),
            "directional_forward_return_pct": _round(directional),
        })
    return rows


def _aggregate(events: list[dict[str, Any]], null_rows: list[dict[str, Any]]) -> dict[str, Any]:
    event_returns = [
        float(row["directional_forward_return_pct"])
        for row in events
        if row.get("directional_forward_return_pct") is not None
    ]
    null_returns = [
        float(row["directional_forward_return_pct"])
        for row in null_rows
        if row.get("directional_forward_return_pct") is not None
    ]
    event_median = _median(event_returns)
    null_median = _median(null_returns)
    edge = (event_median - null_median) if event_median is not None and null_median is not None else None
    positive_events = sum(1 for value in event_returns if value > 0.0)
    positive_null = sum(1 for value in null_returns if value > 0.0)
    p_proxy = None
    if event_median is not None and null_returns:
        p_proxy = sum(1 for value in null_returns if value >= event_median) / len(null_returns)
    return {
        "events": len(events),
        "null_rows": len(null_rows),
        "event_median_directional_return_pct": _round(event_median),
        "null_median_directional_return_pct": _round(null_median),
        "edge_vs_matched_null_pct": _round(edge),
        "event_positive_rate": _round(positive_events / len(event_returns)) if event_returns else None,
        "null_positive_rate": _round(positive_null / len(null_returns)) if null_returns else None,
        "matched_null_p_proxy": _round(p_proxy),
    }


def build_closed_daily_event_null(
    *,
    input_path: Path = EXCHANGE_LATEST,
    lookback: int = 20,
    forward_window: int = 10,
    expansion_multiple: float = 1.5,
    close_location_threshold: float = 0.7,
    controls_per_event: int = 20,
    min_events: int = 8,
    min_providers_per_day: int = 2,
) -> dict[str, Any]:
    exchange = _read_json(input_path)
    gate = _closed_gate_state()
    cutoff = gate.get("latest_closed_common_date")
    candles = [
        row for row in _median_daily_candles(exchange)
        if int(row.get("providers") or 0) >= min_providers_per_day
        and (not cutoff or str(row.get("date")) <= str(cutoff))
    ]
    events = [
        row for index in range(lookback, len(candles) - forward_window)
        if (row := _event_row(
            candles,
            index,
            lookback=lookback,
            forward_window=forward_window,
            expansion_multiple=expansion_multiple,
            close_location_threshold=close_location_threshold,
        ))
    ]
    null_rows = [
        null_row
        for event in events
        for null_row in _matched_null_rows(
            candles,
            event,
            lookback=lookback,
            forward_window=forward_window,
            controls_per_event=controls_per_event,
        )
    ]
    metrics = _aggregate(events, null_rows)
    edge = metrics.get("edge_vs_matched_null_pct")
    p_proxy = metrics.get("matched_null_p_proxy")
    if metrics["events"] < min_events:
        decision = "observe"
        verdict = "CLOSED_DAILY_EVENT_NULL_DENOMINATOR_LOW"
        next_test = "Keep collecting closed daily candles or relax only a predeclared event threshold."
    elif edge is not None and edge > 0.0 and p_proxy is not None and p_proxy <= 0.2:
        decision = "test"
        verdict = "CLOSED_DAILY_EVENT_NULL_POSITIVE_EDGE"
        next_test = "Connect this event family to paper ledger simulation and retest after the next closed-data refresh."
    elif edge is not None and edge <= 0.0:
        decision = "redesign"
        verdict = "CLOSED_DAILY_EVENT_NULL_NOT_BEATEN"
        next_test = "Try another event source or null family; do not mutate method policy from this family."
    else:
        decision = "watch"
        verdict = "CLOSED_DAILY_EVENT_NULL_AMBIGUOUS"
        next_test = "Retain as watch until closed-data denominator or null separation improves."

    return {
        "schema": "dndlab.bitcoin.closed_daily_event_null.v1",
        "generated_at": _utc_now(),
        "domain": DOMAIN,
        "version": VERSION,
        "intent": "Test a different closed-daily event/null family after daily_inefficiency failed strict-null pressure.",
        "input_artifacts": {
            "exchange_ohlcv": str(input_path),
            "daily_closed_evidence_gate": str(CLOSED_GATE_LATEST),
        },
        "event_contract": {
            "event_family": "closed_daily_range_expansion_directional_close",
            "lookback_days": lookback,
            "forward_window_days": forward_window,
            "range_expansion_multiple": expansion_multiple,
            "close_location_threshold": close_location_threshold,
            "price_source": "median OHLC across available exchange-native daily feeds",
            "closed_evidence_gate": gate,
        },
        "null_contract": {
            "family": "deterministic_matched_date_directional_null",
            "controls_per_event": controls_per_event,
            "matching": "same forward window and same event direction, sampled from other closed daily dates with enough future candles",
            "seed": "sha256(event_date|direction|controls_per_event)",
        },
        "decision": decision,
        "verdict": verdict,
        "next_test": next_test,
        "metrics": metrics,
        "summary": {
            "observe": 1 if decision == "observe" else 0,
            "watch": 1 if decision == "watch" else 0,
            "test": 1 if decision == "test" else 0,
            "reject": 0,
            "redesign": 1 if decision == "redesign" else 0,
            "trading_signal": False,
        },
        "cards": [
            {
                "claim_id": "btc_closed_daily_event_null",
                "title": "BTC closed daily event/null family",
                "decision": decision,
                "verdict": verdict,
                "evidence": (
                    f"{metrics['events']} events; event median {metrics.get('event_median_directional_return_pct')}% "
                    f"vs matched null median {metrics.get('null_median_directional_return_pct')}%; "
                    f"edge {metrics.get('edge_vs_matched_null_pct')}%; p_proxy {metrics.get('matched_null_p_proxy')}."
                ),
                "next_test": next_test,
                "boundary": "Closed-daily event/null research only: simulated measurement, no entries, exits, price targets, advice or real orders.",
            }
        ],
        "events": events,
        "matched_null_rows": null_rows,
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
        artifact_prefix="btc_closed_daily_event_null",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build BTC closed-daily event/null family artifact.")
    parser.add_argument("--input", default=str(EXCHANGE_LATEST))
    parser.add_argument("--lookback", type=int, default=20)
    parser.add_argument("--forward-window", type=int, default=10)
    parser.add_argument("--expansion-multiple", type=float, default=1.5)
    parser.add_argument("--close-location-threshold", type=float, default=0.7)
    parser.add_argument("--controls-per-event", type=int, default=20)
    parser.add_argument("--min-events", type=int, default=8)
    parser.add_argument("--min-providers-per-day", type=int, default=2)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = build_closed_daily_event_null(
        input_path=Path(args.input),
        lookback=args.lookback,
        forward_window=args.forward_window,
        expansion_multiple=args.expansion_multiple,
        close_location_threshold=args.close_location_threshold,
        controls_per_event=args.controls_per_event,
        min_events=args.min_events,
        min_providers_per_day=args.min_providers_per_day,
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
