#!/usr/bin/env python3
"""Finance Lab end-to-end smoke check.

This verifies the current autonomous surface from generated artifacts and
read-only tools. It does not fetch a new market family, run a cognitive cycle,
place orders, or promote paper/live-sim.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


DOMAIN_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = DOMAIN_DIR.parents[1]
VALUE_DIR = REPO_ROOT / "data" / "finance" / "value"


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def run_json(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(DOMAIN_DIR / "tools" / script), "--json"],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    if proc.returncode != 0:
        return {
            "status": "error",
            "error": proc.stderr.strip() or proc.stdout.strip(),
            "returncode": proc.returncode,
        }
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"status": "error", "error": "invalid_json", "stdout": proc.stdout[:500]}
    return payload if isinstance(payload, dict) else {"status": "error", "error": "non_object_json"}


def summary(name: str) -> dict[str, Any]:
    payload = read_json(VALUE_DIR / name)
    item = payload.get("summary")
    return item if isinstance(item, dict) else {}


def add(checks: list[dict[str, Any]], ok: bool, check: str, detail: str) -> None:
    checks.append({"check": check, "ok": ok, "detail": detail})


def build_smoke() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    health = run_json("finance_operational_health.py")
    health_summary = health.get("summary") if isinstance(health.get("summary"), dict) else {}
    add(
        checks,
        health.get("status") == "pass",
        "operational_health_pass",
        f"status={health.get('status')}; failures={health_summary.get('failures')}",
    )
    add(
        checks,
        health_summary.get("price_branch_closed") is True,
        "price_branch_closure_absorbed",
        str(health_summary.get("price_branch_closure")),
    )

    contract = run_json("finance_autonomous_trading_contract.py")
    contract_summary = contract.get("summary") if isinstance(contract.get("summary"), dict) else {}
    add(
        checks,
        contract_summary.get("current_stage") == "diagnostic_only"
        and contract_summary.get("paper_live_sim_allowed") is False
        and contract_summary.get("broker_sandbox_allowed") is False
        and contract_summary.get("real_execution_allowed") is False,
        "execution_boundaries_closed",
        (
            f"stage={contract_summary.get('current_stage')}; "
            f"paper={contract_summary.get('paper_live_sim_allowed')}; "
            f"sandbox={contract_summary.get('broker_sandbox_allowed')}; "
            f"real={contract_summary.get('real_execution_allowed')}"
        ),
    )

    scout = run_json("finance_autonomy_opportunity_scout.py")
    scout_summary = scout.get("summary") if isinstance(scout.get("summary"), dict) else {}
    add(
        checks,
        scout_summary.get("selected_opportunity") in {
            "external_macro_provider_or_pause",
            "external_macro_provider_repair",
            "no_current_edge_or_new_external_provider",
        },
        "autonomy_selects_non_repeating_next_step",
        str(scout_summary.get("selected_opportunity")),
    )

    readiness = run_json("finance_profit_readiness.py")
    readiness_summary = readiness.get("summary") if isinstance(readiness.get("summary"), dict) else {}
    add(
        checks,
        readiness_summary.get("status") == "not_ready"
        and readiness_summary.get("next_action") in {
            "external_macro_or_new_data_source_review",
            "repair_or_replace_external_macro_provider",
            "no_current_edge_or_new_external_provider",
        },
        "profit_readiness_blocks_repeat",
        f"status={readiness_summary.get('status')}; next={readiness_summary.get('next_action')}",
    )

    data = run_json("finance_data_intake_audit.py")
    data_summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    add(
        checks,
        data_summary.get("status") in {"pass", "warn"}
        and data_summary.get("selected_opportunity") in {
            "external_macro_provider_or_pause",
            "external_macro_provider_repair",
            "no_current_edge_or_new_external_provider",
        },
        "data_intake_stage_fit",
        f"status={data_summary.get('status')}; selected={data_summary.get('selected_opportunity')}",
    )

    volatility = summary("finance_volatility_macro_object_review_latest.json")
    add(
        checks,
        volatility.get("label") == "no_volatility_macro_candidate",
        "volatility_macro_branch_closed",
        str(volatility.get("label")),
    )
    external_macro = read_json(VALUE_DIR / "finance_external_macro_probe_latest.json")
    external_class = external_macro.get("classification") if isinstance(external_macro.get("classification"), dict) else {}
    add(
        checks,
        external_class.get("label") in {
            "no_external_macro_delta",
            "external_macro_provider_review_required",
            "external_macro_probe_candidate",
        },
        "external_macro_probe_read",
        str(external_class.get("label")),
    )

    failures = [row for row in checks if not row["ok"]]
    return {
        "schema": "dndlab.finance.e2e_smoke.v1",
        "domain": "finance",
        "status": "pass" if not failures else "fail",
        "checks": checks,
        "failures": failures,
        "boundary": "Read-only E2E smoke: verifies autonomous lab state, no orders and no paper promotion.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = build_smoke()
    print(json.dumps(payload, indent=2 if args.json else None, ensure_ascii=False))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
