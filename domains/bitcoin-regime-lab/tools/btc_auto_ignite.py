#!/usr/bin/env python3
"""btc_auto_ignite.py - first autonomous ignition contract for BTC Lab.

The tool does not trade, predict or run the cognitive cycle. It gathers the
current value artifacts, creates explicit provisional assumptions for the
LVN/Volume Profile method, builds a deterministic daily OHLCV proxy and
writes the next observable contract for the Lab.
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
FIRST_HYPOTHESIS_LATEST = VALUE_DIR / "btc_first_hypothesis_latest.json"
TIMEFRAME_LATEST = VALUE_DIR / "btc_timeframe_matrix_latest.json"
METHOD_INTAKE_LATEST = VALUE_DIR / "btc_method_intake_latest.json"
DAILY_INEFFICIENCY_LATEST = VALUE_DIR / "btc_daily_inefficiency_latest.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json_optional(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


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
            "volume": _median([float(c.get("volume") or 0.0) for c in candles]),
        })
    return rows


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(max(int(round((len(ordered) - 1) * q)), 0), len(ordered) - 1)
    return float(ordered[index])


def _build_volume_profile_proxy(candles: list[dict[str, Any]], *, bins: int) -> dict[str, Any]:
    if not candles:
        return {"bins": [], "error": "no candles"}
    low = min(float(c["low"]) for c in candles)
    high = max(float(c["high"]) for c in candles)
    width = (high - low) / bins if bins > 0 and high > low else 0.0
    if width <= 0:
        return {"bins": [], "error": "invalid price range"}

    rows = []
    for i in range(bins):
        rows.append({
            "index": i,
            "lower": low + (i * width),
            "upper": low + ((i + 1) * width),
            "volume": 0.0,
            "days": 0,
        })

    for candle in candles:
        typical = (float(candle["high"]) + float(candle["low"]) + float(candle["close"])) / 3.0
        index = min(max(int((typical - low) / width), 0), bins - 1)
        rows[index]["volume"] += max(float(candle.get("volume") or 0.0), 0.0)
        rows[index]["days"] += 1

    volumes = [r["volume"] for r in rows if r["volume"] > 0]
    q25 = _quantile(volumes, 0.25)
    q75 = _quantile(volumes, 0.75)
    poc = max(rows, key=lambda r: r["volume"])
    for row in rows:
        row["lower"] = round(row["lower"], 2)
        row["upper"] = round(row["upper"], 2)
        row["volume"] = round(row["volume"], 8)
        if row["volume"] == poc["volume"]:
            row["class"] = "POC"
        elif row["volume"] > 0 and row["volume"] <= q25:
            row["class"] = "LVN"
        elif row["volume"] >= q75:
            row["class"] = "HVN"
        else:
            row["class"] = "MID"

    return {
        "price_range": {"low": round(low, 2), "high": round(high, 2), "bin_width": round(width, 2)},
        "thresholds": {"lvn_volume_q25": round(q25, 8), "hvn_volume_q75": round(q75, 8)},
        "poc": {
            "lower": round(poc["lower"], 2),
            "upper": round(poc["upper"], 2),
            "volume": round(poc["volume"], 8),
            "days": int(poc["days"]),
        },
        "bins": rows,
    }


def _nearest_lvn_zones(profile: dict[str, Any], current_close: float, *, limit: int = 5) -> list[dict[str, Any]]:
    zones = []
    for row in profile.get("bins") or []:
        if row.get("class") != "LVN":
            continue
        lower = float(row["lower"])
        upper = float(row["upper"])
        midpoint = (lower + upper) / 2.0
        if lower <= current_close <= upper:
            relation = "inside"
            distance_pct = 0.0
        elif current_close < lower:
            relation = "above_price"
            distance_pct = ((lower - current_close) / current_close) * 100.0
        else:
            relation = "below_price"
            distance_pct = ((current_close - upper) / current_close) * 100.0
        zones.append({
            "zone_id": f"btc_lvn_proxy_bin_{row['index']}",
            "lower": lower,
            "upper": upper,
            "midpoint": round(midpoint, 2),
            "relation_to_current_close": relation,
            "distance_pct": round(distance_pct, 4),
            "volume": row.get("volume"),
            "days": row.get("days"),
            "status": "watch",
        })
    return sorted(zones, key=lambda z: z["distance_pct"])[:limit]


def _artifact_state(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": payload.get("schema"),
        "generated_at": payload.get("generated_at"),
        "summary": payload.get("summary"),
        "metrics": payload.get("metrics"),
    }


def build_auto_ignite(*, bins: int = 36, window_days: int = 180) -> dict[str, Any]:
    generated_at = _utc_now()
    exchange = _read_json_optional(EXCHANGE_LATEST)
    first = _read_json_optional(FIRST_HYPOTHESIS_LATEST)
    timeframe = _read_json_optional(TIMEFRAME_LATEST)
    method = _read_json_optional(METHOD_INTAKE_LATEST)
    inefficiency = _read_json_optional(DAILY_INEFFICIENCY_LATEST)

    candles = _median_daily_candles(exchange)[-window_days:]
    current = candles[-1] if candles else {}
    current_close = float(current.get("close") or 0.0)
    profile = _build_volume_profile_proxy(candles, bins=bins)
    lvn_zones = _nearest_lvn_zones(profile, current_close) if current_close > 0 else []

    providers_ok = int((exchange.get("metrics") or {}).get("providers_ok") or 0)
    field_card = (first.get("cards") or [{}])[0] if isinstance(first.get("cards"), list) else {}
    field_ok = field_card.get("decision") in {
        "ADMIT_FIELD_FOR_ONE_NEXT_MECHANICAL_HYPOTHESIS",
        "admit",
        "test",
    }
    enough_candles = len(candles) >= min(window_days, 90)
    proxy_ready = bool(profile.get("bins")) and providers_ok >= 2 and enough_candles
    decision = "test" if proxy_ready and field_ok else "watch"
    verdict = "BTC_AUTO_IGNITE_PROXY_READY" if decision == "test" else "BTC_AUTO_IGNITE_WATCH"

    assumptions = {
        "profile_type": "system_generated_daily_ohlcv_volume_profile_proxy",
        "source_priority": ["Bitstamp BTC/USD", "Coinbase BTC/USD", "Binance BTC/USDT"],
        "price_basis": "median daily OHLC across available exchange-native feeds",
        "volume_basis": "median daily venue volume, binned by daily typical price",
        "window_days": window_days,
        "bins": bins,
        "lvn_rule": "nonzero volume bin <= first quartile of proxy-bin volume",
        "hvn_rule": "bin volume >= third quartile of proxy-bin volume",
        "poc_rule": "bin with maximum proxy volume",
        "fill_rule": "not simulated yet; next tool must define touch/close/full-traversal",
        "profile_replay_boundary": "proxy only; not a TradingView Volume Profile replay",
    }

    next_questions = [
        "Can the proxy LVN zones be tested against equal-width random zones without lookahead?",
        "Does an adjacent profile window move the same LVN/POC structure?",
        "Does shuffled volume destroy the LVN/POC relation?",
        "Which fill rule should be simulated first: wick touch, close inside or full traversal?",
        "Should the first simulator measure only watch-zone closure, or also a buy/sell rule?",
    ]

    return {
        "schema": "dndlab.bitcoin.auto_ignite.v1",
        "generated_at": generated_at,
        "domain": "bitcoin-regime-lab",
        "version": VERSION,
        "intent": "Autonomously create the first provisional LVN/Volume Profile method contract from available BTC artifacts without waiting for manual parameters.",
        "input_artifacts": {
            "exchange_ohlcv": str(EXCHANGE_LATEST),
            "field_gate": str(FIRST_HYPOTHESIS_LATEST),
            "timeframe_matrix": str(TIMEFRAME_LATEST),
            "method_intake": str(METHOD_INTAKE_LATEST),
            "daily_inefficiency": str(DAILY_INEFFICIENCY_LATEST),
        },
        "artifact_state": {
            "exchange_ohlcv": _artifact_state(exchange),
            "field_gate": _artifact_state(first),
            "timeframe_matrix": _artifact_state(timeframe),
            "method_intake": _artifact_state(method),
            "daily_inefficiency": _artifact_state(inefficiency),
        },
        "auto_spec": {
            "method_id": "volume_profile_lvn_void",
            "title": "LVN / Volume Profile void auto-ignition",
            "decision": decision,
            "verdict": verdict,
            "assumptions": assumptions,
            "verified": {
                "candles": len(candles),
                "providers_ok": providers_ok,
                "current_date": current.get("date"),
                "current_close": round(current_close, 2) if current_close else None,
                "field_gate_decision": field_card.get("decision"),
                "proxy_ready": proxy_ready,
            },
            "inferred": {
                "profile_window": f"last {len(candles)} median daily candles",
                "selected_method": "LVN/Volume Profile proxy because current BTC method material emphasizes low-volume inefficiency.",
            },
            "not_verified": [
                "TradingView profile rows/bin setting",
                "exact manual profile window from screenshot",
                "true tick/volume-at-price data",
                "fill/invalidation preference",
            ],
        },
        "volume_profile_proxy": {
            "poc": profile.get("poc"),
            "nearest_lvn_zones": lvn_zones,
            "thresholds": profile.get("thresholds"),
            "price_range": profile.get("price_range"),
            "bin_count": len(profile.get("bins") or []),
        },
        "next_contract": {
            "tool_candidate": "btc_volume_profile_lvn_proxy.py",
            "baseline": "equal-width random zones with same distance distribution",
            "nulls": [
                "adjacent profile window",
                "shuffled volume profile proxy",
                "no-lookahead declared window",
            ],
            "simulator_candidate": {
                "allowed": True,
                "first_scope": "research backtest of watch-zone closure, then optional buy/sell rule only after explicit entry/exit/invalidation assumptions",
                "metrics": ["event_count", "closure_rate", "random_zone_delta", "max_drawdown_if_strategy_defined", "buy_and_hold_baseline_if_strategy_defined"],
            },
            "next_questions": next_questions,
        },
        "summary": {
            "observe": 1,
            "watch": 1 if decision == "watch" else 0,
            "test": 1 if decision == "test" else 0,
            "reject": 0,
            "trading_signal": False,
        },
        "cards": [
            {
                "claim_id": "btc_auto_ignite_lvn_proxy",
                "title": "BTC LVN auto-ignite proxy",
                "claim": "The system can create a provisional LVN/Volume Profile proxy from available exchange OHLCV and expose its assumptions before a cycle.",
                "decision": decision,
                "verdict": verdict,
                "evidence": f"{len(candles)} median daily candles, {providers_ok} providers, {len(lvn_zones)} nearest LVN proxy zones.",
                "baseline": "No manual profile parameter is treated as known; generated assumptions are explicit and falsifiable.",
                "null": "equal-width random zones, adjacent profile window, shuffled volume profile proxy.",
                "falsifier": "If proxy zones do not beat controls or move under adjacent windows, keep method in watch/reject.",
                "boundary": "No trading signal: auto-ignite creates an observable contract, not target, entry, exit or advice.",
                "next_test": "Implement the LVN proxy test/backtest using the declared assumptions and controls.",
            }
        ],
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
        artifact_prefix="btc_auto_ignite",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build BTC auto-ignite artifact.")
    parser.add_argument("--bins", type=int, default=36)
    parser.add_argument("--window-days", type=int, default=180)
    parser.add_argument("--write", action="store_true", help="Write under data/bitcoin-regime-lab/value/")
    parser.add_argument("--json", action="store_true", help="Print JSON payload.")
    args = parser.parse_args()

    payload = build_auto_ignite(bins=args.bins, window_days=args.window_days)
    if args.write:
        payload["files"] = write_artifact(payload)
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"status": "OK", "files": payload.get("files"), "summary": payload["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
