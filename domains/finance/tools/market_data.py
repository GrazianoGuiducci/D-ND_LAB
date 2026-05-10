#!/usr/bin/env python3
"""market_data.py — acquisizione dati di mercato per il D-ND finance lab.

Provider abstraction (intent OpenBB): un singolo schema, N fonti dietro.
Stocks via yfinance (Yahoo Finance, no auth, gestisce crumb internamente).
Crypto via CoinGecko (free tier, no auth, JSON market_chart). Aggiungere
un provider non tocca il consumer (exp_regime_shift, agent, falsifier).

Storico decisione: la prima implementazione usava Stooq direct CSV (no
auth, no deps). 2026-05-05: Stooq ha introdotto requirement apikey →
TEMPORAL hook si è materializzato. Switch a yfinance che gestisce il
crumb Yahoo internamente. CoinGecko regge ancora senza key.

Schema universale di ritorno (numpy + dict, NIENTE pandas):

    {
        "symbol": "SPY",
        "provider": "stooq",
        "interval": "1d",
        "dates":   list[str],     # YYYY-MM-DD
        "open":    np.ndarray,
        "high":    np.ndarray,
        "low":     np.ndarray,
        "close":   np.ndarray,
        "volume":  np.ndarray | None,
        "returns": np.ndarray,    # log-return close-to-close, len = N-1
        "n_obs":   int,
        "data_card": { ... }      # provenance, license, retrieval_ts, era_hint
    }

Cache (intent: riproducibilità + audit trail).
- File: data/finance/market_cache/<provider>_<symbol>_<start>_<end>_<interval>.json
- Sidecar non separato: il data_card vive dentro il JSON come campo first-class.
- TTL configurabile (default 86400s); stale → re-fetch.
- Mai eliminare cache silenziosamente: il file resta come record storico.

Era hint (intent Numerai): metadata che vincola dove la shuffle del
test ordered-vs-shuffle può operare. L'agent può chiedere "era 2008Q4"
e il tool sa che lo shuffle deve restare DENTRO quel finestra, non
across asset/anno.

CLI:
    python market_data.py --symbol SPY --provider stooq --period 1y
    python market_data.py --symbol bitcoin --provider coingecko --days 365
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import numpy as np


VERSION = "1.1.0"

DOMAIN_DIR = Path(__file__).resolve().parents[1]
CACHE_DIR = DOMAIN_DIR.parent.parent / "data" / "finance" / "market_cache"
DEFAULT_TTL_SEC = 86_400  # 1 day

COINGECKO_BASE = "https://api.coingecko.com/api/v3"

UA = "D-ND-Lab/1.0 (research; +https://lab.d-nd.com)"


# ---------- cache ----------

def _cache_key(provider: str, symbol: str, start: str, end: str, interval: str) -> str:
    raw = f"{provider}|{symbol.lower()}|{start}|{end}|{interval}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _cache_path(provider: str, symbol: str, start: str, end: str, interval: str) -> Path:
    key = _cache_key(provider, symbol, start, end, interval)
    safe_sym = symbol.lower().replace("/", "_")
    return CACHE_DIR / f"{provider}_{safe_sym}_{start}_{end}_{interval}_{key}.json"


def _cache_load(path: Path, ttl_sec: int) -> dict[str, Any] | None:
    if not path.exists():
        return None
    age = time.time() - path.stat().st_mtime
    if age > ttl_sec:
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _cache_store(path: Path, payload: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str))


# ---------- helpers ----------

def _log_returns(close: np.ndarray) -> np.ndarray:
    if len(close) < 2:
        return np.array([], dtype=float)
    return np.diff(np.log(close))


def _era_hint(dates: list[str]) -> str:
    """Era hint per partizionamento alla Numerai.

    Per finanza usiamo il quarter (~63 giorni daily). Lo shuffle del
    protocollo ordered-vs-shuffle deve restare DENTRO l'era se l'agent
    vuole separare struttura intra-quarter da macrostruttura.
    """
    if not dates:
        return "unknown"
    first = dates[0]
    last = dates[-1]
    try:
        d0 = datetime.fromisoformat(first)
        d1 = datetime.fromisoformat(last)
        if d0.year == d1.year:
            q0 = (d0.month - 1) // 3 + 1
            q1 = (d1.month - 1) // 3 + 1
            if q0 == q1:
                return f"{d0.year}Q{q0}"
            return f"{d0.year}Q{q0}-Q{q1}"
        return f"{d0.year}-{d1.year}"
    except Exception:
        return f"{first}_{last}"


def _data_card(provider: str, symbol: str, source_url: str, license_str: str,
               dates: list[str], frequency: str) -> dict[str, Any]:
    return {
        "retrieval_ts": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "symbol_resolved": symbol,
        "source_url": source_url,
        "license": license_str,
        "frequency": frequency,
        "first_date": dates[0] if dates else None,
        "last_date":  dates[-1] if dates else None,
        "era_hint":   _era_hint(dates),
        "n_obs":      len(dates),
        "fetcher_version": VERSION,
    }


# ---------- provider: yfinance (stocks/ETF/indices) ----------

def fetch_yfinance(symbol: str, period: str = "1y", interval: str = "1d",
                   ttl_sec: int = DEFAULT_TTL_SEC) -> dict[str, Any]:
    """Fetch daily OHLCV via yfinance.

    symbol: e.g. "SPY", "QQQ", "^GSPC", "BTC-USD".
    period: yfinance period string ("1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max").
    interval: "1d", "1wk", "1mo", "1h" (intraday limited a 60d).

    yfinance gestisce crumb cookie + scrape Yahoo internamente. Output
    pandas DataFrame; convertiamo in numpy/list per uscire.
    """
    cache_p = _cache_path("yfinance", symbol, period, "now", interval)
    cached = _cache_load(cache_p, ttl_sec)
    if cached is not None:
        return _arrayify(cached)

    # Lazy import: yfinance trascina pandas, isoliamo a runtime
    import yfinance as yf  # type: ignore[import-not-found]

    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval, auto_adjust=True)
    if df is None or df.empty:
        raise RuntimeError(f"yfinance empty result for {symbol} period={period}")

    dates = [d.strftime("%Y-%m-%d") for d in df.index.to_pydatetime()]
    open_ = [float(x) for x in df["Open"].tolist()]
    high = [float(x) for x in df["High"].tolist()]
    low = [float(x) for x in df["Low"].tolist()]
    close = [float(x) for x in df["Close"].tolist()]
    volume = [float(x) for x in df["Volume"].tolist()] if "Volume" in df.columns else None

    payload = {
        "symbol": symbol,
        "provider": "yfinance",
        "interval": interval,
        "dates": dates,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "data_card": _data_card(
            provider="yfinance",
            symbol=symbol,
            source_url=f"yfinance://Ticker({symbol}).history(period={period}, interval={interval})",
            license_str="Yahoo Finance terms — research/personal use; verify for redistribution",
            dates=dates,
            frequency="daily" if interval == "1d" else interval,
        ),
    }
    payload["data_card"]["adjustments"] = "auto_adjust=True (split + dividend adjusted close)"

    _cache_store(cache_p, payload)
    return _arrayify(payload)


# ---------- provider: coingecko (crypto) ----------

def fetch_coingecko(coin_id: str, days: int = 365,
                    ttl_sec: int = DEFAULT_TTL_SEC) -> dict[str, Any]:
    """Fetch crypto market chart from CoinGecko free tier.

    coin_id: "bitcoin", "ethereum", "solana" (CoinGecko slug).
    days: 1..max. Per days > 90, granularità daily forzata.
    Returns: prices interpretati come close (CoinGecko non espone OHLC su free).
    """
    end_ts = datetime.now(timezone.utc).strftime("%Y%m%d")
    start_ts = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y%m%d")
    cache_p = _cache_path("coingecko", coin_id, start_ts, end_ts, f"{days}d")
    cached = _cache_load(cache_p, ttl_sec)
    if cached is not None:
        return _arrayify(cached)

    url = f"{COINGECKO_BASE}/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": str(days)}
    with httpx.Client(timeout=20.0, headers={"User-Agent": UA}) as client:
        r = client.get(url, params=params)
        r.raise_for_status()
        data = r.json()

    prices_raw = data.get("prices", [])
    volumes_raw = data.get("total_volumes", [])
    if not prices_raw:
        raise RuntimeError(f"CoinGecko returned empty prices for {coin_id}")

    dates = [datetime.fromtimestamp(p[0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
             for p in prices_raw]
    close = [float(p[1]) for p in prices_raw]
    volume = [float(v[1]) for v in volumes_raw] if volumes_raw else None

    # CoinGecko free non espone OHL — usiamo close come proxy unico.
    payload = {
        "symbol": coin_id,
        "provider": "coingecko",
        "interval": "1d" if days >= 90 else "auto",
        "dates": dates,
        "open":   close,  # proxy
        "high":   close,  # proxy
        "low":    close,  # proxy
        "close":  close,
        "volume": volume,
        "data_card": _data_card(
            provider="coingecko",
            symbol=coin_id,
            source_url=f"{url}?vs_currency=usd&days={days}",
            license_str="CoinGecko Free API — attribution required; no redistribution as primary product",
            dates=dates,
            frequency="daily" if days >= 90 else "auto",
        ),
    }
    payload["data_card"]["note"] = (
        "CoinGecko free tier expone solo close prices; OHL impostati = close. "
        "Per OHLC reali usare exchange via ccxt (richiede config)."
    )

    _cache_store(cache_p, payload)
    return _arrayify(payload)


# ---------- normalization (return numpy arrays + add returns) ----------

def _arrayify(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    for k in ("open", "high", "low", "close"):
        if k in out and out[k] is not None:
            out[k] = np.asarray(out[k], dtype=float)
    if out.get("volume") is not None:
        out["volume"] = np.asarray(out["volume"], dtype=float)
    out["returns"] = _log_returns(out["close"])
    out["n_obs"] = len(out["close"])
    return out


# ---------- public dispatch ----------

def fetch(provider: str, symbol: str, **kwargs: Any) -> dict[str, Any]:
    """Provider dispatch. Stesso schema in uscita."""
    if provider == "yfinance":
        period = kwargs.get("period", "1y")
        interval = kwargs.get("interval", "1d")
        ttl = int(kwargs.get("ttl_sec", DEFAULT_TTL_SEC))
        return fetch_yfinance(symbol, period, interval, ttl)
    if provider == "coingecko":
        days = int(kwargs.get("days", 365))
        ttl = int(kwargs.get("ttl_sec", DEFAULT_TTL_SEC))
        return fetch_coingecko(symbol, days, ttl)
    raise ValueError(f"Unknown provider: {provider}. Supported: yfinance, coingecko")


# ---------- CLI ----------

def _summarize(d: dict[str, Any]) -> dict[str, Any]:
    closes = d["close"]
    returns = d["returns"]
    return {
        "symbol": d["symbol"],
        "provider": d["provider"],
        "n_obs": d["n_obs"],
        "first_date": d["data_card"]["first_date"],
        "last_date":  d["data_card"]["last_date"],
        "era_hint":   d["data_card"]["era_hint"],
        "close_first": float(closes[0]) if len(closes) else None,
        "close_last":  float(closes[-1]) if len(closes) else None,
        "return_mean": float(returns.mean()) if len(returns) else None,
        "return_std":  float(returns.std()) if len(returns) else None,
        "return_pct_total": float((closes[-1] / closes[0] - 1) * 100) if len(closes) > 1 else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--provider", choices=["yfinance", "coingecko"], required=True)
    ap.add_argument("--symbol", required=True,
                    help="SPY/QQQ/^GSPC for yfinance; bitcoin/ethereum for coingecko")
    ap.add_argument("--period", default="1y",
                    help="yfinance period: 1mo/3mo/6mo/1y/2y/5y/10y/max (yfinance only)")
    ap.add_argument("--interval", default="1d",
                    help="yfinance interval: 1d/1wk/1mo/1h (yfinance only)")
    ap.add_argument("--days", type=int, default=365, help="coingecko only")
    ap.add_argument("--ttl", type=int, default=DEFAULT_TTL_SEC)
    ap.add_argument("--json", action="store_true", help="Print full payload as JSON")
    args = ap.parse_args()

    kwargs: dict[str, Any] = {"ttl_sec": args.ttl}
    if args.provider == "yfinance":
        kwargs["period"] = args.period
        kwargs["interval"] = args.interval
    else:
        kwargs["days"] = args.days

    try:
        d = fetch(args.provider, args.symbol, **kwargs)
    except Exception as e:
        print(json.dumps({"error": str(e), "provider": args.provider, "symbol": args.symbol}), file=sys.stderr)
        return 2

    if args.json:
        # numpy → list per JSON
        out = dict(d)
        for k in ("open", "high", "low", "close", "volume", "returns"):
            if isinstance(out.get(k), np.ndarray):
                out[k] = out[k].tolist()
        print(json.dumps(out, indent=2, default=str))
    else:
        print(json.dumps(_summarize(d), indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
