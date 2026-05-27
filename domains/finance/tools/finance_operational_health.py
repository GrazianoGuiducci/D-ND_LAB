#!/usr/bin/env python3
"""Finance Lab operational health guard.

Read-only by default. It checks whether the Finance Lab is ready for the next
real-market transfer/health step without running a cognitive cycle, making a
market claim, or producing a trading signal.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DOMAIN = "finance"
DOMAIN_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = DOMAIN_DIR.parents[1]
DATA_DIR = REPO_ROOT / "data" / DOMAIN
DIAGNOSTICS_DIR = DATA_DIR / "diagnostics"
HEALTH_DIR = DATA_DIR / "health"
VALUE_DIR = DATA_DIR / "value"
PRECONDITION_CONTRACT = DOMAIN_DIR / "precondition_contract.json"
CONFIG = DOMAIN_DIR / "config.json"
MML = DOMAIN_DIR / "mml.json"
SEED = DATA_DIR / "seed.json"
TRAJECTORY_STATE = DATA_DIR / "trajectory_state.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path)


def _latest(pattern: str) -> Path | None:
    paths = sorted(DIAGNOSTICS_DIR.glob(pattern))
    return paths[-1] if paths else None


def _run_assertions() -> dict[str, Any]:
    script = DOMAIN_DIR / "assertions.py"
    try:
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc), "results": []}
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": proc.stderr.strip() or "invalid_json", "results": []}
    failures = [row for row in results if isinstance(row, dict) and row.get("status") == "FAIL"]
    return {"ok": proc.returncode == 0 and not failures, "error": proc.stderr.strip(), "results": results}


def _add(rows: list[dict[str, Any]], ok: bool, check: str, detail: str, *, level: str = "failure") -> None:
    rows.append({"check": check, "ok": ok, "level": level, "detail": detail})


def build_health(*, run_assertions: bool = True) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for path in (CONFIG, MML, PRECONDITION_CONTRACT, SEED):
        _add(checks, path.exists(), "required_file_present", _repo_path(path))

    config = _read_json(CONFIG)
    movements = config.get("movements") if isinstance(config.get("movements"), dict) else {}
    for movement in ("trajectory_apply", "veritas_score", "trajectory_evaluator", "report_falsifier"):
        enabled = bool((movements.get(movement) or {}).get("enabled"))
        _add(checks, enabled, "movement_enabled", movement)

    mml = _read_json(MML)
    skills = mml.get("skills_attive") if isinstance(mml.get("skills_attive"), dict) else {}
    skill_count = sum(len(value) for value in skills.values() if isinstance(value, list))
    _add(checks, skill_count >= 16, "mml_skill_count", f"{skill_count}")

    precondition = _read_json(PRECONDITION_CONTRACT)
    selected = precondition.get("selected_precondition") if isinstance(precondition.get("selected_precondition"), dict) else {}
    calibration = precondition.get("calibration_summary") if isinstance(precondition.get("calibration_summary"), dict) else {}
    allowed = precondition.get("allowed_next_cycle") if isinstance(precondition.get("allowed_next_cycle"), dict) else {}
    must_not = allowed.get("must_not_do") if isinstance(allowed.get("must_not_do"), list) else []
    _add(
        checks,
        selected.get("score_min") == 0.55 and selected.get("metric") == "matched_filter_score_at_candidate_split",
        "precondition_selected",
        f"metric={selected.get('metric')}; score_min={selected.get('score_min')}",
    )
    _add(
        checks,
        calibration.get("selected_controls") == 0
        and (calibration.get("positive_robust_rate_after_precondition") or 0) >= 0.70,
        "precondition_calibration",
        (
            f"selected_controls={calibration.get('selected_controls')}; "
            f"positive_robust={calibration.get('positive_robust_rate_after_precondition')}"
        ),
    )
    _add(
        checks,
        any(("trading" in str(row).lower() and "advice" in str(row).lower()) for row in must_not),
        "precondition_no_advice_boundary",
        "must_not contains trading-advice block",
    )

    transfer_path = _latest("finance_transfer_diagnostic_*.json")
    recurrence_path = _latest("finance_recurrence_diagnostic_*.json")
    diagnostic = _read_json(transfer_path) if transfer_path else {}
    classification = diagnostic.get("classification") if isinstance(diagnostic.get("classification"), dict) else {}
    rows = diagnostic.get("rows") if isinstance(diagnostic.get("rows"), list) else []
    ok_rows = [row for row in rows if isinstance(row, dict) and row.get("status") == "OK"]
    review_rows = [row for row in rows if isinstance(row, dict) and row.get("status") != "OK"]
    _add(checks, transfer_path is not None, "latest_transfer_diagnostic_present", _repo_path(transfer_path) if transfer_path else "missing")
    _add(checks, diagnostic.get("schema") == "finance_transfer_diagnostic.v1", "latest_transfer_schema", str(diagnostic.get("schema")))
    _add(
        checks,
        classification.get("operational") is False
        and classification.get("public_claim") is False
        and classification.get("trading_signal") is False,
        "transfer_boundary",
        (
            f"operational={classification.get('operational')}; "
            f"public_claim={classification.get('public_claim')}; "
            f"trading_signal={classification.get('trading_signal')}"
        ),
    )
    _add(checks, len(ok_rows) >= 3 and not review_rows, "transfer_rows_evaluable", f"ok={len(ok_rows)}; review={len(review_rows)}")
    provenance_ok = all(
        isinstance(row.get("data_card"), dict)
        and row["data_card"].get("source_url")
        and row["data_card"].get("retrieval_ts")
        and row["data_card"].get("n_obs")
        for row in ok_rows
    )
    _add(checks, bool(ok_rows) and provenance_ok, "transfer_data_card_provenance", f"rows={len(ok_rows)}")
    _add(
        checks,
        classification.get("label") in {"no_transfer_delta", "single_or_partial_window", "iid_only_review", "correlated_equity_local", "cross_asset_candidate"},
        "transfer_classification_known",
        str(classification.get("label")),
    )
    if classification.get("label") == "no_transfer_delta":
        warnings.append({
            "check": "transfer_delta_absent",
            "detail": "Latest real-market transfer diagnostic is a negative constraint, not a failure.",
        })
    _add(checks, recurrence_path is not None, "latest_recurrence_diagnostic_present", _repo_path(recurrence_path) if recurrence_path else "missing")

    trajectory = _read_json(TRAJECTORY_STATE)
    if trajectory.get("decision") == "NEXT_CYCLE" and trajectory.get("confidence") == "low":
        warnings.append({
            "check": "low_confidence_trajectory",
            "detail": "Use finance_reference_audit/seed direction before treating pending NEXT_CYCLE as authority.",
        })
    _add(checks, trajectory.get("domain") == DOMAIN, "trajectory_domain", str(trajectory.get("domain")))

    assertion_payload = {"ok": None, "results": []}
    if run_assertions:
        assertion_payload = _run_assertions()
        results = assertion_payload.get("results") if isinstance(assertion_payload.get("results"), list) else []
        passed = [row for row in results if isinstance(row, dict) and row.get("status") == "PASS"]
        _add(checks, bool(assertion_payload.get("ok")) and len(passed) == 5, "assertions_pass", f"{len(passed)}/5")

    failures = [row for row in checks if not row["ok"] and row["level"] == "failure"]
    return {
        "schema": "dndlab.finance.operational_health.v1",
        "generated_at": _utc_now(),
        "domain": DOMAIN,
        "status": "pass" if not failures else "fail",
        "checks": checks,
        "failures": failures,
        "warnings": warnings,
        "summary": {
            "checks": len(checks),
            "failures": len(failures),
            "warnings": len(warnings),
            "latest_transfer_diagnostic": _repo_path(transfer_path) if transfer_path else None,
            "latest_transfer_label": classification.get("label"),
            "transfer_ok_rows": len(ok_rows),
            "latest_recurrence_diagnostic": _repo_path(recurrence_path) if recurrence_path else None,
            "trajectory_decision": trajectory.get("decision"),
            "trajectory_confidence": trajectory.get("confidence"),
            "assertions_checked": run_assertions,
        },
        "boundary": (
            "Operational health only: diagnostic-stage readback, no public advice, "
            "no real order execution and no cognitive cycle. Internal trading "
            "decisions require the autonomous trading stage contract."
        ),
    }


def write_health(payload: dict[str, Any]) -> dict[str, str]:
    HEALTH_DIR.mkdir(parents=True, exist_ok=True)
    VALUE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stamped = HEALTH_DIR / f"finance_operational_health_{stamp}.json"
    latest = HEALTH_DIR / "finance_operational_health_latest.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    stamped.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")

    value_payload = build_value_artifact(payload)
    value_text = json.dumps(value_payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    value_stamped = VALUE_DIR / f"finance_operational_health_{stamp}.json"
    value_latest = VALUE_DIR / "finance_operational_health_latest.json"
    value_stamped.write_text(value_text, encoding="utf-8")
    value_latest.write_text(value_text, encoding="utf-8")
    return {
        "stamped": str(stamped),
        "latest": str(latest),
        "value_stamped": str(value_stamped),
        "value_latest": str(value_latest),
    }


def build_value_artifact(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    failures = payload.get("failures") if isinstance(payload.get("failures"), list) else []
    status = str(payload.get("status") or "unknown")
    latest_label = summary.get("latest_transfer_label") or "unknown"
    trajectory_decision = summary.get("trajectory_decision") or "unknown"
    trajectory_confidence = summary.get("trajectory_confidence") or "unknown"
    checks = summary.get("checks")
    failure_count = summary.get("failures")
    warning_count = summary.get("warnings")
    card = {
        "claim_id": "finance_operational_health",
        "title": "Finance operational health",
        "claim": "The Finance Lab has enough local substrate to attempt the next supervised real-market transfer diagnostic step.",
        "decision": "watch" if status == "pass" else "repair",
        "verdict": f"FINANCE_HEALTH_{status.upper()}",
        "evidence": f"{checks} checks; {failure_count} failures; {warning_count} warnings; latest transfer label {latest_label}.",
        "baseline": "Required files, MML movements, precondition contract, latest diagnostics, recurrence diagnostic and assertions are checked before a new cycle.",
        "null": "A pass does not promote a trade: it only says the operational surface is coherent enough to continue.",
        "falsifier": "Any missing required file, disabled required movement, broken no-advice boundary, invalid latest diagnostic or assertion failure returns fail.",
        "boundary": payload.get("boundary"),
        "next_test": "Run a supervised finance transfer diagnostic or autonomy-stage readback only if the next object/mechanism is materially new and predeclared.",
    }
    return {
        "schema": "dndlab.finance.operational_health.value.v1",
        "generated_at": payload.get("generated_at"),
        "domain": DOMAIN,
        "summary": {
            "status": status,
            "checks": checks,
            "failures": failure_count,
            "warnings": warning_count,
            "latest_transfer_label": latest_label,
            "transfer_ok_rows": summary.get("transfer_ok_rows"),
            "trajectory_decision": trajectory_decision,
            "trajectory_confidence": trajectory_confidence,
            "trading_signal": False,
            "operational": False,
        },
        "cards": [card],
        "warnings": warnings[:5],
        "failures": failures[:5],
        "boundary": payload.get("boundary"),
        "source": {
            "tool": _repo_path(Path(__file__)),
            "health_schema": payload.get("schema"),
            "latest_transfer_diagnostic": summary.get("latest_transfer_diagnostic"),
            "latest_recurrence_diagnostic": summary.get("latest_recurrence_diagnostic"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Finance Lab operational health.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--no-assertions", action="store_true")
    args = parser.parse_args()

    payload = build_health(run_assertions=not args.no_assertions)
    if args.write:
        payload["files"] = write_health(payload)
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps({"status": payload["status"], "files": payload.get("files"), "summary": payload["summary"]}, indent=2))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
