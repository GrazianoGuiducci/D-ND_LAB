#!/usr/bin/env python3
"""biosignal_data.py — acquisizione biosegnali per il D-ND bio-rhythms lab.

Provider abstraction (intent OpenBB): un singolo schema, N fonti dietro.
Provider iniziale: PhysioNet — record pubblici di RR-interval e ECG via
mirror HTTPS (no auth, license PhysioNet/CC).

Schema universale di ritorno (numpy + dict, NIENTE pandas):

    {
        "record": "nsr2db/sel100",
        "provider": "physionet",
        "signal": "RR",
        "rr_ms":   np.ndarray,   # RR-intervals in milliseconds
        "n_obs":   int,
        "data_card": { ... }     # provenance, license, retrieval_ts
    }

Caching su disco con TTL + data_card first-class. Stesso pattern del
tool finance/market_data.py.

CLI:
    python biosignal_data.py --provider physionet --record nsr2db/sel100 --signal RR
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import numpy as np


VERSION = "0.1.0"

DOMAIN_DIR = Path(__file__).resolve().parents[1]
CACHE_DIR = DOMAIN_DIR.parent.parent / "data" / "bio-rhythms" / "biosignal_cache"
DEFAULT_TTL_SEC = 86_400  # 1 day

# PhysioNet pubblica annotations e RR via mirror HTTPS.
# Per ora supportiamo un endpoint generico che restituisce CSV con una colonna
# di RR-intervals. Per record che non hanno questo formato pre-cooked, il
# tool genera fallback synthetic con un seed deterministico sul nome record.
PHYSIONET_BASE = "https://physionet.org/files/"

UA = "D-ND-Lab/1.0 (research; +https://lab.d-nd.com)"


# ---------- cache ----------

def _cache_key(provider: str, record: str, signal: str) -> str:
    raw = f"{provider}|{record.lower()}|{signal.lower()}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _cache_path(provider: str, record: str, signal: str) -> Path:
    key = _cache_key(provider, record, signal)
    safe_record = record.lower().replace("/", "_")
    return CACHE_DIR / f"{provider}_{safe_record}_{signal}_{key}.json"


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

def _data_card(provider: str, record: str, source_url: str, license_str: str,
               n_obs: int, signal: str, fallback: bool = False) -> dict[str, Any]:
    return {
        "retrieval_ts": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "record": record,
        "signal": signal,
        "source_url": source_url,
        "license": license_str,
        "n_obs": n_obs,
        "fetcher_version": VERSION,
        "fallback_synthetic": fallback,
    }


# ---------- provider: physionet (RR via mirror CSV best-effort) ----------

def fetch_physionet(record: str, signal: str = "RR",
                    ttl_sec: int = DEFAULT_TTL_SEC) -> dict[str, Any]:
    """Fetch RR-interval series from PhysioNet.

    record: "<database>/<record_id>", e.g. "nsr2db/sel100", "afdb/04015".
    signal: "RR" (default) or "ECG" (not yet implemented).

    Implementation note: PhysioNet stores ECG in WFDB binary format
    (.dat + .hea). For minimal-deps acquisition we try a CSV/TXT
    annotation-derived RR file when available; otherwise fall back to
    synthetic with a deterministic seed from the record name. The
    fallback is marked in data_card.fallback_synthetic = true so the
    consumer knows.
    """
    if signal != "RR":
        raise NotImplementedError("Only signal='RR' supported in v0.1.0; ECG raw needs wfdb dep")

    cache_p = _cache_path("physionet", record, signal)
    cached = _cache_load(cache_p, ttl_sec)
    if cached is not None:
        return _arrayify(cached)

    # Try a few CSV/TXT path conventions on the public mirror.
    candidate_urls = [
        f"{PHYSIONET_BASE}{record}.atr.txt",
        f"{PHYSIONET_BASE}{record}.rr.csv",
        f"{PHYSIONET_BASE}{record}.rr.txt",
    ]
    rr_ms: list[float] = []
    fetched_url = ""
    fallback = False

    for url in candidate_urls:
        try:
            with httpx.Client(timeout=15.0, headers={"User-Agent": UA}) as client:
                r = client.get(url)
                if r.status_code != 200:
                    continue
                text = r.text
                if len(text.strip()) < 10:
                    continue
                # Parse: one RR value per line, or CSV with rr column
                values: list[float] = []
                for line in text.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    # split on comma or whitespace, take last numeric token
                    parts = [p for p in line.replace(",", " ").split() if p]
                    for p in reversed(parts):
                        try:
                            v = float(p)
                            # heuristic: RR in ms typically 250-2000;
                            # if value < 5 might be seconds
                            if 0.25 < v < 2.5:
                                v *= 1000.0
                            if 200 < v < 3000:
                                values.append(v)
                                break
                        except ValueError:
                            continue
                if len(values) >= 50:
                    rr_ms = values
                    fetched_url = url
                    break
        except Exception:
            continue

    if not rr_ms:
        # Fallback: synthetic with deterministic seed from record name.
        # Marked explicitly in data_card so the consumer knows.
        seed = abs(hash(record)) % (2 ** 31 - 1)
        rng = np.random.default_rng(seed)
        n = 600
        # plausible HRV under regime shift rest → activity
        split = n // 2
        rest = rng.normal(900.0, 35.0, split)
        active = rng.normal(680.0, 75.0, n - split)
        rr_ms = [float(x) for x in np.concatenate([rest, active])]
        fetched_url = "synthetic_fallback (record not retrievable from public mirror)"
        fallback = True

    license_str = (
        "PhysioNet Restricted Health Data License (research use; "
        "verify per-database before redistribution)"
        if not fallback else
        "Synthetic fallback — no license claim, marked in data_card"
    )

    payload = {
        "record": record,
        "provider": "physionet",
        "signal": signal,
        "rr_ms": rr_ms,
        "data_card": _data_card(
            provider="physionet",
            record=record,
            source_url=fetched_url,
            license_str=license_str,
            n_obs=len(rr_ms),
            signal=signal,
            fallback=fallback,
        ),
    }
    _cache_store(cache_p, payload)
    return _arrayify(payload)


# ---------- normalization ----------

def _arrayify(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    if "rr_ms" in out and out["rr_ms"] is not None:
        out["rr_ms"] = np.asarray(out["rr_ms"], dtype=float)
    out["n_obs"] = len(out["rr_ms"]) if out.get("rr_ms") is not None else 0
    return out


# ---------- public dispatch ----------

def fetch(provider: str, record: str, **kwargs: Any) -> dict[str, Any]:
    """Provider dispatch. Stesso schema in uscita."""
    if provider == "physionet":
        signal = kwargs.get("signal", "RR")
        ttl = int(kwargs.get("ttl_sec", DEFAULT_TTL_SEC))
        return fetch_physionet(record, signal, ttl)
    raise ValueError(f"Unknown provider: {provider}. Supported: physionet")


# ---------- CLI ----------

def _summarize(d: dict[str, Any]) -> dict[str, Any]:
    rr = d["rr_ms"]
    return {
        "record": d["record"],
        "provider": d["provider"],
        "signal": d["signal"],
        "n_obs": d["n_obs"],
        "rr_mean_ms": float(rr.mean()) if len(rr) else None,
        "rr_std_ms": float(rr.std()) if len(rr) else None,
        "rr_min_ms": float(rr.min()) if len(rr) else None,
        "rr_max_ms": float(rr.max()) if len(rr) else None,
        "fallback_synthetic": d["data_card"].get("fallback_synthetic", False),
        "source_url": d["data_card"].get("source_url"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--provider", choices=["physionet"], default="physionet")
    ap.add_argument("--record", required=True,
                    help="Database/record path, e.g. nsr2db/sel100, afdb/04015")
    ap.add_argument("--signal", default="RR", choices=["RR"])
    ap.add_argument("--ttl", type=int, default=DEFAULT_TTL_SEC)
    ap.add_argument("--json", action="store_true", help="Print full payload as JSON")
    args = ap.parse_args()

    try:
        d = fetch(args.provider, args.record, signal=args.signal, ttl_sec=args.ttl)
    except Exception as e:
        print(json.dumps({"error": str(e), "provider": args.provider, "record": args.record}),
              file=sys.stderr)
        return 2

    if args.json:
        out = dict(d)
        if isinstance(out.get("rr_ms"), np.ndarray):
            out["rr_ms"] = out["rr_ms"].tolist()
        print(json.dumps(out, indent=2, default=str))
    else:
        print(json.dumps(_summarize(d), indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
