#!/usr/bin/env python3
"""btc_retention_regime_selector.py - explicit BTC retain/decay/reject/watch.

Mnemos and Kairos already make memory and phase visible. This artifact sits one
level above them and turns that state into explicit per-source decisions while
consuming the policy-mutation contract, paper ledger, daily gate and trajectory.
It does not apply decay or mutate method policy.
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
    "policy_mutation_contract": VALUE_DIR / "btc_policy_mutation_contract_latest.json",
    "policy_simulator": VALUE_DIR / "btc_policy_simulator_latest.json",
    "paper_simulation_ledger": VALUE_DIR / "btc_paper_simulation_ledger_latest.json",
    "mnemos_memory": VALUE_DIR / "btc_mnemos_memory_latest.json",
    "kairos_phase": VALUE_DIR / "btc_kairos_phase_latest.json",
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


def _decision_for_retention(row: dict[str, Any], mutation_allowed: bool, policy_mutation_allowed: bool) -> tuple[str, str]:
    action = str(row.get("retention_action") or "")
    decay_contract = row.get("decay_contract") if isinstance(row.get("decay_contract"), dict) else {}
    decay_state = str(decay_contract.get("decay_state") or "")
    decision = str(row.get("decision") or row.get("verdict") or "").lower()

    if action == "retain_as_guard" or decay_state == "guard_active":
        return "retain", "guard protects the open-daily policy boundary"
    if "reject" in decision:
        return "reject", "source has explicit reject decision"
    if action == "retain_for_redesign" or "redesign" in decision or "not_beaten" in str(row.get("verdict") or "").lower():
        return "decay" if policy_mutation_allowed else "watch", (
            "negative/control evidence should decay into redesign when policy mutation is allowed"
            if policy_mutation_allowed
            else "negative/control evidence is watched until the policy contract permits mutation"
        )
    if action == "retain_for_next_closed_review":
        return "retain" if mutation_allowed else "watch", (
            "testable artifact can be retained for closed-daily review"
            if mutation_allowed
            else "testable artifact waits for closed-daily mutation permission"
        )
    return "watch", "context retained without promotion"


def build_selector() -> dict[str, Any]:
    artifacts = {name: _read_json(path) for name, path in INPUTS.items()}
    gate = artifacts["daily_closed_evidence_gate"]
    gate_state = gate.get("gate") if isinstance(gate.get("gate"), dict) else {}
    policy_contract = artifacts["policy_mutation_contract"]
    contract = policy_contract.get("contract") if isinstance(policy_contract.get("contract"), dict) else {}
    mnemos = artifacts["mnemos_memory"]
    kairos = artifacts["kairos_phase"]
    trajectory = artifacts["trajectory_state"]
    ledger = artifacts["paper_simulation_ledger"]

    mutation_allowed = bool(gate_state.get("mutation_allowed"))
    policy_mutation_allowed = bool(contract.get("policy_mutation_allowed"))
    retention = mnemos.get("retention") if isinstance(mnemos.get("retention"), list) else []
    ledger_metrics = ledger.get("metrics") if isinstance(ledger.get("metrics"), dict) else {}

    decisions = []
    counts = {"retain": 0, "decay": 0, "reject": 0, "watch": 0}
    for row in retention:
        if not isinstance(row, dict):
            continue
        decision, reason = _decision_for_retention(row, mutation_allowed, policy_mutation_allowed)
        counts[decision] += 1
        decisions.append({
            "source": row.get("source"),
            "schema": row.get("schema"),
            "source_decision": row.get("decision"),
            "source_verdict": row.get("verdict"),
            "selector_decision": decision,
            "reason": reason,
            "retention_action": row.get("retention_action"),
            "decay_state": (row.get("decay_contract") or {}).get("decay_state") if isinstance(row.get("decay_contract"), dict) else None,
            "review_horizon": (row.get("decay_contract") or {}).get("review_horizon") if isinstance(row.get("decay_contract"), dict) else None,
        })

    phase = kairos.get("phase") if isinstance(kairos.get("phase"), dict) else {}
    card_decision = "watch"
    if counts["reject"]:
        card_decision = "reject"
    elif counts["decay"]:
        card_decision = "redesign"
    elif counts["retain"]:
        card_decision = "test"

    return {
        "schema": "dndlab.bitcoin.retention_regime_selector.v1",
        "generated_at": _utc_now(),
        "domain": DOMAIN,
        "version": VERSION,
        "intent": "Return explicit retain/decay/reject/watch decisions from BTC memory, regime and policy-contract evidence.",
        "input_artifacts": {name: str(path) for name, path in INPUTS.items()},
        "selector": {
            "mutation_allowed": mutation_allowed,
            "policy_mutation_allowed": policy_mutation_allowed,
            "phase": phase.get("current"),
            "recommended_action": phase.get("recommended_action"),
            "trajectory_decision": trajectory.get("decision"),
            "trajectory_direction": trajectory.get("direction"),
            "ledger_hit_rate_vs_baseline": ledger_metrics.get("hit_rate_vs_baseline"),
            "ledger_median_error_vs_baseline_pct": ledger_metrics.get("median_error_vs_baseline_pct"),
            "decisions": decisions,
            "counts": counts,
            "effects_applied": {
                "hard_decay_applied_count": 0,
                "policy_mutation_applied_count": 0,
                "boundary": "Selector returns decisions only; it does not mutate method policy or apply hard decay.",
            },
        },
        "summary": {
            "observe": 1,
            "watch": counts["watch"],
            "test": counts["retain"],
            "reject": counts["reject"],
            "redesign": counts["decay"],
            "retain": counts["retain"],
            "decay": counts["decay"],
            "policy_mutation_allowed": policy_mutation_allowed,
            "trading_signal": False,
        },
        "cards": [
            {
                "claim_id": "btc_retention_regime_selector",
                "title": "BTC retention/regime selector",
                "decision": card_decision,
                "verdict": "RETENTION_REGIME_SELECTOR_BOUNDARY_HELD" if not policy_mutation_allowed else "RETENTION_REGIME_SELECTOR_MUTATION_REVIEW_READY",
                "evidence": (
                    f"retain={counts['retain']}; decay={counts['decay']}; "
                    f"reject={counts['reject']}; watch={counts['watch']}; "
                    f"policy_mutation_allowed={policy_mutation_allowed}."
                ),
                "boundary": "Selector only: explicit memory/regime decisions without hard decay, real orders, public advice or BTC method-policy mutation.",
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
        artifact_prefix="btc_retention_regime_selector",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build BTC retention/regime selector artifact.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = build_selector()
    if args.write:
        payload["written"] = write_artifact(payload)
    print(json.dumps(payload, indent=2 if args.json else None, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
