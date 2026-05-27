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
    autonomy = load_json(autonomy_path) or {}
    health = load_json(health_path) or {}
    transfer = load_json(transfer_path) or {}
    recurrence = load_json(recurrence_path) or {}

    summary = autonomy.get("summary") if isinstance(autonomy.get("summary"), dict) else {}
    transfer_class = transfer.get("classification") if isinstance(transfer.get("classification"), dict) else {}
    recurrence_class = recurrence.get("classification") if isinstance(recurrence.get("classification"), dict) else {}

    stage = summary.get("current_stage") or "unknown"
    latest_transfer_label = summary.get("latest_transfer_label") or transfer_class.get("label") or "unknown"
    robust_symbols = summary.get("robust_all_null_symbols") or transfer_class.get("robust_all_null_symbols") or []
    recurrence_label = recurrence_class.get("label") or "unknown"
    health_status = summary.get("operational_health") or (health.get("summary") or {}).get("status") or "unknown"

    opportunities = [
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
        "robust_all_null_symbols": robust_symbols,
        "selected_opportunity": selected["id"],
        "selected_decision": selected["decision"],
        "next_cycle_type": (
            "candidate_discovery_cycle"
            if selected["id"] == "cross_asset_candidate_discovery"
            else "paper_live_sim_design_cycle"
        ),
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
        },
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
