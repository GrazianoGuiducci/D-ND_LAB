#!/usr/bin/env python3
"""Window/universe scout for Finance candidate discovery.

Low-cost first pass: use no/low-auth market feeds to identify which asset/window
pairs deserve expensive cross-provider validation. It does not promote trades,
paper/live-sim, or broker actions.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from exp_regime_shift import run_experiment  # noqa: E402
from finance_transfer_diagnostic import finite, null_stats  # noqa: E402
from market_data import fetch  # noqa: E402


SCHEMA = "dndlab.finance.window_universe_scout.value.v1"


@dataclass(frozen=True)
class SymbolSpec:
    symbol: str
    provider: str
    asset_class: str


DEFAULT_UNIVERSE = [
    SymbolSpec("SPY", "yfinance", "us_equity_index"),
    SymbolSpec("QQQ", "yfinance", "us_growth_equity"),
    SymbolSpec("IWM", "yfinance", "us_small_caps"),
    SymbolSpec("DIA", "yfinance", "us_large_value"),
    SymbolSpec("EFA", "yfinance", "developed_ex_us"),
    SymbolSpec("EEM", "yfinance", "emerging_markets"),
    SymbolSpec("TLT", "yfinance", "long_bonds"),
    SymbolSpec("IEF", "yfinance", "intermediate_bonds"),
    SymbolSpec("GLD", "yfinance", "gold"),
    SymbolSpec("SLV", "yfinance", "silver"),
    SymbolSpec("USO", "yfinance", "oil_proxy"),
    SymbolSpec("UUP", "yfinance", "usd_index_proxy"),
    SymbolSpec("FXE", "yfinance", "eur_usd_proxy"),
    SymbolSpec("FXY", "yfinance", "jpy_usd_proxy"),
    SymbolSpec("BTC-USD", "coinbase", "crypto_asset_class"),
    SymbolSpec("ETH-USD", "coinbase", "crypto_asset_class"),
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


ROOT = repo_root()
VALUE_DIR = ROOT / "data" / "finance" / "value"
SCOUT_DIR = ROOT / "data" / "finance" / "window_universe_scout"


def rel(path: Path | None) -> str | None:
    if not path:
        return None
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def write_json_pair(payload: dict[str, Any]) -> dict[str, str]:
    SCOUT_DIR.mkdir(parents=True, exist_ok=True)
    VALUE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    artifact = SCOUT_DIR / f"finance_window_universe_scout_{stamp}.json"
    value_path = VALUE_DIR / f"finance_window_universe_scout_{stamp}.json"
    latest = VALUE_DIR / "finance_window_universe_scout_latest.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    artifact.write_text(text, encoding="utf-8")
    value_path.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    return {
        "artifact": rel(artifact) or str(artifact),
        "stamped": rel(value_path) or str(value_path),
        "latest": rel(latest) or str(latest),
    }


def parse_universe(raw: str | None) -> list[SymbolSpec]:
    if not raw:
        return DEFAULT_UNIVERSE
    specs: list[SymbolSpec] = []
    for item in raw.split(","):
        symbol = item.strip().upper()
        if not symbol:
            continue
        provider = "coinbase" if symbol in {"BTC", "BTC-USD", "ETH", "ETH-USD"} else "yfinance"
        specs.append(SymbolSpec(symbol, provider, "operator_supplied"))
    return specs


def window_start(end: date, days: int) -> str:
    return (end - timedelta(days=days)).isoformat()


def row_score(row: dict[str, Any]) -> float:
    if row.get("status") != "OK":
        return -1.0
    iid_z = row.get("iid", {}).get("effect_z") or 0.0
    b5_z = row.get("block5", {}).get("effect_z") or 0.0
    b21_z = row.get("block21", {}).get("effect_z") or 0.0
    confirmations = sum(
        1
        for key in ("iid", "block5", "block21")
        if row.get(key, {}).get("verdict") == "DND_DELTA"
    )
    return float(confirmations * 10.0 + max(0.0, iid_z) + max(0.0, b5_z) * 0.7 + max(0.0, b21_z) * 0.5)


def run_symbol_window(spec: SymbolSpec, *, start: str, end: str, seed: int, shuffles: int) -> dict[str, Any]:
    try:
        data = fetch(spec.provider, spec.symbol, start=start, end=end, interval="1d")
        returns = np.asarray(data["returns"], dtype=float)
        if len(returns) < 20:
            raise RuntimeError(f"not enough returns for scout: {len(returns)}")
        iid = run_experiment(
            shuffles=shuffles,
            seed=seed,
            real_returns=returns,
            real_meta=data["data_card"],
        )
        block5 = null_stats(returns, seed=seed + 9005, shuffles=shuffles, block=5)
        block21 = null_stats(returns, seed=seed + 9021, shuffles=shuffles, block=21)
        card = iid.get("data_card") or {}
        row = {
            "symbol": data["symbol"],
            "provider": spec.provider,
            "asset_class": spec.asset_class,
            "status": "OK",
            "requested_start": start,
            "requested_end": end,
            "actual_start": card.get("first_date"),
            "actual_end": card.get("last_date"),
            "n": iid["n"],
            "iid": {
                "verdict": iid["verdict"],
                "effect_z": finite(float(iid["effect_z"])),
                "ordered": finite(float(iid["ordered"])),
                "shuffle_mean": finite(float(iid["shuffle_mean"])),
            },
            "block5": block5,
            "block21": block21,
            "robust_all_nulls": all(
                item["verdict"] == "DND_DELTA"
                for item in ({"verdict": iid["verdict"]}, block5, block21)
            ),
            "partial_confirmations": sum(
                item["verdict"] == "DND_DELTA"
                for item in ({"verdict": iid["verdict"]}, block5, block21)
            ),
            "var_95": finite(float(iid["var_95"])),
            "realized_vol": finite(float(iid["realized_vol"])),
            "data_card": card,
        }
        row["scout_score"] = row_score(row)
        return row
    except Exception as exc:
        return {
            "symbol": spec.symbol,
            "provider": spec.provider,
            "asset_class": spec.asset_class,
            "status": "REVIEW_REQUIRED",
            "requested_start": start,
            "requested_end": end,
            "error": str(exc),
            "scout_score": -1.0,
        }


def build_payload(symbols: list[SymbolSpec], windows: list[int], end: str, seed: int, shuffles: int) -> dict[str, Any]:
    end_date = datetime.fromisoformat(end).date()
    rows: list[dict[str, Any]] = []
    for window_days in windows:
        start = window_start(end_date, window_days)
        for spec in symbols:
            row = run_symbol_window(spec, start=start, end=end, seed=seed + window_days, shuffles=shuffles)
            row["window_days"] = window_days
            rows.append(row)

    ok_rows = [row for row in rows if row.get("status") == "OK"]
    robust = [row for row in ok_rows if row.get("robust_all_nulls")]
    partial = [row for row in ok_rows if row.get("partial_confirmations", 0) > 0 and not row.get("robust_all_nulls")]
    review = [row for row in rows if row.get("status") != "OK"]
    ranked = sorted(ok_rows, key=lambda row: row.get("scout_score", -1.0), reverse=True)
    selected_for_crosscheck = [
        {
            "symbol": row["symbol"],
            "provider": row["provider"],
            "asset_class": row["asset_class"],
            "window_days": row["window_days"],
            "start": row["requested_start"],
            "end": row["requested_end"],
            "scout_score": row["scout_score"],
            "robust_all_nulls": row["robust_all_nulls"],
            "partial_confirmations": row["partial_confirmations"],
        }
        for row in ranked[:6]
        if row.get("robust_all_nulls") or row.get("partial_confirmations", 0) > 0
    ]

    if robust:
        decision = "send_robust_scout_rows_to_cross_provider_validation"
        next_gate = "Validate robust rows with provider cross-check or recurrence before paper/live-sim."
    elif selected_for_crosscheck:
        decision = "review_partial_rows_before_cross_provider_spend"
        next_gate = "Human/system review should choose whether partial rows deserve cross-provider cost."
    else:
        decision = "redesign_universe_or_null_family"
        next_gate = "No useful scout rows; change universe/window/null family before spending API budget."

    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(UTC).isoformat(),
        "domain": "finance",
        "intent": "Select candidate symbol/window pairs before spending cross-provider API budget.",
        "summary": {
            "decision": decision,
            "end": end,
            "windows_days": windows,
            "symbols": [spec.symbol for spec in symbols],
            "rows": len(rows),
            "ok_rows": len(ok_rows),
            "review_required_rows": len(review),
            "robust_rows": len(robust),
            "partial_rows": len(partial),
            "selected_for_crosscheck": selected_for_crosscheck,
            "paper_live_sim_allowed": False,
            "broker_sandbox_allowed": False,
            "real_execution_allowed": False,
            "next_gate": next_gate,
        },
        "design_contract": {
            "object": "low-cost multi-window/multi-asset scout before cross-provider validation",
            "mechanism": "scan no/low-auth feeds for iid/block null hints, then spend stronger providers only on nominated rows",
            "falsifier": "no robust or partial rows means the current universe/window/null family has no useful candidate",
            "stop_rule": "do not open paper/live-sim from scout rows; require cross-provider validation and recurrence",
        },
        "rows": rows,
        "ranked_top": ranked[:10],
        "boundary": {
            "operational": False,
            "public_claim": False,
            "trading_signal": False,
            "paper_live_sim": False,
        },
        "cards": [
            {
                "claim_id": "finance_window_universe_scout",
                "title": "Finance window/universe scout",
                "decision": "test" if robust else "watch" if selected_for_crosscheck else "redesign",
                "evidence": f"rows={len(rows)}; robust={len(robust)}; partial={len(partial)}; review={len(review)}",
                "boundary": "Scout selects where to spend validation work; it is not a trading signal.",
            }
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", help="comma-separated symbols; default broad ETF/crypto universe")
    parser.add_argument("--windows", default="45,90,180", help="calendar-day windows ending at --end")
    parser.add_argument("--end", default="2026-05-27")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--shuffles", type=int, default=512)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    symbols = parse_universe(args.symbols)
    windows = [int(item.strip()) for item in args.windows.split(",") if item.strip()]
    payload = build_payload(symbols, windows, args.end, args.seed, args.shuffles)
    if args.write:
        payload["written"] = write_json_pair(payload)
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"status": "ok", "written": payload.get("written")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
