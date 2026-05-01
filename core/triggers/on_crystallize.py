#!/usr/bin/env python3
"""on_crystallize — SSP intake automatico per cicli del Lab fisica D-ND.

Input: cycle_ts (es. 20260429_1041) o --latest
Reads: agent_<ts>.md + falsifier_<ts>.json + valutatore_log.jsonl + seme.json
Gate (TM7-aligned strict, BP §G):
  - 0 high flag obbligatorio
  - CRYSTALLIZE_high da valutatore
  - medium flag passano ma vengono dichiarati come visible_risks
Output: scaffold drafts in /opt/MM_D-ND/applications/scoperte/<ts>_<slug>/
  - lab-note.draft.md  (audience livello 1-2, copy authority TM1)
  - cycle-report.draft.md  (audience tecnico, copy authority TM3+TM1)

Boundary:
  - niente publish, niente API CMS, niente runtime touch
  - non sovrascrive drafts esistenti senza --force
  - --out-suffix=_auto per shakedown (genera dir parallela ai drafts manuali)
"""

import argparse
import json
import re
import os
import sys
from pathlib import Path

# Path resolution domain-agnostic per D-ND_LAB.
# LAB_DATA_DIR e DOMAIN sono parametrizzabili via env o argomenti CLI.
# Default: leggi da env (come fa core.api/core.lab_agent in D-ND_LAB).
def _resolve_paths(domain: str | None = None) -> dict[str, Path]:
    """Risolve i path per il dominio dato (default da env DOMAIN o 'physics').

    D-ND_LAB layout (vs MM_D-ND):
      LAB_DATA_DIR/<domain>/reports/agent_*.md           (era tools/data/reports/)
      LAB_DATA_DIR/<domain>/falsifier/falsifier_*.json   (era tools/data/reports/falsifier_*)
      LAB_DATA_DIR/<domain>/trajectory_log.jsonl         (era valutatore_log.jsonl)
      LAB_DATA_DIR/<domain>/seed.json                    (era tools/data/seme.json)
      LAB_DATA_DIR/<domain>/scoperte/<ts>_<slug>/        (era applications/scoperte/)
    """
    lab_data = Path(os.environ.get("LAB_DATA_DIR", "/opt/D-ND_LAB/data"))
    dom = domain or os.environ.get("DOMAIN", "physics")
    domain_dir = lab_data / dom
    return {
        "domain": dom,
        "lab_data": lab_data,
        "domain_dir": domain_dir,
        "reports": domain_dir / "reports",
        "falsifier": domain_dir / "falsifier",
        "trajectory_log": domain_dir / "trajectory_log.jsonl",
        "session_log": domain_dir / "session_log.jsonl",  # opzionale
        "seed": domain_dir / "seed.json",
        "apps_base": domain_dir / "scoperte",
    }


# Inizializzato a runtime (può essere ri-risolto per dominio diverso).
_PATHS = _resolve_paths()
LAB_BASE = _PATHS["domain_dir"].parent
REPORTS = _PATHS["reports"]
FALSIFIER_DIR = _PATHS["falsifier"]
VALUT_LOG = _PATHS["trajectory_log"]
SESSION_LOG = _PATHS["session_log"]
SEME = _PATHS["seed"]
APPS_BASE = _PATHS["apps_base"]


def slugify(text: str) -> str:
    t = text.lower()
    t = re.sub(r"[^\w\s-]", "", t)
    t = re.sub(r"[\s_]+", "-", t)
    t = re.sub(r"-+", "-", t).strip("-")
    return "-".join(t.split("-")[:6])


def parse_agent_report(path: Path) -> dict:
    text = path.read_text()
    title_m = re.search(r"^#\s+Agent Report\s+[—-]\s+(.+)$", text, re.M)
    title = title_m.group(1).strip() if title_m else path.stem.replace("agent_", "")
    date_m = re.search(r"\*\*Date\*\*:\s*([^\n]+)", text)
    piano_m = re.search(r"\*\*Piano\*\*:\s*(\d+)", text)
    tension_m = re.search(r"\*\*Tension explored\*\*:\s*([^\n]+)", text)
    script_m = re.search(r"Script:\s*`([^`]+)`", text)
    data_m = re.search(r"Data:\s*`([^`]+)`", text)
    return {
        "title": title,
        "date": date_m.group(1).strip() if date_m else "",
        "piano": piano_m.group(1) if piano_m else "",
        "tension": tension_m.group(1).strip() if tension_m else "",
        "exp_script": script_m.group(1) if script_m else "",
        "data_file": data_m.group(1) if data_m else "",
    }


