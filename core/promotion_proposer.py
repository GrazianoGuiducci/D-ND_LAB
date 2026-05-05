"""promotion_proposer movement — chiude G3 (Fine B ricadute pratiche).

Quando un cycle produce un finding eligible (falsifier coherent +
aeternitas non VETO + verify_assertions con PASS reali), questo movement
estrae proposte di promozione del finding a regola sistemica:
  - regola_operativa  → memoria operatore (feedback_<slug>.md)
  - skill            → catalogo .claude/skills/<slug>.md
  - hook             → settings.json hook entry
  - voce_kernel      → COWORK_KERNEL.md sezione
  - voce_libro       → D-ND_BOOK.md sezione III/IV/...

Le proposte sono **proposte**, non apply automatici. Vengono scritte in
`data/<lab>/promotions/promotion_<ts>.json`. L'operatore le revisiona
e decide quali promuovere effettivamente — atto Approve.

Razionale: oggi un finding di ops-decisions (es. "advisory→gate
pattern" cycle 1608) resta dentro il cycle. Il sistema non si modifica
strutturalmente ad ogni cycle. Con questo movement, il sistema **vede**
le proprie regole emergenti e l'operatore le promuove con consapevolezza.

Comportamento opt-in: lab di funzione (ops-decisions, lab futuri di
funzione) hanno enabled=true di default nel template generator. Lab di
dominio (physics, editorial — producono finding scientifici, non
regole sistemiche) hanno enabled=false di default.

Eligibility check (whitelist conservativa):
1. falsifier_coherent == True (claim ha superato 5 lenti L1-L5)
2. aeternitas_decision != "VETO" (invarianti seme rispettati)
3. verify_assertions.n_pass > 0 (test reali eseguiti, non solo SKIP)
4. report file esiste e ha length > 1024 bytes
5. confidence != "exploratory_N2" (corpus troppo piccolo per universal claim)

Pattern parser: rule-based su markdown del report agent. Estrae:
- Sezione "## Verdict" → candidate rule
- Sezione "## Bicono" sub-section "Candidate rule" / "Proposta"
- Markers espliciti "PROPOSAL:" / "Regola candidata:"

Estensione futura (atto strutturale): scribe-sys mega skill può
produrre proposte più ricche con LLM call dedicato. Per ora rule-based.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import config as cfg
from core import paths
from core.lab_agent import CycleContext, register_movement

logger = logging.getLogger(__name__)


CONFIDENCE_BLACKLIST = {"exploratory_N2", "exploratory_n2"}
MIN_REPORT_BYTES = 1024


def _eligibility_check(ctx: CycleContext) -> tuple[bool, dict[str, Any]]:
    """Verifica se il cycle è eligible per produrre promotion proposals.

    Ritorna (eligible, checks_dict). checks_dict ha campi:
      falsifier_coherent, aeternitas_decision, n_pass, report_size,
      confidence_ok, all_passed.
    """
    checks: dict[str, Any] = {}

    # Falsifier coherent
    falsifier_metrics = ctx.metrics.get("report_falsifier", {}) or {}
    coherent = falsifier_metrics.get("coherent")
    if coherent is None:
        # legacy: try reading from falsifier file
        try:
            fal_dir = paths.domain_data_dir(ctx.domain) / "falsifier"
            fal_path = fal_dir / f"falsifier_{ctx.timestamp}.json"
            if fal_path.exists():
                fal = json.loads(fal_path.read_text())
                coherent = fal.get("coherent", False)
        except Exception:
            coherent = False
    checks["falsifier_coherent"] = bool(coherent)

    # Aeternitas decision (from seed_integrator metrics)
    seed_metrics = ctx.metrics.get("seed_integrator", {}) or {}
    aeternitas_decision = seed_metrics.get("aeternitas_decision", "PROCEED")
    checks["aeternitas_decision"] = aeternitas_decision

    # Assertions: at least 1 PASS, no FAIL
    va_metrics = ctx.metrics.get("verify_assertions", {}) or {}
    n_pass = va_metrics.get("n_pass", 0)
    n_fail = va_metrics.get("n_fail", 0)
    checks["n_pass"] = n_pass
    checks["n_fail"] = n_fail

    # Report exists and has size
    report_path = ctx.report_path
    report_size = 0
    if report_path and Path(report_path).exists():
        report_size = Path(report_path).stat().st_size
    checks["report_size"] = report_size

    # Confidence (from cycle-specific verifica section if available)
    confidence = "unknown"
    try:
        seed = ctx.seed or {}
        verifica = seed.get("verifica", {}) or {}
        cycle_key = f"cycle_{ctx.timestamp}"
        if cycle_key in verifica:
            confidence = verifica[cycle_key].get("confidence", "unknown")
    except Exception:
        pass
    checks["confidence"] = confidence
    confidence_ok = confidence not in CONFIDENCE_BLACKLIST
    checks["confidence_ok"] = confidence_ok

    # Combined eligibility
    eligible = (
        checks["falsifier_coherent"]
        and aeternitas_decision != "VETO"
        and n_pass > 0
        and n_fail == 0
        and report_size > MIN_REPORT_BYTES
        and confidence_ok
    )
    checks["all_passed"] = eligible
    return eligible, checks


# Pattern markers per estrazione candidate rules dal markdown del report
_PROPOSAL_MARKERS = [
    r"^##\s+Verdict\b",
    r"^##\s+Verdetto\b",
    r"PROPOSAL:",
    r"Candidate rule:",
    r"Regola candidata:",
    r"Proposta:",
]
_RULE_KEYWORDS = (
    "regola",
    "rule",
    "propos",
    "applicare",
    "guard",
    "should",
    "must ",
    "deve",
    "constraint",
    "vincolo",
    "gate ",
)


def _extract_proposals(report_text: str, cycle_ts: str) -> list[dict[str, Any]]:
    """Estrazione rule-based di candidate rules dal markdown del report.

    Pattern:
    1. Sezione `## Verdict` o `## Verdetto` → 1 proposta tipo regola_operativa
    2. Sezione `## Bicono` con sub-section "Candidate rule"/"Proposta" → 1 proposta
    3. Markers espliciti "PROPOSAL:" / "Regola candidata:" → 1 proposta ognuno

    Output: list of proposal dicts. Empty se nessun pattern matched.
    """
    proposals: list[dict[str, Any]] = []

    # Pattern 1: Verdict section
    for verdict_re in (r"##\s+Verdict\s*\n(.*?)(?=\n##\s|\Z)",
                        r"##\s+Verdetto\s*\n(.*?)(?=\n##\s|\Z)"):
        m = re.search(verdict_re, report_text, re.DOTALL)
        if m:
            text = m.group(1).strip()[:1500]
            text_lower = text.lower()
            if any(kw in text_lower for kw in _RULE_KEYWORDS):
                # estraggo titolo dalla prima riga non vuota
                first_line = next(
                    (line.strip() for line in text.split("\n") if line.strip()),
                    "Verdict (rule candidate)",
                )
                proposals.append({
                    "type": "regola_operativa",
                    "title": first_line[:120],
                    "summary": text[:600],
                    "rationale": "Verdict section contains rule-language keywords",
                    "source_section": "verdict",
                    "destination_hint": f"memory/feedback_<slug>_{cycle_ts}.md",
                    "confidence": "medium",
                })
            break  # solo uno tra Verdict/Verdetto

    # Pattern 2: Bicono section "Candidate rule" / "Proposta"
    bicono_re = r"##\s+Bicono.*?\n(.*?)(?=\n##\s|\Z)"
    bm = re.search(bicono_re, report_text, re.DOTALL)
    if bm:
        bicono_text = bm.group(1)
        for sub_marker in (r"Candidate\s*rule[:\s]*\n?(.*?)(?=\n[A-Z]|\Z)",
                            r"Proposta[:\s]*\n?(.*?)(?=\n[A-Z]|\Z)",
                            r"Regola[:\s]*\n?(.*?)(?=\n[A-Z]|\Z)"):
            sm = re.search(sub_marker, bicono_text, re.DOTALL | re.IGNORECASE)
            if sm:
                text = sm.group(1).strip()[:1000]
                if text and len(text) > 30:
                    proposals.append({
                        "type": "regola_operativa",
                        "title": (text.split("\n")[0] or "Bicono candidate rule")[:120],
                        "summary": text[:600],
                        "rationale": "Bicono section explicit candidate marker",
                        "source_section": "bicono",
                        "destination_hint": f"memory/feedback_<slug>_{cycle_ts}.md",
                        "confidence": "medium",
                    })
                break

    # Pattern 3: explicit markers anywhere
    for marker_pattern, marker_name in [
        (r"PROPOSAL:\s*([^\n]+(?:\n(?![\n#]).+)*)", "PROPOSAL"),
        (r"Regola\s+candidata:\s*([^\n]+(?:\n(?![\n#]).+)*)", "regola_candidata"),
    ]:
        for m in re.finditer(marker_pattern, report_text, re.MULTILINE):
            text = m.group(1).strip()[:800]
            if text and len(text) > 20:
                proposals.append({
                    "type": "regola_operativa",
                    "title": (text.split("\n")[0] or marker_name)[:120],
                    "summary": text[:500],
                    "rationale": f"Explicit marker '{marker_name}' in report",
                    "source_section": f"marker:{marker_name}",
                    "destination_hint": f"memory/feedback_<slug>_{cycle_ts}.md",
                    "confidence": "high",
                })

    return proposals


def promotion_proposer(ctx: CycleContext) -> None:
    """Movement: extract promotion proposals from cycle finding.

    Mutates: writes data/<domain>/promotions/promotion_<ts>.json (se eligible
             + proposals trovate)
             ctx.metrics["promotion_proposer"]
    """
    params = cfg.movement_params(ctx.config, "promotion_proposer")
    enabled = params.get("enabled", True)
    if not enabled:
        ctx.metrics.setdefault("promotion_proposer", {}).update(
            decision="DISABLED",
            reason="movement disabled in config",
        )
        return

    eligible, checks = _eligibility_check(ctx)
    if not eligible:
        # log perché non eligibile
        reasons = []
        if not checks["falsifier_coherent"]:
            reasons.append("falsifier_not_coherent")
        if checks["aeternitas_decision"] == "VETO":
            reasons.append("aeternitas_VETO")
        if checks["n_pass"] <= 0:
            reasons.append("no_assertions_pass")
        if checks["n_fail"] > 0:
            reasons.append(f"assertions_fail={checks['n_fail']}")
        if checks["report_size"] <= MIN_REPORT_BYTES:
            reasons.append(f"report_size={checks['report_size']}<{MIN_REPORT_BYTES}")
        if not checks["confidence_ok"]:
            reasons.append(f"confidence={checks['confidence']}_blacklisted")
        ctx.metrics.setdefault("promotion_proposer", {}).update(
            decision="SKIP_NOT_ELIGIBLE",
            checks=checks,
            reasons=reasons,
        )
        logger.info("promotion_proposer: SKIP — %s", ", ".join(reasons))
        return

    # Eligible — read report, extract proposals
    report_path = Path(ctx.report_path) if ctx.report_path else None
    if not report_path or not report_path.exists():
        ctx.metrics.setdefault("promotion_proposer", {}).update(
            decision="SKIP_NO_REPORT",
            checks=checks,
        )
        logger.info("promotion_proposer: SKIP — report path missing")
        return

    try:
        report_text = report_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        ctx.metrics.setdefault("promotion_proposer", {}).update(
            decision="SKIP_READ_ERROR",
            checks=checks,
            error=str(e),
        )
        return

    proposals = _extract_proposals(report_text, ctx.timestamp)
    if not proposals:
        ctx.metrics.setdefault("promotion_proposer", {}).update(
            decision="ELIGIBLE_NO_PROPOSALS",
            checks=checks,
            n_proposals=0,
            note="cycle eligible ma report non contiene pattern di candidate rule",
        )
        logger.info(
            "promotion_proposer: ELIGIBLE but no proposals extracted (no rule-language "
            "in verdict/bicono/markers)"
        )
        return

    # Write proposals
    out_dir = paths.domain_data_dir(ctx.domain) / "promotions"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"promotion_{ctx.timestamp}.json"

    output = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "cycle_ref": ctx.timestamp,
        "lab": ctx.domain,
        "eligibility": checks,
        "proposals": proposals,
        "operator_action_required": (
            "Review proposals. For each, decide: approve (apply via "
            "appropriate atto Approve), defer (keep in this file), reject "
            "(annotate _rejected:true). The lab does NOT apply automatically."
        ),
        "_apply_methods_hint": {
            "regola_operativa": "Crea memoria operatore feedback_<slug>.md + index in MEMORY.md",
            "skill": "Crea .claude/skills/<slug>.md con eval section",
            "hook": "Aggiungi entry a settings.json hooks",
            "voce_kernel": "Aggiungi sezione a /opt/THIA/docs/core/COWORK_KERNEL.md",
            "voce_libro": "Aggiungi sezione a /opt/MM_D-ND/D-ND_BOOK.md sezione III/IV/...",
        },
    }
    try:
        out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False, default=str))
    except OSError as e:
        ctx.metrics.setdefault("promotion_proposer", {}).update(
            decision="WRITE_ERROR",
            checks=checks,
            error=str(e),
        )
        return

    ctx.metrics.setdefault("promotion_proposer", {}).update(
        decision="PROPOSED",
        checks=checks,
        n_proposals=len(proposals),
        out_path=str(out_path),
    )
    logger.info(
        "promotion_proposer: %d proposals written → %s",
        len(proposals),
        out_path,
    )


register_movement("promotion_proposer", promotion_proposer)
