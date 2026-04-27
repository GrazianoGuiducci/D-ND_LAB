"""Movement 13 — seed_integrator (extracted from dipartimento.py --seme).

Crystallizes the seed after the cycle. Closes the autopoietic loop A5:
tensions accumulated during the cycle → filter against condensate →
relevant tensions survive → direction rotated by priority.

Without this movement, the seed does not evolve and the direction stays
locked on the previous operator input.

Phase 1 scope (minimal viable):
  - Increment piano
  - Preserve manual tensions (operator-injected) and "porta=sessione_interattiva"
  - Sort tensions by intensity, cap to top N
  - Archive previous seed under <data>/<domain>/seed_archive/piano_<n>.json
  - Compute direction from highest-priority tension
  - Write new seed atomically (write to .tmp, rename)

What's NOT in Phase 1 (lives in dipartimento.py original, deferred):
  - Two-gate filter (condensate match vs unclassifiable-recurring)
  - Axiom distillation when archive > 9 entries
  - Cross-source tension aggregation (autoricerca journal, domandatore)

These are domain-rich behaviors that the physics domain currently uses.
They can re-enter as a domain plugin (params.integrator_module) in Phase 4
without polluting core.
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


def seed_integrator(ctx: CycleContext) -> None:
    """Crystallize the seed for the next cycle.

    Reads ctx.seed (current state, possibly mutated by structural_check
    META injection earlier in this cycle), bumps piano, sorts tensions,
    archives previous, writes new.

    Mutates: writes seed.json + archive
             ctx.seed (refreshed with new piano + direzione)
             ctx.metrics["seed_integrator"]
    """
    params = cfg.movement_params(ctx.config, "seed_integrator")
    max_tensions = int(params.get("max_tensions", 12))

    seed_path = paths.seed_path(ctx.domain)
    archive_dir = paths.domain_data_dir(ctx.domain) / "seed_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    # Read current seed (post-cycle state — may have new META tensions)
    if seed_path.exists():
        try:
            seed = json.loads(seed_path.read_text())
        except json.JSONDecodeError:
            seed = {}
    else:
        seed = {}

    prev_piano = seed.get("piano", 0)
    if not isinstance(prev_piano, (int, float)):
        prev_piano = 0
    new_piano = int(prev_piano) + 1

    # Archive previous (only if it has a piano number)
    if seed and prev_piano:
        archive_path = archive_dir / f"piano_{int(prev_piano)}.json"
        if not archive_path.exists():
            try:
                archive_path.write_text(json.dumps(seed, indent=2, ensure_ascii=False, default=str))
            except Exception as e:
                logger.warning("seed archive failed: %s", e)

    # Preserve manual tensions + sort by intensity descending
    tensioni = list(seed.get("tensioni", []))
    # Stable: keep manually-injected at their position relative to themselves
    tensioni = [t for t in tensioni if isinstance(t, dict)]
    tensioni.sort(
        key=lambda t: t.get("intensità", t.get("intensita", 0)) or 0,
        reverse=True,
    )
    if max_tensions and len(tensioni) > max_tensions:
        # Trim, but keep manual + condensato-anchored items
        kept = []
        seen_ids: set[str] = set()
        for t in tensioni:
            if t.get("manuale") or t.get("condensato_ref"):
                kept.append(t)
                seen_ids.add(t.get("id", ""))
        for t in tensioni:
            if t.get("id", "") in seen_ids:
                continue
            kept.append(t)
            if len(kept) >= max_tensions:
                break
        tensioni = kept

    # Direction = highest-priority tension claim
    direzione = _direction_from_tensions(tensioni)

    new_seed = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "piano": new_piano,
        "tensioni": tensioni,
        "potenziale_bloccato": seed.get("potenziale_bloccato", []),
        "varianza": seed.get("varianza", []),
        "filtro": seed.get("filtro", {"promosse": len(tensioni), "filtrate": 0}),
        "direzione": direzione,
        "verifica": seed.get("verifica", {}),
        "fonti_consumate": seed.get("fonti_consumate", 0),
        "fonti_esterne": seed.get("fonti_esterne", []),
    }

    # Atomic write: write to .tmp, rename
    tmp_path = seed_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(new_seed, indent=2, ensure_ascii=False, default=str))
    tmp_path.replace(seed_path)

    ctx.seed = new_seed
    ctx.metrics.setdefault("seed_integrator", {}).update(
        new_piano=new_piano,
        n_tensions=len(tensioni),
        direzione=direzione[:80],
    )
    logger.info(
        "seed_integrator: piano %s → %s, %d tensions, direction='%s...'",
        prev_piano, new_piano, len(tensioni), direzione[:60],
    )


def _direction_from_tensions(tensioni: list[dict[str, Any]]) -> str:
    """Compute the direction line from current tensions.

    Priority order (universal — derived from D-ND): contraddizione >
    confine_inesplorato > simmetria_sospetta > anything else with
    high intensity.
    """
    if not tensioni:
        return "no active tensions — direction unset"

    priority = ["contraddizione", "confine_inesplorato", "simmetria_sospetta"]
    by_type: dict[str, list[dict[str, Any]]] = {}
    for t in tensioni:
        by_type.setdefault(t.get("tipo", "altro"), []).append(t)

    for ptype in priority:
        if ptype in by_type:
            top = by_type[ptype][0]
            return (top.get("claim") or "")[:200]

    # Fallback: highest-intensity tension
    return (tensioni[0].get("claim") or "")[:200]


# ─── Movement registration ─────────────────────────────────────────

register_movement("seed_integrator", seed_integrator)
