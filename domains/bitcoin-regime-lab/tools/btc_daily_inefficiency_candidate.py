#!/usr/bin/env python3
"""btc_daily_inefficiency_candidate.py - daily BTC FVG/inefficiency proxy.

Consumes the exchange OHLCV value artifact and builds a conservative daily
three-candle inefficiency proxy. This is a method-test substrate, not a market
signal, target or operational rule.
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
DOMAIN_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = DOMAIN_DIR.parents[1]
DATA_ROOT = Path(os.environ.get("LAB_DATA_DIR", REPO_ROOT / "data")).resolve()
DATA_DIR = DATA_ROOT / "bitcoin-regime-lab"
VALUE_DIR = DATA_DIR / "value"
EXCHANGE_LATEST = VALUE_DIR / "btc_exchange_ohlcv_latest.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing required artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _median(values: list[float]) -> float:
    return round(float(statistics.median(values)), 8)


def _median_daily_candles(exchange: dict[str, Any]) -> list[dict[str, Any]]:
    by_date: dict[str, list[dict[str, Any]]] = {}
    for feed in exchange.get("series") or []:
        candles = feed.get("candles") if isinstance(feed, dict) else None
        if not isinstance(candles, list):
            continue
        for candle in candles:
            if not isinstance(candle, dict) or not candle.get("date"):
                continue
            by_date.setdefault(str(candle["date"]), []).append(candle)

    rows: list[dict[str, Any]] = []
    for date in sorted(by_date):
        candles = by_date[date]
        if len(candles) < 2:
            continue
        rows.append({
            "date": date,
            "providers": len(candles),
            "open": _median([float(c["open"]) for c in candles]),
            "high": _median([float(c["high"]) for c in candles]),
            "low": _median([float(c["low"]) for c in candles]),
            "close": _median([float(c["close"]) for c in candles]),
            "volume": _median([float(c.get("volume") or 0) for c in candles]),
        })
    return rows


def _zone_fill(
    *,
    candles: list[dict[str, Any]],
    start_index: int,
    lower: float,
    upper: float,
    direction: str,
    forward_window: int,
    fill_threshold: float,
    rule: str,
) -> dict[str, Any]:
    width = max(upper - lower, 0.0)
    threshold_price = lower + (width * fill_threshold)
    forward = candles[start_index + 1:start_index + 1 + forward_window]
    best_fill = 0.0
    fill_date = None
    filled = False

    for candle in forward:
        if rule == "close":
            probe = float(candle["close"])
            touched = lower <= probe <= upper
        else:
            probe = float(candle["low"] if direction == "bullish" else candle["high"])
            touched = probe <= upper if direction == "bullish" else probe >= lower

        if direction == "bullish":
            fill_ratio = max(0.0, min(1.0, (upper - probe) / width)) if width else 0.0
            threshold_hit = probe <= threshold_price
        else:
            fill_ratio = max(0.0, min(1.0, (probe - lower) / width)) if width else 0.0
            threshold_hit = probe >= threshold_price

        best_fill = max(best_fill, fill_ratio)
        if touched and threshold_hit:
            filled = True
            fill_date = candle["date"]
            break

    status = "filled" if filled else ("pending" if len(forward) < forward_window else "unfilled")
    return {
        "status": status,
        "filled": filled,
        "fill_date": fill_date,
        "best_fill_ratio": round(best_fill, 4),
        "forward_candles_seen": len(forward),
    }


def _control_zone(lower: float, upper: float, direction: str) -> tuple[float, float]:
    width = upper - lower
    if direction == "bullish":
        return lower - width, lower
    return upper, upper + width


def build_daily_inefficiency_candidate(
    *,
    input_path: Path = EXCHANGE_LATEST,
    forward_window: int = 10,
    min_zone_width_pct: float = 0.15,
    fill_threshold: float = 0.5,
    fill_rule: str = "wick",
    min_providers_per_day: int = 2,
) -> dict[str, Any]:
    exchange = _read_json(input_path)
    source_metrics = exchange.get("metrics") or {}
    candles = [
        c for c in _median_daily_candles(exchange)
        if int(c.get("providers") or 0) >= min_providers_per_day
    ]

    zones: list[dict[str, Any]] = []
    controls: list[dict[str, Any]] = []
    for index in range(2, len(candles)):
        prev2 = candles[index - 2]
        current = candles[index]
        close = float(current["close"])
        if close <= 0:
            continue

        if float(current["low"]) > float(prev2["high"]):
            direction = "bullish"
            lower = float(prev2["high"])
            upper = float(current["low"])
        elif float(current["high"]) < float(prev2["low"]):
            direction = "bearish"
            lower = float(current["high"])
            upper = float(prev2["low"])
        else:
            continue

        width = upper - lower
        width_pct = (width / close) * 100
        if width <= 0 or width_pct < min_zone_width_pct:
            continue

        fill = _zone_fill(
            candles=candles,
            start_index=index,
            lower=lower,
            upper=upper,
            direction=direction,
            forward_window=forward_window,
            fill_threshold=fill_threshold,
            rule=fill_rule,
        )
        control_lower, control_upper = _control_zone(lower, upper, direction)
        control_fill = _zone_fill(
            candles=candles,
            start_index=index,
            lower=control_lower,
            upper=control_upper,
            direction=direction,
            forward_window=forward_window,
            fill_threshold=fill_threshold,
            rule=fill_rule,
        )
        zone_id = f"btc_daily_fvg_{current['date']}_{direction}"
        zones.append({
            "zone_id": zone_id,
            "direction": direction,
            "event_date": current["date"],
            "anchor_dates": [prev2["date"], current["date"]],
            "lower": round(lower, 2),
            "upper": round(upper, 2),
            "width": round(width, 2),
            "width_pct_of_close": round(width_pct, 4),
            "fill": fill,
        })
        controls.append({
            "zone_id": f"{zone_id}_control",
            "matched_zone_id": zone_id,
            "direction": direction,
            "event_date": current["date"],
            "lower": round(control_lower, 2),
            "upper": round(control_upper, 2),
            "width": round(width, 2),
            "fill": control_fill,
            "null": "adjacent_equal_width_zone_control",
        })

    evaluable_zones = [z for z in zones if z["fill"]["status"] != "pending"]
    evaluable_controls = [c for c in controls if c["fill"]["status"] != "pending"]
    filled_zones = [z for z in evaluable_zones if z["fill"]["filled"]]
    filled_controls = [c for c in evaluable_controls if c["fill"]["filled"]]
    pending_zones = [z for z in zones if z["fill"]["status"] == "pending"]

    zone_rate = (len(filled_zones) / len(evaluable_zones)) if evaluable_zones else None
    control_rate = (len(filled_controls) / len(evaluable_controls)) if evaluable_controls else None
    enough_denominator = len(evaluable_zones) >= 5 and len(evaluable_controls) >= 5
    if not zones:
        decision = "watch"
        verdict = "NO_DAILY_INEFFICIENCY_CANDIDATES"
        next_test = "Refresh data or lower no threshold only after declaring why; do not infer from no event."
    elif enough_denominator:
        decision = "test"
        verdict = "DAILY_INEFFICIENCY_PROXY_READY_FOR_CYCLE_REVIEW"
        next_test = "Run a cognitive cycle only to review this proxy against its matched null and falsifiers."
    else:
        decision = "watch"
        verdict = "DAILY_INEFFICIENCY_PROXY_DENOMINATOR_LOW"
        next_test = "Accumulate more daily candles or keep this as a watch surface before interpretation."

    generated_at = _utc_now()
    return {
        "schema": "dndlab.bitcoin.daily_inefficiency.v1",
        "generated_at": generated_at,
        "domain": "bitcoin-regime-lab",
        "input_artifact": str(input_path),
        "method_contract": {
            "observable": "daily three-candle FVG/inefficiency proxy",
            "zone_definition": "bullish if candle[i].low > candle[i-2].high; bearish if candle[i].high < candle[i-2].low",
            "fill_threshold": fill_threshold,
            "fill_rule": fill_rule,
            "forward_window_days": forward_window,
            "minimum_zone_width_pct_of_close": min_zone_width_pct,
            "invalidation_rule": "unfilled after the forward window is classified as unfilled; incomplete forward window remains pending",
            "price_source": "median OHLC across available exchange-native daily feeds",
        },
        "summary": {
            "observe": 0,
            "watch": 1 if decision == "watch" else 0,
            "test": 1 if decision == "test" else 0,
            "reject": 0,
            "trading_signal": False,
        },
        "cards": [
            {
                "claim_id": "btc_daily_inefficiency_proxy",
                "title": "BTC daily inefficiency proxy",
                "claim": "Daily OHLCV can define candidate FVG/inefficiency zones before any POC or Volume Profile target exists.",
                "decision": decision,
                "verdict": verdict,
                "evidence": (
                    f"{len(zones)} zones found, {len(evaluable_zones)} evaluable, "
                    f"{len(filled_zones)} filled; matched controls filled "
                    f"{len(filled_controls)} of {len(evaluable_controls)}."
                ),
                "baseline": "No inefficiency rule is the baseline: do not infer direction from candles alone.",
                "null": "adjacent_equal_width_zone_control with the same event date, width and forward window.",
                "falsifier": "If matched controls fill at the same or higher rate, downgrade the proxy as non-informative.",
                "boundary": "No trading signal: zones are test objects, not targets, entries, exits or advice.",
                "next_test": next_test,
            }
        ],
        "metrics": {
            "providers_ok": source_metrics.get("providers_ok"),
            "providers_error": source_metrics.get("providers_error"),
            "daily_candles": len(candles),
            "zones_total": len(zones),
            "zones_evaluable": len(evaluable_zones),
            "zones_pending": len(pending_zones),
            "zones_filled": len(filled_zones),
            "controls_evaluable": len(evaluable_controls),
            "controls_filled": len(filled_controls),
            "zone_fill_rate": round(zone_rate, 4) if zone_rate is not None else None,
            "control_fill_rate": round(control_rate, 4) if control_rate is not None else None,
            "denominator_ready": enough_denominator,
        },
        "zones": zones,
        "matched_controls": controls,
        "boundary": {
            "public_claim": False,
            "trading_signal": False,
            "operational": False,
            "advice": False,
            "price_target": False,
            "entry_exit": False,
        },
    }


def write_artifact(payload: dict[str, Any]) -> dict[str, str]:
    VALUE_DIR.mkdir(parents=True, exist_ok=True)
    latest = VALUE_DIR / "btc_daily_inefficiency_latest.json"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stamped = VALUE_DIR / f"btc_daily_inefficiency_{stamp}.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    latest.write_text(text + "\n", encoding="utf-8")
    stamped.write_text(text + "\n", encoding="utf-8")
    return {"latest": str(latest), "stamped": str(stamped)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build BTC daily inefficiency candidate artifact.")
    parser.add_argument("--input", default=str(EXCHANGE_LATEST), help="Path to btc_exchange_ohlcv_latest.json")
    parser.add_argument("--forward-window", type=int, default=10)
    parser.add_argument("--min-zone-width-pct", type=float, default=0.15)
    parser.add_argument("--fill-threshold", type=float, default=0.5)
    parser.add_argument("--fill-rule", choices=["wick", "close"], default="wick")
    parser.add_argument("--min-providers-per-day", type=int, default=2)
    parser.add_argument("--write", action="store_true", help="Write under data/bitcoin-regime-lab/value/")
    parser.add_argument("--json", action="store_true", help="Print JSON payload.")
    args = parser.parse_args()

    payload = build_daily_inefficiency_candidate(
        input_path=Path(args.input),
        forward_window=args.forward_window,
        min_zone_width_pct=args.min_zone_width_pct,
        fill_threshold=args.fill_threshold,
        fill_rule=args.fill_rule,
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
