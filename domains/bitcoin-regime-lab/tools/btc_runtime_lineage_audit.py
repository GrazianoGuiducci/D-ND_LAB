#!/usr/bin/env python3
"""Post-cycle BTC runtime lineage closure audit."""
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
CLOSURE_DIR = DATA_DIR / "closure"
EXPECTED_OUTPUT_ARTIFACTS = {
    f"data/{DOMAIN}/value/{name}"
    for name in (
        "btc_market_context_latest.json",
        "btc_exchange_ohlcv_latest.json",
        "btc_daily_closed_evidence_gate_latest.json",
        "btc_first_hypothesis_latest.json",
        "btc_timeframe_matrix_latest.json",
        "btc_method_intake_latest.json",
        "btc_daily_inefficiency_latest.json",
        "btc_fill_rule_sensitivity_latest.json",
        "btc_zone_denominator_sensitivity_latest.json",
        "btc_auto_ignite_latest.json",
        "btc_volume_profile_lvn_proxy_latest.json",
        "btc_policy_simulator_latest.json",
        "btc_paper_simulation_ledger_latest.json",
        "btc_policy_mutation_contract_latest.json",
        "btc_mnemos_memory_latest.json",
        "btc_kairos_phase_latest.json",
        "btc_coherence_check_latest.json",
        "btc_retention_regime_selector_latest.json",
        "btc_daily_method_pressure_test_latest.json",
        "btc_cognitive_state_latest.json",
        "btc_producer_trace_sink_latest.json",
    )
}


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


