#!/usr/bin/env python3
"""Volatility/macro market-object review for Finance Lab.

Single assets, lag-memory partials and pair-relative objects can all fail
without proving that Finance is exhausted. This tool changes the object again:
it tests realized-volatility objects and volatility-spread objects across
rolling windows, still as diagnostic evidence only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from exp_regime_shift import run_experiment  # noqa: E402
from finance_transfer_diagnostic import finite, null_stats  # noqa: E402
from market_data import fetch  # noqa: E402


SCHEMA = "dndlab.finance.volatility_macro_object_review.value.v1"
DEFAULT_OBJECTS = [
    "vol:SPY",
    "vol:QQQ",
    "vol:TLT",
    "vol:GLD",
    "vol:UUP",
    "vol:BTC-USD",
    "vol:ETH-USD",
    "volspread:SPY/TLT",
    "volspread:GLD/SPY",
    "volspread:HYG/LQD",
    "volspread:UUP/SPY",
    "volspread:BTC-USD/ETH-USD",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


ROOT = repo_root()
VALUE_DIR = ROOT / "data" / "finance" / "value"
REVIEW_DIR = ROOT / "data" / "finance" / "volatility_macro_review"


def rel(path: Path | None) -> str | None:
    if not path:
        return None
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def provider(symbol: str) -> str:
    return "coinbase" if symbol in {"BTC-USD", "ETH-USD"} else "yfinance"


def rolling_windows(end: str, days: int, *, step_days: int, count: int) -> list[dict[str, str]]:
    end_dt = datetime.fromisoformat(end).date()
    windows = []
    for idx in range(count):
        shifted_end = end_dt - timedelta(days=idx * step_days)
        shifted_start = shifted_end - timedelta(days=days)
        windows.append({
            "label": "anchor" if idx == 0 else f"prev_step_{idx}",
            "start": shifted_start.isoformat(),
            "end": shifted_end.isoformat(),
        })
    return windows


def aligned_closes(left: dict[str, Any], right: dict[str, Any]) -> tuple[list[str], np.ndarray, np.ndarray]:
    left_dates = left.get("dates") or []
    right_dates = right.get("dates") or []
    left_close = np.asarray(left.get("close"), dtype=float)
    right_close = np.asarray(right.get("close"), dtype=float)
    lmap = {date: float(left_close[idx]) for idx, date in enumerate(left_dates)}
    rmap = {date: float(right_close[idx]) for idx, date in enumerate(right_dates)}
    dates = sorted(set(lmap).intersection(rmap))
    return dates, np.asarray([lmap[date] for date in dates], dtype=float), np.asarray([rmap[date] for date in dates], dtype=float)


def rolling_vol(log_returns: np.ndarray, window: int) -> np.ndarray:
    if len(log_returns) < window + 2:
        return np.asarray([], dtype=float)
    values = [
        float(np.std(log_returns[idx - window:idx], ddof=1))
        for idx in range(window, len(log_returns) + 1)
    ]
    return np.asarray(values, dtype=float)


def vol_change_object(close: np.ndarray, vol_window: int) -> np.ndarray:
    returns = np.diff(np.log(close))
    vol = rolling_vol(returns, vol_window)
    if len(vol) < 3:
        return np.asarray([], dtype=float)
    return np.diff(np.log(vol + 1e-9))


def vol_spread_object(left_close: np.ndarray, right_close: np.ndarray, vol_window: int) -> np.ndarray:
    left_vol = rolling_vol(np.diff(np.log(left_close)), vol_window)
    right_vol = rolling_vol(np.diff(np.log(right_close)), vol_window)
    n = min(len(left_vol), len(right_vol))
    if n < 3:
        return np.asarray([], dtype=float)
    spread = np.log(left_vol[-n:] + 1e-9) - np.log(right_vol[-n:] + 1e-9)
    return np.diff(spread)


def object_returns(name: str, start: str, end: str, vol_window: int) -> tuple[np.ndarray, dict[str, Any]]:
    kind, spec = name.split(":", 1)
    if kind == "vol":
        symbol = spec.upper()
        data = fetch(provider(symbol), symbol, start=start, end=end, interval="1d")
        close = np.asarray(data.get("close"), dtype=float)
        if len(close) < vol_window + 63:
            raise RuntimeError(f"not enough close observations for {name}: {len(close)}")
        returns = vol_change_object(close, vol_window)
        card = data.get("data_card") or {}
        meta = {
            "provider": card.get("provider") or provider(symbol),
            "symbol_resolved": name,
            "first_date": (data.get("dates") or [None])[0],
            "last_date": (data.get("dates") or [None])[-1],
            "n_obs": len(close),
            "source_url": card.get("source_url") or f"vol://{symbol}?start={start}&end={end}",
            "vol_window": vol_window,
            "object_kind": "realized_volatility_change",
        }
        return returns, meta
    if kind == "volspread":
        left_symbol, right_symbol = [item.strip().upper() for item in spec.split("/", 1)]
        left = fetch(provider(left_symbol), left_symbol, start=start, end=end, interval="1d")
        right = fetch(provider(right_symbol), right_symbol, start=start, end=end, interval="1d")
        dates, left_close, right_close = aligned_closes(left, right)
        if len(dates) < vol_window + 63:
            raise RuntimeError(f"not enough aligned observations for {name}: {len(dates)}")
        returns = vol_spread_object(left_close, right_close, vol_window)
        meta = {
            "provider": "aligned_volspread",
            "symbol_resolved": name,
            "first_date": dates[0],
            "last_date": dates[-1],
            "n_obs": len(dates),
            "source_url": f"volspread://{left_symbol}/{right_symbol}?start={start}&end={end}",
            "left_source": (left.get("data_card") or {}).get("source_url"),
            "right_source": (right.get("data_card") or {}).get("source_url"),
            "vol_window": vol_window,
            "object_kind": "realized_volatility_spread_change",
        }
        return returns, meta
    raise ValueError(f"unknown object kind: {kind}")


def review_window(name: str, start: str, end: str, *, label: str, seed: int, shuffles: int, vol_window: int) -> dict[str, Any]:
    try:
        returns, meta = object_returns(name, start, end, vol_window)
        if len(returns) < 60:
            raise RuntimeError(f"not enough object returns: {len(returns)}")
        iid = run_experiment(shuffles=shuffles, seed=seed, real_returns=returns, real_meta=meta)
        block5 = null_stats(returns, seed=seed + 16005, shuffles=shuffles, block=5)
        block21 = null_stats(returns, seed=seed + 16021, shuffles=shuffles, block=21)
        robust = all(item["verdict"] == "DND_DELTA" for item in ({"verdict": iid["verdict"]}, block5, block21))
        return {
            "label": label,
            "object": name,
            "status": "OK",
            "requested_start": start,
            "requested_end": end,
            "actual_start": meta.get("first_date"),
            "actual_end": meta.get("last_date"),
            "n": len(returns),
            "iid": {
                "verdict": iid["verdict"],
                "effect_z": finite(float(iid["effect_z"])),
                "ordered": finite(float(iid["ordered"])),
                "shuffle_mean": finite(float(iid["shuffle_mean"])),
                "shuffle_std": finite(float(iid["shuffle_std"])),
            },
            "block5": block5,
            "block21": block21,
            "robust_all_nulls": robust,
            "partial_confirmations": sum(
                item["verdict"] == "DND_DELTA"
                for item in ({"verdict": iid["verdict"]}, block5, block21)
            ),
            "var_95": finite(float(iid["var_95"])),
            "realized_vol": finite(float(iid["realized_vol"])),
            "data_card": meta,
        }
    except Exception as exc:
        return {
            "label": label,
            "object": name,
            "status": "REVIEW_REQUIRED",
            "requested_start": start,
            "requested_end": end,
            "error": str(exc),
        }


def review_object(name: str, *, end: str, days: int, step_days: int, count: int, seed: int, shuffles: int, vol_window: int) -> dict[str, Any]:
    rows = [
        review_window(
            name,
            window["start"],
            window["end"],
            label=window["label"],
            seed=seed + idx,
            shuffles=shuffles,
            vol_window=vol_window,
        )
        for idx, window in enumerate(rolling_windows(end, days, step_days=step_days, count=count))
    ]
    robust_windows = [row["label"] for row in rows if row.get("robust_all_nulls")]
    review_windows = [row["label"] for row in rows if row.get("status") != "OK"]
    if len(robust_windows) >= 2:
        label = "volatility_macro_recurring_candidate"
        decision = "prepare_volatility_macro_paper_design_inputs"
    elif robust_windows:
        label = "volatility_macro_local_candidate"
        decision = "redesign_volatility_macro_window_or_object"
    elif review_windows:
        label = "volatility_macro_review_required"
        decision = "repair_volatility_macro_data"
    else:
        label = "no_volatility_macro_candidate"
        decision = "need_new_data_provider_or_domain_object"
    return {
        "object": name,
        "rows": rows,
        "classification": {
            "label": label,
            "decision": decision,
            "robust_windows": robust_windows,
            "review_windows": review_windows,
            "paper_live_sim_allowed": False,
            "broker_sandbox_allowed": False,
            "real_execution_allowed": False,
        },
    }


def build_payload(objects: list[str], *, end: str, days: int, step_days: int, count: int, seed: int, shuffles: int, vol_window: int) -> dict[str, Any]:
    results = [
        review_object(name, end=end, days=days, step_days=step_days, count=count, seed=seed + idx * 100, shuffles=shuffles, vol_window=vol_window)
        for idx, name in enumerate(objects)
    ]
    recurring = [row["object"] for row in results if row["classification"]["label"] == "volatility_macro_recurring_candidate"]
    local = [row["object"] for row in results if row["classification"]["label"] == "volatility_macro_local_candidate"]
    review = [row["object"] for row in results if row["classification"]["label"] == "volatility_macro_review_required"]
    if recurring:
        label = "volatility_macro_recurring_candidate_found"
        decision = "prepare_inactive_volatility_macro_paper_inputs"
        next_gate = "Design costs, slippage, risk and inactive paper ledger for the recurring object."
    elif local:
        label = "volatility_macro_local_only"
        decision = "redesign_volatility_macro_window_or_object"
        next_gate = "Volatility/macro object appears local only; do not open paper."
    elif review:
        label = "volatility_macro_review_required"
        decision = "repair_volatility_macro_data"
        next_gate = "Repair data coverage before interpreting this family."
    else:
        label = "no_volatility_macro_candidate"
        decision = "need_new_data_source_or_object_family"
        next_gate = "Current price-derived families are exhausted; use a new macro/provider dataset or pause the autonomous loop."
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(UTC).isoformat(),
        "domain": "finance",
        "intent": "Test realized-volatility and macro-volatility objects after single, lag and pair objects fail.",
        "summary": {
            "label": label,
            "decision": decision,
            "objects": objects,
            "recurring_objects": recurring,
            "local_objects": local,
            "review_objects": review,
            "paper_live_sim_allowed": False,
            "broker_sandbox_allowed": False,
            "real_execution_allowed": False,
            "next_gate": next_gate,
        },
        "parameters": {
            "end": end,
            "window_days": days,
            "step_days": step_days,
            "window_count": count,
            "vol_window": vol_window,
            "seed": seed,
            "shuffles": shuffles,
        },
        "object_results": results,
        "boundary": {
            "operational": False,
            "public_claim": False,
            "trading_signal": False,
            "paper_live_sim": False,
        },
        "sources": {
            "profit_readiness": rel(VALUE_DIR / "finance_profit_readiness_latest.json"),
            "pair_object_review": rel(VALUE_DIR / "finance_pair_object_review_latest.json"),
        },
        "cards": [
            {
                "claim_id": "finance_volatility_macro_object_review",
                "title": "Finance volatility/macro object review",
                "decision": decision,
                "evidence": f"label={label}; recurring={len(recurring)}; local={len(local)}; review={len(review)}",
                "boundary": "Volatility/macro review; no paper/live-sim or execution is authorized.",
            }
        ],
    }


def write_payload(payload: dict[str, Any]) -> dict[str, str]:
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    VALUE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    artifact = REVIEW_DIR / f"finance_volatility_macro_object_review_{stamp}.json"
    stamped = VALUE_DIR / f"finance_volatility_macro_object_review_{stamp}.json"
    latest = VALUE_DIR / "finance_volatility_macro_object_review_latest.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    artifact.write_text(text, encoding="utf-8")
    stamped.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    return {
        "artifact": rel(artifact) or str(artifact),
        "stamped": rel(stamped) or str(stamped),
        "latest": rel(latest) or str(latest),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--objects", default=",".join(DEFAULT_OBJECTS))
    parser.add_argument("--end", default="2026-05-27")
    parser.add_argument("--window-days", type=int, default=300)
    parser.add_argument("--step-days", type=int, default=45)
    parser.add_argument("--window-count", type=int, default=5)
    parser.add_argument("--vol-window", type=int, default=21)
    parser.add_argument("--seed", type=int, default=442)
    parser.add_argument("--shuffles", type=int, default=512)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    objects = [item.strip() for item in args.objects.split(",") if item.strip()]
    payload = build_payload(
        objects,
        end=args.end,
        days=args.window_days,
        step_days=args.step_days,
        count=args.window_count,
        seed=args.seed,
        shuffles=args.shuffles,
        vol_window=args.vol_window,
    )
    if args.write:
        payload["written"] = write_payload(payload)
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"status": "ok", "written": payload.get("written")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
