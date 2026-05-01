#!/usr/bin/env python3
"""application_designer — Stage 2 SSP per scoperte PASS gate.

Replica di /opt/MM_D-ND/tools/triggers/application_designer.py con
risoluzione path domain-agnostic (LAB_DATA_DIR + DOMAIN).

Input: cycle_ts (deve aver passato gate strict via on_crystallize)
Reads: agent_<ts>.md (key findings) + scoperte/<ts>_<slug>_auto/cycle-report.draft.md
Output: LAB_DATA_DIR/<domain>/soluzioni/<ts>_<slug>/manifest.draft.json
        LAB_DATA_DIR/<domain>/soluzioni/<ts>_<slug>/summary.draft.md

Boundary:
  - Niente codice prodotto scritto.
  - Niente install claim, niente PASS-style copy.
  - Niente runtime touch (lab_agent.sh, seed.json).
  - Tutto marker [TARGET] / [TO BE VERIFIED].
  - L'output è un'idea applicativa proposta, non un prodotto verificato.

Filosofia:
  Per ora = scaffold-generator. Per ogni key finding propone N candidate
  applicazioni canonical-shape (library / kernel / demo / agent), ognuna
  marcata come "to be verified".
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime, timezone


def _resolve_paths(domain: str | None = None) -> dict[str, Path]:
    lab_data = Path(os.environ.get("LAB_DATA_DIR", "/opt/D-ND_LAB/data"))
    dom = domain or os.environ.get("DOMAIN", "physics")
    domain_dir = lab_data / dom
    return {
        "domain": dom,
        "lab_data": lab_data,
        "domain_dir": domain_dir,
        "reports": domain_dir / "reports",
        "scoperte": domain_dir / "scoperte",
        "soluzioni": domain_dir / "soluzioni",
    }


_PATHS = _resolve_paths()
REPORTS = _PATHS["reports"]
SCOPERTE = _PATHS["scoperte"]
SOLUZIONI = _PATHS["soluzioni"]


def slugify(text: str) -> str:
    t = text.lower()
    t = re.sub(r"[^\w\s-]", "", t)
    t = re.sub(r"[\s_]+", "-", t)
    t = re.sub(r"-+", "-", t).strip("-")
    return "-".join(t.split("-")[:6])


def find_scoperta_dir(cycle_ts: str) -> Path | None:
    if not SCOPERTE.exists():
        return None
    auto = list(SCOPERTE.glob(f"{cycle_ts}_*_auto"))
    if auto:
        return auto[0]
    manual = [d for d in SCOPERTE.glob(f"{cycle_ts}_*") if d.is_dir()]
    return manual[0] if manual else None


def parse_key_findings(report_text: str) -> list[dict]:
    m = re.search(r"##\s+Key [Ff]indings\s*\n(.+?)(?=\n##\s+|\Z)", report_text, re.S)
    if not m:
        return []
    block = m.group(1)
    findings = []
    for fm in re.finditer(r"^\s*(\d+)\.\s+(\*\*[^*]+\*\*[^\n]*(?:\n(?!\s*\d+\.\s).*)*)", block, re.M):
        idx = int(fm.group(1))
        body = fm.group(2).strip()
        title_m = re.match(r"\*\*([^*]+)\*\*", body)
        title = title_m.group(1).strip() if title_m else body[:80]
        findings.append({"idx": idx, "title": title, "body": body[:600]})
    return findings


def parse_consecutio(report_text: str) -> str | None:
    m = re.search(r"##\s+[Cc]onsecutio\s*\n(.+?)(?=\n##\s+|\Z)", report_text, re.S)
    return m.group(1).strip()[:600] if m else None


def parse_verdict(report_text: str) -> str | None:
    m = re.search(r"##\s+[Vv]erdict\s*\n(.+?)(?=\n##\s+|\Z)", report_text, re.S)
    return m.group(1).strip()[:400] if m else None


def make_verification_spec(candidate_type: str) -> dict:
    if candidate_type == "library":
        return {
            "status": "SPEC_ONLY",
            "verifier_form": "benchmark",
            "alternative_forms": ["unit_test", "reproduction"],
            "required_inputs": [
                "[TARGET] dataset di input ben definito",
                "[TARGET] baseline algorithm implementation (naive)",
                "[TARGET] informed agent implementation (rule-aware)",
            ],
            "success_criteria": [
                "[TARGET] correctness: output identical to ground-truth library",
                "[TARGET] performance: speedup_median > threshold da definire",
                "[TARGET] significance: wilcoxon_p < alpha da definire",
            ],
            "falsification_criteria": [
                "[TARGET] mismatch su ≥1 test case → invalida correctness",
                "[TARGET] speedup ≤ 1.0 → invalida claim di vantaggio",
                "[TARGET] regressione su edge case noto → invalida generalità",
            ],
            "expected_artifacts": [
                "[TARGET] verification.json con metrics reali",
                "[TARGET] benchmark log riproducibile",
                "[TARGET] tests/test_baseline.py + tests/test_correctness.py",
            ],
            "risks": [
                "[TARGET] vantaggio dipende dal range — dichiarare perimetro operativo",
                "[TARGET] cache effects possono mascherare il segnale",
            ],
        }
    if candidate_type == "kernel":
        return {
            "status": "SPEC_ONLY",
            "verifier_form": "human_review",
            "alternative_forms": ["dataset_comparison", "not_yet_verifiable"],
            "required_inputs": [
                "[TARGET] prompt template versionato",
                "[TARGET] task suite rappresentativo (input distribution)",
                "[TARGET] judge protocol (operatore o LLM judge separato)",
            ],
            "success_criteria": [
                "[TARGET] output quality misurata su rubric esplicita",
                "[TARGET] bias reduction vs naive prompt (a/b)",
                "[TARGET] reproducibility del modus su task non visti in training",
            ],
            "falsification_criteria": [
                "[TARGET] judge inter-rater agreement < soglia → metric non affidabile",
                "[TARGET] no improvement vs naive prompt → kernel non operativo",
            ],
            "expected_artifacts": [
                "[TARGET] kernel.template.md versionato",
                "[TARGET] benchmark_protocol.md",
                "[TARGET] judge_results.json con scores",
            ],
            "risks": [
                "[TARGET] kernel cognitivi richiedono metric non-computazionale",
                "[TARGET] judge bias se LLM judge stesso provider del kernel",
            ],
        }
    return {
        "status": "SPEC_ONLY",
        "verifier_form": "reproduction",
        "alternative_forms": ["human_review", "not_yet_verifiable"],
        "required_inputs": [
            "[TARGET] runtime ambiente (Pyodide / browser / notebook)",
            "[TARGET] dataset minimo per illustrare il pattern",
        ],
        "success_criteria": [
            "[TARGET] gira senza errori sul runtime target",
            "[TARGET] mostra il pattern del finding in modo intelligibile",
            "[TARGET] reproducible da chi clona il repo",
        ],
        "falsification_criteria": [
            "[TARGET] non gira → demo non publishabile",
            "[TARGET] mostra pattern diverso dal claim → demo fuorviante",
        ],
        "expected_artifacts": [
            "[TARGET] demo runnable file (es. demo.html / notebook.ipynb)",
            "[TARGET] README con istruzioni run",
        ],
        "risks": [
            "[TARGET] demo può ridurre il claim a illustrazione invece che a strumento",
            "[TARGET] runtime constraint può limitare ciò che si può mostrare",
        ],
    }


def propose_canonical_applications(finding: dict, cycle_ts: str) -> list[dict]:
    base_slug = slugify(finding["title"])
    title_short = finding["title"][:120]
    base_template = lambda ctype: {
        "discovery_finding_idx": finding["idx"],
        "discovery_finding_title": finding["title"],
        "feasibility": "[TARGET — to be assessed]",
        "verification_spec": make_verification_spec(ctype),
    }
    return [
        {
            **base_template("library"),
            "name": f"[TARGET] {base_slug}-lib",
            "type": "library",
            "what_it_does": f"[TARGET] Applicazione computazionale derivata dal finding: {title_short}",
            "what_it_skips": "[TARGET — to be verified]",
            "stack_proposed": "[TARGET — sistema decide caso per caso]",
        },
        {
            **base_template("kernel"),
            "name": f"[TARGET] {base_slug}-kernel",
            "type": "kernel",
            "what_it_does": f"[TARGET] Kernel cognitivo / prompt template derivato dal finding: {title_short}",
            "what_it_skips": "[TARGET — pattern operativo che riduce latenza in altri agenti]",
            "stack_proposed": "[TARGET — prompt template + harness LLM]",
        },
        {
            **base_template("demo"),
            "name": f"[TARGET] {base_slug}-demo",
            "type": "demo",
            "what_it_does": f"[TARGET] Visualizzazione interattiva del finding: {title_short}",
            "what_it_skips": "[TARGET — niente verifica empirica, scopo educational]",
            "stack_proposed": "[TARGET — Pyodide / HTML + JS / notebook]",
        },
    ]


def render_manifest_draft(cycle_ts: str, slug: str, findings: list[dict],
                          consecutio: str | None, verdict: str | None,
                          report_path: str, cycle_report_path: str | None,
                          eligibility_index: dict | None = None) -> dict:
    candidates = []
    non_application_findings = []
    review_required_findings = []

    if eligibility_index:
        eligibility_by_id = {f["finding_id"]: f for f in eligibility_index["findings"]}
        for f in findings:
            cls = eligibility_by_id.get(f["idx"])
            if cls is None:
                review_required_findings.append({
                    "finding_id": f["idx"],
                    "title": f["title"],
                    "reason": "missing from eligibility_index — anomalia",
                })
                continue
            if cls["application_eligible"] is True:
                candidates.extend(propose_canonical_applications(f, cycle_ts))
            elif cls["application_eligible"] == "REVIEW_REQUIRED":
                review_required_findings.append({
                    "finding_id": f["idx"],
                    "title": f["title"],
                    "role": cls["role"],
                    "reason": cls["skip_reason"],
                })
            else:
                non_application_findings.append({
                    "finding_id": f["idx"],
                    "title": f["title"],
                    "role": cls["role"],
                    "skip_reason": cls["skip_reason"],
                })
    else:
        for f in findings:
            candidates.extend(propose_canonical_applications(f, cycle_ts))

    return {
        "schema_version": "0.1",
        "stage": 2,
        "stage_name": "application_designer",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "application_designer.py",
        "discovery_provenance": {
            "cycle_ts": cycle_ts,
            "domain": _PATHS["domain"],
            "lab_instance": f"D-ND_LAB/{_PATHS['domain']}",
            "agent_report": report_path,
            "cycle_report": cycle_report_path,
            "eligibility_index": "finding_index.draft.json" if eligibility_index else None,
        },
        "discovery_summary": {
            "n_findings_total": len(findings),
            "n_findings_eligible": len(candidates) // 3 if candidates else 0,
            "n_findings_review_required": len(review_required_findings),
            "n_findings_skipped": len(non_application_findings),
            "verdict_excerpt": verdict,
            "consecutio_excerpt": consecutio,
        },
        "applications_candidate": candidates,
        "non_application_findings": non_application_findings,
        "review_required_findings": review_required_findings,
        "no_application_yet": len(candidates) == 0,
        "next_stage": "Stage 3 SPEC è già inline in ogni candidate.verification_spec (status SPEC_ONLY). Stage 4 = esecuzione manuale post-review.",
        "boundary": [
            "[TARGET] e [TO BE VERIFIED] ovunque finché Stage 4 non viene eseguito",
            "Niente codice scritto — solo design proposto + verification_spec",
            "verification_spec.status = SPEC_ONLY (come si verificherebbe, non verifica avvenuta)",
            "Niente install claim, niente PASS-style copy",
            "Niente runtime touch",
            "Pubblicazione live richiede operatore + TM1 review",
            "REVIEW_REQUIRED findings richiedono operatore prima di Stage 2 manuale",
        ],
    }


def render_summary_draft(cycle_ts: str, slug: str, manifest: dict) -> str:
    apps = manifest["applications_candidate"]
    summary = manifest["discovery_summary"]
    apps_lines = []
    for a in apps:
        apps_lines.append(f"- **{a['name']}** ({a['type']}) — finding #{a['discovery_finding_idx']} · verifier_form: `{a['verification_spec']['verifier_form']}`")
    apps_block = "\n".join(apps_lines) if apps_lines else "- (nessuna applicazione proposta — vedi sezioni sotto)"

    non_app_lines = []
    for naf in manifest.get("non_application_findings", []):
        non_app_lines.append(f"- finding #{naf['finding_id']} ({naf['role']}): {naf['title']}\n  - skip_reason: {naf['skip_reason']}")
    non_app_block = "\n".join(non_app_lines) if non_app_lines else "- (nessuno)"

    review_lines = []
    for rrf in manifest.get("review_required_findings", []):
        review_lines.append(f"- finding #{rrf['finding_id']}: {rrf['title']}\n  - reason: {rrf.get('reason') or rrf.get('skip_reason', '')}")
    review_block = "\n".join(review_lines) if review_lines else "- (nessuno)"

    domain = manifest["discovery_provenance"]["domain"]

    return f"""# Application Designer summary — {cycle_ts}