def _path_from_lineage(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def _latest_cycle_ts() -> str:
    active = os.environ.get("DND_LAB_ACTIVE_CYCLE_TS", "").strip()
    if active:
        return active
    trace_files = sorted(DATA_DIR.glob("cycle_trace_*.json"))
    if trace_files:
        return trace_files[-1].stem.removeprefix("cycle_trace_")
    trajectory = _read_json(DATA_DIR / "trajectory_state.json")
    return str(trajectory.get("cycle_ts") or "")


def build_audit(cycle_ts: str) -> dict[str, Any]:
    rows_by_output: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(VALUE_DIR.glob("btc_*.json")):
        payload = _read_json(path)
        lineage = payload.get("runtime_lineage")
        if not isinstance(lineage, dict) or lineage.get("cycle_ts") != cycle_ts:
            continue
        if _repo_relative(path) != lineage.get("output_artifact_stamped"):
            continue
        raw_trace = _path_from_lineage(lineage.get("raw_trace"))
        raw_log = _path_from_lineage(lineage.get("raw_log"))
        report = _path_from_lineage(lineage.get("report"))
        inputs = lineage.get("input_artifacts")
        row = {
            "file": _repo_relative(path),
            "schema": payload.get("schema"),
            "producer": lineage.get("producer"),
            "tool_path": lineage.get("tool_path"),
            "session": lineage.get("session"),
            "input_artifacts_count": len(inputs) if isinstance(inputs, list) else 0,
            "output_artifact": lineage.get("output_artifact"),
            "output_artifact_stamped": lineage.get("output_artifact_stamped"),
            "raw_trace": lineage.get("raw_trace"),
            "raw_trace_exists": bool(raw_trace and raw_trace.exists()),
            "raw_log": lineage.get("raw_log"),
            "raw_log_exists": bool(raw_log and raw_log.exists()),
            "report": lineage.get("report"),
            "report_exists": bool(report and report.exists()),
        }
        rows_by_output.setdefault(str(row.get("output_artifact") or ""), []).append(row)

    duplicate_cycle_bindings: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    for output_artifact, rows in sorted(rows_by_output.items()):
        sorted_rows = sorted(rows, key=lambda row: str(row.get("output_artifact_stamped") or row.get("file") or ""))
        artifacts.append(sorted_rows[0])
        for duplicate in sorted_rows[1:]:
            duplicate_cycle_bindings.append({
                "output_artifact": output_artifact,
                "ignored_file": duplicate.get("file"),
                "kept_file": sorted_rows[0].get("file"),
                "reason": "duplicate cycle binding ignored for closure audit; standalone refreshes must not create cycle_ts bindings",
            })

    total = len(artifacts)
    lineage_required_ok = sum(
        1
        for row in artifacts
        if row.get("producer")
        and row.get("tool_path")
        and row.get("output_artifact")
        and row.get("output_artifact_stamped")
    )
    summary = {
        "value_artifacts_total": total,
        "expected_outputs_total": len(EXPECTED_OUTPUT_ARTIFACTS),
        "runtime_lineage_ok": lineage_required_ok,
        "cycle_binding_ok": total,
        "raw_trace_exists": sum(1 for row in artifacts if row["raw_trace_exists"]),
        "raw_log_exists": sum(1 for row in artifacts if row["raw_log_exists"]),
        "report_exists": sum(1 for row in artifacts if row["report_exists"]),
        "input_artifacts_nonempty": sum(1 for row in artifacts if row["input_artifacts_count"] > 0),
        "duplicate_cycle_bindings_ignored": len(duplicate_cycle_bindings),
    }
    observed_outputs = {
        str(row.get("output_artifact"))
        for row in artifacts
        if row.get("output_artifact")
    }
    missing_expected_outputs = sorted(EXPECTED_OUTPUT_ARTIFACTS - observed_outputs)
    unexpected_outputs = sorted(observed_outputs - EXPECTED_OUTPUT_ARTIFACTS)
    report_exists = summary["report_exists"] == total
    raw_trace_exists = summary["raw_trace_exists"] == total
    phase = "post_cycle" if report_exists and raw_trace_exists else "in_cycle_or_pre_report"
    complete_expected_set = (
        total == len(EXPECTED_OUTPUT_ARTIFACTS)
        and not missing_expected_outputs
        and not unexpected_outputs
    )
    status = "pass" if complete_expected_set and all(
        summary[key] == total
        for key in ("runtime_lineage_ok", "cycle_binding_ok", "raw_trace_exists", "raw_log_exists", "report_exists")
    ) else ("pending" if phase == "in_cycle_or_pre_report" else "review")
    return {
        "schema": "dndlab.bitcoin.runtime_lineage_closure_audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "domain": DOMAIN,
        "cycle_ts": cycle_ts,
        "phase": phase,
        "status": status,
        "summary": summary,
        "missing_expected_outputs": missing_expected_outputs,
        "unexpected_outputs": unexpected_outputs,
        "duplicate_cycle_bindings": duplicate_cycle_bindings,
        "boundary": "Post-cycle provenance closure audit only: process telemetry; no real order execution or public advice.",
        "interpretation": (
            "Use status=pass from a post_cycle audit as the closure contract. "
            "During an in-cycle/pre-report audit, missing report or cycle_trace "
            "materialization is pending, not a standalone mutation blocker."
        ),
        "artifacts": artifacts,
    }


def write_audit(payload: dict[str, Any]) -> dict[str, str]:
    CLOSURE_DIR.mkdir(parents=True, exist_ok=True)
    cycle_ts = str(payload["cycle_ts"])
    latest = CLOSURE_DIR / "btc_runtime_lineage_closure_latest.json"
    stamped = CLOSURE_DIR / f"btc_runtime_lineage_closure_{cycle_ts}.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    latest.write_text(text + "\n", encoding="utf-8")
    stamped.write_text(text + "\n", encoding="utf-8")
    return {"latest": str(latest), "stamped": str(stamped)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit BTC runtime lineage after cycle closure.")
    parser.add_argument("--cycle-ts", default="")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    cycle_ts = args.cycle_ts or _latest_cycle_ts()
    if not cycle_ts:
        raise SystemExit("missing cycle_ts")
    payload = build_audit(cycle_ts)
    if args.write:
        payload["written"] = write_audit(payload)
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"status": payload["status"], "summary": payload["summary"], "written": payload["written"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
