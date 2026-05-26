#!/usr/bin/env python3
"""First-class producer trace sink for BTC value artifacts.

This artifact indexes the deterministic producers that feed the BTC Lab. It is
process telemetry: it may index paper-trading evidence, but it does not execute
real orders or publish advice.
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

EXPECTED_UPSTREAM = {
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
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _producer_row(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    lineage = payload.get("runtime_lineage") if isinstance(payload.get("runtime_lineage"), dict) else {}
    stamped = _path_from_repo(lineage.get("output_artifact_stamped"))
    raw_trace = _path_from_repo(lineage.get("raw_trace") or lineage.get("last_cycle_trace"))
    raw_log = _path_from_repo(lineage.get("raw_log") or lineage.get("last_cycle_log"))
    report = _path_from_repo(lineage.get("report") or lineage.get("last_cycle_report"))
    inputs = lineage.get("input_artifacts")
    return {
        "artifact": path.name,
        "available": bool(payload),
        "schema": payload.get("schema"),
        "producer": lineage.get("producer"),
        "tool_path": lineage.get("tool_path"),
        "session": lineage.get("session"),
        "cycle_ts": lineage.get("cycle_ts"),
        "refresh_ts": lineage.get("refresh_ts"),
        "last_cycle_ref": lineage.get("last_cycle_ref"),
        "output_artifact": lineage.get("output_artifact"),
        "output_artifact_stamped": lineage.get("output_artifact_stamped"),
        "output_artifact_stamped_exists": bool(stamped and stamped.exists()),
        "input_artifacts_count": len(inputs) if isinstance(inputs, list) else 0,
        "trace_ref": lineage.get("raw_trace") or lineage.get("last_cycle_trace"),
        "trace_ref_exists": bool(raw_trace and raw_trace.exists()),
        "log_ref": lineage.get("raw_log") or lineage.get("last_cycle_log"),
        "log_ref_exists": bool(raw_log and raw_log.exists()),
        "report_ref": lineage.get("report") or lineage.get("last_cycle_report"),
        "report_ref_exists": bool(report and report.exists()),
    }


def build_artifact() -> dict[str, Any]:
    rows = [_producer_row(VALUE_DIR / name) for name in sorted(EXPECTED_UPSTREAM)]
    missing = [row["artifact"] for row in rows if not row["available"]]
    missing_lineage = [row["artifact"] for row in rows if row["available"] and not row.get("producer")]
    missing_stamped = [row["artifact"] for row in rows if row["available"] and not row["output_artifact_stamped_exists"]]
    sessions = sorted({str(row.get("session")) for row in rows if row.get("session")})
    cycle_refs = sorted({str(row.get("cycle_ts")) for row in rows if row.get("cycle_ts")})
    refresh_refs = sorted({str(row.get("refresh_ts")) for row in rows if row.get("refresh_ts")})
    last_cycle_refs = sorted({str(row.get("last_cycle_ref")) for row in rows if row.get("last_cycle_ref")})
    complete = not missing and not missing_lineage and not missing_stamped

    return {
        "schema": "dndlab.bitcoin.producer_trace_sink.v1",
        "generated_at": _utc_now(),
        "domain": DOMAIN,
        "version": VERSION,
        "intent": "Make BTC value-artifact producer traces first-class before relying on downstream interpretation.",
        "input_artifacts": {
            name.removesuffix("_latest.json"): _repo_relative(VALUE_DIR / name)
            for name in sorted(EXPECTED_UPSTREAM)
        },
        "producer_traces": rows,
        "summary": {
            "observe": 1,
            "watch": 0 if complete else 1,
            "test": 1 if complete else 0,
            "reject": 0,
            "redesign": 0,
            "expected_producers": len(EXPECTED_UPSTREAM),
            "available_producers": len(rows) - len(missing),
            "missing_producers": len(missing),
            "missing_lineage": len(missing_lineage),
            "missing_stamped_outputs": len(missing_stamped),
            "sessions": sessions,
            "cycle_refs": cycle_refs,
            "refresh_refs": refresh_refs,
            "last_cycle_refs": last_cycle_refs,
            "trading_signal": False,
        },
        "cards": [
            {
                "claim_id": "btc_producer_trace_sink",
                "title": "BTC producer trace sink",
                "decision": "test" if complete else "watch",
                "evidence": (
                    f"{len(rows) - len(missing)}/{len(EXPECTED_UPSTREAM)} producers available; "
                    f"missing_lineage={len(missing_lineage)}; missing_stamped_outputs={len(missing_stamped)}."
                ),
                "boundary": "Producer trace sink only: process telemetry; it indexes paper-trading evidence without executing real orders or publishing advice.",
            }
        ],
        "failures": {
            "missing_producers": missing,
            "missing_lineage": missing_lineage,
            "missing_stamped_outputs": missing_stamped,
        },
        "boundary": {
            "public_claim": False,
            "trading_signal": False,
            "operational": False,
            "advice": False,
            "price_target": False,
            "entry_exit": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build BTC producer trace sink artifact.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = build_artifact()
    written = None
    if args.write:
        written = write_json_artifact(
            payload=payload,
            value_dir=VALUE_DIR,
            data_dir=DATA_DIR,
            repo_root=REPO_ROOT,
            tool_path=Path(__file__).resolve(),
            artifact_prefix="btc_producer_trace_sink",
        )
        payload["written"] = written

    if args.json or not args.write:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"status": "OK", "files": written, "summary": payload["summary"]}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
