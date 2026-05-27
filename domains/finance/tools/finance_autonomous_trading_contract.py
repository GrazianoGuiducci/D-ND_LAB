#!/usr/bin/env python3
"""Readiness artifact for Finance Lab autonomous trading.

This tool does not fetch market data and cannot place orders. It reads the
latest Finance artifacts and states which autonomy stage is currently allowed.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA = "dndlab.finance.autonomous_trading_contract.value.v1"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


ROOT = repo_root()
CONTRACT_PATH = ROOT / "domains" / "finance" / "autonomous_trading_contract.json"
DIAGNOSTIC_DIR = ROOT / "data" / "finance" / "diagnostics"
VALUE_DIR = ROOT / "data" / "finance" / "value"


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


def bool_path(data: dict[str, Any] | None, *keys: str) -> bool | None:
    cur: Any = data
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur if isinstance(cur, bool) else None


def stage_readiness() -> dict[str, Any]:
    contract = load_json(CONTRACT_PATH) or {}
    transfer_path = latest("finance_transfer_diagnostic_*.json", DIAGNOSTIC_DIR)
    recurrence_path = latest("finance_recurrence_diagnostic_*.json", DIAGNOSTIC_DIR)
    health_path = VALUE_DIR / "finance_operational_health_latest.json"
    transfer = load_json(transfer_path)
    recurrence = load_json(recurrence_path)
    health = load_json(health_path)

    classification = transfer.get("classification") if isinstance(transfer, dict) else {}
    if not isinstance(classification, dict):
        classification = {}
    robust_symbols = classification.get("robust_all_null_symbols") or []
    review_required = classification.get("review_required_symbols") or []
    transfer_label = classification.get("label") or "missing"
    health_status = (health or {}).get("status") or (health or {}).get("summary", {}).get("status")
    recurrence_class = (recurrence or {}).get("classification") or {}
    recurrence_label = recurrence_class.get("label") if isinstance(recurrence_class, dict) else None

    blocked_by: list[str] = []
    warnings: list[str] = []

    if not transfer:
        blocked_by.append("missing_transfer_diagnostic")
    if transfer_label in {"missing", "no_transfer_delta", "iid_only_review", "single_or_partial_window"}:
        blocked_by.append(f"latest_transfer_label:{transfer_label}")
    if not robust_symbols:
        blocked_by.append("no_robust_all_null_symbols")
    if review_required:
        blocked_by.append("review_required_symbols_present")
    if not recurrence:
        blocked_by.append("missing_recurrence_diagnostic")
    elif recurrence_label in {None, "current_iid_partial", "no_recurrence_delta", "review"}:
        blocked_by.append(f"recurrence_not_promotable:{recurrence_label or 'unknown'}")
    if health_status != "pass":
        blocked_by.append(f"operational_health_not_pass:{health_status or 'missing'}")

    blocked_by.extend([
        "no_cost_slippage_model_for_candidate",
        "no_paper_trade_ledger",
        "no_risk_contract",
        "no_broker_sandbox_adapter",
        "no_operator_reviewed_real_execution_contract",
    ])

    paper_allowed = not blocked_by[:5] and bool(robust_symbols)
    sandbox_allowed = False
    real_allowed = False

    if paper_allowed:
        current_stage = "paper_live_sim_ready"
        next_gate = "Write and run simulated decision ledger with costs, slippage, drawdown and false-positive budget."
    else:
        current_stage = "diagnostic_only"
        next_gate = (
            "Keep Finance in diagnostic autonomy. Design a materially new market object or "
            "candidate that can survive transfer, recurrence, costs and data-card review."
        )

    if transfer_label == "no_transfer_delta":
        warnings.append("Latest transfer diagnostic is useful negative evidence, not a trade candidate.")
    if health_status == "pass":
        warnings.append("Operational health passes; it does not authorize paper or broker execution by itself.")

    generated_at = datetime.now(UTC).isoformat()
    summary = {
        "target": "autonomous_trading",
        "current_stage": current_stage,
        "paper_live_sim_allowed": paper_allowed,
        "broker_sandbox_allowed": sandbox_allowed,
        "real_execution_allowed": real_allowed,
        "latest_transfer_label": transfer_label,
        "robust_all_null_symbols": robust_symbols,
        "operational_health": health_status or "missing",
        "next_gate": next_gate,
    }
    cards = [
        {
            "claim_id": "finance_autonomous_trading_stage",
            "title": "Finance autonomous trading stage",
            "decision": "test" if paper_allowed else "observe",
            "evidence": f"stage={current_stage}; transfer={transfer_label}; robust={len(robust_symbols)}",
            "boundary": "No broker or real-capital order is allowed from this artifact.",
        },
        {
            "claim_id": "finance_execution_boundary",
            "title": "Execution boundary",
            "decision": "reject",
            "evidence": "paper/live-sim, sandbox and real execution require separate ledgers/contracts.",
            "boundary": "Internal trading autonomy is the target; public advice and unreviewed real orders remain blocked.",
        },
    ]
    return {
        "schema": SCHEMA,
        "generated_at": generated_at,
        "source_contract": str(CONTRACT_PATH.relative_to(ROOT)),
        "summary": summary,
        "blocked_by": blocked_by,
        "warnings": warnings,
        "sources": {
            "transfer_diagnostic": str(transfer_path.relative_to(ROOT)) if transfer_path else None,
            "recurrence_diagnostic": str(recurrence_path.relative_to(ROOT)) if recurrence_path else None,
            "operational_health": str(health_path.relative_to(ROOT)) if health_path.exists() else None,
        },
        "stage_contract": {
            "target": contract.get("target", "autonomous_trading"),
            "stages": contract.get("stages", []),
            "risk_contract_minimum": contract.get("risk_contract_minimum", {}),
            "public_boundary": contract.get("public_boundary", {}),
            "metalab_transfer": contract.get("metalab_transfer", {}),
        },
        "cards": cards,
    }


def write_payload(payload: dict[str, Any]) -> dict[str, str]:
    VALUE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    stamped = VALUE_DIR / f"finance_autonomous_trading_contract_{stamp}.json"
    latest_path = VALUE_DIR / "finance_autonomous_trading_contract_latest.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    stamped.write_text(text, encoding="utf-8")
    latest_path.write_text(text, encoding="utf-8")
    return {
        "stamped": str(stamped.relative_to(ROOT)),
        "latest": str(latest_path.relative_to(ROOT)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write value artifact")
    parser.add_argument("--json", action="store_true", help="pretty-print JSON")
    args = parser.parse_args()

    payload = stage_readiness()
    if args.write:
        payload["written"] = write_payload(payload)
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"status": "ok", "written": payload.get("written")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
