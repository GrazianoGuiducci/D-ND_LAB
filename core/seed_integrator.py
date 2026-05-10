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

from core import aeternitas, config as cfg
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

    # Cross-source aggregation (Phase 1.5, 29/04): integra le tensioni che
    # vengono dai movements del ciclo. Senza questo, A5 e' parzialmente
    # aperto — il verify_assertions produce risultati che il seed non vede.
    # Universale: ogni dominio puo' avere il suo verify_assertions, ogni
    # FAIL diventa tensione "contraddizione", tutti PASS su >5 test
    # diventa tensione META "simmetria sospetta" (anti-tautologica).
    new_from_assertions = _tensions_from_assertions(ctx.metrics.get("verify_assertions", {}))
    if new_from_assertions:
        existing_ids = {t.get("id") for t in tensioni if t.get("id")}
        for nt in new_from_assertions:
            if nt.get("id") not in existing_ids:
                tensioni.append(nt)
                existing_ids.add(nt.get("id"))
                logger.info(
                    "seed_integrator: +tensione %s da verify_assertions (%s)",
                    nt.get("id"), nt.get("tipo"),
                )

    # ── Universal mapping: ogni tensione DEVE avere condensato_ref ─────
    # Aggiunto 06/05 per chiudere VETO P0 (Lignaggio) ricorrente. Tensioni
    # nuove generate dall'agent o da seed_tensions iniziali possono mancare
    # di ref; senza ref Aeternitas P0 fallisce e blocca la promotion gate.
    # Pattern: keep ref esplicito → manual flag → mapping per tipo → default.
    # Cascata del fix MM_D-ND/dipartimento.py commit 632ce79 (05/05 mattina).
    _TYPE_TO_REF: dict[str, str] = {
        "scoperta":       "A1,A2",
        "metodo":         "A4,F4",
        "vincolo":        "A2,A14",
        "prodotto":       "A5,A8",
        "baseline":       "A4,F4",
        "ipotesi":        "A1,A4",
        "contraddizione": "A2,A4,C2",
        "boundary":       "A6,A7",
        "meta":           "A4,A12,C2",
        "regola":         "A4,A8,A14",
    }
    _REF_MANUAL = "operator"
    _REF_DEFAULT = "A2,A4"
    _normalized_count = 0
    for t in tensioni:
        if not isinstance(t, dict):
            continue
        if t.get("condensato_ref"):
            continue
        if t.get("manuale"):
            t["condensato_ref"] = _REF_MANUAL
        else:
            tipo = (t.get("tipo") or "").lower()
            t["condensato_ref"] = _TYPE_TO_REF.get(tipo, _REF_DEFAULT)
        _normalized_count += 1
    if _normalized_count:
        logger.info(
            "seed_integrator: condensato_ref normalizzato su %d tensione/i",
            _normalized_count,
        )

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

    # ── Aeternitas gate (Phase 2.A.7+ propagation 05/05) ─────────
    # Verify P0/P1/P5 invariants pre-crystallization. Default mode
    # 'warn': log decision + reason, do NOT block write. Set
    # movements.seed_integrator.params.aeternitas_mode='hard' for veto.
    # Visibility: every cycle leaves trace in data/<domain>/aeternitas/.
    aeternitas_mode = str(params.get("aeternitas_mode", "warn")).lower()
    aeternitas_result = aeternitas.verify_invariants(seed, new_seed)
    aeternitas_log_path = aeternitas.log_decision(
        ctx.domain, ctx.timestamp, aeternitas_result
    )
    decision = aeternitas_result["decision"]
    if decision == "VETO":
        if aeternitas_mode == "hard":
            logger.error(
                "aeternitas: VETO (hard mode) — seed write blocked. Reason: %s",
                aeternitas_result["reason"],
            )
            ctx.metrics.setdefault("seed_integrator", {}).update(
                aeternitas_decision="VETO",
                aeternitas_reason=aeternitas_result["reason"],
                aeternitas_mode=aeternitas_mode,
                seed_written=False,
            )
            return
        logger.warning(
            "aeternitas: VETO (warn mode, write proceeds) — Reason: %s",
            aeternitas_result["reason"],
        )
    elif decision == "WARN":
        logger.info("aeternitas: WARN — %s", aeternitas_result["reason"])
    else:
        logger.info("aeternitas: PROCEED — %s", aeternitas_result["reason"])

    # Atomic write: write to .tmp, rename
    tmp_path = seed_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(new_seed, indent=2, ensure_ascii=False, default=str))
    tmp_path.replace(seed_path)

    ctx.seed = new_seed
    ctx.metrics.setdefault("seed_integrator", {}).update(
        new_piano=new_piano,
        n_tensions=len(tensioni),
        direzione=direzione[:80],
        aeternitas_decision=decision,
        aeternitas_reason=aeternitas_result["reason"],
        aeternitas_mode=aeternitas_mode,
        aeternitas_log=str(aeternitas_log_path) if aeternitas_log_path else None,
        seed_written=True,
    )
    logger.info(
        "seed_integrator: piano %s → %s, %d tensions, direction='%s...'",
        prev_piano, new_piano, len(tensioni), direzione[:60],
    )


