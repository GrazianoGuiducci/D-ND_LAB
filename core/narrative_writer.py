"""Movement — narrative_writer (universal).

Distilla l'output tecnico del cycle in una narrazione di ~200 parole
leggibile da chi non sa nulla di AI o D-ND. Pattern Apple-like:
dato → storia → significato.

Legge:
- agent report (`reports/agent_<ts>.md`)
- falsifier (`falsifier/falsifier_<ts>.json` o `reports/...`)
- veritas (`veritas/veritas_*.json` con cycle_ref matching)
- aeternitas (`aeternitas/aeternitas_<ts>.json`)
- trajectory_evaluator (`trajectory_log.jsonl` ultimo)
- bicono (`biconi/bicono_<ts>.json`)

Compone un prompt LLM breve, chiede narrativa human-readable, salva in
`data/<lab>/narratives/narrative_<ts>.md`.

Critical=False: se LLM fallisce o artefatti mancano, skip silenzioso.
Il cycle resta completo e auditabile dai file tecnici.

Costo stimato: 1 LLM call breve (~2k input + 300 output tokens) = ~$0.01
su DeepSeek-V4-pro, $0 su codex-cli/claude-cli (subscription).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from core import config as cfg
from core import paths
from core.lab_agent import CycleContext, register_movement
from core.llm_adapter import AdapterConfig, run_agent

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """\
Sei il narratore del lab D-ND. Distilli un cycle di ricerca tecnico in
una narrazione breve, leggibile da chi non sa nulla di AI, ricerca o
matematica.

Regole non negoziabili:
1. **200 parole massimo**. Se sfori, hai fallito.
2. **No jargon**. Sostituisci: effect_z → "il segnale", ρ veritas → "la
   qualità del cycle", ordered-vs-shuffle → "ordinato vs mescolato",
   DND_DELTA → "lo schema regge", NO_DELTA → "lo schema non regge",
   REDESIGN → "il sistema chiede di riprogettare", ecc.
3. **Storia in 3 atti**: cosa volevamo verificare → cosa il sistema ha
   trovato → cosa cambia adesso. Niente bullet, prosa fluida.
4. **Onestà sopra tutto**. Se il cycle ha falsificato, racconta la
   falsificazione come scoperta non come fallimento. Se è synthetic
   o fallback, dichiaralo.
5. **Niente claim diagnostici/finanziari/predittivi non supportati**.
   Il lab misura struttura, non promette risultati.
6. **Tono Apple-like**: lirico ma preciso, mai roboante. Scrivi al
   presente. Italiano.

