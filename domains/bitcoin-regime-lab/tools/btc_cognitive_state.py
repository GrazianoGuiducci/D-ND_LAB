#!/usr/bin/env python3
"""btc_cognitive_state.py - observable cognitive state for BTC Lab.

This tool does not fetch market data and does not run a cognitive cycle. It
reads the current BTC Lab artifacts and writes a compact state object that makes
the Lab's reasoning loop visible: what it is observing, what it has learned,
where it is adjusting itself, and which capability is still missing.
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

SEED_PATH = DATA_DIR / "seed.json"
LAB_DATA_PATH = DATA_DIR / "lab_data.json"
TRAJECTORY_PATH = DATA_DIR / "trajectory_state.json"
MML_PATH = DOMAIN_DIR / "mml.json"

VALUE_INPUTS = {
    "exchange_ohlcv": VALUE_DIR / "btc_exchange_ohlcv_latest.json",
    "field_gate": VALUE_DIR / "btc_first_hypothesis_latest.json",
    "timeframe_matrix": VALUE_DIR / "btc_timeframe_matrix_latest.json",
    "method_intake": VALUE_DIR / "btc_method_intake_latest.json",
    "daily_inefficiency": VALUE_DIR / "btc_daily_inefficiency_latest.json",
    "auto_ignite": VALUE_DIR / "btc_auto_ignite_latest.json",
    "lvn_proxy": VALUE_DIR / "btc_volume_profile_lvn_proxy_latest.json",
    "policy_simulator": VALUE_DIR / "btc_policy_simulator_latest.json",
    "paper_simulation_ledger": VALUE_DIR / "btc_paper_simulation_ledger_latest.json",
    "daily_closed_evidence_gate": VALUE_DIR / "btc_daily_closed_evidence_gate_latest.json",
    "mnemos_memory": VALUE_DIR / "btc_mnemos_memory_latest.json",
    "kairos_phase": VALUE_DIR / "btc_kairos_phase_latest.json",
    "coherence_check": VALUE_DIR / "btc_coherence_check_latest.json",
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


def _artifact_digest(artifacts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, payload in artifacts.items():
        if not payload:
            out[name] = {"available": False}
            continue
        card = _first_card(payload)
        out[name] = {
            "available": True,
            "schema": payload.get("schema"),
            "generated_at": payload.get("generated_at"),
            "decision": card.get("decision") or card.get("status"),
            "verdict": card.get("verdict"),
            "summary": payload.get("summary") if isinstance(payload.get("summary"), dict) else {},
        }
    return out


def _layer_alignment(mml: dict[str, Any]) -> list[dict[str, Any]]:
    skills = mml.get("skills_attive") if isinstance(mml.get("skills_attive"), dict) else {}

    def names(layer: str) -> list[str]:
        entries = skills.get(layer)
        if not isinstance(entries, list):
            return []
        out = []
        for entry in entries:
            if isinstance(entry, dict) and entry.get("name"):
                out.append(str(entry["name"]))
            elif isinstance(entry, str):
                out.append(entry)
        return out

    return [
        {
            "layer": "validation",
            "active": sorted(set(names("validation_layer") + names("domain_layer"))),
            "expected_capabilities": ["baseline/null", "falsifier", "veritas score", "aeternitas seed veto"],
            "state": "partial",
            "gap": "veritas/aeternitas are represented by artifacts and veto checks, but not yet a unified numeric gate in every cycle",
        },
        {
            "layer": "processing",
            "active": sorted(set(names("processing_layer") + names("logic_layer"))),
            "expected_capabilities": ["autological observation", "trajectory decision", "mnemos retention", "kairos regime selection"],
            "state": "partial",
            "gap": "trajectory exists; mnemos/kairos are still implicit in seed and trajectory artifacts",
        },
        {
            "layer": "research",
            "active": sorted(set(names("research_layer") + names("domain_layer"))),
            "expected_capabilities": ["method translation", "simulator", "normal-chart comparison", "mutation proposal"],
            "state": "active",
            "gap": "policy simulator is manual-first; it is not yet closed into autonomous policy mutation",
        },
        {
            "layer": "observation",
            "active": sorted(set(names("observation_layer") + names("interface_layer"))),
            "expected_capabilities": ["runtime trace", "dashboard artifact", "coherence/triage"],
            "state": "partial",
            "gap": "runtime awareness exists; coherence/triage are not yet automated as first-class artifacts",
        },
    ]


def build_cognitive_state() -> dict[str, Any]:
    seed = _read_json(SEED_PATH)
    lab_data = _read_json(LAB_DATA_PATH)
    trajectory = _read_json(TRAJECTORY_PATH)
    mml = _read_json(MML_PATH)
    artifacts = {name: _read_json(path) for name, path in VALUE_INPUTS.items()}
    simulator = artifacts.get("policy_simulator") or {}
    simulator_card = _first_card(simulator)
    lab_value = simulator.get("lab_value") if isinstance(simulator.get("lab_value"), dict) else {}
    trajectory_decision = str(trajectory.get("decision") or "pending")
    summary_counts = _summary_counts(artifacts)

    current_learning = []
    if simulator:
        current_learning.append({
            "source": "btc_policy_simulator",
            "learned": simulator_card.get("interpretation") or "Policy simulator measured method structure against controls and normal chart movement.",
            "decision": simulator_card.get("research_decision") or simulator_card.get("decision"),
            "value_score": lab_value.get("lab_value_score"),
            "classification": lab_value.get("classification"),
        })
    ledger = artifacts.get("paper_simulation_ledger") or {}
    ledger_card = _first_card(ledger)
    ledger_metrics = ledger.get("metrics") if isinstance(ledger.get("metrics"), dict) else {}
    if ledger:
        current_learning.append({
            "source": "btc_paper_simulation_ledger",
            "learned": ledger_card.get("interpretation") or "Paper simulation ledger measures simulated decisions against the normal BTC baseline.",
            "decision": ledger_card.get("decision"),
            "median_error_vs_baseline_pct": ledger_metrics.get("median_error_vs_baseline_pct"),
            "hit_rate_vs_baseline": ledger_metrics.get("hit_rate_vs_baseline"),
        })
    if trajectory:
        current_learning.append({
            "source": "trajectory_evaluator",
            "learned": trajectory.get("reason"),
            "decision": trajectory_decision,
            "next_direction": trajectory.get("direction"),
        })
    closed_gate = artifacts.get("daily_closed_evidence_gate") or {}
    closed_gate_card = _first_card(closed_gate)
    closed_gate_state = closed_gate.get("gate") if isinstance(closed_gate.get("gate"), dict) else {}
    if closed_gate:
        current_learning.append({
            "source": "btc_daily_closed_evidence_gate",
            "learned": closed_gate_card.get("evidence") or "Daily evidence gate separates closed daily evidence from current open-candle refresh noise.",
            "decision": closed_gate_state.get("decision") or closed_gate_card.get("verdict") or closed_gate_card.get("decision"),
            "latest_closed_common_date": closed_gate_state.get("latest_closed_common_date"),
            "mutation_allowed": closed_gate_state.get("mutation_allowed"),
        })
    mnemos = artifacts.get("mnemos_memory") or {}
    kairos = artifacts.get("kairos_phase") or {}
    coherence = artifacts.get("coherence_check") or {}
    if mnemos:
        current_learning.append({
            "source": "btc_mnemos_memory",
            "learned": _first_card(mnemos).get("evidence") or "Mnemos retention artifact is available.",
            "decision": _first_card(mnemos).get("decision"),
        })
    if kairos:
        phase = kairos.get("phase") if isinstance(kairos.get("phase"), dict) else {}
        current_learning.append({
            "source": "btc_kairos_phase",
            "learned": phase.get("reason") or _first_card(kairos).get("evidence") or "Kairos phase artifact is available.",
            "decision": phase.get("recommended_action") or _first_card(kairos).get("decision"),
            "phase": phase.get("current"),
        })
    if coherence:
        current_learning.append({
            "source": "btc_coherence_check",
            "learned": _first_card(coherence).get("evidence") or "Coherence artifact checks drift between boundary and artifacts.",
            "decision": _first_card(coherence).get("decision"),
        })

    not_yet_closed = [
        "autonomous policy mutation contract after the next stable closed-data run",
    ]
    if not ledger:
        not_yet_closed.insert(0, "paper-simulation ledger with simulated decisions, outcome, error and baseline")

    auto_adjustment = {
        "current_mode": "research_autonomy_observable",
        "closed_loop_state": "partial",
        "can_adjust_now": bool(trajectory_decision in {"REDESIGN", "NEXT_CYCLE", "CRYSTALLIZE"} or simulator),
        "adjustment_source": "trajectory_state + policy_simulator + paper_simulation_ledger + seed constraints" if ledger else "trajectory_state + policy_simulator + seed constraints",
        "next_mutation": (
            closed_gate_card.get("next_test")
            or trajectory.get("direction")
            or "Promote the simulator from isolated artifact to a declared policy-mutation contract after the next reviewed run."
        ),
        "not_yet_closed": not_yet_closed,
    }

    cards = [
        {
            "claim_id": "btc_cognitive_state_loop",
            "title": "BTC Lab cognitive loop",
            "decision": "watch" if auto_adjustment["closed_loop_state"] == "partial" else "test",
            "evidence": (
                f"Cycle count {lab_data.get('cicli_totali', 0)}; "
                f"trajectory {trajectory_decision}; "
                f"value artifacts observe/watch/test/reject/redesign = "
                f"{summary_counts['observe']}/{summary_counts['watch']}/{summary_counts['test']}/"
                f"{summary_counts['reject']}/{summary_counts['redesign']}."
            ),
            "boundary": "Cognitive-state artifact: learning, gaps and adjustment readiness. Paper simulation ledger: available." if ledger else "Cognitive-state artifact: learning, gaps and adjustment readiness. Paper simulation ledger: missing.",
        },
        {
            "claim_id": "btc_autological_gap",
            "title": "Autological closure gap",
            "decision": "redesign",
            "evidence": "BTC has falsifier, trajectory, seed updates and simulator, but mnemos/kairos/coherence are still implicit or partial.",
            "boundary": "Next implementation should make retention, regime selection and policy mutation first-class artifacts.",
        },
    ]

    return {
        "schema": "dndlab.bitcoin.cognitive_state.v1",
        "generated_at": _utc_now(),
        "domain": DOMAIN,
        "version": VERSION,
        "intent": "Make the BTC Lab cognitive/autological process observable without running a market-data fetch or a cognitive cycle.",
        "input_artifacts": {name: str(path) for name, path in VALUE_INPUTS.items()},
        "seed_state": {
            "piano": seed.get("piano"),
            "timestamp": seed.get("timestamp"),
            "direction": seed.get("direzione") or lab_data.get("direzione"),
            "tensions": len(seed.get("tensioni") or []),
        },
        "cognitive_cycle": [
            {"stage": "intent", "state": "active", "evidence": "domain request is preserved in seed/context"},
            {"stage": "field", "state": "active", "evidence": "feed, timeframe and method artifacts are present when refreshed"},
            {"stage": "test", "state": "active", "evidence": "LVN/FVG/policy simulator artifacts define measurable objects"},
            {"stage": "falsify", "state": "active", "evidence": "strict controls, random matched controls and trajectory decisions are recorded"},
            {"stage": "learn", "state": "active" if mnemos else "partial", "evidence": "mnemos artifact records retention/redesign memory; paper ledger records simulated decision error" if mnemos and ledger else ("mnemos artifact records retention/redesign memory" if mnemos else "learning is readable in seed/trajectory/report, not yet a dedicated mnemos artifact")},
            {"stage": "adjust", "state": "active" if kairos else "partial", "evidence": "kairos artifact selects current Lab phase/action" if kairos else "trajectory can request redesign; autonomous policy mutation is not yet closed"},
            {"stage": "cohere", "state": "active" if coherence else "partial", "evidence": "coherence artifact checks drift between gate, artifacts and boundary" if coherence else "coherence checks are not yet first-class"},
            {"stage": "propagate", "state": "partial", "evidence": "capability cascade exists as contract, not yet automatic cross-lab propagation"},
        ],
        "layer_alignment": _layer_alignment(mml),
        "artifact_digest": _artifact_digest(artifacts),
        "current_learning": current_learning,
        "auto_adjustment": auto_adjustment,
        "summary": {
            **summary_counts,
            "cognitive_cards": len(cards),
            "closed_loop_state": auto_adjustment["closed_loop_state"],
        },
        "cards": cards,
    }


def write_artifact(payload: dict[str, Any]) -> dict[str, str]:
    VALUE_DIR.mkdir(parents=True, exist_ok=True)
    latest = VALUE_DIR / "btc_cognitive_state_latest.json"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stamped = VALUE_DIR / f"btc_cognitive_state_{stamp}.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    latest.write_text(text + "\n", encoding="utf-8")
    stamped.write_text(text + "\n", encoding="utf-8")
    return {"latest": str(latest), "stamped": str(stamped)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build BTC Lab cognitive-state artifact.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = build_cognitive_state()
    if args.write:
        payload["written"] = write_artifact(payload)
    print(json.dumps(payload, indent=2 if args.json else None, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
