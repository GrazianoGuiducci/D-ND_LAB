#!/usr/bin/env python3
"""btc_exchange_ohlcv.py - exchange-native OHLCV context for BTC.

Fetches public daily candles from multiple exchange APIs and writes a
value-facing robustness card. The artifact is descriptive: it measures feed
agreement/disagreement before any POC/FVG/timeframe hypothesis can be tested.
It never emits trading signals, targets or advice.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


VERSION = "0.1.0"
DOMAIN_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = DOMAIN_DIR.parents[1]
DATA_ROOT = Path(os.environ.get("LAB_DATA_DIR", REPO_ROOT / "data")).resolve()
DATA_DIR = DATA_ROOT / "bitcoin-regime-lab"
VALUE_DIR = DATA_DIR / "value"
UA = "D-ND-Lab/1.0 (research; +https://lab.d-nd.com)"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _date_from_seconds(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def _pct_dispersion(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    midpoint = sum(values) / len(values)
    if midpoint == 0:
        return None
    return (max(values) - min(values)) / midpoint * 100.0


def _client() -> httpx.Client:
    return httpx.Client(timeout=20.0, headers={"User-Agent": UA})


def fetch_bitstamp(client: httpx.Client, limit: int) -> dict[str, Any]:
    url = "https://www.bitstamp.net/api/v2/ohlc/btcusd/"
    params = {"step": "86400", "limit": str(limit)}
    response = client.get(url, params=params)
    response.raise_for_status()
    raw = response.json()
    candles = []
    for row in raw.get("data", {}).get("ohlc", []) or []:
        ts = int(row["timestamp"])
        candles.append({
            "date": _date_from_seconds(ts),
            "ts": ts,
            "open": _safe_float(row.get("open")),
            "high": _safe_float(row.get("high")),
            "low": _safe_float(row.get("low")),
            "close": _safe_float(row.get("close")),
            "volume": _safe_float(row.get("volume")),
        })
    return {
        "provider": "bitstamp",
        "pair": "BTC/USD",
        "source_url": str(response.url),
        "candles": candles,
    }


def fetch_coinbase(client: httpx.Client, limit: int) -> dict[str, Any]:
    url = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
    params = {"granularity": "86400", "limit": str(limit)}
    response = client.get(url, params=params)
    response.raise_for_status()
    raw = response.json()
    candles = []
    # Coinbase returns [time, low, high, open, close, volume], newest first.
    for row in raw or []:
        if not isinstance(row, list) or len(row) < 6:
            continue
        ts = int(row[0])
        candles.append({
            "date": _date_from_seconds(ts),
            "ts": ts,
            "open": _safe_float(row[3]),
            "high": _safe_float(row[2]),
            "low": _safe_float(row[1]),
            "close": _safe_float(row[4]),
            "volume": _safe_float(row[5]),
        })
    candles.sort(key=lambda c: c["ts"])
    return {
        "provider": "coinbase",
        "pair": "BTC/USD",
        "source_url": str(response.url),
        "candles": candles[-limit:],
    }


def fetch_binance(client: httpx.Client, limit: int) -> dict[str, Any]:
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "1d", "limit": str(limit)}
    response = client.get(url, params=params)
    response.raise_for_status()
    raw = response.json()
    candles = []
    # Binance returns open time ms, open, high, low, close, volume, ...
    for row in raw or []:
        if not isinstance(row, list) or len(row) < 6:
            continue
        ts = int(row[0]) // 1000
        candles.append({
            "date": _date_from_seconds(ts),
            "ts": ts,
            "open": _safe_float(row[1]),
            "high": _safe_float(row[2]),
            "low": _safe_float(row[3]),
            "close": _safe_float(row[4]),
            "volume": _safe_float(row[5]),
        })
    return {
        "provider": "binance",
        "pair": "BTC/USDT",
        "source_url": str(response.url),
        "candles": candles,
    }


FETCHERS = {
    "bitstamp": fetch_bitstamp,
    "coinbase": fetch_coinbase,
    "binance": fetch_binance,
}


def build_feed_card(limit: int = 31, providers: list[str] | None = None) -> dict[str, Any]:
    selected = providers or list(FETCHERS)
    feeds: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    retrieval_ts = _utc_now()
    with _client() as client:
        for provider in selected:
            fetcher = FETCHERS.get(provider)
            if fetcher is None:
                errors.append({"provider": provider, "error": "unknown_provider"})
                continue
            try:
                feeds.append(fetcher(client, limit))
            except Exception as exc:  # noqa: BLE001 - keep provider failures observable
                errors.append({"provider": provider, "error": f"{type(exc).__name__}: {exc}"})

    feed_summaries = []
    latest_by_provider = []
    closes_by_common_date: dict[str, list[float]] = {}
    for feed in feeds:
        candles = [c for c in feed.get("candles", []) if c.get("close") is not None]
        if not candles:
            feed_summaries.append({
                "provider": feed["provider"],
                "pair": feed["pair"],
                "status": "empty",
                "n_obs": 0,
                "source_url": feed["source_url"],
            })
            continue
        latest = candles[-1]
        latest_by_provider.append({
            "provider": feed["provider"],
            "pair": feed["pair"],
            "date": latest["date"],
            "close": round(float(latest["close"]), 2),
            "volume": round(float(latest["volume"]), 6) if latest.get("volume") is not None else None,
        })
        for candle in candles:
            closes_by_common_date.setdefault(candle["date"], []).append(float(candle["close"]))
        feed_summaries.append({
            "provider": feed["provider"],
            "pair": feed["pair"],
            "status": "ok",
            "n_obs": len(candles),
            "window_start": candles[0]["date"],
            "window_end": candles[-1]["date"],
            "latest_close": round(float(latest["close"]), 2),
            "source_url": feed["source_url"],
        })

    common_dates = sorted(date for date, closes in closes_by_common_date.items() if len(closes) >= 2)
    latest_common_date = common_dates[-1] if common_dates else None
    latest_dispersion = (
        _pct_dispersion(closes_by_common_date[latest_common_date])
        if latest_common_date is not None else None
    )
    max_dispersion = None
    if common_dates:
        dispersions = [_pct_dispersion(closes_by_common_date[date]) for date in common_dates]
        clean = [d for d in dispersions if d is not None]
        max_dispersion = max(clean) if clean else None

    status = "observe"
    if len(feed_summaries) < 2:
        status = "insufficient_feeds"
    elif errors:
        status = "observe_with_provider_errors"

    generated_at = _utc_now()
    metrics = {
        "providers_ok": len([f for f in feed_summaries if f.get("status") == "ok"]),
        "providers_error": len(errors),
        "latest_common_date": latest_common_date,
        "latest_close_dispersion_pct": round(latest_dispersion, 4) if latest_dispersion is not None else None,
        "max_close_dispersion_pct": round(max_dispersion, 4) if max_dispersion is not None else None,
        "common_days_compared": len(common_dates),
    }
    return {
        "schema": "dndlab.bitcoin.exchange_ohlcv.v1",
        "generated_at": generated_at,
        "domain": "bitcoin-regime-lab",
        "summary": {
            "observe": 1,
            "watch": 0,
            "test": 0,
            "reject": 0,
            "trading_signal": False,
        },
        "cards": [
            {
                "claim_id": f"btc_exchange_ohlcv_{latest_common_date or generated_at[:10]}",
                "title": "BTC exchange feed robustness data-card",
                "claim": "BTC daily OHLCV context can be compared across exchange-native feeds before hypothesis tests.",
                "decision": status,
                "evidence": (
                    f"{metrics['providers_ok']} provider feeds ok; latest common date "
                    f"{metrics['latest_common_date']}; close dispersion "
                    f"{metrics['latest_close_dispersion_pct']}%."
                ),
                "boundary": (
                    "No trading signal: feed agreement is a precondition for later "
                    "POC/FVG/timeframe tests, not an operational direction."
                ),
                "metrics": metrics,
                "next_test": "Use feed disagreement as a null/edge-case guard before testing any BTC level or timeframe claim.",
            }
        ],
        "data_card": {
            "providers": selected,
            "retrieval_ts": retrieval_ts,
            "granularity": "1d OHLCV",
            "timezone": "UTC",
            "known_limitations": [
                "Binance feed is BTC/USDT, not BTC/USD.",
                "Daily candles are exchange-native and can disagree by timezone/session and pair construction.",
                "Volume is native to each venue and must not be aggregated without normalization.",
                "This artifact is context for monitoring and falsification, not trading advice.",
            ],
            "fetcher_version": VERSION,
        },
        "metrics": metrics,
        "latest_by_provider": latest_by_provider,
        "series": [
            {
                "provider": feed["provider"],
                "pair": feed["pair"],
                "candles": feed.get("candles", []),
            }
            for feed in feeds
        ],
        "feeds": feed_summaries,
        "errors": errors,
        "boundary": {
            "public_claim": False,
            "trading_signal": False,
            "operational": False,
            "advice": False,
        },
    }


def write_artifact(payload: dict[str, Any]) -> dict[str, str]:
    VALUE_DIR.mkdir(parents=True, exist_ok=True)
    latest = VALUE_DIR / "btc_exchange_ohlcv_latest.json"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stamped = VALUE_DIR / f"btc_exchange_ohlcv_{stamp}.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    latest.write_text(text + "\n", encoding="utf-8")
    stamped.write_text(text + "\n", encoding="utf-8")
    return {"latest": str(latest), "stamped": str(stamped)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build BTC exchange OHLCV value artifact.")
    parser.add_argument("--limit", type=int, default=31)
    parser.add_argument("--providers", default="bitstamp,coinbase,binance")
    parser.add_argument("--write", action="store_true", help="Write under data/bitcoin-regime-lab/value/")
    parser.add_argument("--json", action="store_true", help="Print JSON payload.")
    args = parser.parse_args()

    providers = [p.strip() for p in args.providers.split(",") if p.strip()]
    payload = build_feed_card(args.limit, providers)
    if args.write:
        payload["files"] = write_artifact(payload)
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"status": "OK", "files": payload.get("files"), "summary": payload["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
