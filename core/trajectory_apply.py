"""trajectory_apply movement — applies log-only trajectory_evaluator decisions.

Chiude il loop autopoietico A8 + A15 che era spezzato:

  trajectory_evaluator (cycle N) decide REDESIGN con confidence=high
    → scrive entry in trajectory_log.jsonl con executed: false (log-only)
    → next cycle non leggeva la decisione
    → REDESIGN proposto ma mai applicato al seed
    → sistema in stallo (P5 sterile rilevato da aeternitas)

Con trajectory_apply, il loop si chiude:

  cycle N+1:
    autopsy → trajectory_apply (legge ultima entry log) → build_field
      ↓
      Se entry eligible (executed=false, confidence=high, modify_seme/trigger_cycle):
        - applica action.detail al seed (modifica direzione o continuità)
        - aggiunge tensione marker porta=trajectory_apply
        - marca executed=true nel log
      Se non eligible: skip + log info

  → build_field legge seed con REDESIGN applicato
  → agent lavora sulla nuova direzione
  → seed_integrator + aeternitas vegliano la cristallizzazione

Whitelist conservativa (matched al trajectory_evaluator design notes):
  - action.type == 'modify_seme'
  - action.detail.field == 'direzione'
  - confidence == 'high'
  - executed == false
  - new_value non vuoto
  - action.type == 'trigger_cycle'
  - decision == 'NEXT_CYCLE'
  - confidence == 'high'
  - action.detail contiene un testo operativo (seed_change/direction/directive/instruction/next_focus)

Altri action types (notify_operator, crystallize_note, escalate_cowork)
sono skip — sono effetti collaterali, non modifiche al seed.
trigger_cycle NON avvia processi: registra nel seed la continuità del
NEXT_CYCLE così il ciclo successivo legge la traiettoria invece di dipendere
da inferenza implicita sui log.

BTC guarded autonomy: `bitcoin-regime-lab` può assorbire anche una direzione
strutturale `medium` se health, closure e falsifier sono verdi e la direzione
resta nel Lab. Il trading simulato e' un oggetto valido di apprendimento; la
distinzione e' tra paper/live-sim misurabile e side effect esterni non
verificati.

Idempotente: marca executed=true dopo application. Re-runs non
re-applicano la stessa entry.

Lab opt-in: il movement è disabled di default. Lab esistenti devono
abilitarlo via config.json:movements.trajectory_apply.enabled=true.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import config as cfg
from core import paths
from core.lab_agent import CycleContext, register_movement
from core.trajectory_state import write_trajectory_state

logger = logging.getLogger(__name__)


# Whitelist conservativa — extend solo dopo che il pattern è validato in vivo
ELIGIBLE_ACTION_TYPES = {"modify_seme", "trigger_cycle"}
ELIGIBLE_FIELDS = {"direzione"}
ELIGIBLE_CONFIDENCES = {"high"}

TRIGGER_TEXT_KEYS = (
    "seed_change",
    "direction",
    "directive",
    "instruction",
    "next_focus",
    "target",
    "constraint",
    "success_gate",
    "reason",
)


def _read_last_trajectory_entry(domain: str) -> dict[str, Any] | None:
    """Read last entry from data/<domain>/trajectory_log.jsonl.

    Returns None if log missing/empty/malformed.
    """
    log_path = paths.domain_data_dir(domain) / "trajectory_log.jsonl"
    if not log_path.exists():
        return None
    try:
        lines = [
            line.strip()
            for line in log_path.read_text().splitlines()
            if line.strip()
        ]
        if not lines:
            return None
        return json.loads(lines[-1])
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("trajectory_apply: failed to read log: %s", e)
        return None


def _is_eligible(entry: dict[str, Any]) -> tuple[bool, str]:
    """Check entry against whitelist. Returns (eligible, reason)."""
    if entry.get("executed") is True:
        return False, "already executed"
    confidence = entry.get("confidence")
    if confidence not in ELIGIBLE_CONFIDENCES:
        return False, f"confidence='{confidence}' not in {ELIGIBLE_CONFIDENCES}"
    action = entry.get("action") or {}
    if not isinstance(action, dict):
        return False, "action not dict"
    a_type = action.get("type")
    if a_type not in ELIGIBLE_ACTION_TYPES:
        return False, f"action.type='{a_type}' not in {ELIGIBLE_ACTION_TYPES}"
    detail = action.get("detail") or {}
    if not isinstance(detail, dict):
        return False, "action.detail not dict"

    if a_type == "modify_seme":
        field = detail.get("field")
        if field not in ELIGIBLE_FIELDS:
            return False, f"action.detail.field='{field}' not in {ELIGIBLE_FIELDS}"
        new_value = detail.get("new_value", "")
        if not isinstance(new_value, str) or not new_value.strip():
            return False, "action.detail.new_value empty or non-string"
        return True, "eligible"

    if a_type == "trigger_cycle":
        decision = entry.get("decision")
        if decision != "NEXT_CYCLE":
            return False, f"trigger_cycle requires decision='NEXT_CYCLE' (got: {decision})"
        if not _trigger_cycle_direction(detail):
            return False, "trigger_cycle detail has no operational text"
        return True, "eligible"

    return True, "eligible"


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _btc_guarded_medium_eligible(domain: str, entry: dict[str, Any]) -> tuple[bool, str]:
    """Narrow BTC self-step for medium-confidence structural directions.

    This lets the next cycle read and work a Lab-evolution direction. Paper
    trading is a valid measurement surface; any later real-money or public
    side effect still has to appear as an artifact, pass the domain gates, and
    be visible to falsifier/health/closure.
    """
    if domain != "bitcoin-regime-lab":
        return False, ""
    if entry.get("executed") is True or entry.get("confidence") != "medium":
        return False, ""
    action = entry.get("action") or {}
    if not isinstance(action, dict) or action.get("type") != "modify_seme":
        return False, ""
    detail = action.get("detail") or {}
    if not isinstance(detail, dict) or detail.get("field") != "direzione":
        return False, ""
    new_value = detail.get("new_value")
    if not isinstance(new_value, str) or not new_value.strip():
        return False, ""
    direction = new_value.upper()
    if "DAILY_GATE_HELD" not in direction and "FIRST_CLASS" not in direction:
        return False, "BTC guarded medium requires DAILY_GATE_HELD or FIRST_CLASS direction"

    data_dir = paths.domain_data_dir(domain)
    health = _read_json_file(data_dir / "health" / "btc_operational_health_latest.json")
    if health.get("status") != "pass":
        return False, "BTC health not pass"
    latest_cycle = health.get("latest_cycle_ref") or entry.get("cycle_ref")
    if not isinstance(latest_cycle, str) or not latest_cycle:
        return False, "missing latest cycle ref"
    closure = _read_json_file(data_dir / "closure" / f"btc_runtime_lineage_closure_{latest_cycle}.json")
    if closure.get("status") != "pass" or closure.get("phase") != "post_cycle":
        return False, "latest closure not post_cycle/pass"
    falsifier = _read_json_file(data_dir / "falsifier" / f"falsifier_{latest_cycle}.json")
    flags = falsifier.get("flags")
    if falsifier.get("coherent") is not True or not isinstance(flags, list) or flags:
        return False, "latest falsifier not coherent zero-flag"
    gate = _read_json_file(data_dir / "value" / "btc_daily_closed_evidence_gate_latest.json")
    gate_state = gate.get("gate") if isinstance(gate.get("gate"), dict) else {}
    if gate_state.get("mutation_allowed") is not False:
        return False, "daily gate is not explicitly held"
    return True, "BTC guarded medium structural self-step"


def _btc_entry_policy_class(entry: dict[str, Any]) -> str:
    action = entry.get("action") or {}
    detail = action.get("detail") if isinstance(action, dict) else {}
    text = " ".join(
        str(value)
        for value in (
            entry.get("decision"),
            entry.get("reasoning"),
            detail.get("new_value") if isinstance(detail, dict) else "",
            detail.get("reason") if isinstance(detail, dict) else "",
        )
        if value
    ).lower()
    structural_tokens = ("contract", "first-class artifact", "first class artifact", "readable", "binding")
    no_mutation_tokens = ("without applying", "no policy mutation", "mutation_allowed=false", "blocked")
    if any(token in text for token in structural_tokens) and any(token in text for token in no_mutation_tokens):
        return "structural_contract"
    policy_tokens = ("method_policy_mutation", "policy mutation", "mutate policy", "mutazione policy", "reinterpret", "promote method", "method promotion")
    if any(token in text for token in policy_tokens):
        return "method_policy_mutation"
    return "structural_seed_direction"


def _btc_policy_contract_allows_entry(domain: str, entry: dict[str, Any]) -> tuple[bool, str]:
    if domain != "bitcoin-regime-lab":
        return True, "not BTC"
    effect = _btc_entry_policy_class(entry)
    if effect != "method_policy_mutation":
        return True, f"BTC {effect} allowed"
    data_dir = paths.domain_data_dir(domain)
    payload = _read_json_file(data_dir / "value" / "btc_policy_mutation_contract_latest.json")
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    if not contract:
        return False, "BTC policy mutation contract missing"
    allowed = contract.get("allowed_effects") if isinstance(contract.get("allowed_effects"), list) else []
    blocked = contract.get("blocked_effects") if isinstance(contract.get("blocked_effects"), list) else []
    if contract.get("policy_mutation_allowed") is True and "method_policy_mutation" in allowed:
        return True, "BTC policy mutation contract allows method_policy_mutation"
    return False, f"BTC policy mutation blocked by contract ({','.join(blocked) or 'no blocked_effects'})"


def _trigger_cycle_direction(detail: dict[str, Any]) -> str:
    """Extract a concise continuation direction from trigger_cycle.detail.

    The evaluator may use slightly different keys by domain. Prefer the
    explicit seed movement, then fall back to directive/instruction fields.
    `success_gate` and `reason` are useful in the marker but should not win
    over a concrete next action when one exists.
    """
    preferred = ("seed_change", "direction", "directive", "instruction", "next_focus", "target")
    for key in preferred:
        value = detail.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    for key in TRIGGER_TEXT_KEYS:
        value = detail.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list):
            joined = "; ".join(str(v).strip() for v in value if str(v).strip())
            if joined:
                return joined
    return ""


def _apply_to_seed(
    seed: dict[str, Any],
    entry: dict[str, Any],
    cycle_ts: str,
) -> dict[str, Any]:
    """Apply entry.action.detail to seed. Returns mutated copy.

    For modify_seme + field=direzione + new_value: replaces seed["direzione"].
    For trigger_cycle: records the NEXT_CYCLE continuation as seed direction.
    Both add a marker tension to track the apply (porta=trajectory_apply,
    condensato_ref derived from action context).
    """
    mutated = json.loads(json.dumps(seed))  # deep copy
    action = entry["action"]
    action_type = action["type"]
    detail = action["detail"]
    if action_type == "modify_seme":
        new_value = detail["new_value"]
        marker_kind = "APPLY"
        decision_label = entry.get("decision", "REDESIGN")
    else:
        new_value = _trigger_cycle_direction(detail)
        marker_kind = "TRIGGER"
        decision_label = "NEXT_CYCLE"
    cycle_ref = entry.get("cycle_ref", "?")

    # Apply direzione/continuation change
    mutated["direzione"] = new_value

    # Add marker tension for traceability + lignaggio (P0-compliant)
    marker_id = f"TRAJECTORY_{marker_kind}_{cycle_ref}"
    tensioni = list(mutated.get("tensioni", []))
    # Skip if already present (idempotent on re-run)
    existing_ids = {t.get("id") for t in tensioni if isinstance(t, dict)}
    if marker_id not in existing_ids:
        extra = []
        for key in ("success_gate", "constraint", "constraints", "reason"):
            value = detail.get(key)
            if isinstance(value, list):
                value = "; ".join(str(v) for v in value)
            if value:
                extra.append(f"{key}: {str(value)[:180]}")
        tensioni.append({
            "tipo": "task",
            "id": marker_id,
            "claim": f"Applied trajectory_evaluator {decision_label} from {cycle_ref}: {new_value[:200]}",
            "description": " | ".join(extra)[:500],
            "intensità": 0.7,
            "porta": "trajectory_apply",
            "condensato_ref": "A8,A14,A15",
            "manuale": False,
            "action_type": action_type,
            "_source_log": entry.get("ts", ""),
            "_source_reasoning": (entry.get("reasoning", "") or "")[:300],
        })
    mutated["tensioni"] = tensioni

    # Track in seed history
    history = mutated.setdefault("_seed_history", {})
    if isinstance(history, dict):
        history[f"trajectory_apply_{cycle_ts}"] = (
            f"applied {action_type} from {cycle_ref}: "
            f"direzione → '{new_value[:100]}...'"
        )

    return mutated


def _mark_entry_executed(domain: str, entry_ts: str) -> bool:
    """Re-write trajectory_log.jsonl marking entry with given ts as executed=true.

    Atomic: write to .tmp, rename. Returns True if marked, False if not found
    or write failed.
    """
    log_path = paths.domain_data_dir(domain) / "trajectory_log.jsonl"
    if not log_path.exists():
        return False
    try:
        lines = log_path.read_text().splitlines()
        out_lines: list[str] = []
        marked = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                e = json.loads(stripped)
            except json.JSONDecodeError:
                out_lines.append(stripped)
                continue
            if e.get("ts") == entry_ts and e.get("executed") is False:
                e["executed"] = True
                e["_executed_at"] = datetime.now(timezone.utc).isoformat()
                e["_executed_by"] = "trajectory_apply"
                marked = True
            out_lines.append(json.dumps(e, ensure_ascii=False))
        if not marked:
            return False
        tmp_path = log_path.with_suffix(".jsonl.tmp")
        tmp_path.write_text("\n".join(out_lines) + "\n")
        tmp_path.replace(log_path)
        return True
    except OSError as e:
        logger.warning("trajectory_apply: failed to mark executed: %s", e)
        return False


def _post_cycle_closure_satisfies_entry(domain: str, entry: dict[str, Any]) -> tuple[bool, str]:
    """Return true when a post-cycle closure audit makes the trajectory obsolete.

    BTC value artifacts are written before the current cycle trace exists, while
    the deterministic closure audit runs after the trace is written. A
    trajectory_evaluator entry created before that post-cycle audit can therefore
    ask to fix raw_trace materialization even though the post-cycle audit has
    already closed it.
    """
    if domain != "bitcoin-regime-lab":
        return False, ""
    text = " ".join(
        str(value)
        for value in (
            entry.get("reasoning"),
            ((entry.get("action") or {}).get("detail") or {}).get("new_value"),
            ((entry.get("action") or {}).get("detail") or {}).get("reason"),
        )
        if value
    ).lower()
    if not any(token in text for token in ("raw_trace", "cycle_trace", "trace materialization")):
        return False, ""

    cycle_ref = entry.get("cycle_ref")
    if not isinstance(cycle_ref, str) or not cycle_ref:
        return False, ""
    closure_path = paths.domain_data_dir(domain) / "closure" / f"btc_runtime_lineage_closure_{cycle_ref}.json"
    if not closure_path.exists():
        return False, ""
    try:
        payload = json.loads(closure_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, ""
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    total = summary.get("value_artifacts_total")
    if (
        payload.get("phase") == "post_cycle"
        and payload.get("status") == "pass"
        and total
        and summary.get("raw_trace_exists") == total
        and summary.get("raw_log_exists") == total
        and summary.get("report_exists") == total
    ):
        return True, f"post-cycle closure audit passed for {cycle_ref}"
    return False, ""


def trajectory_apply(ctx: CycleContext) -> None:
    """Movement: apply last log-only trajectory_evaluator decision if eligible.

    Reads ctx.seed (loaded by run_cycle pre-dispatch), mutates if applicable,
    writes back to seed.json + ctx.seed atomically.

    Mutates: writes seed.json + trajectory_log.jsonl (mark executed)
             ctx.seed (refreshed)
             ctx.metrics["trajectory_apply"]
    """
    entry = _read_last_trajectory_entry(ctx.domain)
    if entry is None:
        write_trajectory_state(
            ctx.domain,
            status="none",
            source="trajectory_apply",
            cycle_ts=ctx.timestamp,
            reason="no trajectory_log.jsonl or empty",
        )
        ctx.metrics.setdefault("trajectory_apply", {}).update(
            decision="SKIP",
            reason="no trajectory_log.jsonl or empty",
        )
        logger.info("trajectory_apply: SKIP (no log)")
        return

    eligible, reason = _is_eligible(entry)
    guarded_medium = False
    if not eligible:
        guarded_medium, guarded_reason = _btc_guarded_medium_eligible(ctx.domain, entry)
        if guarded_medium:
            eligible = True
            reason = guarded_reason
    if not eligible:
        write_trajectory_state(
            ctx.domain,
            status="skipped",
            source="trajectory_apply",
            cycle_ts=ctx.timestamp,
            entry=entry,
            reason=reason,
            extra={
                "entry_executed": entry.get("executed"),
                "entry_confidence": entry.get("confidence"),
            },
        )
        ctx.metrics.setdefault("trajectory_apply", {}).update(
            decision="SKIP",
            reason=reason,
            entry_cycle_ref=entry.get("cycle_ref"),
            entry_executed=entry.get("executed"),
            entry_confidence=entry.get("confidence"),
        )
        logger.info("trajectory_apply: SKIP — %s", reason)
        return

    contract_allowed, contract_reason = _btc_policy_contract_allows_entry(ctx.domain, entry)
    if not contract_allowed:
        write_trajectory_state(
            ctx.domain,
            status="blocked_by_policy_contract",
            source="trajectory_apply",
            cycle_ts=ctx.timestamp,
            entry=entry,
            reason=contract_reason,
            extra={
                "entry_executed": entry.get("executed"),
                "entry_confidence": entry.get("confidence"),
            },
        )
        ctx.metrics.setdefault("trajectory_apply", {}).update(
            decision="SKIP_BLOCKED",
            reason=contract_reason,
            entry_cycle_ref=entry.get("cycle_ref"),
            entry_confidence=entry.get("confidence"),
        )
        logger.info("trajectory_apply: SKIP_BLOCKED — %s", contract_reason)
        return

    satisfied, satisfied_reason = _post_cycle_closure_satisfies_entry(ctx.domain, entry)
    if satisfied:
        marked = _mark_entry_executed(ctx.domain, entry.get("ts", ""))
        write_trajectory_state(
            ctx.domain,
            status="satisfied_by_post_cycle_closure",
            source="trajectory_apply",
            cycle_ts=ctx.timestamp,
            entry={**entry, "executed": True},
            reason=satisfied_reason,
            extra={"log_entry_marked_executed": marked},
        )
        ctx.metrics.setdefault("trajectory_apply", {}).update(
            decision="SKIP_SATISFIED",
            reason=satisfied_reason,
            entry_cycle_ref=entry.get("cycle_ref"),
            log_entry_marked_executed=marked,
        )
        logger.info("trajectory_apply: SKIP_SATISFIED — %s", satisfied_reason)
        return

    # Apply
    seed_path = paths.seed_path(ctx.domain)
    if not seed_path.exists():
        # Edge case: trajectory exists but seed missing — apply to ctx.seed only
        seed = ctx.seed or {}
    else:
        try:
            seed = json.loads(seed_path.read_text())
        except json.JSONDecodeError:
            logger.warning("trajectory_apply: seed.json malformed, skipping apply")
            ctx.metrics.setdefault("trajectory_apply", {}).update(
                decision="SKIP",
                reason="seed.json malformed",
            )
            return

    mutated = _apply_to_seed(seed, entry, ctx.timestamp)

    # Atomic write seed
    tmp_path = seed_path.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(mutated, indent=2, ensure_ascii=False, default=str)
    )
    tmp_path.replace(seed_path)
    ctx.seed = mutated

    # Mark log entry executed
    marked = _mark_entry_executed(ctx.domain, entry.get("ts", ""))

    cycle_ref = entry.get("cycle_ref", "?")
    action_type = entry["action"]["type"]
    if action_type == "modify_seme":
        new_direzione = entry["action"]["detail"]["new_value"]
    else:
        new_direzione = _trigger_cycle_direction(entry["action"]["detail"])
    ctx.metrics.setdefault("trajectory_apply", {}).update(
        decision="APPLIED",
        from_cycle_ref=cycle_ref,
        new_direzione=new_direzione[:100],
        log_entry_marked_executed=marked,
        action_type=action_type,
        confidence=entry.get("confidence"),
        guarded_medium=guarded_medium,
    )
    write_trajectory_state(
        ctx.domain,
        status="applied",
        source="trajectory_apply",
        cycle_ts=ctx.timestamp,
        entry={**entry, "executed": True},
        direction=new_direzione,
        reason=f"applied {action_type} from {cycle_ref}",
        extra={"log_entry_marked_executed": marked, "guarded_medium": guarded_medium, "eligibility_reason": reason},
    )
    logger.info(
        "trajectory_apply: APPLIED %s from %s — direzione → '%s...'",
        action_type,
        cycle_ref,
        new_direzione[:80],
    )


register_movement("trajectory_apply", trajectory_apply)
