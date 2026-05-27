#!/usr/bin/env python3
"""Choose the next Finance autonomy investigation from current artifacts.

The scout is a self-awareness/readiness layer, not a detector and not a
trading system. It decides where the next cycle should look for the possibility
of trading autonomy.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA = "dndlab.finance.autonomy_opportunity_scout.value.v1"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


ROOT = repo_root()
VALUE_DIR = ROOT / "data" / "finance" / "value"
DIAGNOSTIC_DIR = ROOT / "data" / "finance" / "diagnostics"
CONTRACTS = {
    "autonomous_trading": ROOT / "domains" / "finance" / "autonomous_trading_contract.json",
    "paper_live_sim": ROOT / "domains" / "finance" / "paper_live_sim_contract.json",
    "risk": ROOT / "domains" / "finance" / "risk_contract_skeleton.json",
}


def latest(pattern: str, directory: Path) -> Path | None:
    files = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def load_json(path: Path | None) -> dict[str, Any] | None:
    if not path or not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def rel(path: Path | None) -> str | None:
    if not path:
        return None
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def contract_status() -> dict[str, Any]:
    return {
        key: {
            "path": rel(path),
            "present": path.exists(),
            "schema": (load_json(path) or {}).get("schema"),
            "status": (load_json(path) or {}).get("status"),
        }
        for key, path in CONTRACTS.items()
    }


def build_opportunities() -> dict[str, Any]:
    autonomy_path = VALUE_DIR / "finance_autonomous_trading_contract_latest.json"
    health_path = VALUE_DIR / "finance_operational_health_latest.json"
    transfer_path = latest("finance_transfer_diagnostic_*.json", DIAGNOSTIC_DIR)
    recurrence_path = latest("finance_recurrence_diagnostic_*.json", DIAGNOSTIC_DIR)
    crypto_path = VALUE_DIR / "finance_crypto_candidate_diagnostic_latest.json"
    window_scout_path = VALUE_DIR / "finance_window_universe_scout_latest.json"
    recurrence_validation_path = VALUE_DIR / "finance_recurrence_validation_cycle_latest.json"
    profit_readiness_path = VALUE_DIR / "finance_profit_readiness_latest.json"
    redesign_path = VALUE_DIR / "finance_window_universe_redesign_latest.json"
    autonomy = load_json(autonomy_path) or {}
    health = load_json(health_path) or {}
    transfer = load_json(transfer_path) or {}
    recurrence = load_json(recurrence_path) or {}
    crypto = load_json(crypto_path) or {}
    window_scout = load_json(window_scout_path) or {}
    recurrence_validation = load_json(recurrence_validation_path) or {}
    profit_readiness = load_json(profit_readiness_path) or {}
    redesign = load_json(redesign_path) or {}

    summary = autonomy.get("summary") if isinstance(autonomy.get("summary"), dict) else {}
    transfer_class = transfer.get("classification") if isinstance(transfer.get("classification"), dict) else {}
    recurrence_class = recurrence.get("classification") if isinstance(recurrence.get("classification"), dict) else {}
    crypto_summary = crypto.get("summary") if isinstance(crypto.get("summary"), dict) else {}
    window_scout_summary = window_scout.get("summary") if isinstance(window_scout.get("summary"), dict) else {}
    recurrence_validation_summary = recurrence_validation.get("summary") if isinstance(recurrence_validation.get("summary"), dict) else {}
    profit_summary = profit_readiness.get("summary") if isinstance(profit_readiness.get("summary"), dict) else {}
    redesign_summary = redesign.get("summary") if isinstance(redesign.get("summary"), dict) else {}

    stage = summary.get("current_stage") or "unknown"
    latest_transfer_label = summary.get("latest_transfer_label") or transfer_class.get("label") or "unknown"
    robust_symbols = summary.get("robust_all_null_symbols") or transfer_class.get("robust_all_null_symbols") or []
    recurrence_label = recurrence_class.get("label") or "unknown"
    crypto_label = crypto_summary.get("crypto_label") or "unknown"
    crypto_robust = crypto_summary.get("robust_all_null_symbols") or []
    health_status = summary.get("operational_health") or (health.get("summary") or {}).get("status") or "unknown"
    latest_scout_robust = int(window_scout_summary.get("robust_rows") or 0)
    latest_scout_partial = int(window_scout_summary.get("partial_rows") or 0)
    recurrence_validation_decision = recurrence_validation_summary.get("decision") or "unknown"

    opportunities = [
        {
            "id": "window_universe_redesign",
            "decision": "investigate",
            "score": 0.93 if recurrence_validation_decision == "redesign_window_or_universe" and latest_scout_robust == 0 else 0.62,
            "object": "redesign symbol/window/null family after local candidates fail recurrence",
            "why": "Latest recurrence failed and the redesigned scout has no robust rows; the Lab needs a materially new scan before recurrence can run again.",
            "cycle_shape": [
                "accumulate failed local symbols",
                "change universe or window family",
                "run scout before spending cross-provider validation",
                "only send robust rows to recurrence"
            ],
            "blocks": ["paper_live_sim", "broker_sandbox", "real_execution"],
        },
        {
            "id": "recurrence_window_validation",
            "decision": "investigate" if robust_symbols and recurrence_label != "recurring_candidate" and latest_scout_robust > 0 else "watch",
            "score": 0.9 if robust_symbols and recurrence_label != "recurring_candidate" and latest_scout_robust > 0 else 0.45,
            "object": "test robust scout/transfer candidates across adjacent windows before any paper ledger work",
            "why": "Robust local candidates exist, but recurrence is not established; paper/live-sim must wait.",
            "cycle_shape": [
                "use latest scout-selected rows as candidate source",
                "run recurrence on candidate windows and adjacent windows",
                "require at least two robust exact windows before paper/live-sim design",
                "if recurrence fails, redesign window or universe"
            ],
            "blocks": ["paper_live_sim", "broker_sandbox", "real_execution"],
        },
        {
            "id": "cross_asset_candidate_discovery",
            "decision": "investigate",
            "score": 0.86 if not robust_symbols and health_status == "pass" else 0.55,
            "object": "rolling multi-symbol exact-window scan excluding the exhausted SPY-only premise",
            "why": "No robust all-null symbols exist; the Lab needs a candidate before paper/live-sim can start.",
            "cycle_shape": [
                "predeclare symbol universe and windows",
                "run transfer diagnostic with data cards",
                "only promote symbols that survive iid, block5 and block21",
                "send survivors to recurrence diagnostic"
            ],
            "blocks": ["paper_live_sim", "broker_sandbox", "real_execution"],
        },
        {
            "id": "crypto_asset_class_window_redesign",
            "decision": "watch" if crypto_label == "no_crypto_delta" else "investigate",
            "score": 0.5 if crypto_robust else 0.42,
            "object": "treat crypto as a Finance asset class without duplicating Bitcoin Regime Lab logic",
            "why": "Coinbase OHLCV makes BTC/ETH usable as Finance data, but the current window did not produce a robust candidate.",
            "cycle_shape": [
                "keep BTC-specific regime interpretation inside Bitcoin Regime Lab",
                "use crypto here only for allocation/risk/autonomy data checks",
                "redesign window or widen asset universe before rerunning"
            ],
            "blocks": ["finance_crypto_lab_fork", "paper_live_sim", "real_execution"],
        },
        {
            "id": "paper_live_sim_schema_preparation",
            "decision": "prepare_inactive",
            "score": 0.72,
            "object": "ledger/risk skeleton usable as soon as a robust candidate appears",
            "why": "Trading autonomy needs a ledger before any buy/sell/hold decision can be measured.",
            "cycle_shape": [
                "keep inactive until paper_live_sim_allowed=true",
                "define costs, slippage, drawdown, false-positive budget",
                "write simulated rows only after candidate gate opens"
            ],
            "blocks": ["broker_sandbox", "real_execution"],
        },
        {
            "id": "spy_recurrence_resume",
            "decision": "reject_for_now",
            "score": 0.24 if recurrence_label == "current_iid_partial" else 0.4,
            "object": "continue SPY current-window recurrence",
            "why": "The SPY premise is exhausted unless a materially new mechanism/falsifier is declared.",
            "cycle_shape": ["do not relaunch the same current-window premise"],
            "blocks": ["same_premise_relaunch"],
        },
        {
            "id": "non_spy_control_basket_retest",
            "decision": "watch",
            "score": 0.35 if latest_transfer_label == "no_transfer_delta" else 0.5,
            "object": "repeat the last non-SPY control basket freshness diagnostic",
            "why": "Latest transfer diagnostic produced no_transfer_delta; repeat only if the object/mechanism changes.",
            "cycle_shape": ["requires new object/mechanism/falsifier before rerun"],
            "blocks": ["silent_repeat"],
        },
    ]
    ranked = sorted(opportunities, key=lambda item: item["score"], reverse=True)
    selected = ranked[0]
    if stage != "diagnostic_only" and summary.get("paper_live_sim_allowed") is True:
        selected = next(item for item in ranked if item["id"] == "paper_live_sim_schema_preparation")
        selected = dict(selected)
        selected["decision"] = "activate_paper_live_sim_design"
        selected["score"] = 0.92

    payload_summary = {
        "current_stage": stage,
        "health_status": health_status,
        "latest_transfer_label": latest_transfer_label,
        "recurrence_label": recurrence_label,
        "crypto_label": crypto_label,
        "recurrence_validation_label": recurrence_validation_summary.get("label") or "unknown",
        "recurrence_validation_decision": recurrence_validation_decision,
        "profit_readiness_status": profit_summary.get("status") or "unknown",
        "latest_redesign_mode": redesign_summary.get("mode") or "unknown",
        "latest_scout_robust_rows": latest_scout_robust,
        "latest_scout_partial_rows": latest_scout_partial,
        "crypto_robust_all_null_symbols": crypto_robust,
        "robust_all_null_symbols": robust_symbols,
        "selected_opportunity": selected["id"],
        "selected_decision": selected["decision"],
        "next_cycle_type": {
            "cross_asset_candidate_discovery": "candidate_discovery_cycle",
            "recurrence_window_validation": "recurrence_validation_cycle",
            "window_universe_redesign": "window_universe_redesign_cycle",
            "paper_live_sim_schema_preparation": "paper_live_sim_design_cycle",
        }.get(selected["id"], "candidate_discovery_cycle"),
        "paper_live_sim_allowed": bool(summary.get("paper_live_sim_allowed")),
        "broker_sandbox_allowed": bool(summary.get("broker_sandbox_allowed")),
        "real_execution_allowed": bool(summary.get("real_execution_allowed")),
    }
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(UTC).isoformat(),
        "domain": "finance",
        "intent": "Select the next investigation point toward autonomous trading without confusing investigation with execution.",
        "summary": payload_summary,
        "contracts": contract_status(),
        "sources": {
            "autonomous_trading_value": rel(autonomy_path if autonomy_path.exists() else None),
            "operational_health": rel(health_path if health_path.exists() else None),
            "transfer_diagnostic": rel(transfer_path),
            "recurrence_diagnostic": rel(recurrence_path),
            "crypto_candidate_diagnostic": rel(crypto_path if crypto_path.exists() else None),
            "window_universe_scout": rel(window_scout_path if window_scout_path.exists() else None),
            "recurrence_validation_cycle": rel(recurrence_validation_path if recurrence_validation_path.exists() else None),
            "profit_readiness": rel(profit_readiness_path if profit_readiness_path.exists() else None),
            "window_universe_redesign": rel(redesign_path if redesign_path.exists() else None),
        },
        "latest_window_scout": window_scout_summary,
        "latest_recurrence_validation": recurrence_validation_summary,
        "opportunities": ranked,
        "selected": selected,
        "cycle_continuum": {
            "now": "diagnose and choose next inquiry",
            "next": selected["cycle_shape"],
            "after_candidate": "write paper/live-sim ledger rows with costs, slippage and baseline comparison",
            "after_paper": "sandbox broker only if paper ledger and risk contract pass",
        },
        "cards": [
            {
                "claim_id": "finance_next_autonomy_inquiry",
                "title": "Finance next autonomy inquiry",
                "decision": selected["decision"],
                "evidence": f"stage={stage}; transfer={latest_transfer_label}; recurrence={recurrence_label}; robust={len(robust_symbols)}",
                "boundary": "This selects an investigation cycle, not a trade or broker order.",
            },
            {
                "claim_id": "finance_autonomy_self_awareness",
                "title": "Autonomy self-awareness",
                "decision": "observe",
                "evidence": "Contracts present for autonomy, inactive paper ledger and risk skeleton.",
                "boundary": "The Lab may choose where to investigate; execution remains stage-gated.",
            },
        ],
    }


def write_payload(payload: dict[str, Any]) -> dict[str, str]:
    VALUE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    stamped = VALUE_DIR / f"finance_autonomy_opportunity_scout_{stamp}.json"
    latest_path = VALUE_DIR / "finance_autonomy_opportunity_scout_latest.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    stamped.write_text(text, encoding="utf-8")
    latest_path.write_text(text, encoding="utf-8")
    return {"stamped": rel(stamped) or str(stamped), "latest": rel(latest_path) or str(latest_path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = build_opportunities()
    if args.write:
        payload["written"] = write_payload(payload)
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"status": "ok", "written": payload.get("written")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
