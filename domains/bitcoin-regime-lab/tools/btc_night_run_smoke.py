#!/usr/bin/env python3
"""Smoke guard for BTC Lab scheduled runs.

Read-only check for cron/night operation. It does not fetch market data, run a
cycle, mutate policy, execute orders, or write artifacts.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DOMAIN = "bitcoin-regime-lab"
DOMAIN_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = DOMAIN_DIR.parents[1]
DATA_DIR = REPO_ROOT / "data" / DOMAIN
VALUE_DIR = DATA_DIR / "value"
CRON_PRIMARY = Path("/etc/cron.d/dnd-lab-bitcoin-regime")
CRON_EXTRA = Path("/etc/cron.d/dnd-lab-bitcoin-regime-extra-night")


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def latest_cycle_ref() -> str | None:
    trajectory = read_json(DATA_DIR / "trajectory_state.json")
    for key in ("cycle_ts", "last_cycle_ts", "entry_cycle_ref"):
        value = trajectory.get(key)
        if isinstance(value, str) and value:
            return value
    traces = sorted(DATA_DIR.glob("cycle_trace_*.json"))
    return traces[-1].stem.removeprefix("cycle_trace_") if traces else None


def cycle_refs_for_date(date: str) -> list[str]:
    refs = []
    for path in sorted(DATA_DIR.glob(f"cycle_trace_{date}_*.json")):
        refs.append(path.stem.removeprefix("cycle_trace_"))
    return refs


def run_health() -> dict[str, Any]:
    script = DOMAIN_DIR / "tools" / "btc_operational_health.py"
    try:
        proc = subprocess.run(
            [sys.executable, str(script), "--json"],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except Exception as exc:
        return {"status": "error", "failures": [{"check": "health_invocation", "issue": str(exc)}]}
    if proc.returncode != 0:
        return {
            "status": "error",
            "failures": [{"check": "health_invocation", "issue": proc.stderr.strip() or proc.stdout.strip()}],
        }
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"status": "error", "failures": [{"check": "health_parse", "issue": "invalid_json"}]}
    return payload if isinstance(payload, dict) else {}


def trajectory_absorbs_falsifier(cycle_ref: str | None, falsifier: dict[str, Any]) -> bool:
    if not cycle_ref:
        return False
    trajectory = read_json(DATA_DIR / "trajectory_state.json")
    flags = falsifier.get("flags") if isinstance(falsifier.get("flags"), list) else []
    direction = str(trajectory.get("direction") or "").lower()
    reason = str(trajectory.get("reason") or "").lower()
    return (
        trajectory.get("cycle_ts") == cycle_ref
        and trajectory.get("decision") == "REDESIGN"
        and trajectory.get("confidence") == "high"
        and bool(flags)
        and any(term in direction + " " + reason for term in ("null", "density", "strict_close", "denominator"))
    )


def producer_trace_closes_cycle(cycle_ref: str | None) -> bool:
    if not cycle_ref:
        return False
    sink = read_json(VALUE_DIR / "btc_producer_trace_sink_latest.json")
    summary = sink.get("summary") if isinstance(sink.get("summary"), dict) else {}
    lineage = sink.get("runtime_lineage") if isinstance(sink.get("runtime_lineage"), dict) else {}
    expected = int(summary.get("expected_producers") or 0)
    available = int(summary.get("available_producers") or 0)
    return (
        expected > 0
        and available == expected
        and int(summary.get("missing_producers") or 0) == 0
        and int(summary.get("missing_lineage") or 0) == 0
        and int(summary.get("missing_stamped_outputs") or 0) == 0
        and lineage.get("last_cycle_ref") == cycle_ref
    )


def add_check(checks: list[dict[str, Any]], ok: bool, name: str, detail: str, **extra: Any) -> None:
    row: dict[str, Any] = {"check": name, "ok": ok, "detail": detail}
    row.update(extra)
    checks.append(row)


def build_smoke(args: argparse.Namespace) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    health = run_health()
    health_failures = health.get("failures") if isinstance(health.get("failures"), list) else []
    health_warnings = health.get("warnings") if isinstance(health.get("warnings"), list) else []

    add_check(
        checks,
        health.get("status") == "pass" and not health_failures,
        "operational_health_pass",
        f"status={health.get('status')}; failures={len(health_failures)}; warnings={len(health_warnings)}",
    )
    add_check(
        checks,
        health.get("status") == "pass"
        and int(health.get("latest_artifacts_total") or 0) >= int(health.get("expected_latest_total") or 0) >= 24,
        "latest_artifact_count",
        f"{health.get('latest_artifacts_total')}/{health.get('expected_latest_total')}; warnings={len(health_warnings)}",
    )

    cycle_ref = args.cycle_ref or latest_cycle_ref()
    trace = read_json(DATA_DIR / f"cycle_trace_{cycle_ref}.json") if cycle_ref else {}
    closure = read_json(DATA_DIR / "closure" / f"btc_runtime_lineage_closure_{cycle_ref}.json") if cycle_ref else {}
    falsifier = read_json(DATA_DIR / "falsifier" / f"falsifier_{cycle_ref}.json") if cycle_ref else {}

    add_check(checks, bool(cycle_ref), "latest_cycle_ref_present", str(cycle_ref))
    if args.after_cycle and cycle_ref:
        add_check(
            checks,
            cycle_ref > args.after_cycle,
            "latest_cycle_after_baseline",
            f"latest={cycle_ref}; baseline={args.after_cycle}",
        )

    add_check(
        checks,
        trace.get("n_errors") == 0 and isinstance(trace.get("movements"), list),
        "cycle_trace_clean",
        f"cycle={cycle_ref}; n_errors={trace.get('n_errors')}",
    )
    assertions = next(
        (
            row.get("metrics", {})
            for row in trace.get("movements", [])
            if isinstance(row, dict) and row.get("name") == "verify_assertions"
        ),
        {},
    )
    add_check(
        checks,
        assertions.get("n_fail") == 0 and assertions.get("n_pass") == assertions.get("n_total") == 4,
        "assertions_pass",
        f"{assertions.get('n_pass')}/{assertions.get('n_total')} pass; fail={assertions.get('n_fail')}",
    )
    closure_ok = (
        closure.get("status") == "pass"
        and (closure.get("summary") or {}).get("expected_outputs_total") == (closure.get("summary") or {}).get("runtime_lineage_ok")
    ) or producer_trace_closes_cycle(cycle_ref)
    add_check(
        checks,
        closure_ok,
        "post_cycle_closure_pass",
        f"status={closure.get('status')}; summary={(closure.get('summary') or {})}; producer_trace_closes={producer_trace_closes_cycle(cycle_ref)}",
    )
    flags = falsifier.get("flags") if isinstance(falsifier.get("flags"), list) else []
    falsifier_ok = (falsifier.get("coherent") is True and len(flags) == 0) or trajectory_absorbs_falsifier(cycle_ref, falsifier)
    add_check(
        checks,
        falsifier_ok,
        "falsifier_clean",
        f"coherent={falsifier.get('coherent')}; flags={len(flags)}; absorbed_by_trajectory={trajectory_absorbs_falsifier(cycle_ref, falsifier)}",
    )

    strict_contract = read_json(VALUE_DIR / "btc_closed_daily_strict_close_contract_latest.json")
    strict_data = strict_contract.get("data_card") if isinstance(strict_contract.get("data_card"), dict) else {}
    strict_boundary = strict_contract.get("boundary") if isinstance(strict_contract.get("boundary"), dict) else {}
    strict_summary = strict_contract.get("summary") if isinstance(strict_contract.get("summary"), dict) else {}
    add_check(
        checks,
        strict_contract.get("decision") in {"test", "watch"}
        and isinstance(strict_data.get("paper_decision_admissible"), bool)
        and strict_data.get("policy_mutation_allowed") is False
        and strict_summary.get("trading_signal") is False
        and strict_boundary.get("real_order_execution") is False,
        "strict_close_contract_guard",
        (
            f"decision={strict_contract.get('decision')}; "
            f"paper={strict_data.get('paper_decision_admissible')}; "
            f"policy_mutation={strict_data.get('policy_mutation_allowed')}; "
            f"trading_signal={strict_summary.get('trading_signal')}"
        ),
    )

    add_check(
        checks,
        CRON_PRIMARY.exists() and "dnd-cycle.sh bitcoin-regime-lab" in CRON_PRIMARY.read_text(encoding="utf-8", errors="replace"),
        "primary_cron_present",
        str(CRON_PRIMARY),
    )
    add_check(
        checks,
        (not args.require_extra_cron) or CRON_EXTRA.exists(),
        "extra_night_cron_present",
        str(CRON_EXTRA),
    )

    date_refs: list[str] = []
    if args.date:
        date_refs = cycle_refs_for_date(args.date)
        add_check(
            checks,
            len(date_refs) >= args.min_cycles_for_date,
            "date_cycle_count",
            f"date={args.date}; cycles={len(date_refs)}; required={args.min_cycles_for_date}",
            cycle_refs=date_refs,
        )

    failed = [row for row in checks if not row["ok"]]
    return {
        "schema": "dndlab.bitcoin.night_run_smoke.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "domain": DOMAIN,
        "status": "pass" if not failed else "fail",
        "cycle_ref": cycle_ref,
        "date": args.date,
        "checks": checks,
        "failures": failed,
        "health": {
            "status": health.get("status"),
            "latest_artifacts_total": health.get("latest_artifacts_total"),
            "expected_latest_total": health.get("expected_latest_total"),
            "latest_cycle_ref": health.get("latest_cycle_ref"),
            "closure_status": health.get("closure_status"),
            "warnings": health_warnings,
        },
        "boundary": "Read-only BTC Lab smoke guard; no market fetch, no cycle run, no real orders, no public advice.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only smoke guard for BTC Lab night runs.")
    parser.add_argument("--json", action="store_true", help="Pretty-print JSON.")
    parser.add_argument("--cycle-ref", help="Specific cycle ref to inspect, e.g. 20260526_1853.")
    parser.add_argument("--after-cycle", help="Require latest cycle ref to be greater than this ref.")
    parser.add_argument("--date", help="YYYYMMDD date prefix to count cycle traces.")
    parser.add_argument("--min-cycles-for-date", type=int, default=0, help="Minimum traces required for --date.")
    parser.add_argument("--require-extra-cron", action="store_true", help="Require the temporary extra-night cron file.")
    args = parser.parse_args()

    payload = build_smoke(args)
    print(json.dumps(payload, indent=2 if args.json else None, ensure_ascii=False))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
