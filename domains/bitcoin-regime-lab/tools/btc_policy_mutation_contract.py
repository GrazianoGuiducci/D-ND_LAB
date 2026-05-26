#!/usr/bin/env python3
"""btc_policy_mutation_contract.py - BTC self-adjustment mutation contract.

The BTC Lab can refresh, learn and run paper/live-sim decisions continuously.
Changing method or policy rules is a narrower effect: it needs closed daily
evidence, a ledgered simulation surface, baseline/null/falsifier obligations
and a readable contract. This artifact exposes that contract without applying
any mutation.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from btc_artifact_lineage import write_json_artifact


VERSION = "0.1.0"
DOMAIN = "bitcoin-regime-lab"
DOMAIN_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = DOMAIN_DIR.parents[1]
DATA_ROOT = Path(os.environ.get("LAB_DATA_DIR", REPO_ROOT / "data")).resolve()
DATA_DIR = DATA_ROOT / DOMAIN
VALUE_DIR = DATA_DIR / "value"

INPUTS = {
    "daily_closed_evidence_gate": VALUE_DIR / "btc_daily_closed_evidence_gate_latest.json",
    "policy_simulator": VALUE_DIR / "btc_policy_simulator_latest.json",
    "paper_simulation_ledger": VALUE_DIR / "btc_paper_simulation_ledger_latest.json",
    "trajectory_state": DATA_DIR / "trajectory_state.json",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _first_card(payload: dict[str, Any]) -> dict[str, Any]:
    cards = payload.get("cards")
    if isinstance(cards, list) and cards and isinstance(cards[0], dict):
        return cards[0]
    card = payload.get("card")
    return card if isinstance(card, dict) else {}


def _ledger_ready(ledger: dict[str, Any]) -> tuple[bool, list[str]]:
    metrics = ledger.get("metrics") if isinstance(ledger.get("metrics"), dict) else {}
    rows = ledger.get("rows") if isinstance(ledger.get("rows"), list) else []
    missing = []
    if not rows:
        missing.append("ledger rows")
    for key in ("median_error_vs_baseline_pct", "hit_rate_vs_baseline"):
        if metrics.get(key) is None:
            missing.append(key)
    return not missing, missing


def build_contract() -> dict[str, Any]:
    gate = _read_json(INPUTS["daily_closed_evidence_gate"])
    simulator = _read_json(INPUTS["policy_simulator"])
    ledger = _read_json(INPUTS["paper_simulation_ledger"])
    trajectory = _read_json(INPUTS["trajectory_state"])

    gate_state = gate.get("gate") if isinstance(gate.get("gate"), dict) else {}
    gate_decision = gate_state.get("decision") or _first_card(gate).get("verdict") or "unknown"
    daily_mutation_allowed = bool(gate_state.get("mutation_allowed"))
    ledger_is_ready, ledger_missing = _ledger_ready(ledger)
    simulator_ready = bool(simulator)
    trajectory_decision = str(trajectory.get("decision") or "pending")
    trajectory_active = trajectory_decision in {"REDESIGN", "NEXT_CYCLE", "CRYSTALLIZE"}

    prerequisites = [
        {
            "id": "closed_daily_evidence_gate",
            "satisfied": daily_mutation_allowed,
            "evidence": gate_decision,
            "required_for": "method_policy_mutation",
        },
        {
            "id": "paper_simulation_ledger",
            "satisfied": ledger_is_ready,
            "evidence": "available" if ledger else "missing",
            "missing": ledger_missing,
            "required_for": "method_policy_mutation",
        },
        {
            "id": "policy_simulator",
            "satisfied": simulator_ready,
            "evidence": _first_card(simulator).get("verdict") or ("available" if simulator_ready else "missing"),
            "required_for": "method_policy_mutation",
        },
        {
            "id": "trajectory_adjustment_decision",
            "satisfied": trajectory_active,
            "evidence": trajectory_decision,
            "required_for": "method_policy_mutation",
        },
    ]
    blocked_by = [row["id"] for row in prerequisites if not row["satisfied"]]
    policy_mutation_allowed = not blocked_by

    allowed_effects = ["refresh_autology", "paper_decision"]
    if policy_mutation_allowed:
        allowed_effects.append("method_policy_mutation")

    contract = {
        "policy_mutation_allowed": policy_mutation_allowed,
        "allowed_effects": allowed_effects,
        "blocked_effects": [
            effect
            for effect in ("method_policy_mutation", "real_execution")
            if effect not in allowed_effects
        ],
        "blocked_by": blocked_by,
        "prerequisites": prerequisites,
        "allowed_evidence_inputs": [
            "daily closed evidence gate",
            "paper simulation ledger",
            "policy simulator",
            "baseline/null/falsifier outputs",
            "trajectory evaluator decision",
        ],
        "ledger_requirements": [
            "simulated decision",
            "outcome versus normal BTC baseline",
            "error versus baseline",
            "path risk",
            "lesson and next adjustment",
        ],
        "baseline_null_obligations": [
            "normal BTC rolling baseline",
            "matched or stricter controls",
            "open-candle exclusion when daily evidence is not closed",
        ],
        "promotion_outcomes": [
            "retain as paper/live-sim rule",
            "redesign method policy",
            "reject candidate",
            "watch until cleaner closed-data evidence",
        ],
        "forbidden_effects": [
            "public financial advice",
            "unlogged signal",
            "real-money execution without separate runtime contract",
            "method promotion without baseline/null/falsifier and ledger evidence",
        ],
    }

    decision = "test" if policy_mutation_allowed else "watch"
    verdict = "POLICY_MUTATION_CONTRACT_READY" if policy_mutation_allowed else "POLICY_MUTATION_CONTRACT_BOUNDARY_HELD"
    return {
        "schema": "dndlab.bitcoin.policy_mutation_contract.v1",
        "generated_at": _utc_now(),
        "domain": DOMAIN,
        "version": VERSION,
        "intent": "Expose the exact contract that controls BTC Lab method/policy self-adjustment without applying mutation.",
        "input_artifacts": {name: str(path) for name, path in INPUTS.items()},
        "contract": contract,
        "summary": {
            "observe": 1,
            "watch": 0 if policy_mutation_allowed else 1,
            "test": 1 if policy_mutation_allowed else 0,
            "reject": 0,
            "redesign": 0 if policy_mutation_allowed else 1,
            "policy_mutation_allowed": policy_mutation_allowed,
            "trading_signal": False,
        },
        "cards": [
            {
                "claim_id": "btc_policy_mutation_contract",
                "title": "BTC policy mutation contract",
                "decision": decision,
                "verdict": verdict,
                "evidence": (
                    f"policy_mutation_allowed={policy_mutation_allowed}; "
                    f"blocked_by={','.join(blocked_by) if blocked_by else 'none'}; "
                    f"gate={gate_decision}."
                ),
                "boundary": "Contract artifact only: it authorizes Lab self-adjustment effects, not public advice or real order execution.",
            }
        ],
        "boundary": {
            "public_claim": False,
            "trading_signal": False,
            "operational": False,
            "advice": False,
            "price_target": False,
            "entry_exit": False,
            "real_order_execution": False,
        },
    }


def write_artifact(payload: dict[str, Any]) -> dict[str, str]:
    return write_json_artifact(
        payload=payload,
        value_dir=VALUE_DIR,
        data_dir=DATA_DIR,
        repo_root=REPO_ROOT,
        tool_path=Path(__file__).resolve(),
        artifact_prefix="btc_policy_mutation_contract",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build BTC policy mutation contract artifact.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = build_contract()
    if args.write:
        payload["written"] = write_artifact(payload)
    print(json.dumps(payload, indent=2 if args.json else None, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
