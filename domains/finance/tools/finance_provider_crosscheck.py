#!/usr/bin/env python3
"""Cross-check yfinance and Twelve Data daily bars.

Read-only with respect to trading: fetches/caches market data and compares
same-date closes before Finance uses a symbol/window as paper-live substrate.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from market_data import fetch  # noqa: E402


SCHEMA = "dndlab.finance.provider_crosscheck.value.v1"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


ROOT = repo_root()
VALUE_DIR = ROOT / "data" / "finance" / "value"
CHECK_DIR = ROOT / "data" / "finance" / "provider_crosscheck"


def rel(path: Path | None) -> str | None:
    if not path:
        return None
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def row_map(data: dict[str, Any]) -> dict[str, dict[str, float]]:
    dates = [str(x) for x in data.get("dates") or []]
    close = data.get("close")
    volume = data.get("volume")
    out: dict[str, dict[str, float]] = {}
    for idx, date in enumerate(dates):
        close_value = float(close[idx])
        item = {"close": close_value}
        if volume is not None and idx < len(volume):
            item["volume"] = float(volume[idx])
        out[date] = item
    return out


def close_diff_bps(a: float, b: float) -> float:
    denom = (abs(a) + abs(b)) / 2.0
    return abs(a - b) / denom * 10_000 if denom else math.inf


def compare_symbol(symbol: str, start: str, end: str, tolerance_bps: float, ttl_sec: int,
                   include_eodhd: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    provider_data: dict[str, dict[str, Any]] = {}
    try:
        yf = fetch("yfinance", symbol, start=start, end=end, interval="1d", ttl_sec=ttl_sec)
        provider_data["yfinance"] = yf
    except Exception as exc:
        yf = None
        errors.append(f"yfinance:{exc}")
    try:
        td = fetch("twelvedata", symbol, start=start, end=end, interval="1d", ttl_sec=ttl_sec)
        provider_data["twelvedata"] = td
    except Exception as exc:
        td = None
        errors.append(f"twelvedata:{exc}")
    if include_eodhd:
        try:
            eodhd = fetch("eodhd", symbol, start=start, end=end, interval="1d", ttl_sec=ttl_sec)
            provider_data["eodhd"] = eodhd
        except Exception as exc:
            errors.append(f"eodhd:{exc}")

    required = {"yfinance", "twelvedata"} | ({"eodhd"} if include_eodhd else set())
    if not required.issubset(provider_data):
        return {
            "symbol": symbol,
            "status": "REVIEW_REQUIRED",
            "errors": errors,
            "common_dates": 0,
            "within_tolerance": False,
        }

    mapped = {name: row_map(data) for name, data in provider_data.items()}
    common_sets = [set(rows) for rows in mapped.values()]
    common = sorted(set.intersection(*common_sets)) if common_sets else []
    diffs = []
    for date in common:
        closes = {name: rows[date]["close"] for name, rows in mapped.items()}
        pair_diffs = {}
        names = sorted(closes)
        for idx, name_a in enumerate(names):
            for name_b in names[idx + 1:]:
                pair_diffs[f"{name_a}_vs_{name_b}_bps"] = close_diff_bps(closes[name_a], closes[name_b])
        diffs.append({"date": date, **{f"{name}_close": value for name, value in closes.items()}, **pair_diffs})
    all_pair_diffs = [
        value
        for row in diffs
        for key, value in row.items()
        if key.endswith("_bps")
    ]
    max_diff = max(all_pair_diffs, default=math.inf)
    median_diff = sorted(all_pair_diffs)[len(all_pair_diffs) // 2] if all_pair_diffs else math.inf
    within = bool(common) and max_diff <= tolerance_bps
    return {
        "symbol": symbol,
        "status": "OK",
        "common_dates": len(common),
        "first_common_date": common[0] if common else None,
        "last_common_date": common[-1] if common else None,
        "provider_dates": {
            name: [min(rows), max(rows)] if rows else []
            for name, rows in mapped.items()
        },
        "max_close_diff_bps": max_diff if math.isfinite(max_diff) else None,
        "median_close_diff_bps": median_diff if math.isfinite(median_diff) else None,
        "within_tolerance": within,
        "tolerance_bps": tolerance_bps,
        "providers": sorted(provider_data),
        "sample_diffs": diffs[-5:],
        "data_cards": {
            name: data.get("data_card")
            for name, data in provider_data.items()
        },
    }


def build_payload(symbols: list[str], start: str, end: str, tolerance_bps: float, ttl_sec: int,
                  include_eodhd: bool = False) -> dict[str, Any]:
    rows = [compare_symbol(symbol, start, end, tolerance_bps, ttl_sec, include_eodhd) for symbol in symbols]
    ok_rows = [row for row in rows if row.get("status") == "OK"]
    review_rows = [row for row in rows if row.get("status") != "OK"]
    failed_tolerance = [row for row in ok_rows if not row.get("within_tolerance")]
    all_ready = bool(ok_rows) and not review_rows and not failed_tolerance
    decision = "ready_for_cross_provider_diagnostic" if all_ready else "review_before_paper_live_sim"
    summary = {
        "status": "pass" if all_ready else "warn" if ok_rows else "fail",
        "decision": decision,
        "symbols": symbols,
        "window": {"start": start, "end": end},
        "ok": len(ok_rows),
        "review_required": len(review_rows),
        "failed_tolerance": len(failed_tolerance),
        "tolerance_bps": tolerance_bps,
        "providers_required": ["yfinance", "twelvedata"] + (["eodhd"] if include_eodhd else []),
    }
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(UTC).isoformat(),
        "domain": "finance",
        "intent": "Verify that yfinance and Twelve Data agree enough before Finance promotes daily bars toward autonomy.",
        "summary": summary,
        "rows": rows,
        "boundary": "Provider agreement is data readiness only; it is not a trading signal, paper decision or broker authorization.",
        "cards": [
            {
                "claim_id": "finance_provider_crosscheck",
                "title": "Finance provider cross-check",
                "decision": "test" if all_ready else "watch",
                "evidence": f"{len(ok_rows)}/{len(rows)} OK; {len(failed_tolerance)} failed tolerance; {len(review_rows)} review.",
                "boundary": "Cross-provider agreement can support diagnostic discovery, not execution.",
            }
        ],
    }


def write_payload(payload: dict[str, Any]) -> dict[str, str]:
    VALUE_DIR.mkdir(parents=True, exist_ok=True)
    CHECK_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    check_path = CHECK_DIR / f"finance_provider_crosscheck_{stamp}.json"
    value_path = VALUE_DIR / f"finance_provider_crosscheck_{stamp}.json"
    latest_path = VALUE_DIR / "finance_provider_crosscheck_latest.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    check_path.write_text(text, encoding="utf-8")
    value_path.write_text(text, encoding="utf-8")
    latest_path.write_text(text, encoding="utf-8")
    return {"check": rel(check_path) or str(check_path), "stamped": rel(value_path) or str(value_path), "latest": rel(latest_path) or str(latest_path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default="SPY,QQQ,IWM,EFA,TLT,GLD")
    parser.add_argument("--start", default="2026-05-20")
    parser.add_argument("--end", default="2026-05-27")
    parser.add_argument("--tolerance-bps", type=float, default=25.0)
    parser.add_argument("--include-eodhd", action="store_true", help="include EODHD as third provider; use sparingly")
    parser.add_argument("--ttl", type=int, default=86_400)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
    payload = build_payload(symbols, args.start, args.end, args.tolerance_bps, args.ttl, args.include_eodhd)
    if args.write:
        payload["written"] = write_payload(payload)
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"status": payload["summary"]["status"], "written": payload.get("written")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
