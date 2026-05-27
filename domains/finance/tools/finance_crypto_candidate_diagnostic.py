#!/usr/bin/env python3
"""Crypto candidate diagnostic for Finance autonomy.

Uses Coinbase Exchange public OHLCV daily bars for BTC/ETH as Finance asset
classes. It does not replace the Bitcoin Regime Lab: Finance asks whether
crypto belongs in a multi-asset trading/autonomy surface, while the BTC Lab owns
crypto-specific regime logic. This is diagnostic only: it can nominate
recurrence work, not trades or paper/live-sim.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from exp_regime_shift import run_experiment  # noqa: E402
from finance_transfer_diagnostic import finite, null_stats  # noqa: E402
from market_data import fetch  # noqa: E402


SCHEMA = "dndlab.finance.crypto_candidate_diagnostic.value.v1"
DEFAULT_SYMBOLS = ["BTC-USD", "ETH-USD"]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


ROOT = repo_root()
VALUE_DIR = ROOT / "data" / "finance" / "value"
CRYPTO_DIR = ROOT / "data" / "finance" / "crypto_candidate"


def rel(path: Path | None) -> str | None:
    if not path:
        return None
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def latest_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def write_json_pair(payload: dict[str, Any], prefix: str) -> dict[str, str]:
    CRYPTO_DIR.mkdir(parents=True, exist_ok=True)
    VALUE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    artifact = CRYPTO_DIR / f"{prefix}_{stamp}.json"
    value_path = VALUE_DIR / f"{prefix}_{stamp}.json"
    latest = VALUE_DIR / f"{prefix}_latest.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    artifact.write_text(text, encoding="utf-8")
    value_path.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    return {
        "artifact": rel(artifact) or str(artifact),
        "stamped": rel(value_path) or str(value_path),
        "latest": rel(latest) or str(latest),
    }


def run_symbol(symbol: str, *, start: str, end: str, seed: int, shuffles: int) -> dict[str, Any]:
    try:
        data = fetch("coinbase", symbol, start=start, end=end, interval="1d")
        returns = np.asarray(data["returns"], dtype=float)
        iid = run_experiment(
            shuffles=shuffles,
            seed=seed,
            real_returns=returns,
            real_meta=data["data_card"],
        )
        block5 = null_stats(returns, seed=seed + 7005, shuffles=shuffles, block=5)
        block21 = null_stats(returns, seed=seed + 7021, shuffles=shuffles, block=21)
        card = iid.get("data_card") or {}
        return {
            "symbol": data["symbol"],
            "provider": "coinbase",
            "status": "OK",
            "requested_start": start,
            "requested_end": end,
            "actual_start": card.get("first_date"),
            "actual_end": card.get("last_date"),
            "n": iid["n"],
            "seed": seed,
            "shuffles": shuffles,
            "iid": {
                "verdict": iid["verdict"],
                "effect_z": finite(float(iid["effect_z"])),
                "ordered": finite(float(iid["ordered"])),
                "shuffle_mean": finite(float(iid["shuffle_mean"])),
                "shuffle_std": finite(float(iid["shuffle_std"])),
            },
            "block5": block5,
            "block21": block21,
            "robust_all_nulls": all(
                item["verdict"] == "DND_DELTA"
                for item in ({"verdict": iid["verdict"]}, block5, block21)
            ),
            "var_95": finite(float(iid["var_95"])),
            "realized_vol": finite(float(iid["realized_vol"])),
            "cassini_residue": finite(float(iid["cassini_residue"])),
            "data_card": card,
        }
    except Exception as exc:
        return {
            "symbol": symbol,
            "provider": "coinbase",
            "status": "REVIEW_REQUIRED",
            "requested_start": start,
            "requested_end": end,
            "error": str(exc),
        }


def classify(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok_rows = [row for row in rows if row.get("status") == "OK"]
    review_rows = [row for row in rows if row.get("status") != "OK"]
    robust = {row["symbol"] for row in ok_rows if row.get("robust_all_nulls")}
    iid_pass = {row["symbol"] for row in ok_rows if row.get("iid", {}).get("verdict") == "DND_DELTA"}

    if review_rows:
        label = "crypto_review_required"
        reason = "At least one Coinbase crypto series could not be acquired."
    elif {"BTC-USD", "ETH-USD"}.issubset(robust):
        label = "paired_crypto_candidate"
        reason = "BTC-USD and ETH-USD both survived iid, block5 and block21 nulls."
    elif robust:
        label = "single_crypto_candidate"
        reason = "At least one crypto symbol survived all nulls, but the pair did not confirm."
    elif iid_pass:
        label = "iid_only_crypto_review"
        reason = "At least one crypto symbol passes iid shuffle but fails block-preserving nulls."
    else:
        label = "no_crypto_delta"
        reason = "No crypto symbol survives the current Coinbase exact-window diagnostic."

    return {
        "label": label,
        "reason": reason,
        "iid_dnd_symbols": sorted(iid_pass),
        "robust_all_null_symbols": sorted(robust),
        "review_required_symbols": sorted(str(row["symbol"]) for row in review_rows),
        "operational": False,
        "public_claim": False,
        "trading_signal": False,
    }


def build_payload(symbols: list[str], start: str, end: str, seed: int, shuffles: int) -> dict[str, Any]:
    generated = datetime.now(UTC)
    rows = [
        run_symbol(symbol, start=start, end=end, seed=seed, shuffles=shuffles)
        for symbol in symbols
    ]
    classification = classify(rows)
    equity_cycle = latest_json(VALUE_DIR / "finance_candidate_discovery_cycle_latest.json") or {}
    equity_summary = equity_cycle.get("summary") if isinstance(equity_cycle.get("summary"), dict) else {}
    robust = classification["robust_all_null_symbols"]
    review = classification["review_required_symbols"]

    if review:
        decision = "repair_crypto_data_before_recurrence"
        next_gate = "Resolve Coinbase acquisition/review rows before recurrence or paper/live-sim."
    elif robust:
        decision = "send_crypto_candidates_to_recurrence"
        next_gate = "Run recurrence across multiple windows before any paper/live-sim contract opens."
    else:
        decision = "stay_diagnostic_redesign_crypto_window"
        next_gate = "No robust crypto candidate; redesign window/nulls or widen crypto universe without opening paper/live-sim."

    payload = {
        "schema": SCHEMA,
        "generated_at": generated.isoformat(),
        "generated_at_compact": generated.strftime("%Y%m%d_%H%M%S"),
        "domain": "finance",
        "intent": "Diagnose whether crypto as a Finance asset class supplies a candidate for autonomous trading investigation.",
        "start": start,
        "end": end,
        "symbols": symbols,
        "provider": "coinbase",
        "seed": seed,
        "shuffles": shuffles,
        "nulls": ["iid_shuffle", "block_permutation_5", "block_permutation_21"],
        "rows": rows,
        "classification": classification,
        "summary": {
            "decision": decision,
            "window": {"start": start, "end": end},
            "symbols": symbols,
            "provider": "coinbase",
            "crypto_label": classification["label"],
            "crypto_reason": classification["reason"],
            "robust_all_null_symbols": robust,
            "iid_dnd_symbols": classification["iid_dnd_symbols"],
            "review_required_symbols": review,
            "equity_etf_comparison_label": equity_summary.get("transfer_label"),
            "equity_etf_comparison_decision": equity_summary.get("decision"),
            "paper_live_sim_allowed": False,
            "broker_sandbox_allowed": False,
            "real_execution_allowed": False,
            "next_gate": next_gate,
        },
        "design_contract": {
            "object": "Coinbase BTC/ETH crypto exact-window candidate diagnostic",
            "mechanism": "use real crypto OHLCV as a multi-asset Finance input instead of duplicating BTC Lab regime logic",
            "falsifier": "no symbol survives iid/block5/block21 or Coinbase data is incomplete/review-required",
            "stop_rule": "without robust symbols, stay diagnostic_only and redesign window/universe",
        },
        "boundary": {
            "operational": False,
            "public_claim": False,
            "trading_signal": False,
        },
        "cards": [
            {
                "claim_id": "finance_crypto_candidate_diagnostic",
                "title": "Finance crypto candidate diagnostic",
                "decision": "test" if robust else "redesign" if not review else "repair",
                "evidence": f"crypto={classification['label']}; robust={len(robust)}; equity={equity_summary.get('transfer_label')}",
                "boundary": "Finance asset-class diagnostic only; BTC-specific regime logic stays in Bitcoin Regime Lab.",
            }
        ],
    }
    payload["written"] = write_json_pair(payload, "finance_crypto_candidate_diagnostic")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--start", default="2026-02-26")
    parser.add_argument("--end", default="2026-05-27")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--shuffles", type=int, default=1024)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
    payload = build_payload(
        symbols=symbols,
        start=args.start,
        end=args.end,
        seed=args.seed,
        shuffles=args.shuffles,
    )
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(payload["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