Output: solo il testo della narrativa. Niente intestazioni, niente
metadati, nessuna frase di apertura tipo "ecco la narrazione".
"""


def _read_text(path: Path, max_chars: int = 6000) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(errors="replace")[:max_chars]
    except Exception:
        return ""


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _find_latest_with_ts(dir_path: Path, pattern: str, ts: str) -> Path | None:
    if not dir_path.exists():
        return None
    # First: exact ts match (e.g. veritas_<ts>.json)
    cand = dir_path / pattern.replace("*", ts)
    if cand.exists():
        return cand
    # Fallback: any file containing ts in name
    matches = sorted(dir_path.glob(pattern))
    matches = [p for p in matches if ts in p.name]
    if matches:
        return matches[-1]
    # Last fallback: any latest matching pattern
    all_matches = sorted(dir_path.glob(pattern))
    return all_matches[-1] if all_matches else None


def _last_trajectory_for(domain_dir: Path, ts: str) -> dict | None:
    log = domain_dir / "trajectory_log.jsonl"
    if not log.exists():
        return None
    try:
        for line in reversed(log.read_text().splitlines()):
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if d.get("cycle_ref") == ts:
                return d
    except Exception:
        return None
    return None


def _compose_user_message(ctx: CycleContext, artifacts: dict) -> str:
    """Build the user message with cycle artifacts bundled compactly."""
    parts = [
        f"Lab: {ctx.domain}",
        f"Cycle timestamp: {ctx.timestamp}",
        "",
    ]

    if artifacts["report"]:
        parts.append("=== AGENT REPORT (technical) ===")
        parts.append(artifacts["report"])
        parts.append("")

    if artifacts["falsifier"]:
        f = artifacts["falsifier"]
        parts.append("=== FALSIFIER ===")
        parts.append(f"coherent: {f.get('coherent')}")
        parts.append(f"summary: {f.get('summary', '')}")
        n_flags = len(f.get("flags", []) or [])
        parts.append(f"n_flags: {n_flags}")
        parts.append("")

    if artifacts["aeternitas"]:
        a = artifacts["aeternitas"]
        parts.append("=== AETERNITAS ===")
        parts.append(f"decision: {a.get('decision')}")
        checks = a.get("checks", {}) or {}
        for k in ("P0", "P1", "P5"):
            v = checks.get(k, {})
            if isinstance(v, dict):
                parts.append(f"  {k}: passed={v.get('passed')} reason={(v.get('reason') or '')[:120]}")
        parts.append("")

    if artifacts["veritas"]:
        v = artifacts["veritas"]
        parts.append("=== VERITAS ===")
        parts.append(f"rho: {v.get('rho')} → {v.get('decision_band')}")
        vec = v.get("vectors", {}) or {}
        parts.append(f"V_a={vec.get('V_a_telemetrica')} V_b={vec.get('V_b_logico_storica')} V_c={vec.get('V_c_conferma_ambientale')}")
        parts.append("")

    if artifacts["trajectory"]:
        t = artifacts["trajectory"]
        parts.append("=== TRAJECTORY EVALUATOR ===")
        parts.append(f"decision: {t.get('decision')} confidence={t.get('confidence')}")
        action = t.get("action", {}) or {}
        if isinstance(action, dict):
            parts.append(f"action.type: {action.get('type')}")
        parts.append("")

    if artifacts["bicono"]:
        b = artifacts["bicono"].get("bicono", {}) if isinstance(artifacts["bicono"], dict) else {}
        if b:
            parts.append("=== BICONO ===")
            for k in ("radici", "singolare", "invariante", "campo"):
                v = b.get(k, "")
                if v:
                    parts.append(f"{k}: {str(v)[:300]}")
            parts.append("")

    parts.append(
        "Produci la narrativa di 200 parole secondo le regole del system prompt."
    )
    return "\n".join(parts)


def narrative_writer(ctx: CycleContext) -> None:
    """Produce data/<lab>/narratives/narrative_<ts>.md from cycle artifacts."""
    params = cfg.movement_params(ctx.config, "narrative_writer")
    max_words = int(params.get("max_words", 200))
    timeout_s = int(params.get("timeout_seconds", 90))

    ts = ctx.timestamp
    domain_dir = paths.domain_data_dir(ctx.domain)

    # Bail early if agent did not produce a report — nothing to narrate
    report_path = paths.reports_dir(ctx.domain) / f"agent_{ts}.md"
    if not report_path.exists():
        ctx.record_skipped("narrative_writer", "no agent report at expected path")
        return

    artifacts = {
        "report": _read_text(report_path, max_chars=6000),
        "falsifier": _read_json(domain_dir / "falsifier" / f"falsifier_{ts}.json")
                     or _read_json(paths.reports_dir(ctx.domain) / f"falsifier_{ts}.json"),
        "veritas": _read_json(_find_latest_with_ts(domain_dir / "veritas", "veritas_*.json", ts)) if (domain_dir / "veritas").exists() else None,
        "aeternitas": _read_json(domain_dir / "aeternitas" / f"aeternitas_{ts}.json"),
        "trajectory": _last_trajectory_for(domain_dir, ts),
        "bicono": _read_json(domain_dir / "biconi" / f"bicono_{ts}.json"),
    }

    if not artifacts["report"]:
        ctx.record_skipped("narrative_writer", "report file empty")
        return

    user_message = _compose_user_message(ctx, artifacts)
    system_prompt = SYSTEM_PROMPT.replace("200 parole", f"{max_words} parole")

    # Run via existing provider chain. tools=None → bare completion path
    # works for codex-cli/claude-cli/openrouter through llm_adapter.
    base_config = AdapterConfig.from_env()
    config = AdapterConfig(
        base_url=base_config.base_url,
        api_key=base_config.api_key,
        model=base_config.model,
        max_turns=1,                  # single response, no tool loop
        timeout_seconds=timeout_s,
        max_cost_usd=0.50,            # narrative is cheap, hard cap
    )

    try:
        result = run_agent(
            system_prompt=system_prompt,
            user_message=user_message,
            tools=None,
            config=config,
        )
    except Exception as e:
        logger.warning(f"narrative_writer: LLM call failed: {e}")
        ctx.movement_status["narrative_writer"] = f"pending: llm failed: {e}"
        return

    text = (result.final_text or "").strip()
    if not text or len(text) < 50:
        ctx.record_skipped("narrative_writer", f"narrative too short ({len(text)} chars)")
        return

    # Sanitize: drop any markdown fences or extraneous wrapper
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Word count gate (soft warning, not failure)
    word_count = len(text.split())
    over_limit = word_count > int(max_words * 1.3)

    out_dir = domain_dir / "narratives"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"narrative_{ts}.md"

    # Emit a small frontmatter for downstream consumers (site, social)
    body = (
        f"---\n"
        f"lab: {ctx.domain}\n"
        f"cycle_ts: {ts}\n"
        f"word_count: {word_count}\n"
        f"verdict_band: {(artifacts['veritas'] or {}).get('decision_band', 'unknown')}\n"
        f"aeternitas: {(artifacts['aeternitas'] or {}).get('decision', 'unknown')}\n"
        f"trajectory_decision: {(artifacts['trajectory'] or {}).get('decision', 'unknown')}\n"
        f"---\n\n"
        f"{text}\n"
    )

    out_path.write_text(body, encoding="utf-8")

    ctx.record_success(
        "narrative_writer",
        word_count=word_count,
        over_limit=over_limit,
        output_path=str(out_path),
        provider_used=getattr(result, "stop_reason", None),
    )
    logger.info(
        "narrative_writer: %d words written → %s%s",
        word_count, out_path,
        " (OVER LIMIT)" if over_limit else "",
    )


register_movement("narrative_writer", narrative_writer)