def _tensions_from_assertions(assertion_metrics: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert verify_assertions output into seed tensions.

    Universale, agnostic to domain. Pattern derivato da MM_D-ND
    dipartimento.cristallizza_seme:

      FAIL (status=FAIL) → tensione 'contraddizione' intensita 1.0
      SKIP (status=SKIP) → tensione 'bloccato' (potenziale bloccato)
      tutti PASS su N>5 test → tensione META 'simmetria sospetta'
        intensita 0.5 (anti-tautologica: il sistema sta verificando
        contenuto o struttura?)

    Output: list of tension dicts (id, tipo, claim, intensità, nota,
    fonte). Empty list se assertion_metrics e' vuoto o malformato.
    """
    results = assertion_metrics.get("results") or []
    if not isinstance(results, list) or not results:
        return []

    out: list[dict[str, Any]] = []

    # Lignaggio condensato per tensioni auto-generate (P0 aeternitas).
    # Mapping universale derivato dal modello D-ND:
    # - contraddizione (FAIL): A2 confine necessario + A4 modus + C2 falsifier
    # - bloccato (SKIP): A6 zero mobile + A7 singolarità operatore
    # - simmetria_sospetta (META): A4 modus + A12 vincolo sovrapposizione + C2
    REF_FAIL = "A2,A4,C2"
    REF_SKIP = "A6,A7"
    REF_META_ALL_PASS = "A4,A12,C2"

    # FAIL → tensione contraddizione (massima intensità)
    for r in results:
        if not isinstance(r, dict):
            continue
        if r.get("status") == "FAIL":
            out.append({
                "tipo": "contraddizione",
                "id": f"ASSERT_{r.get('id', '?')}",
                "claim": r.get("claim", "")[:200],
                "dettaglio": r.get("detail", "")[:300],
                "intensità": 1.0,
                "nota": "verify_assertions FAIL — claim del modello vs dato divergono. O il claim va corretto o il test e' sbagliato.",
                "fonte": r.get("source", "verify_assertions"),
                "condensato_ref": REF_FAIL,
                "porta": "verify_assertions_FAIL",
            })
        elif r.get("status") == "SKIP":
            # Tracciato ma intensità più bassa — è potenziale bloccato, non contraddizione
            out.append({
                "tipo": "bloccato",
                "id": f"SKIP_{r.get('id', '?')}",
                "claim": r.get("claim", "")[:200],
                "dettaglio": r.get("detail", "")[:300],
                "intensità": 0.4,
                "nota": "verify_assertions SKIP — il test non si e' eseguito (manca prerequisito).",
                "fonte": r.get("source", "verify_assertions"),
                "condensato_ref": REF_SKIP,
                "porta": "verify_assertions_SKIP",
            })

    # Tutti PASS su >5 test → simmetria sospetta (META anti-tautologica)
    n_pass = assertion_metrics.get("n_pass", 0)
    n_total = assertion_metrics.get("n_total", 0)
    if n_total > 5 and n_pass == n_total:
        out.append({
            "tipo": "simmetria_sospetta",
            "id": "META_ALL_PASS",
            "claim": f"Tutti i {n_total} test passano — verifica che non stiamo testando solo tautologie",
            "intensità": 0.5,
            "nota": "Convergenza univoca su tutti i test = segnale ambiguo. I test stanno verificando contenuto o struttura? Possibile shuffle/null check necessario.",
            "fonte": "verify_assertions META",
            "condensato_ref": REF_META_ALL_PASS,
            "porta": "verify_assertions_META_ALL_PASS",
        })

    return out


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
