#!/usr/bin/env python3
"""Deterministic BTC operational health check.

This is a maintenance guard for scheduled value refreshes. It does not fetch
market data, run a cognitive cycle, or execute real orders.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DOMAIN = "bitcoin-regime-lab"
DOMAIN_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = DOMAIN_DIR.parents[1]
DATA_ROOT = Path(os.environ.get("LAB_DATA_DIR", REPO_ROOT / "data")).resolve()
DATA_DIR = DATA_ROOT / DOMAIN
VALUE_DIR = DATA_DIR / "value"
HEALTH_DIR = DATA_DIR / "health"
EXPECTED_LATEST = {
    "btc_market_context_latest.json",
    "btc_exchange_ohlcv_latest.json",
    "btc_daily_closed_evidence_gate_latest.json",
    "btc_first_hypothesis_latest.json",
    "btc_timeframe_matrix_latest.json",
    "btc_method_intake_latest.json",
    "btc_daily_inefficiency_latest.json",
    "btc_auto_ignite_latest.json",
    "btc_volume_profile_lvn_proxy_latest.json",
    "btc_policy_simulator_latest.json",
    "btc_paper_simulation_ledger_latest.json",
    "btc_mnemos_memory_latest.json",
    "btc_kairos_phase_latest.json",
    "btc_coherence_check_latest.json",
    "btc_cognitive_state_latest.json",
    "btc_producer_trace_sink_latest.json",
}
STALE_COGNITIVE_PHRASES = (
    "mnemos/kairos/coherence are still implicit or partial",
    "Next implementation should make retention, regime selection and policy mutation first-class artifacts.",
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path)


def _path_from_repo(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def _latest_cycle_ref() -> str | None:
    trajectory = _read_json(DATA_DIR / "trajectory_state.json")
    value = trajectory.get("cycle_ts") or trajectory.get("last_cycle_ts")
    if isinstance(value, str) and value:
        return value
    traces = sorted(DATA_DIR.glob("cycle_trace_*.json"))
    return traces[-1].stem.removeprefix("cycle_trace_") if traces else None


def _latest_closure_for(cycle_ref: str | None) -> dict[str, Any]:
    if not cycle_ref:
        return {}
    return _read_json(DATA_DIR / "closure" / f"btc_runtime_lineage_closure_{cycle_ref}.json")


def build_health() -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    latest_files = {path.name for path in VALUE_DIR.glob("btc_*_latest.json")}
    missing_latest = sorted(EXPECTED_LATEST - latest_files)
    unexpected_latest = sorted(latest_files - EXPECTED_LATEST)
    for name in missing_latest:
        failures.append({"check": "latest_artifact_present", "artifact": name, "issue": "missing"})
    for name in unexpected_latest:
        warnings.append({"check": "latest_artifact_set", "artifact": name, "issue": "unexpected_latest_artifact"})

    refresh_ts_values: set[str] = set()
    last_cycle_refs: set[str] = set()
    for name in sorted(EXPECTED_LATEST & latest_files):
        path = VALUE_DIR / name
        payload = _read_json(path)
        lineage = payload.get("runtime_lineage")
        if not isinstance(lineage, dict):
            failures.append({"check": "runtime_lineage", "artifact": name, "issue": "missing"})
            continue
        if lineage.get("session") != "btc_value_refresh":
            failures.append({"check": "lineage_session", "artifact": name, "issue": str(lineage.get("session"))})
        if lineage.get("cycle_ts") is not None:
            failures.append({"check": "value_refresh_cycle_ts_null", "artifact": name, "issue": str(lineage.get("cycle_ts"))})
        refresh_ts = lineage.get("refresh_ts")
        if not isinstance(refresh_ts, str) or not refresh_ts:
            failures.append({"check": "refresh_ts", "artifact": name, "issue": "missing"})
        else:
            refresh_ts_values.add(refresh_ts)
        last_cycle_ref = lineage.get("last_cycle_ref")
        if isinstance(last_cycle_ref, str) and last_cycle_ref:
            last_cycle_refs.add(last_cycle_ref)
        output = lineage.get("output_artifact")
        if output != f"data/{DOMAIN}/value/{name}":
            failures.append({"check": "output_artifact", "artifact": name, "issue": str(output)})
        stamped = _path_from_repo(lineage.get("output_artifact_stamped"))
        if not stamped or not stamped.exists():
            failures.append({"check": "output_artifact_stamped", "artifact": name, "issue": "missing_or_absent"})

    if len(refresh_ts_values) > 1:
        warnings.append({"check": "refresh_ts_consistency", "artifact": "latest_set", "issue": ",".join(sorted(refresh_ts_values))})

    cognitive = _read_json(VALUE_DIR / "btc_cognitive_state_latest.json")
    cognitive_text = json.dumps(cognitive, ensure_ascii=False)
    for phrase in STALE_COGNITIVE_PHRASES:
        if phrase in cognitive_text:
            failures.append({"check": "cognitive_state_stale_phrase", "artifact": "btc_cognitive_state_latest.json", "issue": phrase})
    card_ids = {
        str(card.get("claim_id"))
        for card in cognitive.get("cards", [])
        if isinstance(card, dict)
    }
    if "btc_policy_mutation_gap" not in card_ids:
        failures.append({"check": "cognitive_policy_gap_card", "artifact": "btc_cognitive_state_latest.json", "issue": "missing"})

    mnemos = _read_json(VALUE_DIR / "btc_mnemos_memory_latest.json")
    retention = mnemos.get("retention") if isinstance(mnemos.get("retention"), list) else []
    decay_classified = [
        row
        for row in retention
        if isinstance(row, dict)
        and all((row.get("decay_contract") or {}).get(key) for key in ("decay_state", "trigger", "review_horizon", "demotion_rule"))
    ]
    if not retention or len(decay_classified) != len(retention):
        failures.append({"check": "mnemos_decay_contract", "artifact": "btc_mnemos_memory_latest.json", "issue": f"{len(decay_classified)}/{len(retention)}"})
    decay_contract = mnemos.get("decay_contract") if isinstance(mnemos.get("decay_contract"), dict) else {}
    mutation_effects = mnemos.get("mutation_effects") if isinstance(mnemos.get("mutation_effects"), dict) else {}
    hard_decay_applied = mutation_effects.get("hard_decay_applied_count", decay_contract.get("hard_decay_applied_count"))
    policy_mutation_applied = mutation_effects.get("policy_mutation_applied_count", decay_contract.get("policy_mutation_applied_count"))
    if hard_decay_applied != 0:
        failures.append({"check": "mnemos_hard_decay_applied_count", "artifact": "btc_mnemos_memory_latest.json", "issue": str(hard_decay_applied)})
    if policy_mutation_applied != 0:
        failures.append({"check": "mnemos_policy_mutation_applied_count", "artifact": "btc_mnemos_memory_latest.json", "issue": str(policy_mutation_applied)})

    trace_sink = _read_json(VALUE_DIR / "btc_producer_trace_sink_latest.json")
    trace_summary = trace_sink.get("summary") if isinstance(trace_sink.get("summary"), dict) else {}
    if trace_summary.get("missing_producers") != 0:
        failures.append({"check": "producer_trace_sink_missing_producers", "artifact": "btc_producer_trace_sink_latest.json", "issue": str(trace_summary.get("missing_producers"))})
    if trace_summary.get("missing_lineage") != 0:
        failures.append({"check": "producer_trace_sink_missing_lineage", "artifact": "btc_producer_trace_sink_latest.json", "issue": str(trace_summary.get("missing_lineage"))})
    if trace_summary.get("missing_stamped_outputs") != 0:
        failures.append({"check": "producer_trace_sink_missing_stamped", "artifact": "btc_producer_trace_sink_latest.json", "issue": str(trace_summary.get("missing_stamped_outputs"))})

    cycle_ref = _latest_cycle_ref()
    closure = _latest_closure_for(cycle_ref)
    closure_summary = closure.get("summary") if isinstance(closure.get("summary"), dict) else {}
    if closure.get("status") != "pass" or closure.get("phase") != "post_cycle":
        failures.append({"check": "latest_cycle_closure", "artifact": str(cycle_ref), "issue": f"{closure.get('phase')}/{closure.get('status')}"})
    elif closure_summary.get("value_artifacts_total") != closure_summary.get("expected_outputs_total"):
        failures.append({
            "check": "latest_cycle_closure_count",
            "artifact": str(cycle_ref),
            "issue": f"{closure_summary.get('value_artifacts_total')}/{closure_summary.get('expected_outputs_total')}",
        })

    return {
        "schema": "dndlab.bitcoin.operational_health.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "domain": DOMAIN,
        "status": "pass" if not failures else "fail",
        "latest_artifacts_total": len(latest_files),
        "expected_latest_total": len(EXPECTED_LATEST),
        "refresh_ts_values": sorted(refresh_ts_values),
        "last_cycle_refs": sorted(last_cycle_refs),
        "latest_cycle_ref": cycle_ref,
        "closure_status": closure.get("status"),
        "closure_phase": closure.get("phase"),
        "closure_summary": closure_summary,
        "failures": failures,
        "warnings": warnings,
        "boundary": "Operational health only: process guard; no real order execution or public advice.",
    }


def write_health(payload: dict[str, Any]) -> dict[str, str]:
    HEALTH_DIR.mkdir(parents=True, exist_ok=True)
    latest = HEALTH_DIR / "btc_operational_health_latest.json"
    stamped = HEALTH_DIR / f"btc_operational_health_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    latest.write_text(text + "\n", encoding="utf-8")
    stamped.write_text(text + "\n", encoding="utf-8")
    return {"latest": str(latest), "stamped": str(stamped)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check BTC Lab operational invariants.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = build_health()
    if args.write:
        payload["written"] = write_health(payload)
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"status": payload["status"], "failures": payload["failures"], "warnings": payload["warnings"], "written": payload.get("written")}, indent=2, ensure_ascii=False))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
