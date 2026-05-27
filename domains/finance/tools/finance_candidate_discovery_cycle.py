#!/usr/bin/env python3
"""Candidate discovery cycle for Finance autonomy.

This is the first cycle that uses the data-intake improvements: it requires
cross-provider daily agreement before running the transfer diagnostic. It still
does not produce paper trades.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from finance_provider_crosscheck import build_payload as build_crosscheck  # noqa: E402
from finance_transfer_diagnostic import classify, run_symbol, write_outputs  # noqa: E402


SCHEMA = "dndlab.finance.candidate_discovery_cycle.value.v1"
DEFAULT_SYMBOLS = ["SPY", "QQQ", "IWM", "EFA", "TLT", "GLD"]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


ROOT = repo_root()
VALUE_DIR = ROOT / "data" / "finance" / "value"
CANDIDATE_DIR = ROOT / "data" / "finance" / "candidate_discovery"
DIAGNOSTIC_DIR = ROOT / "data" / "finance" / "diagnostics"
PROVIDER_DIR = ROOT / "data" / "finance" / "provider_crosscheck"


def rel(path: Path | None) -> str | None:
    if not path:
        return None
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def write_json_pair(payload: dict[str, Any], prefix: str, directory: Path) -> dict[str, str]:
    directory.mkdir(parents=True, exist_ok=True)
    VALUE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    path = directory / f"{prefix}_{stamp}.json"
    value_path = VALUE_DIR / f"{prefix}_{stamp}.json"
    latest = VALUE_DIR / f"{prefix}_latest.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")
    value_path.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    return {"artifact": rel(path) or str(path), "stamped": rel(value_path) or str(value_path), "latest": rel(latest) or str(latest)}


def run_transfer(symbols: list[str], start: str, end: str, seed: int, shuffles: int) -> dict[str, Any]:
    generated = datetime.now(UTC)
    rows = [
        run_symbol(symbol, start=start, end=end, seed=seed, shuffles=shuffles)
        for symbol in symbols
    ]
    payload = {
        "schema": "finance_transfer_diagnostic.v1",
        "generated_at": generated.isoformat(),
        "generated_at_compact": generated.strftime("%Y%m%d_%H%M%S"),
        "domain": "finance",
        "kind": "transfer_diagnostic",
        "start": start,
        "end": end,
        "symbols": symbols,
        "seed": seed,
        "shuffles": shuffles,
        "nulls": ["iid_shuffle", "block_permutation_5", "block_permutation_21"],
        "rows": rows,
        "classification": classify(rows),
        "design_contract": {
            "object": "cross-provider equity/ETF candidate discovery",
            "mechanism": "require yfinance/Twelve Data daily agreement before exact-window transfer diagnostics",
            "falsifier": "any provider review row, tolerance failure, or absence of robust all-null symbols blocks paper/live-sim",
            "stop_rule": "if no robust all-null symbols appear, stay diagnostic_only and redesign candidate universe/window",
        },
        "boundary": {
            "operational": False,
            "public_claim": False,
            "trading_signal": False,
        },
    }
    json_path, md_path = write_outputs(payload, DIAGNOSTIC_DIR)
    payload["written"] = {"json": rel(json_path), "markdown": rel(md_path)}
    return payload


def build_cycle(symbols: list[str], start: str, end: str, seed: int, shuffles: int,
                tolerance_bps: float, ttl_sec: int, include_eodhd: bool) -> dict[str, Any]:
    generated_at = datetime.now(UTC).isoformat()
    crosscheck = build_crosscheck(symbols, start, end, tolerance_bps, ttl_sec, include_eodhd)
    crosscheck_summary = crosscheck.get("summary", {})
    provider_written = write_json_pair(crosscheck, "finance_provider_crosscheck", PROVIDER_DIR)

    transfer: dict[str, Any] | None = None
    if crosscheck_summary.get("status") == "pass":
        transfer = run_transfer(symbols, start, end, seed, shuffles)

    classification = (transfer or {}).get("classification") or {}
    robust = classification.get("robust_all_null_symbols") or []
    review = classification.get("review_required_symbols") or []
    if crosscheck_summary.get("status") != "pass":
        decision = "repair_data_before_candidate_discovery"
        next_gate = "Fix provider review/tolerance issues before running transfer diagnostics."
    elif robust:
        decision = "send_robust_candidates_to_recurrence"
        next_gate = "Run recurrence diagnostic on robust symbols, then only open paper/live-sim if recurrence and risk gates pass."
    else:
        decision = "stay_diagnostic_redesign_universe"
        next_gate = "No robust all-null candidate; redesign window/universe or add crypto OHLC provider before paper/live-sim."

    payload = {
        "schema": SCHEMA,
        "generated_at": generated_at,
        "domain": "finance",
        "intent": "Discover daily equity/ETF candidates for autonomous trading investigation after cross-provider data agreement.",
        "summary": {
            "decision": decision,
            "window": {"start": start, "end": end},
            "symbols": symbols,
            "provider_crosscheck_status": crosscheck_summary.get("status"),
            "provider_crosscheck_decision": crosscheck_summary.get("decision"),
            "transfer_label": classification.get("label"),
            "robust_all_null_symbols": robust,
            "iid_dnd_symbols": classification.get("iid_dnd_symbols") or [],
            "review_required_symbols": review,
            "paper_live_sim_allowed": False,
            "broker_sandbox_allowed": False,
            "real_execution_allowed": False,
            "next_gate": next_gate,
        },
        "provider_crosscheck": {
            "summary": crosscheck_summary,
            "written": provider_written,
        },
        "transfer_diagnostic": {
            "summary": classification,
            "written": (transfer or {}).get("written"),
        } if transfer else None,
        "boundary": "Candidate discovery is diagnostic only. It can nominate recurrence tests, not trades or broker orders.",
        "cards": [
            {
                "claim_id": "finance_candidate_discovery_cycle",
                "title": "Finance candidate discovery cycle",
                "decision": "test" if robust else "redesign" if crosscheck_summary.get("status") == "pass" else "repair",
                "evidence": f"providers={crosscheck_summary.get('status')}; transfer={classification.get('label')}; robust={len(robust)}",
                "boundary": "No paper/live-sim or real execution is authorized by this cycle.",
            }
        ],
    }
    payload["written"] = write_json_pair(payload, "finance_candidate_discovery_cycle", CANDIDATE_DIR)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--start", default="2026-02-26")
    parser.add_argument("--end", default="2026-05-27")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--shuffles", type=int, default=1024)
    parser.add_argument("--tolerance-bps", type=float, default=25.0)
    parser.add_argument("--ttl", type=int, default=86_400)
    parser.add_argument("--include-eodhd", action="store_true", help="spot-check EODHD too; use sparingly")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
    payload = build_cycle(
        symbols=symbols,
        start=args.start,
        end=args.end,
        seed=args.seed,
        shuffles=args.shuffles,
        tolerance_bps=args.tolerance_bps,
        ttl_sec=args.ttl,
        include_eodhd=args.include_eodhd,
    )
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(payload["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