> Stage 2 SSP scaffold + Stage 3 SPEC inline. Niente codice, niente PASS.
> Tutti i candidati sono `[TARGET]` finché Stage 4 non viene eseguito manualmente.

## Provenance

- Discovery cycle: `{cycle_ts}`
- Domain: `{domain}`
- Lab instance: D-ND_LAB/{domain}
- Findings totali: {summary['n_findings_total']}
- Findings eligible: {summary['n_findings_eligible']}
- Findings review_required: {summary['n_findings_review_required']}
- Findings skipped (non-application): {summary['n_findings_skipped']}

## Applicazioni candidate proposte (canonical scaffold)

{apps_block}

## Findings che richiedono review prima di generare app

{review_block}

## Non-application findings (skipped da gate, non buttati via)

{non_app_block}

## Stage 3 (SPEC inline)

Ogni candidate include un `verification_spec` con:
- `verifier_form`: benchmark | unit_test | proof_check | reproduction | human_review | dataset_comparison | not_yet_verifiable
- `required_inputs` / `success_criteria` / `falsification_criteria` / `expected_artifacts` / `risks`
- `status: SPEC_ONLY` — come si verificherebbe, NON verifica avvenuta

## Stage 4 (non in questa pipeline)

Esecuzione manuale post-review operatore. Produce `verification.json` reale
(NON `verification.spec.json` — quello è solo design).

