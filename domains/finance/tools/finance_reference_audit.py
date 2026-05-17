#!/usr/bin/env python3
"""Audit the finance reference lab state before another cycle.

This tool is intentionally conservative. It does not run a new detector and it
does not promote finance claims. It checks whether the installable finance lab
contains the current reference substrate: skill-reading matrix, corrected MML
roles, latest runtime direction when available, and a clear next-cycle
precondition.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def collect_mml(domain: Path) -> dict[str, Any]:
    mml = read_json(domain / "mml.json") or {}
    skills = []
    support_only = []
    missing_depth = []
    bad_sources = []
    raw_layers = mml.get("skills_attive", {})
    if isinstance(raw_layers, dict):
        for layer, entries in raw_layers.items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name")
                if not name:
                    continue
                skills.append({"name": name, "layer": layer, **entry})
                if entry.get("support_only"):
                    support_only.append(name)
                if not entry.get("read_depth"):
                    missing_depth.append(name)
                source = str(entry.get("source") or "")
                if source.endswith("agent_skills_research_lab.md") and source.startswith("kernel/"):
                    bad_sources.append({"name": name, "source": source})
                if source == ".claude/skills/dnd-method.md":
                    bad_sources.append({"name": name, "source": source})
    return {
        "skill_count": len(skills),
        "support_only": support_only,
        "missing_read_depth": missing_depth,
        "bad_sources": bad_sources,
        "skills": skills,
    }


def latest_trajectory(data_dir: Path) -> dict[str, Any] | None:
    path = data_dir / "trajectory_log.jsonl"
    if not path.exists():
        return None
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return None
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError:
        return {"parse_error": "last trajectory line is not valid JSON"}


def latest_trajectory_path(data_dir: Path) -> str:
    return str((data_dir / "trajectory_log.jsonl").relative_to(repo_root()))


def latest_trajectory_state(data_dir: Path) -> dict[str, Any] | None:
    path = data_dir / "trajectory_state.json"
    return read_json(path)


def latest_trajectory_state_path(data_dir: Path) -> str:
    return str((data_dir / "trajectory_state.json").relative_to(repo_root()))


def seed_path(data_dir: Path) -> str:
    return str((data_dir / "seed.json").relative_to(repo_root()))


def latest_diagnostic(data_dir: Path) -> dict[str, Any] | None:
    diagnostics = data_dir / "diagnostics"
    if not diagnostics.exists():
        return None
    files = sorted(
        diagnostics.glob("*diagnostic*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not files:
        return None
    payload = read_json(files[0]) or {}
    return {
        "path": str(files[0].relative_to(repo_root())),
        "kind": payload.get("kind"),
        "schema": payload.get("schema"),
        "classification": payload.get("classification"),
        "maturity": payload.get("maturity"),
        "boundary": payload.get("boundary"),
    }


def audit(root: Path) -> dict[str, Any]:
    domain = root / "domains" / "finance"
    data_dir = root / "data" / "finance"
    context = (domain / "context.md").read_text(encoding="utf-8")
    transduction = (domain / "transduction.md").read_text(encoding="utf-8")
    precondition_contract = read_json(domain / "precondition_contract.json")
    mml_state = collect_mml(domain)
    seed = read_json(data_dir / "seed.json")
    trajectory = latest_trajectory(data_dir)
    trajectory_state = latest_trajectory_state(data_dir)
    diagnostic = latest_diagnostic(data_dir)

    has_skill_matrix = "skill_reading_matrix" in transduction
    has_reference_correction = "Skill reading reference" in context
    has_precondition_rule = "precondizione mancante" in context or "missing precondition" in context
    has_precondition_contract = (
        isinstance(precondition_contract, dict)
        and precondition_contract.get("schema") == "dndlab.finance_precondition_contract.v1"
        and isinstance(precondition_contract.get("selected_precondition"), dict)
    )
    precondition_policy = None
    followup_policy = None
    followup_artifact = None
    if isinstance(precondition_contract, dict):
        allowed_next = precondition_contract.get("allowed_next_cycle", {})
        if isinstance(allowed_next, dict):
            precondition_policy = allowed_next.get("policy")
        followup = precondition_contract.get("selected_followup_branch", {})
        if isinstance(followup, dict):
            followup_policy = followup.get("policy")
            followup_artifact = followup.get("current_artifact")
    runtime_present = seed is not None and trajectory is not None

    latest_decision = trajectory.get("decision") if isinstance(trajectory, dict) else None
    latest_reasoning = trajectory.get("reasoning") if isinstance(trajectory, dict) else None
    latest_executed = trajectory.get("executed") if isinstance(trajectory, dict) else None
    latest_action = trajectory.get("action", {}) if isinstance(trajectory, dict) else {}
    if isinstance(latest_action, dict):
        detail = latest_action.get("detail", {})
    else:
        detail = {}
    if not isinstance(detail, dict):
        detail = {}
    pending_direction = detail.get("new_value") or detail.get("direction") or detail.get("seed_change")
    seed_direction = seed.get("direzione") if isinstance(seed, dict) else None
    state_direction = None
    state_status = None
    if isinstance(trajectory_state, dict):
        state_direction = trajectory_state.get("direction")
        state_status = trajectory_state.get("status")

    if state_status == "pending" and state_direction:
        next_direction = state_direction
        next_direction_source = "trajectory_state_pending"
    elif state_status == "applied" and seed_direction:
        next_direction = seed_direction
        next_direction_source = "trajectory_state_applied_seed"
    elif latest_executed is False and pending_direction:
        next_direction = pending_direction
        next_direction_source = "pending_trajectory"
    elif seed_direction:
        next_direction = seed_direction
        next_direction_source = "seed_current"
        if latest_executed is True:
            next_direction_source = "applied_seed_direction"
    else:
        next_direction = pending_direction
        next_direction_source = "unknown"

    trajectory_observability = {
        "seed_path": seed_path(data_dir),
        "trajectory_log_path": latest_trajectory_path(data_dir),
        "trajectory_state_path": latest_trajectory_state_path(data_dir),
        "latest_diagnostic_path": diagnostic.get("path") if isinstance(diagnostic, dict) else None,
        "latest_log_cycle_ref": trajectory.get("cycle_ref") if isinstance(trajectory, dict) else None,
        "latest_log_executed": latest_executed,
        "latest_log_decision": latest_decision,
        "latest_log_action_type": latest_action.get("type") if isinstance(latest_action, dict) else None,
        "latest_state_status": state_status,
        "latest_state_cycle_ts": trajectory_state.get("cycle_ts") if isinstance(trajectory_state, dict) else None,
        "latest_state_entry_cycle_ref": trajectory_state.get("entry_cycle_ref") if isinstance(trajectory_state, dict) else None,
        "latest_state_decision": trajectory_state.get("decision") if isinstance(trajectory_state, dict) else None,
        "latest_state_executed": trajectory_state.get("executed") if isinstance(trajectory_state, dict) else None,
        "resolved_next_direction_source": next_direction_source,
        "resolved_next_direction": next_direction,
    }

    blockers: list[str] = []
    if not has_skill_matrix:
        blockers.append("missing skill_reading_matrix in transduction.md")
    if not has_reference_correction:
        blockers.append("missing Skill reading reference section in context.md")
    if mml_state["missing_read_depth"]:
        blockers.append("some MML skills lack read_depth")
    if mml_state["bad_sources"]:
        blockers.append("some MML skills still point to unresolved legacy sources")
    if not has_precondition_rule:
        blockers.append("next-cycle precondition rule not stated in context.md")

    crystallized_boundary = (
        isinstance(precondition_contract, dict)
        and isinstance(precondition_contract.get("boundary_crystallization"), dict)
    )

    next_cycle_policy = "DESIGN_PRECONDITION_FIRST"
    if blockers:
        next_cycle_policy = "BLOCKED_REFERENCE_INCOMPLETE"
    elif next_direction_source == "trajectory_state_pending":
        next_cycle_policy = "PENDING_TRAJECTORY"
    elif crystallized_boundary and followup_policy:
        next_cycle_policy = str(followup_policy)
    elif crystallized_boundary and latest_decision == "CRYSTALLIZE":
        next_cycle_policy = "CRYSTALLIZE_PROMOTION_BOUNDARY"
    elif has_precondition_contract and precondition_policy:
        next_cycle_policy = str(precondition_policy)
    elif runtime_present and latest_decision == "REDESIGN":
        next_cycle_policy = "DESIGN_PRECONDITION_FIRST"
    elif runtime_present:
        next_cycle_policy = "CYCLE_ALLOWED_WITH_MONITORING"

    return {
        "schema": "finance_reference_audit.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "domain": "finance",
        "reference_ready": not blockers,
        "next_cycle_policy": next_cycle_policy,
        "blockers": blockers,
        "runtime_present": runtime_present,
        "seed_piano": seed.get("piano") if isinstance(seed, dict) else None,
        "latest_trajectory_decision": latest_decision,
        "latest_trajectory_reasoning": latest_reasoning,
        "latest_trajectory_executed": latest_executed,
        "latest_trajectory_state": trajectory_state,
        "trajectory_observability": trajectory_observability,
        "next_direction": next_direction,
        "next_direction_source": next_direction_source,
        "latest_diagnostic": diagnostic,
        "checks": {
            "skill_reading_matrix": has_skill_matrix,
            "context_reference_correction": has_reference_correction,
            "precondition_rule": has_precondition_rule,
            "precondition_contract": has_precondition_contract,
            "precondition_policy": precondition_policy,
            "followup_policy": followup_policy,
            "followup_artifact": followup_artifact,
            "boundary_crystallization": crystallized_boundary,
            "latest_diagnostic_kind": diagnostic.get("kind") if isinstance(diagnostic, dict) else None,
            "latest_diagnostic_path": diagnostic.get("path") if isinstance(diagnostic, dict) else None,
            "next_direction_source": next_direction_source,
            "mml_skill_count": mml_state["skill_count"],
            "mml_support_only": mml_state["support_only"],
            "mml_missing_read_depth": mml_state["missing_read_depth"],
            "mml_bad_sources": mml_state["bad_sources"],
        },
        "interpretation": (
            "Finance is a reference lab only after the skill-reading substrate is "
            "present. If the promotion boundary is crystallized and a follow-up "
            "branch is selected, the next work follows that branch while preserving "
            "the gate as provisional, keeping below-gate survivors visible, and "
            "blocking trading-signal language. next_direction_source distinguishes "
            "a pending trajectory from an already applied seed direction so a future "
            "cycle does not relaunch stale continuation. Otherwise the lab must "
            "discover or test the precondition before more adaptive lag-map tuning."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(repo_root()), help="D-ND_LAB root")
    parser.add_argument("--json", action="store_true", help="emit JSON only")
    args = parser.parse_args()

    payload = audit(Path(args.root).resolve())
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if payload["reference_ready"] else 1

    print("Finance reference audit")
    print(f"reference_ready: {payload['reference_ready']}")
    print(f"next_cycle_policy: {payload['next_cycle_policy']}")
    print(f"seed_piano: {payload['seed_piano']}")
    if payload["blockers"]:
        print("blockers:")
        for blocker in payload["blockers"]:
            print(f"- {blocker}")
    else:
        print("blockers: none")
    return 0 if payload["reference_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
