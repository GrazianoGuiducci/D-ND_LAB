#!/usr/bin/env python3
"""Pair/relative-strength market-object review for Finance Lab.

After single-asset orientation and lag-memory reviews fail to produce recurring
candidates, this tool changes the market object itself: it evaluates relative
strength spreads such as XLK/SPY and GLD/SPY. The output remains diagnostic and
stage-gated.
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


SCHEMA = "dndlab.finance.pair_object_review.value.v1"
DEFAULT_PAIRS = [
    "XLK/SPY", "XLE/SPY", "XLV/SPY", "XLF/SPY", "XLY/SPY", "XLP/SPY",
    "GLD/SPY", "TLT/SPY", "QQQ/SPY", "IWM/SPY", "EEM/EFA", "HYG/LQD",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


ROOT = repo_root()
VALUE_DIR = ROOT / "data" / "finance" / "value"
PAIR_DIR = ROOT / "data" / "finance" / "pair_object_review"


def rel(path: Path | None) -> str | None:
    if not path:
        return None
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path | None) -> dict[str, Any] | None:
    if not path or not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def align_pair_returns(left: dict[str, Any], right: dict[str, Any]) -> tuple[list[str], np.ndarray]:
    left_dates = left.get("dates") or []
    right_dates = right.get("dates") or []
    left_close = np.asarray(left.get("close"), dtype=float)
    right_close = np.asarray(right.get("close"), dtype=float)
    lmap = {date: float(left_close[idx]) for idx, date in enumerate(left_dates)}
    rmap = {date: float(right_close[idx]) for idx, date in enumerate(right_dates)}
    dates = sorted(set(lmap).intersection(rmap))
    if len(dates) < 3:
        return [], np.asarray([], dtype=float)
    ratio_log = np.asarray([np.log(lmap[date]) - np.log(rmap[date]) for date in dates], dtype=float)
    return dates, np.diff(ratio_log)


def pair_provider(symbol: str) -> str:
    return "coinbase" if symbol in {"BTC-USD", "ETH-USD"} else "yfinance"


def review_pair_window(pair: str, start: str, end: str, *, label: str, seed: int, shuffles: int) -> dict[str, Any]:
    left_symbol, right_symbol = [item.strip().upper() for item in pair.split("/", 1)]
    try:
        left = fetch(pair_provider(left_symbol), left_symbol, start=start, end=end, interval="1d")
        right = fetch(pair_provider(right_symbol), right_symbol, start=start, end=end, interval="1d")
        dates, returns = align_pair_returns(left, right)
        if len(returns) < 60:
            raise RuntimeError(f"not enough aligned pair returns: {len(returns)}")
        iid = run_experiment(
            shuffles=shuffles,
            seed=seed,
            real_returns=returns,
            real_meta={
                "provider": "pair_aligned",
                "symbol_resolved": pair,
                "first_date": dates[0],
                "last_date": dates[-1],
                "n_obs": len(dates),
                "source_url": f"pair://{pair}?start={start}&end={end}",
            },
        )
        block5 = null_stats(returns, seed=seed + 15005, shuffles=shuffles, block=5)
        block21 = null_stats(returns, seed=seed + 15021, shuffles=shuffles, block=21)
        robust = all(item["verdict"] == "DND_DELTA" for item in ({"verdict": iid["verdict"]}, block5, block21))
        return {
            "label": label,
            "pair": pair,
            "status": "OK",
            "requested_start": start,
            "requested_end": end,
            "actual_start": dates[0],
            "actual_end": dates[-1],
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
            "data_card": {
                "provider": "pair_aligned",
                "symbol_resolved": pair,
                "first_date": dates[0],
                "last_date": dates[-1],
                "n_obs": len(dates),
                "source_url": f"pair://{pair}?start={start}&end={end}",
                "left_source": (left.get("data_card") or {}).get("source_url"),
                "right_source": (right.get("data_card") or {}).get("source_url"),
            },
        }
    except Exception as exc:
        return {
            "label": label,
            "pair": pair,
            "status": "REVIEW_REQUIRED",
            "requested_start": start,
            "requested_end": end,
            "error": str(exc),
        }


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


def review_pair(pair: str, *, end: str, days: int, step_days: int, count: int, seed: int, shuffles: int) -> dict[str, Any]:
    windows = rolling_windows(end, days, step_days=step_days, count=count)
    rows = [
        review_pair_window(pair, window["start"], window["end"], label=window["label"], seed=seed + idx, shuffles=shuffles)
        for idx, window in enumerate(windows)
    ]
    robust_windows = [row["label"] for row in rows if row.get("robust_all_nulls")]
    review_windows = [row["label"] for row in rows if row.get("status") != "OK"]
    if len(robust_windows) >= 2:
        label = "pair_recurring_candidate"
        decision = "prepare_pair_paper_design_inputs"
    elif robust_windows:
        label = "pair_local_candidate"
        decision = "redesign_pair_window_or_object"
    elif review_windows:
        label = "pair_review_required"
        decision = "repair_pair_data"
    else:
        label = "no_pair_candidate"
        decision = "try_next_market_object"
    return {
        "pair": pair,
        "windows": windows,
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


def build_payload(pairs: list[str], *, end: str, days: int, step_days: int, count: int, seed: int, shuffles: int) -> dict[str, Any]:
    results = [
        review_pair(pair, end=end, days=days, step_days=step_days, count=count, seed=seed + idx * 100, shuffles=shuffles)
        for idx, pair in enumerate(pairs)
    ]
    recurring = [row["pair"] for row in results if row["classification"]["label"] == "pair_recurring_candidate"]
    local = [row["pair"] for row in results if row["classification"]["label"] == "pair_local_candidate"]
    review = [row["pair"] for row in results if row["classification"]["label"] == "pair_review_required"]
    if recurring:
        label = "pair_recurring_candidate_found"
        decision = "prepare_inactive_pair_paper_inputs"
        next_gate = "Design pair-specific costs, slippage, risk and inactive paper ledger."
    elif local:
        label = "pair_local_only"
        decision = "redesign_pair_window_or_universe"
        next_gate = "Pair object found local-only signals; do not open paper."
    elif review:
        label = "pair_review_required"
        decision = "repair_pair_data"
        next_gate = "Repair pair data before interpreting."
    else:
        label = "no_pair_candidate"
        decision = "change_market_object_family"
        next_gate = "No pair object survived; try volatility or macro-relative object."
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(UTC).isoformat(),
        "domain": "finance",
        "intent": "Test relative-strength pair objects after single-asset mechanisms fail.",
        "summary": {
            "label": label,
            "decision": decision,
            "pairs": pairs,
            "recurring_pairs": recurring,
            "local_pairs": local,
            "review_pairs": review,
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
            "seed": seed,
            "shuffles": shuffles,
        },
        "pair_results": results,
        "boundary": {
            "operational": False,
            "public_claim": False,
            "trading_signal": False,
            "paper_live_sim": False,
        },
        "sources": {
            "profit_readiness": rel(VALUE_DIR / "finance_profit_readiness_latest.json"),
            "lag_memory_candidate_review": rel(VALUE_DIR / "finance_lag_memory_candidate_review_latest.json"),
        },
        "cards": [
            {
                "claim_id": "finance_pair_object_review",
                "title": "Finance pair-object review",
                "decision": decision,
                "evidence": f"label={label}; recurring={len(recurring)}; local={len(local)}; review={len(review)}",
                "boundary": "Pair-object review; no paper/live-sim or execution is authorized.",
            }
        ],
    }


def write_payload(payload: dict[str, Any]) -> dict[str, str]:
    PAIR_DIR.mkdir(parents=True, exist_ok=True)
    VALUE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    artifact = PAIR_DIR / f"finance_pair_object_review_{stamp}.json"
    stamped = VALUE_DIR / f"finance_pair_object_review_{stamp}.json"
    latest = VALUE_DIR / "finance_pair_object_review_latest.json"
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
    parser.add_argument("--pairs", default=",".join(DEFAULT_PAIRS))
    parser.add_argument("--end", default="2026-05-27")
    parser.add_argument("--window-days", type=int, default=240)
    parser.add_argument("--step-days", type=int, default=45)
    parser.add_argument("--window-count", type=int, default=5)
    parser.add_argument("--seed", type=int, default=342)
    parser.add_argument("--shuffles", type=int, default=512)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    pairs = [item.strip().upper() for item in args.pairs.split(",") if item.strip()]
    payload = build_payload(
        pairs,
        end=args.end,
        days=args.window_days,
        step_days=args.step_days,
        count=args.window_count,
        seed=args.seed,
        shuffles=args.shuffles,
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
