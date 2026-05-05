"""veritas_score movement — ρ ∈ [0,1] da 3 vettori (G2).

Implementazione adattata della mega skill veritas-sys (kernel/reference/
agent_skills_veritas.md): Firewall Ontologico + Triangolazione
Epistemologica. Tre vettori indipendenti convergono sull'Indice di Realtà
ρ del cycle.

Le mega skill veritas-sys e aeternitas-sys sono complementari:
- aeternitas: verifica invarianti del SEME (P0/P1/P5) — gate strutturale
- veritas: misura affidabilità del FINDING (ρ score) — termometro qualità

Adattamento al lab D-ND_LAB (la mega skill è progettata per "dati che
descrivono il reale" generico; qui adattiamo i 3 vettori al cycle):

V_a TELEMETRICA — hard data del cycle (oggettivi, misurabili):
  - assertions ratio: n_pass / n_total ∈ [0,1]
  - falsifier flag penalty: 1 - (high*0.5 + medium*0.2 + low*0.05)
  - bicono extracted: 4 sub-sections present? 1 / 0.5 / 0
  - report size: > 1024 bytes? 1 / 0
  V_a = mean dei componenti

V_b LOGICO-STORICA — coerenza con cycle precedenti (continuità):
  - aeternitas P5 (autopoiesi): PASS=1, FAIL=0.5
  - aeternitas P0 (lignaggio): PASS=1, FAIL=0.3
  - aeternitas P1 (integrità): PASS=1, FAIL=0
  - direzione cambiata o stabile: cambiata=0.8, stabile=0.6
  V_b = mean dei componenti

V_c CONFERMA AMBIENTALE — cross-check con altre fonti del sistema:
  - report ha sezioni strutturate (Verdict + Question + Method): 1/0
  - tools_custom invocati (shell_exec menzionato nel report): 1/0.5
  - bicono coerente con verdict (sub-sections presenti): 1/0.5
  V_c = mean dei componenti

ρ = (V_a × W_a + V_b × W_b + V_c × W_c) — pesi default 0.4/0.3/0.3

Decision band (allineata a veritas-sys mega skill):
- ρ < 0.4   → SCARTO       (cycle non affidabile, finding non promovibile)
- 0.4-0.9  → SOSPENSIONE   (cycle utilizzabile con caveat — confidence band)
- ρ ≥ 0.9   → COLLASSO      (cycle affidabile, finding può essere promosso)

Output: data/<lab>/veritas/veritas_<ts>.json con breakdown completo +
ρ aggregato + decision band.

Posizione pipeline: dopo seed_integrator (ha aeternitas decision) e
prima di trajectory_evaluator (può usare ρ come segnale aggiuntivo) e
promotion_proposer (può usare ρ come criterio eligibility extra).

Il movement è additivo, non rompe consumer esistenti — falsifier
classico continua a funzionare in parallelo. ρ è un secondo livello di
osservabilità, non sostituisce il primo.
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


# Default weights — overridable via movements.veritas_score.params.weights
DEFAULT_WEIGHTS = {"V_a": 0.4, "V_b": 0.3, "V_c": 0.3}

# Soglie di decision band (allineate a veritas-sys mega skill)
THRESHOLD_SCARTO = 0.4
THRESHOLD_COLLASSO = 0.9


def _compute_v_a(ctx: CycleContext) -> tuple[float, dict[str, Any]]:
    """V_a TELEMETRICA — hard data del cycle."""
    components: dict[str, Any] = {}

    # assertions ratio
    va_metrics = ctx.metrics.get("verify_assertions", {}) or {}
    n_pass = va_metrics.get("n_pass", 0)
    n_total = va_metrics.get("n_total", 0) or 1
    components["assertions_ratio"] = n_pass / n_total

    # falsifier flag penalty
    falsifier_metrics = ctx.metrics.get("report_falsifier", {}) or {}
    flags = falsifier_metrics.get("flags") or []
    if not flags:
        # try reading from file
        try:
            fal_path = paths.domain_data_dir(ctx.domain) / "falsifier" / f"falsifier_{ctx.timestamp}.json"
            if fal_path.exists():
                fal = json.loads(fal_path.read_text())
                flags = fal.get("flags", []) or []
        except Exception:
            flags = []
    n_high = sum(1 for f in flags if isinstance(f, dict) and f.get("severity") == "high")
    n_medium = sum(1 for f in flags if isinstance(f, dict) and f.get("severity") == "medium")
    n_low = sum(1 for f in flags if isinstance(f, dict) and f.get("severity") == "low")
    falsifier_penalty = max(0.0, 1.0 - (n_high * 0.5 + n_medium * 0.2 + n_low * 0.05))
    components["falsifier_penalty"] = falsifier_penalty
    components["n_flags_breakdown"] = {"high": n_high, "medium": n_medium, "low": n_low}

    # bicono extracted
    bicono_metrics = ctx.metrics.get("bicono_extractor", {}) or {}
    n_subsections = bicono_metrics.get("n_subsections", 0)
    if n_subsections >= 4:
        components["bicono_completeness"] = 1.0
    elif n_subsections >= 2:
        components["bicono_completeness"] = 0.5
    else:
        components["bicono_completeness"] = 0.0

    # report size
    report_size = 0
    if ctx.report_path and Path(ctx.report_path).exists():
        report_size = Path(ctx.report_path).stat().st_size
    components["report_size_ok"] = 1.0 if report_size > 1024 else 0.0
    components["report_size_bytes"] = report_size

    numeric_vals = [
        components["assertions_ratio"],
        components["falsifier_penalty"],
        components["bicono_completeness"],
        components["report_size_ok"],
    ]
    v_a = sum(numeric_vals) / len(numeric_vals)
    return v_a, components


def _compute_v_b(ctx: CycleContext) -> tuple[float, dict[str, Any]]:
    """V_b LOGICO-STORICA — coerenza con cycle precedenti."""
    components: dict[str, Any] = {}

    # aeternitas decisions (P0/P1/P5 individuali)
    aeternitas_log_path = paths.domain_data_dir(ctx.domain) / "aeternitas" / f"aeternitas_{ctx.timestamp}.json"
    if aeternitas_log_path.exists():
        try:
            aet = json.loads(aeternitas_log_path.read_text())
            checks = aet.get("checks", {}) or {}
            p0_pass = checks.get("P0", {}).get("passed", False)
            p1_pass = checks.get("P1", {}).get("passed", False)
            p5_pass = checks.get("P5", {}).get("passed", False)
            components["aeternitas_P0_lignaggio"] = 1.0 if p0_pass else 0.3
            components["aeternitas_P1_integrita"] = 1.0 if p1_pass else 0.0
            components["aeternitas_P5_autopoiesi"] = 1.0 if p5_pass else 0.5
        except Exception:
            components["aeternitas_P0_lignaggio"] = 0.5
            components["aeternitas_P1_integrita"] = 0.5
            components["aeternitas_P5_autopoiesi"] = 0.5
    else:
        # No aeternitas log — neutral score
        components["aeternitas_P0_lignaggio"] = 0.5
        components["aeternitas_P1_integrita"] = 0.5
        components["aeternitas_P5_autopoiesi"] = 0.5
        components["_aeternitas_log_present"] = False

    # direzione cambiata (post seed_integrator)
    seed_metrics = ctx.metrics.get("seed_integrator", {}) or {}
    new_direzione = seed_metrics.get("direzione", "")
    # heuristic: cycle precedente se differente direzione → bonus (evolve)
    # ma non penalizziamo continuità (alcuni cycle legitimately stable)
    # Usiamo aeternitas check P5 direzione_changed se disponibile
    direzione_changed = False
    if aeternitas_log_path.exists():
        try:
            aet = json.loads(aeternitas_log_path.read_text())
            direzione_changed = aet.get("checks", {}).get("P5", {}).get("direzione_changed", False)
        except Exception:
            pass
    components["direzione_evolution"] = 0.8 if direzione_changed else 0.6

    numeric_vals = [
        components["aeternitas_P0_lignaggio"],
        components["aeternitas_P1_integrita"],
        components["aeternitas_P5_autopoiesi"],
        components["direzione_evolution"],
    ]
    v_b = sum(numeric_vals) / len(numeric_vals)
    return v_b, components


def _compute_v_c(ctx: CycleContext) -> tuple[float, dict[str, Any]]:
    """V_c CONFERMA AMBIENTALE — cross-check con altre fonti del sistema."""
    components: dict[str, Any] = {}

    # report ha sezioni strutturate (Verdict + Question + Method)
    report_text = ""
    if ctx.report_path and Path(ctx.report_path).exists():
        try:
            report_text = Path(ctx.report_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            report_text = ""
    has_verdict = "## Verdict" in report_text or "## Verdetto" in report_text
    has_question = "## Question" in report_text or "## Domanda" in report_text
    has_method = "## Method" in report_text or "## Metodo" in report_text
    structured_count = sum([has_verdict, has_question, has_method])
    components["report_structured_sections"] = structured_count / 3.0

    # tools_custom invocati (shell_exec menzionato nel report o tool reference)
    if "shell_exec" in report_text or "exp_" in report_text or "python3 tools/" in report_text:
        components["tools_custom_invoked"] = 1.0
    else:
        components["tools_custom_invoked"] = 0.5

    # bicono coerente con verdict (sub-sections presenti nel bicono extractor)
    bicono_metrics = ctx.metrics.get("bicono_extractor", {}) or {}
    n_subsections = bicono_metrics.get("n_subsections", 0)
    components["bicono_coherence"] = 1.0 if n_subsections >= 4 else 0.5

    numeric_vals = [
        components["report_structured_sections"],
        components["tools_custom_invoked"],
        components["bicono_coherence"],
    ]
    v_c = sum(numeric_vals) / len(numeric_vals)
    return v_c, components


def _decision_band(rho: float) -> str:
    if rho < THRESHOLD_SCARTO:
        return "SCARTO"
    elif rho >= THRESHOLD_COLLASSO:
        return "COLLASSO"
    else:
        return "SOSPENSIONE"


def veritas_score(ctx: CycleContext) -> None:
    """Movement: calcola ρ del cycle aggregando V_a + V_b + V_c.

    Mutates: writes data/<domain>/veritas/veritas_<ts>.json
             ctx.metrics["veritas_score"]
    """
    params = cfg.movement_params(ctx.config, "veritas_score")
    weights = params.get("weights", DEFAULT_WEIGHTS)
    # Validate weights sum approx 1.0
    w_sum = sum(weights.values())
    if abs(w_sum - 1.0) > 0.01:
        # Re-normalize
        weights = {k: v / w_sum for k, v in weights.items()}

    v_a, comp_a = _compute_v_a(ctx)
    v_b, comp_b = _compute_v_b(ctx)
    v_c, comp_c = _compute_v_c(ctx)

    rho = (v_a * weights["V_a"] + v_b * weights["V_b"] + v_c * weights["V_c"])
    rho = max(0.0, min(1.0, rho))  # clamp
    band = _decision_band(rho)

    result = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "cycle_ref": ctx.timestamp,
        "lab": ctx.domain,
        "rho": round(rho, 4),
        "decision_band": band,
        "vectors": {
            "V_a_telemetrica": round(v_a, 4),
            "V_b_logico_storica": round(v_b, 4),
            "V_c_conferma_ambientale": round(v_c, 4),
        },
        "weights": weights,
        "components": {
            "V_a": comp_a,
            "V_b": comp_b,
            "V_c": comp_c,
        },
        "thresholds": {
            "SCARTO": f"rho < {THRESHOLD_SCARTO}",
            "SOSPENSIONE": f"{THRESHOLD_SCARTO} <= rho < {THRESHOLD_COLLASSO}",
            "COLLASSO": f"rho >= {THRESHOLD_COLLASSO}",
        },
    }

    out_dir = paths.domain_data_dir(ctx.domain) / "veritas"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"veritas_{ctx.timestamp}.json"
    try:
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    except OSError as e:
        logger.warning("veritas_score: write failed: %s", e)
        out_path = None

    ctx.metrics.setdefault("veritas_score", {}).update(
        rho=round(rho, 4),
        decision_band=band,
        V_a=round(v_a, 4),
        V_b=round(v_b, 4),
        V_c=round(v_c, 4),
        log_path=str(out_path) if out_path else None,
    )
    logger.info(
        "veritas_score: rho=%.3f → %s · V_a=%.3f V_b=%.3f V_c=%.3f",
        rho, band, v_a, v_b, v_c,
    )


register_movement("veritas_score", veritas_score)
