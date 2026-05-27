#!/usr/bin/env python3
"""market_data.py — acquisizione dati di mercato per il D-ND finance lab.

Provider abstraction (intent OpenBB): un singolo schema, N fonti dietro.
Stocks via yfinance (Yahoo Finance, no auth, gestisce crumb internamente).
Twelve Data e' disponibile come secondo provider con API key esterna.
Crypto via CoinGecko (free tier, no auth, JSON market_chart) and Coinbase
Exchange candles (no auth, OHLCV). Aggiungere un provider non tocca il consumer
(exp_regime_shift, agent, falsifier).

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
    python market_data.py --symbol BTC-USD --provider coinbase --start 2026-02-26 --end 2026-05-27
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
TWELVE_DATA_BASE = "https://api.twelvedata.com"
EODHD_BASE = "https://eodhd.com/api"
COINBASE_EXCHANGE_BASE = "https://api.exchange.coinbase.com"

UA = "D-ND-Lab/1.0 (research; +https://lab.d-nd.com)"


def _read_opt_env_key(*names: str) -> str | None:
    """Read API keys without exposing them.

    Preferred shape is NAME=value in environment or /opt/.env. For the current
    VPS operator file, the first non-empty non-assignment line may be a Twelve
    Data key; only the Twelve Data provider uses that fallback.
    """
    for name in names:
        value = os.environ.get(name)
        if value:
            return value.strip().strip('"').strip("'")
    env_path = Path("/opt/.env")
    if not env_path.exists():
        return None
    first_plain: str | None = None
    previous_mentions_provider = False
    provider_markers = {
        "TWELVE_DATA_API_KEY": ("twelve", "twelvedata"),
        "TWELVEDATA_API_KEY": ("twelve", "twelvedata"),
        "EODHD_API_TOKEN": ("eod", "eodhd", "eodhistoricaldata"),
        "EODHD_API_KEY": ("eod", "eodhd", "eodhistoricaldata"),
    }
    markers = tuple(
        marker
        for name in names
        for marker in provider_markers.get(name, ())
    )
    for raw in env_path.read_text(errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            if key.strip() in names:
                return value.strip().strip('"').strip("'")
        elif first_plain is None:
            first_plain = line
            previous_mentions_provider = any(marker in line.lower() for marker in markers)
        elif previous_mentions_provider and line.replace("_", "").replace("-", "").replace(".", "").isalnum() and len(line) >= 12:
            if markers:
                return line.strip().strip('"').strip("'")
            previous_mentions_provider = False
        else:
            previous_mentions_provider = previous_mentions_provider or any(marker in line.lower() for marker in markers)
    if (
        ("TWELVE_DATA_API_KEY" in names or "TWELVEDATA_API_KEY" in names)
        and first_plain
        and any(marker in first_plain.lower() for marker in markers)
    ):
        return first_plain
    return None


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
                   ttl_sec: int = DEFAULT_TTL_SEC,
                   start: str | None = None,
                   end: str | None = None) -> dict[str, Any]:
    """Fetch daily OHLCV via yfinance.

    symbol: e.g. "SPY", "QQQ", "^GSPC", "BTC-USD".
    period: yfinance period string ("1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max").
    interval: "1d", "1wk", "1mo", "1h" (intraday limited a 60d).

    yfinance gestisce crumb cookie + scrape Yahoo internamente. Output
    pandas DataFrame; convertiamo in numpy/list per uscire.
    """
    if (start is None) ^ (end is None):
        raise ValueError("yfinance explicit window requires both start and end")

    cache_start = start or period
    cache_end = end or "now"
    cache_p = _cache_path("yfinance", symbol, cache_start, cache_end, interval)
    cached = _cache_load(cache_p, ttl_sec)
    if cached is not None:
        return _arrayify(cached)

    # Lazy import: yfinance trascina pandas, isoliamo a runtime
    import yfinance as yf  # type: ignore[import-not-found]

    ticker = yf.Ticker(symbol)
    if start and end:
        df = ticker.history(start=start, end=end, interval=interval, auto_adjust=True)
        source_url = (
            f"yfinance://Ticker({symbol}).history(start={start}, "
            f"end={end}, interval={interval})"
        )
    else:
        df = ticker.history(period=period, interval=interval, auto_adjust=True)
        source_url = f"yfinance://Ticker({symbol}).history(period={period}, interval={interval})"
    if df is None or df.empty:
        if start and end:
            raise RuntimeError(f"yfinance empty result for {symbol} start={start} end={end}")
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
            source_url=source_url,
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


# ---------- provider: Twelve Data (stocks/ETF/FX/crypto, API key) ----------

def fetch_twelvedata(symbol: str, period: str = "1y", interval: str = "1d",
                     ttl_sec: int = DEFAULT_TTL_SEC,
                     start: str | None = None,
                     end: str | None = None,
                     outputsize: int | None = None) -> dict[str, Any]:
    """Fetch OHLCV through Twelve Data `/time_series`.

    Official interval names use `1day`, `1week`, `1month`, `1h`, etc. The
    Finance Lab accepts `1d` as alias for compatibility with yfinance.
    """
    api_key = _read_opt_env_key("TWELVE_DATA_API_KEY", "TWELVEDATA_API_KEY")
    if not api_key:
        raise RuntimeError("Twelve Data API key not found in env or /opt/.env")

    interval_map = {"1d": "1day", "1wk": "1week", "1mo": "1month"}
    td_interval = interval_map.get(interval, interval)
    cache_start = start or period
    cache_end = end or "now"
    cache_p = _cache_path("twelvedata", symbol, cache_start, cache_end, td_interval)
    cached = _cache_load(cache_p, ttl_sec)
    if cached is not None:
        return _arrayify(cached)

    if outputsize is None:
        period_sizes = {
            "1mo": 32,
            "3mo": 95,
            "6mo": 190,
            "1y": 370,
            "2y": 740,
            "5y": 1850,
            "10y": 3700,
        }
        outputsize = period_sizes.get(period, 370)
    outputsize = max(1, min(int(outputsize), 5000))

    params: dict[str, Any] = {
        "symbol": symbol,
        "interval": td_interval,
        "apikey": api_key,
        "format": "JSON",
        "order": "asc",
        "adjust": "all",
    }
    if start:
        params["start_date"] = start
    if end:
        params["end_date"] = end
    if not start and not end:
        params["outputsize"] = outputsize

    url = f"{TWELVE_DATA_BASE}/time_series"
    with httpx.Client(timeout=30.0, headers={"User-Agent": UA}) as client:
        r = client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    if data.get("status") == "error":
        raise RuntimeError(f"Twelve Data error for {symbol}: {data.get('message') or data}")
    values = data.get("values") or []
    if not values:
        raise RuntimeError(f"Twelve Data empty result for {symbol}")

    # `order=asc` should already sort oldest -> newest, but keep deterministic.
    values = sorted(values, key=lambda row: str(row.get("datetime", "")))
    dates = [str(row.get("datetime", ""))[:10] for row in values]
    open_ = [float(row["open"]) for row in values]
    high = [float(row["high"]) for row in values]
    low = [float(row["low"]) for row in values]
    close = [float(row["close"]) for row in values]
    volume = [
        float(row.get("volume") or 0.0)
        for row in values
    ] if any("volume" in row for row in values) else None
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}

    payload = {
        "symbol": symbol,
        "provider": "twelvedata",
        "interval": "1d" if td_interval == "1day" else td_interval,
        "dates": dates,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "data_card": _data_card(
            provider="twelvedata",
            symbol=str(meta.get("symbol") or symbol),
            source_url=(
                f"{url}?symbol={symbol}&interval={td_interval}"
                f"&start_date={start or ''}&end_date={end or ''}&outputsize={outputsize}"
            ),
            license_str="Twelve Data API terms; API key external; verify redistribution rights",
            dates=dates,
            frequency="daily" if td_interval == "1day" else td_interval,
        ),
    }
    payload["data_card"]["exchange"] = meta.get("exchange")
    payload["data_card"]["mic_code"] = meta.get("mic_code")
    payload["data_card"]["currency"] = meta.get("currency")
    payload["data_card"]["asset_type"] = meta.get("type")
    payload["data_card"]["adjustments"] = "adjust=all"

    _cache_store(cache_p, payload)
    return _arrayify(payload)


# ---------- provider: EODHD (end-of-day historical, API token) ----------

def _eodhd_symbol(symbol: str) -> str:
    """Map local symbol notation to EODHD notation.

    EODHD generally expects exchange suffixes, e.g. SPY.US. If a suffix is
    already present, preserve it.
    """
    sym = symbol.upper()
    if "." in sym:
        return sym
    if sym.endswith("=X"):
        return sym
    return f"{sym}.US"


def fetch_eodhd(symbol: str, period: str = "1y", interval: str = "1d",
                ttl_sec: int = DEFAULT_TTL_SEC,
                start: str | None = None,
                end: str | None = None) -> dict[str, Any]:
    """Fetch EOD historical OHLCV through EODHD.

    Free plan is limited, so this provider is intended for spot cross-checks
    rather than broad scans.
    """
    api_token = _read_opt_env_key("EODHD_API_TOKEN", "EODHD_API_KEY")
    if not api_token:
        raise RuntimeError("EODHD API token not found in env or /opt/.env")
    if interval not in {"1d", "d"}:
        raise ValueError("EODHD provider currently supports daily interval only")

    eod_symbol = _eodhd_symbol(symbol)
    cache_start = start or period
    cache_end = end or "now"
    cache_p = _cache_path("eodhd", eod_symbol, cache_start, cache_end, "1d")
    cached = _cache_load(cache_p, ttl_sec)
    if cached is not None:
        return _arrayify(cached)

    params: dict[str, Any] = {
        "api_token": api_token,
        "fmt": "json",
        "period": "d",
    }
    if start:
        params["from"] = start
    if end:
        params["to"] = end

    url = f"{EODHD_BASE}/eod/{eod_symbol}"
    with httpx.Client(timeout=30.0, headers={"User-Agent": UA}) as client:
        r = client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    if isinstance(data, dict) and data.get("message"):
        raise RuntimeError(f"EODHD error for {eod_symbol}: {data.get('message')}")
    if not isinstance(data, list) or not data:
        raise RuntimeError(f"EODHD empty result for {eod_symbol}")

    rows = sorted(data, key=lambda row: str(row.get("date", "")))
    dates = [str(row["date"])[:10] for row in rows]
    open_ = [float(row["open"]) for row in rows]
    high = [float(row["high"]) for row in rows]
    low = [float(row["low"]) for row in rows]
    close = [float(row.get("adjusted_close") or row["close"]) for row in rows]
    volume = [float(row.get("volume") or 0.0) for row in rows]

    payload = {
        "symbol": symbol.upper(),
        "provider": "eodhd",
        "interval": "1d",
        "dates": dates,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "data_card": _data_card(
            provider="eodhd",
            symbol=eod_symbol,
            source_url=f"{url}?from={start or ''}&to={end or ''}&period=d&fmt=json",
            license_str="EODHD API terms; token external; free plan limited; verify redistribution rights",
            dates=dates,
            frequency="daily",
        ),
    }
    payload["data_card"]["adjustments"] = "close uses adjusted_close when present"
    payload["data_card"]["free_plan_note"] = "Free tier is limited; use for spot checks, not broad scans."

    _cache_store(cache_p, payload)
    return _arrayify(payload)


# ---------- provider: Coinbase Exchange (crypto spot OHLCV, no auth) ----------

def _coinbase_product(symbol: str) -> str:
    """Map common local crypto symbols to Coinbase Exchange product ids."""
    sym = symbol.upper().replace("_", "-")
    aliases = {
        "BTC": "BTC-USD",
        "BITCOIN": "BTC-USD",
        "ETH": "ETH-USD",
        "ETHEREUM": "ETH-USD",
    }
    return aliases.get(sym, sym)


def fetch_coinbase(symbol: str, period: str = "1y", interval: str = "1d",
                   ttl_sec: int = DEFAULT_TTL_SEC,
                   start: str | None = None,
                   end: str | None = None) -> dict[str, Any]:
    """Fetch crypto OHLCV through Coinbase Exchange public candles.

    Coinbase Exchange caps a single candle request at 300 buckets. Daily
    discovery windows are therefore fine; broader history should be chunked by
    a future manifest rather than hidden inside this adapter.
    """
    if interval not in {"1d", "d"}:
        raise ValueError("Coinbase provider currently supports daily interval only")
    if (start is None) ^ (end is None):
        raise ValueError("Coinbase explicit window requires both start and end")

    product = _coinbase_product(symbol)
    cache_start = start or period
    cache_end = end or "now"
    cache_p = _cache_path("coinbase", product, cache_start, cache_end, "1d")
    cached = _cache_load(cache_p, ttl_sec)
    if cached is not None:
        return _arrayify(cached)

    if not start or not end:
        days_by_period = {
            "1mo": 31,
            "3mo": 92,
            "6mo": 184,
            "1y": 365,
        }
        days = days_by_period.get(period, 92)
        if days > 300:
            raise ValueError("Coinbase single-request daily window must be <= 300 candles; pass --start/--end")
        end_dt = datetime.now(timezone.utc).date()
        start_dt = end_dt - timedelta(days=days)
        start = start_dt.isoformat()
        end = end_dt.isoformat()

    start_date = datetime.fromisoformat(start).date()
    end_date = datetime.fromisoformat(end).date()
    if (end_date - start_date).days > 300:
        raise ValueError("Coinbase single-request daily window must be <= 300 candles")

    url = f"{COINBASE_EXCHANGE_BASE}/products/{product}/candles"
    params = {"start": start, "end": end, "granularity": 86_400}
    with httpx.Client(timeout=30.0, headers={"User-Agent": UA}) as client:
        r = client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    if not isinstance(data, list) or not data:
        raise RuntimeError(f"Coinbase empty result for {product}")

    rows = sorted(data, key=lambda row: int(row[0]))
    dates = [datetime.fromtimestamp(int(row[0]), tz=timezone.utc).strftime("%Y-%m-%d") for row in rows]
    low = [float(row[1]) for row in rows]
    high = [float(row[2]) for row in rows]
    open_ = [float(row[3]) for row in rows]
    close = [float(row[4]) for row in rows]
    volume = [float(row[5]) for row in rows] if any(len(row) > 5 for row in rows) else None

    payload = {
        "symbol": product,
        "provider": "coinbase",
        "interval": "1d",
        "dates": dates,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "data_card": _data_card(
            provider="coinbase",
            symbol=product,
            source_url=f"{url}?start={start}&end={end}&granularity=86400",
            license_str="Coinbase Exchange API terms; public candles; verify redistribution rights",
            dates=dates,
            frequency="daily",
        ),
    }
    payload["data_card"]["exchange"] = "Coinbase Exchange"
    payload["data_card"]["bucket_limit"] = "Single request limited to 300 candles by provider contract."
    payload["data_card"]["incompleteness_note"] = "Provider notes historical rates may be incomplete when no ticks exist."

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
        start = kwargs.get("start")
        end = kwargs.get("end")
        return fetch_yfinance(symbol, period, interval, ttl, start=start, end=end)
    if provider == "coingecko":
        days = int(kwargs.get("days", 365))
        ttl = int(kwargs.get("ttl_sec", DEFAULT_TTL_SEC))
        return fetch_coingecko(symbol, days, ttl)
    if provider == "twelvedata":
        period = kwargs.get("period", "1y")
        interval = kwargs.get("interval", "1d")
        ttl = int(kwargs.get("ttl_sec", DEFAULT_TTL_SEC))
        start = kwargs.get("start")
        end = kwargs.get("end")
        outputsize = kwargs.get("outputsize")
        return fetch_twelvedata(symbol, period, interval, ttl, start=start, end=end, outputsize=outputsize)
    if provider == "eodhd":
        period = kwargs.get("period", "1y")
        interval = kwargs.get("interval", "1d")
        ttl = int(kwargs.get("ttl_sec", DEFAULT_TTL_SEC))
        start = kwargs.get("start")
        end = kwargs.get("end")
        return fetch_eodhd(symbol, period, interval, ttl, start=start, end=end)
    if provider == "coinbase":
        period = kwargs.get("period", "3mo")
        interval = kwargs.get("interval", "1d")
        ttl = int(kwargs.get("ttl_sec", DEFAULT_TTL_SEC))
        start = kwargs.get("start")
        end = kwargs.get("end")
        return fetch_coinbase(symbol, period, interval, ttl, start=start, end=end)
    raise ValueError(f"Unknown provider: {provider}. Supported: yfinance, coingecko, twelvedata, eodhd, coinbase")


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
    ap.add_argument("--provider", choices=["yfinance", "coingecko", "twelvedata", "eodhd", "coinbase"], required=True)
    ap.add_argument("--symbol", required=True,
                    help="SPY/QQQ/^GSPC for equity providers; bitcoin/ethereum for coingecko; BTC-USD/ETH-USD for coinbase")
    ap.add_argument("--period", default="1y",
                    help="yfinance period: 1mo/3mo/6mo/1y/2y/5y/10y/max (yfinance only)")
    ap.add_argument("--start", help="yfinance explicit start date YYYY-MM-DD")
    ap.add_argument("--end", help="yfinance explicit end date YYYY-MM-DD")
    ap.add_argument("--interval", default="1d",
                    help="yfinance interval: 1d/1wk/1mo/1h (yfinance only)")
    ap.add_argument("--days", type=int, default=365, help="coingecko only")
    ap.add_argument("--outputsize", type=int, help="twelvedata only")
    ap.add_argument("--ttl", type=int, default=DEFAULT_TTL_SEC)
    ap.add_argument("--json", action="store_true", help="Print full payload as JSON")
    args = ap.parse_args()

    kwargs: dict[str, Any] = {"ttl_sec": args.ttl}
    if args.provider in {"yfinance", "twelvedata", "eodhd", "coinbase"}:
        kwargs["period"] = args.period
        kwargs["interval"] = args.interval
        if args.outputsize:
            kwargs["outputsize"] = args.outputsize
        if args.start or args.end:
            kwargs["start"] = args.start
            kwargs["end"] = args.end
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
