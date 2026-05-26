#!/usr/bin/env python3
"""btc_autology_artifacts.py - Mnemos/Kairos/Coherence artifacts for BTC Lab.

This tool makes three previously implicit cognitive layers first-class:

- Mnemos: what the Lab retains, decays or sends to redesign.
- Kairos: which phase/action is admissible now.
- Coherence: whether current artifacts agree with the Lab boundary.

It reads local artifacts only. It does not fetch market data and does not run a
cognitive cycle.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VERSION = "0.1.0"
DOMAIN = "bitcoin-regime-lab"
DOMAIN_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = DOMAIN_DIR.parents[1]
DATA_ROOT = Path(os.environ.get("LAB_DATA_DIR", REPO_ROOT / "data")).resolve()
DATA_DIR = DATA_ROOT / DOMAIN
VALUE_DIR = DATA_DIR / "value"
TRAJECTORY_PATH = DATA_DIR / "trajectory_state.json"

INPUTS = {
    "exchange_ohlcv": VALUE_DIR / "btc_exchange_ohlcv_latest.json",
    "daily_closed_evidence_gate": VALUE_DIR / "btc_daily_closed_evidence_gate_latest.json",
    "timeframe_matrix": VALUE_DIR / "btc_timeframe_matrix_latest.json",
    "method_intake": VALUE_DIR / "btc_method_intake_latest.json",
    "daily_inefficiency": VALUE_DIR / "btc_daily_inefficiency_latest.json",
    "lvn_proxy": VALUE_DIR / "btc_volume_profile_lvn_proxy_latest.json",
    "policy_simulator": VALUE_DIR / "btc_policy_simulator_latest.json",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
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


def _summary_counts(artifacts: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts = {"observe": 0, "watch": 0, "test": 0, "reject": 0, "redesign": 0}
    for payload in artifacts.values():
        summary = payload.get("summary")
        if not isinstance(summary, dict):
            continue
        for key in counts:
            value = summary.get(key)
            if isinstance(value, (int, float)):
                counts[key] += int(value)
    return counts


def _artifact_row(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    card = _first_card(payload)
    return {
        "source": name,
        "available": bool(payload),
        "schema": payload.get("schema"),
        "generated_at": payload.get("generated_at"),
        "decision": card.get("decision") or card.get("status"),
        "verdict": card.get("verdict"),
        "evidence": card.get("evidence"),
        "boundary": card.get("boundary"),
    }


def _boundary_ok(payload: dict[str, Any]) -> bool:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    if not boundary:
        return True
    return not any(bool(boundary.get(key)) for key in ("trading_signal", "operational", "advice", "price_target", "entry_exit"))


def build_mnemos(artifacts: dict[str, dict[str, Any]], trajectory: dict[str, Any], generated_at: str) -> dict[str, Any]:
    rows = [_artifact_row(name, payload) for name, payload in artifacts.items() if payload]
    retention = []
    for row in rows:
        decision = str(row.get("decision") or row.get("verdict") or "").lower()
        source = row["source"]
        if "redesign" in decision or "not_beaten" in str(row.get("verdict") or "").lower():
            action = "retain_for_redesign"
            reason = "negative/control evidence is useful for method redesign"
        elif "test" in decision:
            action = "retain_for_next_closed_review"
            reason = "artifact is testable when the closed-evidence gate permits mutation"
        elif source == "daily_closed_evidence_gate":
            action = "retain_as_guard"
            reason = "gate protects mutation from open-candle noise"
        else:
            action = "retain_watch"
            reason = "watch artifact preserves context without promotion"
        retention.append({**row, "retention_action": action, "reason": reason})

    cards = [
        {
            "claim_id": "btc_mnemos_retention_state",
            "title": "BTC Mnemos retention state",
            "decision": "watch",
            "evidence": f"{len(retention)} artifacts retained; trajectory={trajectory.get('decision') or 'pending'}.",
            "boundary": "Mnemos decides retention/decay/redesign memory only; it does not promote market action.",
        }
    ]
    return {
        "schema": "dndlab.bitcoin.mnemos_memory.v1",
        "generated_at": generated_at,
        "domain": DOMAIN,
        "version": VERSION,
        "intent": "Make retention, decay and redesign memory explicit for BTC Lab.",
        "input_artifacts": {name: str(path) for name, path in INPUTS.items()},
        "retention": retention,
        "trajectory": {
            "decision": trajectory.get("decision"),
            "direction": trajectory.get("direction"),
            "reason": trajectory.get("reason"),
        },
        "summary": {
            "observe": 1,
            "watch": 1,
            "test": 0,
            "reject": 0,
            "redesign": sum(1 for row in retention if row["retention_action"] == "retain_for_redesign"),
            "trading_signal": False,
        },
        "cards": cards,
        "boundary": {
            "public_claim": False,
            "trading_signal": False,
            "operational": False,
            "advice": False,
            "price_target": False,
            "entry_exit": False,
        },
    }


def build_kairos(artifacts: dict[str, dict[str, Any]], trajectory: dict[str, Any], generated_at: str) -> dict[str, Any]:
    gate = artifacts.get("daily_closed_evidence_gate") or {}
    gate_state = gate.get("gate") if isinstance(gate.get("gate"), dict) else {}
    counts = _summary_counts(artifacts)
    policy_card = _first_card(artifacts.get("policy_simulator") or {})
    lvn_card = _first_card(artifacts.get("lvn_proxy") or {})
    daily_card = _first_card(artifacts.get("daily_inefficiency") or {})
    mutation_allowed = bool(gate_state.get("mutation_allowed"))

    if not mutation_allowed:
        phase = "hold_open_daily_candle"
        action = "observe_context_do_not_mutate"
        reason = "daily closed-evidence gate excludes current open candle from policy mutation"
    elif policy_card.get("decision") == "redesign" or trajectory.get("decision") == "REDESIGN":
        phase = "redesign_method_contract"
        action = "redesign_before_next_test"
        reason = "policy simulator or trajectory asks for redesign before promotion"
    elif counts.get("test", 0) > 0:
        phase = "closed_review_available"
        action = "review_testable_artifacts"
        reason = "closed evidence is available and at least one artifact is testable"
    else:
        phase = "watch_accumulate"
        action = "retain_watch_state"
        reason = "no artifact currently justifies advancement"

    cards = [
        {
            "claim_id": "btc_kairos_current_phase",
            "title": "BTC Kairos current phase",
            "decision": "watch" if action.startswith(("observe", "retain")) else "redesign",
            "evidence": f"phase={phase}; action={action}; gate_mutation_allowed={mutation_allowed}.",
            "boundary": "Kairos selects Lab phase/action only; it does not execute trades or public operational advice.",
        }
    ]
    return {
        "schema": "dndlab.bitcoin.kairos_phase.v1",
        "generated_at": generated_at,
        "domain": DOMAIN,
        "version": VERSION,
        "intent": "Select the current BTC Lab phase from gate, simulator, null/control and trajectory evidence.",
        "phase": {
            "current": phase,
            "recommended_action": action,
            "reason": reason,
            "mutation_allowed": mutation_allowed,
            "latest_closed_common_date": gate_state.get("latest_closed_common_date"),
            "open_daily_date": gate_state.get("open_daily_date"),
        },
        "evidence": {
            "summary_counts": counts,
            "trajectory_decision": trajectory.get("decision"),
            "policy_decision": policy_card.get("decision"),
            "policy_verdict": policy_card.get("verdict"),
            "lvn_verdict": lvn_card.get("verdict"),
            "daily_inefficiency_verdict": daily_card.get("verdict"),
        },
        "summary": {
            "observe": 1,
            "watch": 1 if action.startswith(("observe", "retain")) else 0,
            "test": 1 if action == "review_testable_artifacts" else 0,
            "reject": 0,
            "redesign": 1 if "redesign" in action else 0,
            "trading_signal": False,
        },
        "cards": cards,
        "boundary": {
            "public_claim": False,
            "trading_signal": False,
            "operational": False,
            "advice": False,
            "price_target": False,
            "entry_exit": False,
        },
    }


def build_coherence(artifacts: dict[str, dict[str, Any]], generated_at: str) -> dict[str, Any]:
    gate = artifacts.get("daily_closed_evidence_gate") or {}
    gate_state = gate.get("gate") if isinstance(gate.get("gate"), dict) else {}
    cutoff = gate_state.get("latest_closed_common_date")
    daily = artifacts.get("daily_inefficiency") or {}
    lvn = artifacts.get("lvn_proxy") or {}
    checks = []

    checks.append({
        "check": "no_signal_boundary",
        "pass": all(_boundary_ok(payload) for payload in artifacts.values() if payload),
        "evidence": "all available artifact boundaries preserve non-operational/no-advice fields",
    })
    checks.append({
        "check": "closed_evidence_gate_present",
        "pass": bool(gate_state.get("decision") and cutoff),
        "evidence": f"gate={gate_state.get('decision')}; latest_closed_common_date={cutoff}",
    })
    checks.append({
        "check": "daily_inefficiency_cutoff_aligned",
        "pass": bool(cutoff and (daily.get("metrics") or {}).get("closed_evidence_cutoff_date") == cutoff),
        "evidence": f"daily_cutoff={(daily.get('metrics') or {}).get('closed_evidence_cutoff_date')}; gate_cutoff={cutoff}",
    })
    checks.append({
        "check": "lvn_proxy_cutoff_aligned",
        "pass": bool(cutoff and (lvn.get("closed_evidence") or {}).get("cutoff_date") == cutoff),
        "evidence": f"lvn_cutoff={(lvn.get('closed_evidence') or {}).get('cutoff_date')}; gate_cutoff={cutoff}",
    })
    checks.append({
        "check": "policy_simulator_declared_manual",
        "pass": bool((artifacts.get("policy_simulator") or {}).get("policy_contract")),
        "evidence": "policy simulator remains a declared research artifact, not a refresh-side execution rule",
    })

    failed = [row for row in checks if not row["pass"]]
    decision = "watch" if failed else "test"
    cards = [
        {
            "claim_id": "btc_coherence_state",
            "title": "BTC coherence state",
            "decision": decision,
            "evidence": f"{len(checks) - len(failed)}/{len(checks)} coherence checks pass.",
            "boundary": "Coherence checks artifact alignment only; it does not authorize public or operational action.",
        }
    ]
    return {
        "schema": "dndlab.bitcoin.coherence_check.v1",
        "generated_at": generated_at,
        "domain": DOMAIN,
        "version": VERSION,
        "intent": "Check drift between BTC Lab intent, closed evidence, artifacts and boundary.",
        "checks": checks,
        "failed_checks": failed,
        "summary": {
            "observe": 1,
            "watch": 1 if failed else 0,
            "test": 1 if not failed else 0,
            "reject": 0,
            "redesign": 0,
            "trading_signal": False,
        },
        "cards": cards,
        "boundary": {
            "public_claim": False,
            "trading_signal": False,
            "operational": False,
            "advice": False,
            "price_target": False,
            "entry_exit": False,
        },
    }


def build_all() -> dict[str, dict[str, Any]]:
    generated_at = _utc_now()
    artifacts = {name: _read_json(path) for name, path in INPUTS.items()}
    trajectory = _read_json(TRAJECTORY_PATH)
    return {
        "mnemos_memory": build_mnemos(artifacts, trajectory, generated_at),
        "kairos_phase": build_kairos(artifacts, trajectory, generated_at),
        "coherence_check": build_coherence(artifacts, generated_at),
    }


def write_artifact(name: str, payload: dict[str, Any]) -> dict[str, str]:
    VALUE_DIR.mkdir(parents=True, exist_ok=True)
    latest = VALUE_DIR / f"btc_{name}_latest.json"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stamped = VALUE_DIR / f"btc_{name}_{stamp}.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    latest.write_text(text + "\n", encoding="utf-8")
    stamped.write_text(text + "\n", encoding="utf-8")
    return {"latest": str(latest), "stamped": str(stamped)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build BTC Mnemos/Kairos/Coherence artifacts.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payloads = build_all()
    if args.write:
        for name, payload in payloads.items():
            payload["written"] = write_artifact(name, payload)
    if args.json or not args.write:
        print(json.dumps(payloads, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({
            "status": "OK",
            "written": {name: payload.get("written") for name, payload in payloads.items()},
            "summary": {name: payload.get("summary") for name, payload in payloads.items()},
        }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
