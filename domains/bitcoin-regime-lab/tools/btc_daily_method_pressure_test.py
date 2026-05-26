#!/usr/bin/env python3
"""btc_daily_method_pressure_test.py - pressure-test BTC daily method autonomy.

This artifact does not invent a new BTC method. It takes the existing
daily_inefficiency surface and verifies that the current autonomy stack handles
it coherently: strict null status, paper ledger evidence, policy contract and
retention/regime selector must agree before any method-policy mutation.
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
    "daily_inefficiency": VALUE_DIR / "btc_daily_inefficiency_latest.json",
    "policy_mutation_contract": VALUE_DIR / "btc_policy_mutation_contract_latest.json",
    "paper_simulation_ledger": VALUE_DIR / "btc_paper_simulation_ledger_latest.json",
    "retention_regime_selector": VALUE_DIR / "btc_retention_regime_selector_latest.json",
    "daily_closed_evidence_gate": VALUE_DIR / "btc_daily_closed_evidence_gate_latest.json",
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


def _selector_decision(selector: dict[str, Any], source: str) -> dict[str, Any]:
    state = selector.get("selector") if isinstance(selector.get("selector"), dict) else {}
    decisions = state.get("decisions") if isinstance(state.get("decisions"), list) else []
    for row in decisions:
        if isinstance(row, dict) and row.get("source") == source:
            return row
    return {}


def build_pressure_test() -> dict[str, Any]:
    artifacts = {name: _read_json(path) for name, path in INPUTS.items()}
    daily = artifacts["daily_inefficiency"]
    daily_card = _first_card(daily)
    daily_metrics = daily.get("metrics") if isinstance(daily.get("metrics"), dict) else {}
    contract = artifacts["policy_mutation_contract"].get("contract")
    contract = contract if isinstance(contract, dict) else {}
    ledger = artifacts["paper_simulation_ledger"]
    ledger_metrics = ledger.get("metrics") if isinstance(ledger.get("metrics"), dict) else {}
    selector = artifacts["retention_regime_selector"]
    selector_row = _selector_decision(selector, "daily_inefficiency")
    gate = artifacts["daily_closed_evidence_gate"]
    gate_state = gate.get("gate") if isinstance(gate.get("gate"), dict) else {}

    strict_rate = daily_metrics.get("strict_control_fill_rate")
    zone_rate = daily_metrics.get("zone_fill_rate")
    strict_null_not_beaten = (
        isinstance(zone_rate, (int, float))
        and isinstance(strict_rate, (int, float))
        and float(zone_rate) <= float(strict_rate)
    )
    checks = [
        {
            "check": "daily_surface_available",
            "passed": bool(daily),
            "evidence": daily.get("schema"),
        },
        {
            "check": "denominator_ready",
            "passed": daily_metrics.get("denominator_ready") is True,
            "evidence": f"zones_evaluable={daily_metrics.get('zones_evaluable')}; strict_controls_evaluable={daily_metrics.get('strict_controls_evaluable')}",
        },
        {
            "check": "strict_null_not_beaten",
            "passed": strict_null_not_beaten and daily_card.get("verdict") == "DAILY_INEFFICIENCY_PROXY_STRICT_NULL_NOT_BEATEN",
            "evidence": f"zone_fill_rate={zone_rate}; strict_control_fill_rate={strict_rate}; verdict={daily_card.get('verdict')}",
        },
        {
            "check": "policy_contract_blocks_mutation",
            "passed": contract.get("policy_mutation_allowed") is False and "method_policy_mutation" in (contract.get("blocked_effects") or []),
            "evidence": f"policy_mutation_allowed={contract.get('policy_mutation_allowed')}; blocked_effects={contract.get('blocked_effects')}",
        },
        {
            "check": "selector_keeps_daily_surface_watch",
            "passed": selector_row.get("selector_decision") == "watch",
            "evidence": f"selector_decision={selector_row.get('selector_decision')}; reason={selector_row.get('reason')}",
        },
        {
            "check": "paper_ledger_visible",
            "passed": ledger_metrics.get("median_error_vs_baseline_pct") is not None and ledger_metrics.get("hit_rate_vs_baseline") is not None,
            "evidence": f"median_error={ledger_metrics.get('median_error_vs_baseline_pct')}; hit_rate={ledger_metrics.get('hit_rate_vs_baseline')}",
        },
        {
            "check": "open_daily_boundary_held",
            "passed": gate_state.get("mutation_allowed") is False,
            "evidence": f"gate={gate_state.get('decision')}; latest_closed={gate_state.get('latest_closed_common_date')}; open_daily={gate_state.get('open_daily_date')}",
        },
    ]
    failed = [row for row in checks if not row["passed"]]
    passed_count = len(checks) - len(failed)
    verdict = "DAILY_METHOD_PRESSURE_TEST_PASS" if not failed else "DAILY_METHOD_PRESSURE_TEST_FAIL"
    decision = "test" if not failed else "redesign"

    return {
        "schema": "dndlab.bitcoin.daily_method_pressure_test.v1",
        "generated_at": _utc_now(),
        "domain": DOMAIN,
        "version": VERSION,
        "intent": "Pressure-test daily_inefficiency through selector, policy contract and paper ledger without mutating method policy.",
        "input_artifacts": {name: str(path) for name, path in INPUTS.items()},
        "target_method": "daily_inefficiency",
        "checks": checks,
        "result": {
            "verdict": verdict,
            "decision": decision,
            "passed": not failed,
            "passed_checks": passed_count,
            "total_checks": len(checks),
            "failed_checks": [row["check"] for row in failed],
            "selector_decision": selector_row.get("selector_decision"),
            "policy_mutation_allowed": contract.get("policy_mutation_allowed"),
            "daily_verdict": daily_card.get("verdict"),
            "zone_fill_rate": zone_rate,
            "strict_control_fill_rate": strict_rate,
            "paper_hit_rate_vs_baseline": ledger_metrics.get("hit_rate_vs_baseline"),
            "paper_median_error_vs_baseline_pct": ledger_metrics.get("median_error_vs_baseline_pct"),
        },
        "summary": {
            "observe": 1,
            "watch": 0,
            "test": 1 if not failed else 0,
            "reject": 0,
            "redesign": 1 if failed else 0,
            "pressure_checks_passed": passed_count,
            "pressure_checks_total": len(checks),
            "trading_signal": False,
        },
        "cards": [
            {
                "claim_id": "btc_daily_method_pressure_test",
                "title": "BTC daily method pressure test",
                "decision": decision,
                "verdict": verdict,
                "evidence": (
                    f"{passed_count}/{len(checks)} checks pass; daily={daily_card.get('verdict')}; "
                    f"selector={selector_row.get('selector_decision')}; "
                    f"policy_mutation_allowed={contract.get('policy_mutation_allowed')}."
                ),
                "boundary": "Pressure test only: validates Lab self-adjustment behavior; no public advice, entries, exits, targets or real orders.",
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
        artifact_prefix="btc_daily_method_pressure_test",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build BTC daily method pressure-test artifact.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = build_pressure_test()
    if args.write:
        payload["written"] = write_artifact(payload)
    print(json.dumps(payload, indent=2 if args.json else None, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