def parse_falsifier(path: Path) -> dict:
    data = json.loads(path.read_text())
    flags = data.get("flags", [])
    by_sev = {"high": [], "medium": [], "low": []}
    for f in flags:
        by_sev.setdefault(f.get("severity", "low"), []).append(f)
    return {
        "coherent": data.get("coherent", False),
        "n_high": len(by_sev["high"]),
        "n_medium": len(by_sev["medium"]),
        "n_low": len(by_sev["low"]),
        "high_flags": by_sev["high"],
        "medium_flags": by_sev["medium"],
        "low_flags": by_sev["low"],
        "summary": data.get("summary", ""),
        "verdict_label": f"{len(by_sev['high'])}_high_{len(by_sev['medium'])}_medium_{len(by_sev['low'])}_low",
    }


def find_valutatore_decision(cycle_ts: str) -> dict | None:
    """Cerca in valutatore_log.jsonl, fallback su lab_session_log.jsonl."""
    if VALUT_LOG.exists():
        for line in VALUT_LOG.read_text().splitlines():
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("cycle_ref") == cycle_ts:
                return {"decision": d.get("decision"), "confidence": d.get("confidence"), "source": "valutatore_log"}
    if SESSION_LOG.exists():
        for line in SESSION_LOG.read_text().splitlines():
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("cycle_ts") == cycle_ts:
                v = d.get("valutatore", {})
                if v.get("decision"):
                    return {"decision": v.get("decision"), "confidence": v.get("confidence"), "source": "lab_session_log"}
    return None


def gate_check(falsifier: dict, valutatore: dict | None) -> tuple[str, str]:
    """Soglia adattiva (rev 01/05 — direttiva operatore: lab notturno deve
    sempre produrre valore visibile).

    Ritorna: (status, message)
      'mature_eligible' — 0 HIGH + valutatore CRYSTALLIZE high → app candidate generabili
      'transitional'    — 1+ HIGH + valutatore CRYSTALLIZE → publish con visible_risks
      'refinement_required' — valutatore non CRYSTALLIZE → niente publish, refinement file
      'invalid'         — assenza entry valutatore o stato non riconosciuto
    """
    if not valutatore:
        return "invalid", "no valutatore entry — cycle non valutato"
    decision = valutatore.get("decision", "")
    if decision != "CRYSTALLIZE":
        return "refinement_required", (
            f"valutatore decision={decision} → cycle in refinement loop, niente publish"
        )
    if falsifier["n_high"] > 0:
        return "transitional", (
            f"{falsifier['n_high']} HIGH flag → publish come transitional con "
            f"visible_risks dichiarati. NO applicazioni candidate."
        )
    return "mature_eligible", (
        f"0 HIGH + CRYSTALLIZE → eligible per applicazioni "
        f"(valutatore source: {valutatore.get('source')})"
    )


def get_seme_version() -> str:
    if not SEME.exists():
        return "unknown"
    try:
        return f"piano_{json.loads(SEME.read_text()).get('piano', 'unknown')}"
    except (json.JSONDecodeError, IOError):
        return "unknown"


def find_predecessor(cycle_ts: str) -> dict | None:
    """Cerca il cycle precedente non-archived nello stesso lab_instance.

    Scansiona applications/scoperte/<ts>_<slug>/cycle-report.draft.md,
    legge il front matter, e prende il cycle più vicino con ts < cycle_ts
    e status != archived.
    """
    if not APPS_BASE.exists():
        return None
    candidates = []
    for d in APPS_BASE.iterdir():
        if not d.is_dir() or d.name.endswith("_auto"):
            continue
        # Estrai cycle_ts dal nome dir (formato: YYYYMMDD_HHMM_slug)
        parts = d.name.split("_", 2)
        if len(parts) < 2:
            continue
        try:
            other_ts = f"{parts[0]}_{parts[1]}"
            if not (other_ts.replace("_", "").isdigit() and len(other_ts) == 13):
                continue
        except (IndexError, ValueError):
            continue
        if other_ts >= cycle_ts:
            continue
        # Leggi front matter del cycle-report per status + slug
        cr = d / "cycle-report.draft.md"
        if not cr.exists():
            continue
        text = cr.read_text()
        # Parse status from front matter
        m = re.search(r"^status:\s*(\S+)", text, re.M)
        status = m.group(1).strip() if m else "draft"
        if status == "archived":
            continue
        candidates.append({
            "cycle_ts": other_ts,
            "dir_name": d.name,
            "lab_note_path": str(d / "lab-note.draft.md"),
            "cycle_report_path": str(cr),
        })
    if not candidates:
        return None
    candidates.sort(key=lambda x: x["cycle_ts"], reverse=True)
    return candidates[0]