## Boundary

- Niente codice scritto in questa fase
- Niente claim PASS / verified / installable
- Niente publish, niente API, niente runtime touch
- Operator review prima di passare a Stage 4
- REVIEW_REQUIRED findings richiedono decisione operatore separata

---

*Auto-scaffold da `application_designer.py`. Sources:
`manifest.draft.json` + `finding_index.draft.json` (se gate eseguito).*
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cycle_ts")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--force-pre-discovery", action="store_true",
                    help="Genera manifest anche per scoperte transitional/pre_discovery (per testing/manual review)")
    ap.add_argument("--domain", default=None)
    args = ap.parse_args()

    if args.domain:
        global _PATHS, REPORTS, SCOPERTE, SOLUZIONI
        _PATHS = _resolve_paths(args.domain)
        REPORTS = _PATHS["reports"]
        SCOPERTE = _PATHS["scoperte"]
        SOLUZIONI = _PATHS["soluzioni"]

    cycle_ts = args.cycle_ts
    print(f"application_designer cycle_ts={cycle_ts} domain={_PATHS['domain']}")

    agent_path = REPORTS / f"agent_{cycle_ts}.md"
    if not agent_path.exists():
        print(f"ERROR: {agent_path} non esiste", file=sys.stderr)
        return 2

    scoperta_dir = find_scoperta_dir(cycle_ts)
    if not scoperta_dir:
        print(f"ERROR: nessuna scoperta dir per {cycle_ts} (eseguire prima on_crystallize)", file=sys.stderr)
        return 2

    cycle_report_path = scoperta_dir / "cycle-report.draft.md"
    print(f"  scoperta dir: {scoperta_dir.name}")

    # Skip se transitional/pre_discovery — claim non maturi
    # (sovrascrivibile con --force-pre-discovery per Stage 4 testing manuale)
    forced_pre_discovery = False
    if cycle_report_path.exists():
        cr_text = cycle_report_path.read_text()
        m = re.search(r"^status:\s*(\S+)", cr_text, re.M)
        scoperta_status = m.group(1).strip() if m else "draft"
        if scoperta_status in ("transitional", "pre_discovery"):
            if not args.force_pre_discovery:
                reason = ("high flag nel falsifier" if scoperta_status == "transitional"
                          else "valutatore non CRYSTALLIZE")
                print(f"  scoperta status={scoperta_status} → SKIP application_designer")
                print(f"  motivazione: {reason}; claim non affidabili per generare")
                print(f"               applicazioni. La scoperta è comunque pubblicata")
                print(f"               con visible_risks dichiarati e disclaimer.")
                print(f"               (--force-pre-discovery per generare comunque, marker presente)")
                return 0
            else:
                forced_pre_discovery = True
                print(f"  scoperta status={scoperta_status} → FORCED generation via --force-pre-discovery")
                print(f"               manifest sarà marcato force_generated_for_testing=true")

    report_text = agent_path.read_text()

    parts = scoperta_dir.name.split("_", 2)
    slug = parts[2].rstrip("_auto").rstrip("_") if len(parts) >= 3 else slugify(cycle_ts)
    if slug.endswith("_auto"):
        slug = slug[:-5]

    findings = parse_key_findings(report_text)
    consecutio = parse_consecutio(report_text)
    verdict = parse_verdict(report_text)

    print(f"  findings parsed: {len(findings)}")
    print(f"  consecutio: {'present' if consecutio else 'none'}")
    print(f"  verdict: {'present' if verdict else 'none'}")

    eligibility_path = SOLUZIONI / f"{cycle_ts}_{slug}" / "finding_index.draft.json"
    eligibility_index = None
    if eligibility_path.exists():
        try:
            eligibility_index = json.loads(eligibility_path.read_text())
            es = eligibility_index["summary"]
            print(f"  eligibility_index: eligible={es['n_application_eligible']} review={es['n_review_required']} skip={es['n_skipped']}")
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  WARN: eligibility_index unreadable ({e}) — fallback no-gate")
    else:
        print(f"  WARN: eligibility_index non trovato — esegui finding_eligibility_gate.py prima")

    if not findings:
        print(f"  WARN: nessun finding parsato")

    manifest = render_manifest_draft(
        cycle_ts, slug, findings, consecutio, verdict,
        str(agent_path),
        str(cycle_report_path) if cycle_report_path.exists() else None,
        eligibility_index=eligibility_index,
    )
    if forced_pre_discovery:
        manifest["force_generated_for_testing"] = True
        manifest["force_reason"] = f"Generated despite scoperta_status={scoperta_status} via --force-pre-discovery"
    summary = render_summary_draft(cycle_ts, slug, manifest)

    out_dir = SOLUZIONI / f"{cycle_ts}_{slug}"
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = out_dir / "manifest.draft.json"
    summary_path = out_dir / "summary.draft.md"

    for p, content in [(manifest_path, json.dumps(manifest, indent=2)), (summary_path, summary)]:
        if p.exists() and not args.force:
            print(f"  SKIP {p} (esiste, --force per sovrascrivere)")
            continue
        p.write_text(content)
        print(f"  WROTE {p}")

    print(f"DONE → {out_dir}")
    print(f"  candidate apps: {len(manifest['applications_candidate'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
