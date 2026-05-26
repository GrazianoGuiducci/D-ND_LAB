#!/usr/bin/env python3
"""btc_volume_profile_lvn_proxy.py - LVN/Volume Profile proxy test.

Builds a deterministic daily OHLCV volume-profile proxy from exchange artifacts
and tests whether nearest LVN zones close more often than simple matched
controls. This is research/backtest substrate only: no target, entry, exit or
advice.
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


VERSION = "0.1.0"
DOMAIN_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = DOMAIN_DIR.parents[1]
DATA_ROOT = Path(os.environ.get("LAB_DATA_DIR", REPO_ROOT / "data")).resolve()
DATA_DIR = DATA_ROOT / "bitcoin-regime-lab"
VALUE_DIR = DATA_DIR / "value"
EXCHANGE_LATEST = VALUE_DIR / "btc_exchange_ohlcv_latest.json"
AUTO_IGNITE_LATEST = VALUE_DIR / "btc_auto_ignite_latest.json"
CLOSED_GATE_LATEST = VALUE_DIR / "btc_daily_closed_evidence_gate_latest.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing required artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json_optional(path: Path) -> dict[str, Any]:
    try:
        return _read_json(path)
    except Exception:
        return {}


def _closed_evidence_gate() -> dict[str, Any]:
    gate = _read_json_optional(CLOSED_GATE_LATEST)
    state = gate.get("gate") if isinstance(gate.get("gate"), dict) else {}
    return {
        "available": bool(gate),
        "decision": state.get("decision"),
        "mutation_allowed": state.get("mutation_allowed"),
        "latest_closed_common_date": state.get("latest_closed_common_date"),
        "open_daily_date": state.get("open_daily_date"),
    }


def _median(values: list[float]) -> float:
    return float(statistics.median(values))


def _median_daily_candles(exchange: dict[str, Any]) -> list[dict[str, Any]]:
    by_date: dict[str, list[dict[str, Any]]] = {}
    for feed in exchange.get("series") or []:
        if not isinstance(feed, dict):
            continue
        for candle in feed.get("candles") or []:
            if isinstance(candle, dict) and candle.get("date"):
                by_date.setdefault(str(candle["date"]), []).append(candle)

    rows = []
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
            "volume": _median([float(c.get("volume") or 0.0) for c in candles]),
        })
    return rows


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(max(int(round((len(ordered) - 1) * q)), 0), len(ordered) - 1)
    return float(ordered[idx])


def _build_profile(candles: list[dict[str, Any]], bins: int, *, volume_shift: int = 0) -> dict[str, Any]:
    low = min(float(c["low"]) for c in candles)
    high = max(float(c["high"]) for c in candles)
    width = (high - low) / bins if bins > 0 and high > low else 0.0
    if width <= 0:
        return {"bins": [], "error": "invalid price range"}
    rows = [{"index": i, "lower": low + i * width, "upper": low + (i + 1) * width, "volume": 0.0, "days": 0} for i in range(bins)]
    volumes = [max(float(c.get("volume") or 0.0), 0.0) for c in candles]
    if volumes and volume_shift:
        shift = volume_shift % len(volumes)
        volumes = volumes[shift:] + volumes[:shift]

    for candle, volume in zip(candles, volumes):
        typical = (float(candle["high"]) + float(candle["low"]) + float(candle["close"])) / 3.0
        idx = min(max(int((typical - low) / width), 0), bins - 1)
        rows[idx]["volume"] += volume
        rows[idx]["days"] += 1

    nonzero = [r["volume"] for r in rows if r["volume"] > 0]
    q25 = _quantile(nonzero, 0.25)
    q75 = _quantile(nonzero, 0.75)
    poc = max(rows, key=lambda r: r["volume"])
    for row in rows:
        if row["volume"] == poc["volume"]:
            row["class"] = "POC"
        elif row["volume"] > 0 and row["volume"] <= q25:
            row["class"] = "LVN"
        elif row["volume"] >= q75:
            row["class"] = "HVN"
        else:
            row["class"] = "MID"
    return {
        "range": {"low": low, "high": high, "bin_width": width},
        "thresholds": {"lvn_q25": q25, "hvn_q75": q75},
        "poc": poc,
        "bins": rows,
    }


def _nearest_lvn(profile: dict[str, Any], price: float) -> dict[str, Any] | None:
    candidates = []
    for row in profile.get("bins") or []:
        if row.get("class") != "LVN":
            continue
        lower = float(row["lower"])
        upper = float(row["upper"])
        if lower <= price <= upper:
            distance = 0.0
            relation = "inside"
        elif price < lower:
            distance = lower - price
            relation = "above_price"
        else:
            distance = price - upper
            relation = "below_price"
        candidates.append((distance, relation, row))
    if not candidates:
        return None
    distance, relation, row = sorted(candidates, key=lambda x: x[0])[0]
    width = float(row["upper"]) - float(row["lower"])
    return {
        "index": int(row["index"]),
        "lower": float(row["lower"]),
        "upper": float(row["upper"]),
        "width": width,
        "relation": relation,
        "distance_pct": (distance / price) * 100.0 if price else 0.0,
        "volume": float(row["volume"]),
        "days": int(row["days"]),
    }


def _zone_closed(future: list[dict[str, Any]], zone: dict[str, Any], rule: str) -> dict[str, Any]:
    lower = float(zone["lower"])
    upper = float(zone["upper"])
    for offset, candle in enumerate(future, start=1):
        if rule == "close":
            close = float(candle["close"])
            hit = lower <= close <= upper
        else:
            hit = float(candle["low"]) <= upper and float(candle["high"]) >= lower
        if hit:
            return {"closed": True, "close_date": candle["date"], "bars_to_close": offset}
    return {"closed": False, "close_date": None, "bars_to_close": None}


def _shift_zone(zone: dict[str, Any], bins: int) -> dict[str, Any]:
    width = float(zone["width"])
    if zone["relation"] == "below_price":
        lower = float(zone["lower"]) - width
    else:
        lower = float(zone["upper"])
    return {"lower": lower, "upper": lower + width, "width": width}


def _opposite_zone(zone: dict[str, Any], event_close: float) -> dict[str, Any]:
    width = float(zone["width"])
    distance = abs(event_close - ((float(zone["lower"]) + float(zone["upper"])) / 2.0))
    if zone["relation"] == "below_price":
        mid = event_close + distance
    else:
        mid = event_close - distance
    return {"lower": mid - width / 2.0, "upper": mid + width / 2.0, "width": width}


def _rate(rows: list[dict[str, Any]], key: str) -> float | None:
    if not rows:
        return None
    return sum(1 for row in rows if row.get(key)) / len(rows)


def build_lvn_proxy(
    *,
    input_path: Path = EXCHANGE_LATEST,
    bins: int = 36,
    window_days: int = 45,
    forward_window: int = 10,
    stride: int = 3,
    closure_rule: str = "close",
) -> dict[str, Any]:
    exchange = _read_json(input_path)
    auto = _read_json_optional(AUTO_IGNITE_LATEST)
    closed_gate = _closed_evidence_gate()
    closed_cutoff = closed_gate.get("latest_closed_common_date")
    candles = [
        c for c in _median_daily_candles(exchange)
        if not closed_cutoff or str(c.get("date")) <= str(closed_cutoff)
    ]
    events = []
    for event_index in range(window_days, max(window_days, len(candles) - forward_window), stride):
        history = candles[event_index - window_days:event_index]
        future = candles[event_index:event_index + forward_window]
        if len(history) < window_days or len(future) < forward_window:
            continue
        event = candles[event_index - 1]
        event_close = float(event["close"])
        profile = _build_profile(history, bins)
        zone = _nearest_lvn(profile, event_close)
        if not zone:
            continue
        adjacent = _shift_zone(zone, bins)
        opposite = _opposite_zone(zone, event_close)
        shuffled = _nearest_lvn(_build_profile(history, bins, volume_shift=max(1, len(history) // 3)), event_close)
        lvn_fill = _zone_closed(future, zone, closure_rule)
        adjacent_fill = _zone_closed(future, adjacent, closure_rule)
        opposite_fill = _zone_closed(future, opposite, closure_rule)
        shuffled_fill = _zone_closed(future, shuffled, closure_rule) if shuffled else {"closed": False, "close_date": None, "bars_to_close": None}
        strict_closed = bool(adjacent_fill["closed"] or opposite_fill["closed"] or shuffled_fill["closed"])
        events.append({
            "event_date": event["date"],
            "event_close": round(event_close, 2),
            "lvn_zone": {
                "lower": round(zone["lower"], 2),
                "upper": round(zone["upper"], 2),
                "relation": zone["relation"],
                "distance_pct": round(zone["distance_pct"], 4),
                "volume": round(zone["volume"], 8),
                "days": zone["days"],
            },
            "lvn_closed": bool(lvn_fill["closed"]),
            "lvn_close_date": lvn_fill["close_date"],
            "lvn_bars_to_close": lvn_fill["bars_to_close"],
            "adjacent_control_closed": bool(adjacent_fill["closed"]),
            "opposite_control_closed": bool(opposite_fill["closed"]),
            "shuffled_volume_control_closed": bool(shuffled_fill["closed"]),
            "strict_control_closed": strict_closed,
        })

    lvn_rate = _rate(events, "lvn_closed")
    adjacent_rate = _rate(events, "adjacent_control_closed")
    opposite_rate = _rate(events, "opposite_control_closed")
    shuffled_rate = _rate(events, "shuffled_volume_control_closed")
    strict_rate = _rate(events, "strict_control_closed")
    denominator_ready = len(events) >= 12
    delta_vs_strict = (lvn_rate - strict_rate) if lvn_rate is not None and strict_rate is not None else None
    if not denominator_ready:
        decision = "watch"
        verdict = "LVN_PROXY_DENOMINATOR_LOW"
    elif delta_vs_strict is not None and delta_vs_strict > 0.05:
        decision = "test"
        verdict = "LVN_PROXY_BEATS_STRICT_CONTROL"
    else:
        decision = "watch"
        verdict = "LVN_PROXY_STRICT_CONTROL_NOT_BEATEN"

    metrics = {
        "events": len(events),
        "window_days": window_days,
        "forward_window": forward_window,
        "stride": stride,
        "bins": bins,
        "closure_rule": closure_rule,
        "lvn_closure_rate": round(lvn_rate, 4) if lvn_rate is not None else None,
        "adjacent_control_rate": round(adjacent_rate, 4) if adjacent_rate is not None else None,
        "opposite_control_rate": round(opposite_rate, 4) if opposite_rate is not None else None,
        "shuffled_volume_control_rate": round(shuffled_rate, 4) if shuffled_rate is not None else None,
        "strict_control_rate": round(strict_rate, 4) if strict_rate is not None else None,
        "delta_vs_strict_control": round(delta_vs_strict, 4) if delta_vs_strict is not None else None,
        "denominator_ready": denominator_ready,
    }

    return {
        "schema": "dndlab.bitcoin.volume_profile_lvn_proxy.v1",
        "generated_at": _utc_now(),
        "domain": "bitcoin-regime-lab",
        "version": VERSION,
        "input_artifacts": {
            "exchange_ohlcv": str(input_path),
            "auto_ignite": str(AUTO_IGNITE_LATEST),
        },
        "method_contract": {
            "method_id": "volume_profile_lvn_void",
            "profile_type": "system_generated_daily_ohlcv_volume_profile_proxy",
            "profile_window_days": window_days,
            "bins": bins,
            "closure_rule": closure_rule,
            "forward_window_days": forward_window,
            "no_lookahead": True,
            "proxy_boundary": "daily OHLCV proxy; not TradingView tick/volume-at-price replay",
            "closed_evidence_gate": closed_gate,
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
                "claim_id": "btc_lvn_proxy_backtest",
                "title": "BTC LVN / Volume Profile proxy",
                "claim": "A generated daily OHLCV LVN proxy can be evaluated against matched controls before any simulator or cycle promotion.",
                "decision": decision,
                "verdict": verdict,
                "evidence": f"{len(events)} events; LVN closure {metrics['lvn_closure_rate']}; strict control {metrics['strict_control_rate']}; delta {metrics['delta_vs_strict_control']}.",
                "baseline": "No LVN effect: equal-width adjacent/opposite zones and shuffled-volume LVN should close at comparable or higher rate.",
                "null": "adjacent equal-width zone, opposite-distance zone and shuffled-volume profile proxy.",
                "falsifier": "If LVN closure does not beat strict controls, keep the method in watch and do not build strategy rules from it.",
                "boundary": "No trading signal: this measures a proxy phenomenon, not target, entry, exit or advice.",
                "next_test": "If useful, build simulator only as separate research layer with explicit entry, exit, costs and baseline.",
            }
        ],
        "metrics": metrics,
        "closed_evidence": {
            "cutoff_date": closed_cutoff,
            "candles_after_gate": len(candles),
        },
        "events": events,
        "auto_ignite_context": {
            "decision": (auto.get("auto_spec") or {}).get("decision"),
            "verdict": (auto.get("auto_spec") or {}).get("verdict"),
        },
        "simulator_candidate": {
            "allowed": True,
            "only_after": "entry/exit/invalidation assumptions are explicit and separated from this proxy phenomenon test",
            "required_metrics": ["event_count", "closure_rate", "random_zone_delta", "fees", "slippage", "max_drawdown", "buy_and_hold_baseline"],
        },
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
    return write_json_artifact(
        payload=payload,
        value_dir=VALUE_DIR,
        data_dir=DATA_DIR,
        repo_root=REPO_ROOT,
        tool_path=Path(__file__),
        artifact_prefix="btc_volume_profile_lvn_proxy",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build BTC LVN/Volume Profile proxy test artifact.")
    parser.add_argument("--input", default=str(EXCHANGE_LATEST))
    parser.add_argument("--bins", type=int, default=36)
    parser.add_argument("--window-days", type=int, default=45)
    parser.add_argument("--forward-window", type=int, default=10)
    parser.add_argument("--stride", type=int, default=3)
    parser.add_argument("--closure-rule", choices=["wick", "close"], default="close")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = build_lvn_proxy(
        input_path=Path(args.input),
        bins=args.bins,
        window_days=args.window_days,
        forward_window=args.forward_window,
        stride=args.stride,
        closure_rule=args.closure_rule,
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