def normalize_visible_risk(flag: dict) -> str:
    """Produce stringa breve coerente con drafts manuali."""
    lens = flag.get("lens", "?")
    severity = flag.get("severity", "medium")
    summary = (flag.get("summary") or flag.get("claim") or "").strip()
    # Trunca a 100 char per coerenza con manual drafts
    short = summary[:100].rstrip()
    if len(summary) > 100:
        short = short.rsplit(" ", 1)[0] + "..."
    return f"L{lens} {severity}: {short}"


def yaml_flag_lines(flags: list, severity: str) -> str:
    if not flags:
        return ""
    out = []
    for f in flags:
        summary = (f.get("summary") or f.get("claim") or "")[:200].replace('"', "'")
        out.append(f"  - lens: {f.get('lens', '?')}")
        out.append(f"    severity: {severity}")
        out.append(f"    summary: {json.dumps(summary)}")
        out.append(f'    addressed_in_artifact: "[TARGET — to fill]"')
    return "\n".join(out)


def visible_risks_lines(medium_flags: list) -> str:
    if not medium_flags:
        return "  - none"
    out = []
    for f in medium_flags:
        normalized = normalize_visible_risk(f).replace('"', "'")
        out.append(f'  - "{normalized}"')
    return "\n".join(out)


def render_lab_note_skeleton(ctx: dict) -> str:
    fals = ctx["falsifier"]
    status = ctx.get("draft_status", "draft")
    transitional_banner = ""
    high_block = "  - none"
    if status in ("transitional", "pre_discovery") and fals["high_flags"]:
        items = [f'  - "{normalize_visible_risk(f).replace(chr(34), chr(39))}"' for f in fals["high_flags"]]
        high_block = "\n".join(items)
    if status == "transitional":
        transitional_banner = (
            "\n> ⚠ **STATO: TRANSITIONAL** — il falsifier ha rilevato "
            f"{fals['n_high']} high flag su questo ciclo. La scoperta è esposta "
            "qui per trasparenza pubblica con i rischi dichiarati. Niente claim "
            "verified finché un cycle successivo non chiude il refinement loop.\n"
        )
    elif status == "pre_discovery":
        valut = ctx.get("valutatore_decision", "non-CRYSTALLIZE")
        transitional_banner = (
            f"\n> ⚠ **STATO: PRE-DISCOVERY** — il valutatore del Lab ha emesso "
            f"`{valut}` (non `CRYSTALLIZE`). La scoperta non è cristallizzata "
            "nel seme. Esposta qui per trasparenza con disclaimer forte: il "
            "ciclo deve maturare prima di consolidarsi. Refinement loop attivato.\n"
        )
    medium_to_address = []
    for f in fals["medium_flags"]:
        normalized = normalize_visible_risk(f).replace('"', "'")
        medium_to_address.append(f'  - "{normalized}"')
    medium_block = "\n".join(medium_to_address) if medium_to_address else "  - none"
    pred = ctx.get("predecessor")
    pred_line = ""
    if pred:
        rel = Path(pred["lab_note_path"]).relative_to(APPS_BASE.parent)
        pred_line = f"related_lab_note_predecessor: {rel}\n"
    return f"""---
ssp_state: scoperte
artifact_type: lab-note
status: {status}
audience: visitatore esterno · vocabolario livello 1-2 (TM7 terminology rule)
copy_authority: TM1 (will refine before publish)
provenance:
  cycle_ts: "{ctx['cycle_ts']}"
  lab_instance: fisica
  seme_version: {ctx['seme_version']}
  exp_script: {ctx['report']['exp_script']}
  data_file: {ctx['report']['data_file']}
  agent_report: tools/data/reports/agent_{ctx['cycle_ts']}.md
  falsifier_report: tools/data/reports/falsifier_{ctx['cycle_ts']}.json
  falsifier_verdict: {fals['verdict_label']}
  valutatore_decision: {ctx.get('valutatore_decision','unknown')}_{ctx.get('valutatore_confidence','unknown')}
  gate_status: {ctx.get('gate_status','unknown')}
target_route: lab.d-nd.com/lab-notes/{ctx['slug']}
target_cms_category: lab-note
title_proposal: "[TARGET — TM1 refinement] {ctx['report']['title']}"
slug_proposal: {ctx['slug']}
{pred_line}high_flags_visible:
{high_block}
medium_flags_to_address:
{medium_block}
generated_by: on_crystallize.py
---

# [TARGET — TM1 refinement] {ctx['report']['title']}

> Nota di laboratorio · Lab fisica D-ND · ciclo del {ctx['report']['date']}
{transitional_banner}
> [SCAFFOLD AUTO-GENERATO] Body da scrivere a mano da TM3 o agente narrativo.
> Sorgente: `{ctx['report_path']}`. Vocabolario livello 1-2 (TM7 terminology rule).

## Tensione esplorata

{ctx['report']['tension']}

## [TARGET — narrazione livello 1-2]

[Storia per visitatore tiepido. Vocabolario chiaro. Niente gergo D-ND.]

## Provenance

Il ciclo completo, con esperimento, dati grezzi, audit del falsifier e bicono della scoperta, è disponibile come `cycle-report` collegato.

---

*Auto-scaffold da `on_crystallize.py`. Copy refinement pending TM1. Status `{status}` = {'eligible per applicazioni' if status == 'draft' else 'pubblicato con visible_risks dichiarati'}.*
"""


