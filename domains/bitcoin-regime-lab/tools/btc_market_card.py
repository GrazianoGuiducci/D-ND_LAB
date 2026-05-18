#!/usr/bin/env python3
"""btc_market_card.py - BTC market data-card for the Bitcoin Regime Lab.

The tool fetches public BTC/USD price history and writes a value-facing
artifact for the dashboard. It is deliberately descriptive: it does not emit
buy/sell, target, forecast or trading-signal language.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx


VERSION = "0.1.0"
DOMAIN_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = DOMAIN_DIR.parents[1]
DATA_DIR = REPO_ROOT / "data" / "bitcoin-regime-lab"
VALUE_DIR = DATA_DIR / "value"
CACHE_DIR = DATA_DIR / "market_cache"
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
UA = "D-ND-Lab/1.0 (research; +https://lab.d-nd.com)"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _pct(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return (current / previous - 1.0) * 100.0


def _nearest_daily_price(points: list[dict[str, Any]], days_back: int) -> dict[str, Any] | None:
    if not points:
        return None
    idx = max(0, len(points) - 1 - days_back)
    return points[idx]


def _cache_path(coin_id: str, vs_currency: str, days: int) -> Path:
    safe = f"{coin_id}_{vs_currency}_{days}d.json".replace("/", "_")
    return CACHE_DIR / safe


def _load_cache(path: Path, ttl_sec: int) -> dict[str, Any] | None:
    if not path.exists():
        return None
    if time.time() - path.stat().st_mtime > ttl_sec:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _store_cache(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def fetch_coingecko_market_chart(coin_id: str, vs_currency: str, days: int, ttl_sec: int) -> dict[str, Any]:
    url = f"{COINGECKO_BASE}/coins/{coin_id}/market_chart"
    params = {"vs_currency": vs_currency, "days": str(days), "interval": "daily"}
    cache = _cache_path(coin_id, vs_currency, days)
    cached = _load_cache(cache, ttl_sec)
    if cached is not None:
        cached["cache"] = {"status": "hit", "path": str(cache), "ttl_sec": ttl_sec}
        return cached

    with httpx.Client(timeout=20.0, headers={"User-Agent": UA}) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        raw = response.json()

    payload = {
        "provider": "coingecko",
        "coin_id": coin_id,
        "vs_currency": vs_currency,
        "source_url": f"{url}?{urlencode(params)}",
        "retrieval_ts": _utc_now(),
        "raw": raw,
        "cache": {"status": "miss", "path": str(cache), "ttl_sec": ttl_sec},
    }
    _store_cache(cache, payload)
    return payload


def build_market_card(coin_id: str = "bitcoin", vs_currency: str = "usd", days: int = 31,
                      ttl_sec: int = 900) -> dict[str, Any]:
    fetched = fetch_coingecko_market_chart(coin_id, vs_currency, days, ttl_sec)
    prices_raw = fetched.get("raw", {}).get("prices") or []
    volumes_raw = fetched.get("raw", {}).get("total_volumes") or []
    if not prices_raw:
        raise RuntimeError(f"no prices returned for {coin_id}/{vs_currency}")

    points: list[dict[str, Any]] = []
    volume_by_ts = {int(v[0]): _safe_float(v[1]) for v in volumes_raw if isinstance(v, list) and len(v) >= 2}
    for point in prices_raw:
        if not isinstance(point, list) or len(point) < 2:
            continue
        ts_ms = int(point[0])
        price = _safe_float(point[1])
        if price is None:
            continue
        points.append({
            "date": datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d"),
            "ts_ms": ts_ms,
            "close": price,
            "volume": volume_by_ts.get(ts_ms),
        })
    if not points:
        raise RuntimeError(f"no usable price points returned for {coin_id}/{vs_currency}")

    latest = points[-1]
    p0 = latest["close"]
    p1 = _nearest_daily_price(points, 1)
    p7 = _nearest_daily_price(points, 7)
    p30 = _nearest_daily_price(points, min(30, len(points) - 1))
    closes = [p["close"] for p in points]
    log_returns = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes)) if closes[i - 1] > 0]
    realized_vol_30d = statistics.pstdev(log_returns) * math.sqrt(365) * 100 if len(log_returns) > 1 else None
    high_30d = max(closes)
    low_30d = min(closes)
    drawdown_from_30d_high = _pct(p0, high_30d)

    generated_at = _utc_now()
    data_card = {
        "provider": fetched["provider"],
        "source_url": fetched["source_url"],
        "retrieval_ts": fetched["retrieval_ts"],
        "asset": "BTC",
        "pair": f"BTC/{vs_currency.upper()}",
        "coin_id": coin_id,
        "vs_currency": vs_currency,
        "granularity": "daily market_chart close proxy",
        "window_start": points[0]["date"],
        "window_end": points[-1]["date"],
        "n_obs": len(points),
        "timezone": "UTC",
        "missing_data_handling": "drop malformed points; no interpolation",
        "price_type": "CoinGecko market_chart price, close proxy",
        "volume_type": "CoinGecko total_volumes when provided",
        "known_limitations": [
            "CoinGecko free market_chart is an aggregated reference, not exchange-native order-flow.",
            "No OHLC candle body or intra-day volume profile is inferred here.",
            "This artifact is context for monitoring and falsification, not trading advice.",
        ],
        "fetcher_version": VERSION,
        "cache": fetched.get("cache", {}),
    }
    metrics = {
        "price_usd": round(p0, 2),
        "change_1d_pct": round(_pct(p0, p1["close"] if p1 else None), 3) if p1 else None,
        "change_7d_pct": round(_pct(p0, p7["close"] if p7 else None), 3) if p7 else None,
        "change_30d_pct": round(_pct(p0, p30["close"] if p30 else None), 3) if p30 else None,
        "realized_vol_30d_annualized_pct": round(realized_vol_30d, 3) if realized_vol_30d is not None else None,
        "drawdown_from_30d_high_pct": round(drawdown_from_30d_high, 3) if drawdown_from_30d_high is not None else None,
        "high_30d": round(high_30d, 2),
        "low_30d": round(low_30d, 2),
    }
    decision = "observe"
    boundary = (
        "No trading signal: this card only establishes current BTC context and "
        "the provenance needed before testing a POC/FVG/timeframe hypothesis."
    )
    return {
        "schema": "dndlab.bitcoin.market_context.v1",
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
                "claim_id": f"btc_market_context_{latest['date']}",
                "title": "BTC market context data-card",
                "claim": f"BTC/USD reference context on {latest['date']}: ${metrics['price_usd']:,.2f}.",
                "decision": decision,
                "evidence": (
                    f"1d {metrics['change_1d_pct']}%, 7d {metrics['change_7d_pct']}%, "
                    f"30d {metrics['change_30d_pct']}%, vol30 {metrics['realized_vol_30d_annualized_pct']}%."
                ),
                "boundary": boundary,
                "data_card": data_card,
                "metrics": metrics,
                "next_test": "Choose one observable hypothesis, then test it against a matched null before watch/test promotion.",
            }
        ],
        "data_card": data_card,
        "metrics": metrics,
        "boundary": {
            "public_claim": False,
            "trading_signal": False,
            "operational": False,
            "advice": False,
        },
    }


def write_artifact(payload: dict[str, Any]) -> dict[str, str]:
    VALUE_DIR.mkdir(parents=True, exist_ok=True)
    latest = VALUE_DIR / "btc_market_context_latest.json"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stamped = VALUE_DIR / f"btc_market_context_{stamp}.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    latest.write_text(text + "\n", encoding="utf-8")
    stamped.write_text(text + "\n", encoding="utf-8")
    return {"latest": str(latest), "stamped": str(stamped)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a BTC market context value artifact.")
    parser.add_argument("--coin-id", default="bitcoin")
    parser.add_argument("--vs-currency", default="usd")
    parser.add_argument("--days", type=int, default=31)
    parser.add_argument("--ttl", type=int, default=900)
    parser.add_argument("--write", action="store_true", help="Write under data/bitcoin-regime-lab/value/")
    parser.add_argument("--json", action="store_true", help="Print JSON payload.")
    args = parser.parse_args()

    payload = build_market_card(args.coin_id, args.vs_currency, args.days, args.ttl)
    if args.write:
        payload["files"] = write_artifact(payload)
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"status": "OK", "files": payload.get("files"), "summary": payload["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
