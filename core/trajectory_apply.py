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
      Se entry eligible (executed=false, confidence=high, modify_seme):
        - applica action.detail al seed (modifica direzione)
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

Altri action types (notify_operator, crystallize_note, escalate_cowork)
sono skip — sono effetti collaterali, non modifiche al seed.
trigger_cycle è riservato all'operatore.

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

logger = logging.getLogger(__name__)


# Whitelist conservativa — extend solo dopo che il pattern è validato in vivo
ELIGIBLE_ACTION_TYPES = {"modify_seme"}
ELIGIBLE_FIELDS = {"direzione"}
ELIGIBLE_CONFIDENCES = {"high"}


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
    field = detail.get("field")
    if field not in ELIGIBLE_FIELDS:
        return False, f"action.detail.field='{field}' not in {ELIGIBLE_FIELDS}"
    new_value = detail.get("new_value", "")
    if not isinstance(new_value, str) or not new_value.strip():
        return False, "action.detail.new_value empty or non-string"
    return True, "eligible"


def _apply_to_seed(
    seed: dict[str, Any],
    entry: dict[str, Any],
    cycle_ts: str,
) -> dict[str, Any]:
    """Apply entry.action.detail to seed. Returns mutated copy.

    For modify_seme + field=direzione + new_value: replaces seed["direzione"]
    and adds a marker tension to track the apply (operator-equivalent
    porta=trajectory_apply, condensato_ref derived from action context).
    """
    mutated = json.loads(json.dumps(seed))  # deep copy
    detail = entry["action"]["detail"]
    new_value = detail["new_value"]
    cycle_ref = entry.get("cycle_ref", "?")

    # Apply direzione change
    mutated["direzione"] = new_value

    # Add marker tension for traceability + lignaggio (P0-compliant)
    marker_id = f"TRAJECTORY_APPLY_{cycle_ref}"
    tensioni = list(mutated.get("tensioni", []))
    # Skip if already present (idempotent on re-run)
    existing_ids = {t.get("id") for t in tensioni if isinstance(t, dict)}
    if marker_id not in existing_ids:
        tensioni.append({
            "tipo": "task",
            "id": marker_id,
            "claim": f"Applied trajectory_evaluator REDESIGN from {cycle_ref}: {new_value[:200]}",
            "intensità": 0.7,
            "porta": "trajectory_apply",
            "condensato_ref": "A8,A14,A15",
            "manuale": False,
            "_source_log": entry.get("ts", ""),
            "_source_reasoning": (entry.get("reasoning", "") or "")[:300],
        })
    mutated["tensioni"] = tensioni

    # Track in seed history
    history = mutated.setdefault("_seed_history", {})
    if isinstance(history, dict):
        history[f"trajectory_apply_{cycle_ts}"] = (
            f"applied {entry['action']['type']} from {cycle_ref}: "
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
        ctx.metrics.setdefault("trajectory_apply", {}).update(
            decision="SKIP",
            reason="no trajectory_log.jsonl or empty",
        )
        logger.info("trajectory_apply: SKIP (no log)")
        return

    eligible, reason = _is_eligible(entry)
    if not eligible:
        ctx.metrics.setdefault("trajectory_apply", {}).update(
            decision="SKIP",
            reason=reason,
            entry_cycle_ref=entry.get("cycle_ref"),
            entry_executed=entry.get("executed"),
            entry_confidence=entry.get("confidence"),
        )
        logger.info("trajectory_apply: SKIP — %s", reason)
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
    new_direzione = entry["action"]["detail"]["new_value"]
    ctx.metrics.setdefault("trajectory_apply", {}).update(
        decision="APPLIED",
        from_cycle_ref=cycle_ref,
        new_direzione=new_direzione[:100],
        log_entry_marked_executed=marked,
        action_type=entry["action"]["type"],
        confidence=entry.get("confidence"),
    )
    logger.info(
        "trajectory_apply: APPLIED REDESIGN from %s — direzione → '%s...'",
        cycle_ref,
        new_direzione[:80],
    )


register_movement("trajectory_apply", trajectory_apply)
