"""ssp_pipeline movement — chiude scoperta → prodotto in autonomia.

Eseguito post trajectory_evaluator, pre notify. Concatena gli step SSP:
  1. on_crystallize           — sempre (anche pre_discovery → scaffold visibile)
  2. finding_eligibility_gate — sempre (classifier multi-segnale dei findings)
  3. application_designer     — solo se mature_eligible (claim affidabili)
  4. stage4_poc_runner        — solo se >=1 applicative_finding eligible
                                 e gate=mature_eligible

Logica: ogni step legge l'output del precedente. Se il gate non è
mature_eligible, application_designer + Stage 4 sono skip (corretto:
non generiamo prodotti su scoperte pre_discovery).

Pattern: subprocess sui trigger script in core/triggers/. Idempotente
(skip se output già esistente). Errori non-critici per il cycle.
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
from pathlib import Path

from core.lab_agent import register_movement, CycleContext


logger = logging.getLogger(__name__)

TRIGGERS_DIR = Path(__file__).parent / "triggers"


def _run_trigger(script_name: str, args: list[str], cwd: Path,
                 timeout: int, env_extra: dict | None = None) -> tuple[int, str]:
    """Esegue uno script trigger. Ritorna (rc, output)."""
    script = TRIGGERS_DIR / script_name
    if not script.exists():
        return 127, f"trigger non trovato: {script}"
    cmd = [sys.executable, str(script), *args]
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    try:
        r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                           timeout=timeout, env=env)
        return r.returncode, (r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr else "")
    except subprocess.TimeoutExpired:
        return 124, f"timeout {timeout}s su {script_name}"


def _gate_status_from_cycle_report(domain_dir: Path, cycle_ts: str) -> str | None:
    """Estrae gate_status dal cycle-report.draft.md scritto da on_crystallize."""
    scoperte = domain_dir / "scoperte"
    if not scoperte.exists():
        return None
    matches = list(scoperte.glob(f"{cycle_ts}_*"))
    if not matches:
        return None
    cr = matches[0] / "cycle-report.draft.md"
    if not cr.exists():
        return None
    text = cr.read_text(errors="replace")
    m = re.search(r"^\s*gate_status:\s*(\S+)", text, re.M) or \
        re.search(r"^\s*status:\s*(\S+)", text, re.M)
    return m.group(1).strip() if m else None


def _eligible_count(domain_dir: Path, cycle_ts: str) -> int:
    """Conta applicative_finding eligible da finding_index.draft.json."""
    soluzioni = domain_dir / "soluzioni"
    if not soluzioni.exists():
        return 0
    matches = list(soluzioni.glob(f"{cycle_ts}_*"))
    if not matches:
        return 0
    fi = matches[0] / "finding_index.draft.json"
    if not fi.exists():
        return 0
    import json
    try:
        data = json.loads(fi.read_text())
        return data.get("summary", {}).get("n_application_eligible", 0)
    except (json.JSONDecodeError, OSError):
        return 0


def ssp_pipeline_movement(ctx: CycleContext) -> None:
    """Movement: orchestra la pipeline SSP scoperta → prodotto."""
    cycle_ts = ctx.timestamp
    domain = ctx.domain
    domain_dir = ctx.data_dir
    env = {"LAB_DATA_DIR": str(domain_dir.parent), "DOMAIN": domain}
    cwd = domain_dir.parent.parent  # repo root (cd /opt/D-ND_LAB)

    # Step 1 — on_crystallize (sempre)
    rc, out = _run_trigger("on_crystallize.py", [cycle_ts, "--out-suffix=_auto"],
                           cwd=cwd, timeout=60, env_extra=env)
    if rc != 0:
        logger.warning("ssp_pipeline: on_crystallize rc=%s — skip resto pipeline\n%s",
                       rc, out[-500:])
        ctx.metrics["ssp_pipeline_status"] = "crystallize_failed"
        return
    logger.info("ssp_pipeline: on_crystallize OK")

    # Step 1.5 — promote_to_publish (refactor 03/05 sera).
    # Sempre, anche per cycle pre_discovery/transitional, perché la
    # dashboard FastAPI espone published/ pubblicamente. Senza promote,
    # i cycle che skippano post-eligibility non sarebbero mai visibili.
    # Sanitize draft → published/ rimuove markup workflow ([TARGET — TM1
    # refinement], copy_authority, sezioni placeholder, scaffold notices).
    rc, out = _run_trigger("promote_to_publish.py", [cycle_ts, "--force"],
                           cwd=cwd, timeout=20, env_extra=env)
    if rc != 0:
        logger.warning("ssp_pipeline: promote_to_publish rc=%s\n%s", rc, out[-300:])
        # Non blocca: degraded display, recoverable.
    else:
        logger.info("ssp_pipeline: promote_to_publish OK")

    # Step 2 — eligibility gate (sempre)
    rc, out = _run_trigger("finding_eligibility_gate.py", [cycle_ts, "--force"],
                           cwd=cwd, timeout=30, env_extra=env)
    if rc != 0:
        logger.warning("ssp_pipeline: eligibility_gate rc=%s — skip designer/stage4\n%s",
                       rc, out[-500:])
        ctx.metrics["ssp_pipeline_status"] = "eligibility_failed"
        return
    logger.info("ssp_pipeline: eligibility_gate OK")

    # Gate decision: scoperta matura?
    gate_status = _gate_status_from_cycle_report(domain_dir, cycle_ts)
    eligible_n = _eligible_count(domain_dir, cycle_ts)
    logger.info("ssp_pipeline: gate_status=%s eligible_findings=%d", gate_status, eligible_n)

    if gate_status not in ("mature_eligible", "draft"):
        # pre_discovery / transitional → scoperta visibile, ma niente designer/stage4
        ctx.metrics["ssp_pipeline_status"] = f"skip_post_eligibility:{gate_status}"
        logger.info("ssp_pipeline: gate_status=%s → skip designer + stage4 (refinement loop)",
                    gate_status)
        return

    # Step 3 — application_designer (solo mature)
    rc, out = _run_trigger("application_designer.py", [cycle_ts, "--force"],
                           cwd=cwd, timeout=30, env_extra=env)
    if rc != 0:
        logger.warning("ssp_pipeline: designer rc=%s — skip stage4\n%s", rc, out[-500:])
        ctx.metrics["ssp_pipeline_status"] = "designer_failed"
        return
    logger.info("ssp_pipeline: application_designer OK")

    if eligible_n < 1:
        ctx.metrics["ssp_pipeline_status"] = "no_applicative_finding"
        logger.info("ssp_pipeline: 0 applicative_finding eligible → skip stage4")
        return

    # Step 4 — stage4 PoC runner (auto-pick primo applicative_finding)
    # Genera library candidate (più adatto al benchmark A/B). Timeout largo
    # perché claude-cli + esecuzione PoC.
    # Multi-candidate (NEW 01/05): genera tutti e 3 i tipi (library/kernel/demo)
    # per il finding eligible. Il sistema produce 3 PoC con verdict diversi,
    # operatore decide quale promuovere. Timeout aumentato proporzionalmente.
    rc, out = _run_trigger("stage4_poc_runner.py",
                           [cycle_ts, "--auto",
                            "--candidate-types", "library,kernel,demo",
                            "--max-turns", "8", "--gen-timeout", "360",
                            "--exec-timeout", "90"],
                           cwd=cwd, timeout=1200, env_extra=env)
    if rc != 0:
        logger.warning("ssp_pipeline: stage4 rc=%s\n%s", rc, out[-1000:])
        ctx.metrics["ssp_pipeline_status"] = f"stage4_failed:rc={rc}"
        return

    # Estrai verdict dal log per metriche del cycle
    verdict_m = re.search(r"verdict:\s*(\S+)", out)
    verdict = verdict_m.group(1) if verdict_m else "unknown"
    ctx.metrics["ssp_pipeline_status"] = f"complete:stage4={verdict}"
    logger.info("ssp_pipeline: stage4 verdict=%s", verdict)

    # Step 5 — build_applications_index (source: published/, refactor 03/05).
    # Rigenera data/applications.json per pagine sito statiche.
    rc, out = _run_trigger("build_applications_index.py", [],
                           cwd=cwd, timeout=30, env_extra=env)
    if rc != 0:
        logger.warning("ssp_pipeline: build_index rc=%s\n%s", rc, out[-300:])
        # Non blocca lo status del cycle — il sito può rimanere stale fino
        # al prossimo cycle, non è critical path.
    else:
        logger.info("ssp_pipeline: build_applications_index OK")


register_movement("ssp_pipeline", ssp_pipeline_movement)
