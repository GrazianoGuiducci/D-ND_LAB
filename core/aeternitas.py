"""Aeternitas gate — invariant veto pre-crystallization.

Implementation of the aeternitas-sys mega skill (kernel/reference/skills/
agent_skills_aeternitas.md): Guardian of the Seed and Axiomatic Invariance.
Verifies P0/P1/P5 invariants before each seed crystallization.

> "Certe logiche sono hardware virtuale. Immutabili."

Invariants checked:
- **P0 Lignaggio**: every non-manual tension must trace to a condensate
  reference (axiom A1-A16, fact F1-F6, claim C1-C3, or domain reference).
  No untraceable tensions enter the seed.
- **P1 Integrità**: internal coherence of the new seed. No duplicate
  tension IDs. Piano must advance monotonically. Required fields present.
- **P5 Autopoiesi**: the cycle must have produced something new (at least
  one new tension ID, or growth in tension count). A cycle that adds
  nothing is potential drift — warning, not hard veto.

Default mode: 'warn' — log decision + reason but do NOT block the write.
Lets aeternitas calibrate without breaking production cycles. Set
movements.seed_integrator.params.aeternitas_mode='hard' to enable veto.

Output: each invocation writes data/<domain>/aeternitas/aeternitas_<ts>.json
for visibility (process visibility direttiva operatore 05/05).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import paths

logger = logging.getLogger(__name__)


def verify_invariants(
    seed_old: dict[str, Any],
    seed_new: dict[str, Any],
) -> dict[str, Any]:
    """Run aeternitas invariant scan on a proposed seed update.

    Returns a structured decision:
        {
          "decision": "PROCEED" | "VETO" | "WARN",
          "checks": { "P0": {...}, "P1": {...}, "P5": {...} },
          "reason": "...",
          "ts": "2026-05-05T..."
        }

    Decision rules:
        - VETO if P0 or P1 fail (lignaggio + integrità sono hard invariants)
        - WARN if only P5 fails (autopoiesi soft — cycle sterile è segnale)
        - PROCEED if all three pass
    """
    checks: dict[str, Any] = {}

    # ── P0 Lignaggio ───────────────────────────────────────────────
    # Every non-manual tension must have condensato_ref or operator porta.
    # Manual tensions (operator-injected) are exempt from the lignaggio
    # constraint — operator is the source.
    operator_portas = {
        "operator_request",
        "operator_directive",
        "sessione_interattiva",
        "manuale",
    }
    p0_violations: list[dict[str, Any]] = []
    for t in seed_new.get("tensioni", []):
        if not isinstance(t, dict):
            continue
        if t.get("manuale") is True or t.get("porta") in operator_portas:
            continue
        ref = t.get("condensato_ref")
        if not ref:
            p0_violations.append(
                {"id": t.get("id", "?"), "issue": "no condensato_ref"}
            )
    checks["P0"] = {
        "name": "Lignaggio",
        "passed": len(p0_violations) == 0,
        "violations": p0_violations,
    }

    # ── P1 Integrità ───────────────────────────────────────────────
    # Internal coherence: no duplicate tension IDs, piano must advance,
    # required top-level fields present.
    p1_violations: list[dict[str, Any]] = []
    ids = [
        t.get("id")
        for t in seed_new.get("tensioni", [])
        if isinstance(t, dict) and t.get("id")
    ]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        p1_violations.append({"issue": "duplicate_tension_ids", "ids": duplicates})

    old_piano = seed_old.get("piano", 0) or 0
    new_piano = seed_new.get("piano", 0) or 0
    if not isinstance(old_piano, (int, float)):
        old_piano = 0
    if not isinstance(new_piano, (int, float)):
        new_piano = 0
    if new_piano <= old_piano and old_piano > 0:
        p1_violations.append(
            {
                "issue": "piano_not_advanced",
                "old": old_piano,
                "new": new_piano,
            }
        )

    required_fields = ["timestamp", "piano", "tensioni", "direzione"]
    missing = [f for f in required_fields if f not in seed_new]
    if missing:
        p1_violations.append({"issue": "missing_required_fields", "fields": missing})

    checks["P1"] = {
        "name": "Integrità",
        "passed": len(p1_violations) == 0,
        "violations": p1_violations,
    }

    # ── P5 Autopoiesi ──────────────────────────────────────────────
    # Cycle must produce something new: a new tension ID, or growth in
    # count, or refreshed direction. Otherwise the system is potentially
    # cycling sterilely — warning (not hard veto, since some cycles
    # legitimately maintain frame).
    new_ids = {
        t.get("id")
        for t in seed_new.get("tensioni", [])
        if isinstance(t, dict) and t.get("id")
    }
    old_ids = {
        t.get("id")
        for t in seed_old.get("tensioni", [])
        if isinstance(t, dict) and t.get("id")
    }
    truly_new = sorted(new_ids - old_ids)

    p5_violations: list[dict[str, Any]] = []
    direzione_changed = (
        seed_old.get("direzione", "") != seed_new.get("direzione", "")
    )
    if not truly_new and len(new_ids) <= len(old_ids) and not direzione_changed:
        p5_violations.append(
            {
                "issue": "no_new_tension_or_direction",
                "old_count": len(old_ids),
                "new_count": len(new_ids),
            }
        )
    checks["P5"] = {
        "name": "Autopoiesi",
        "passed": len(p5_violations) == 0,
        "violations": p5_violations,
        "new_tension_ids": truly_new,
        "direzione_changed": direzione_changed,
    }

    # ── Decision ───────────────────────────────────────────────────
    p0_ok = checks["P0"]["passed"]
    p1_ok = checks["P1"]["passed"]
    p5_ok = checks["P5"]["passed"]

    if not p0_ok or not p1_ok:
        decision = "VETO"
        reasons: list[str] = []
        if not p0_ok:
            reasons.append(
                f"P0 (Lignaggio): {len(p0_violations)} tensioni senza condensato_ref"
            )
        if not p1_ok:
            reasons.append(f"P1 (Integrità): {len(p1_violations)} violazioni")
        reason = " · ".join(reasons)
    elif not p5_ok:
        decision = "WARN"
        reason = "P5 (Autopoiesi): ciclo non ha prodotto tensioni nuove né cambiato direzione"
    else:
        decision = "PROCEED"
        reason = "P0 OK · P1 OK · P5 OK"

    return {
        "decision": decision,
        "checks": checks,
        "reason": reason,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def log_decision(
    domain: str,
    cycle_ts: str,
    result: dict[str, Any],
) -> Path | None:
    """Persist aeternitas decision to data/<domain>/aeternitas/aeternitas_<ts>.json.

    Visibility: every cycle leaves a trace of the gate decision, regardless
    of mode (warn/hard). Operator can audit the gate calibration over time.

    Returns the path written, or None if write failed (non-critical —
    aeternitas decision in ctx.metrics anyway).
    """
    try:
        out_dir = paths.domain_data_dir(domain) / "aeternitas"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"aeternitas_{cycle_ts}.json"
        out_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False, default=str)
        )
        return out_path
    except Exception as e:
        logger.warning("aeternitas log_decision failed: %s", e)
        return None