def render_cycle_report_skeleton(ctx: dict) -> str:
    fals = ctx["falsifier"]
    status = ctx.get("draft_status", "draft")
    flags_block = ""
    parts = []
    if fals["high_flags"]:
        parts.append(yaml_flag_lines(fals["high_flags"], "high"))
    if fals["medium_flags"]:
        parts.append(yaml_flag_lines(fals["medium_flags"], "medium"))
    if fals["low_flags"]:
        parts.append(yaml_flag_lines(fals["low_flags"], "low"))
    flags_block = "\n".join(parts) if parts else "  - none"
    # visible_risks include high E medium quando transitional o pre_discovery
    show_high = status in ("transitional", "pre_discovery")
    risk_flags = (fals["high_flags"] if show_high else []) + fals["medium_flags"]
    visible = visible_risks_lines(risk_flags)
    transitional_banner = ""
    if status == "transitional":
        transitional_banner = (
            "\n> ⚠ **STATO: TRANSITIONAL** — falsifier ha rilevato "
            f"{fals['n_high']} HIGH flag. Pubblicato qui per trasparenza con "
            "high_flags esposti come visible_risks. Refinement loop attivato.\n"
        )
    elif status == "pre_discovery":
        valut = ctx.get("valutatore_decision", "non-CRYSTALLIZE")
        transitional_banner = (
            f"\n> ⚠ **STATO: PRE-DISCOVERY** — valutatore Lab ha emesso "
            f"`{valut}` (non CRYSTALLIZE). Scoperta non cristallizzata nel seme. "
            "Pubblicato per trasparenza con disclaimer forte. Refinement loop attivato.\n"
        )
    return f"""---
ssp_state: scoperte
artifact_type: cycle-report
status: {status}
audience: lettore tecnico · vocabolario livello 3-4 (TM7 terminology rule)
copy_authority: TM3 (technical) · TM1 (refinement before publish)
provenance:
  cycle_ts: "{ctx['cycle_ts']}"
  piano: {ctx['report']['piano']}
  lab_instance: fisica
  seme_version: {ctx['seme_version']}
  tension_explored: {json.dumps(ctx['report']['tension'])}
  exp_script: {ctx['report']['exp_script']}
  data_file: {ctx['report']['data_file']}
  agent_report: tools/data/reports/agent_{ctx['cycle_ts']}.md
  falsifier_report: tools/data/reports/falsifier_{ctx['cycle_ts']}.json
  falsifier_verdict: {fals['verdict_label']}
  valutatore_decision: {ctx.get('valutatore_decision','unknown')}_{ctx.get('valutatore_confidence','unknown')}
target_route: lab.d-nd.com/cycles/{ctx['cycle_ts']}
target_cms_category: cycle-report
related_lab_note: lab-note.draft.md
{ctx.get('predecessor_yaml', '')}medium_flags:
{flags_block}
visible_risks:
{visible}
generated_by: on_crystallize.py
---

# Cycle Report — {ctx['report']['title']}
{transitional_banner}
> [SCAFFOLD AUTO-GENERATO] Body da riprodurre/riformattare dal report originale `{ctx['report_path']}`.
> TM3 o agente tecnico aggiunge gestione esplicita dei medium flag come visible_risks.

## Provenance machine-readable

Vedi front matter sopra.

## Falsifier audit summary

{fals['summary']}

## [TARGET — gestione medium flag come rischi visibili]

[TM3 elabora ogni medium flag come dichiarazione pubblica trasparente.]

## [TARGET — risultati dal report originale]

[Tabelle, scaling, dimostrazioni, key findings, bicono — riformattare dal report originale. Vedi `{ctx['report_path']}`.]

## Files

- Report originale: `{ctx['report_path']}`
- Falsifier audit: `tools/data/reports/falsifier_{ctx['cycle_ts']}.json`
- Data: {ctx['report']['data_file']}
- Script: {ctx['report']['exp_script']}

---

*Auto-scaffold da `on_crystallize.py`. Pubblicazione richiede operatore + TM7 review della gestione esplicita dei medium flag.*
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cycle_ts", nargs="?")
    ap.add_argument("--latest", action="store_true")
    ap.add_argument("--out-suffix", default="")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if args.latest:
        agents = sorted(REPORTS.glob("agent_*.md"))
        if not agents:
            print("ERROR: nessun agent_*.md", file=sys.stderr)
            return 2
        cycle_ts = agents[-1].stem.replace("agent_", "")
    elif args.cycle_ts:
        cycle_ts = args.cycle_ts
    else:
        print("usage: on_crystallize.py <cycle_ts> | --latest [--out-suffix=_auto] [--force]", file=sys.stderr)
        return 2

    print(f"on_crystallize cycle_ts={cycle_ts}")

    agent_path = REPORTS / f"agent_{cycle_ts}.md"
    falsifier_path = FALSIFIER_DIR / f"falsifier_{cycle_ts}.json"
    if not agent_path.exists() or not falsifier_path.exists():
        print(f"ERROR: agent o falsifier mancante per {cycle_ts}", file=sys.stderr)
        return 2

    report = parse_agent_report(agent_path)
    falsifier = parse_falsifier(falsifier_path)
    valutatore = find_valutatore_decision(cycle_ts)
    print(f"  title: {report['title'][:90]}")
    print(f"  falsifier: {falsifier['verdict_label']}")
    print(f"  valutatore: {valutatore.get('decision') if valutatore else 'NONE'}/{valutatore.get('confidence') if valutatore else ''} (src: {valutatore.get('source') if valutatore else 'n/a'})")

    gate_status, msg = gate_check(falsifier, valutatore)
    print(f"  gate: [{gate_status}] {msg}")
    if gate_status == "invalid":
        return 2

    # Direttiva operatore 01/05: lab notturno deve SEMPRE produrre valore.
    # Anche refinement_required (valutatore non CRYSTALLIZE) produce scaffold,
    # ma con status pre_discovery — visibile sul sito con disclaimer forte
    # ("scoperta in elaborazione, non passa il valutatore"). Niente cycle muto.
    if gate_status == "mature_eligible":
        draft_status = "draft"
    elif gate_status == "transitional":
        draft_status = "transitional"
    else:  # refinement_required
        draft_status = "pre_discovery"

    slug = slugify(report["title"])
    predecessor = find_predecessor(cycle_ts)
    if predecessor:
        print(f"  predecessor: {predecessor['cycle_ts']} ({predecessor['dir_name']})")
    pred_yaml = ""
    if predecessor:
        rel_cr = Path(predecessor["cycle_report_path"]).relative_to(APPS_BASE.parent)
        pred_yaml = f"related_cycle_predecessor: {rel_cr}\n"
    ctx = {
        "cycle_ts": cycle_ts,
        "slug": slug,
        "report": report,
        "falsifier": falsifier,
        "seme_version": get_seme_version(),
        "report_path": str(agent_path),
        "predecessor": predecessor,
        "predecessor_yaml": pred_yaml,
        "draft_status": draft_status,
        "gate_status": gate_status,
        "valutatore_decision": valutatore.get("decision", "unknown") if valutatore else "no-entry",
        "valutatore_confidence": valutatore.get("confidence", "unknown") if valutatore else "no-entry",
    }

    out_dir = APPS_BASE / f"{cycle_ts}_{slug}{args.out_suffix}"
    out_dir.mkdir(parents=True, exist_ok=True)

    for fname, renderer in [
        ("lab-note.draft.md", render_lab_note_skeleton),
        ("cycle-report.draft.md", render_cycle_report_skeleton),
    ]:
        p = out_dir / fname
        if p.exists() and not args.force:
            print(f"  SKIP {p} (esiste, --force per sovrascrivere)")
            continue
        p.write_text(renderer(ctx))
        print(f"  WROTE {p}")

    print(f"DONE → {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
