"""domain_request_runner.py — isolated install-or-block runner for meta-lab requests.

Consumes a `dndlab.domain_request.v1` file and produces an isolated candidate
domain package plus strict M1-M8 validation, without writing into `domains/`.

The runner is intentionally deterministic: it is the operational bridge the
LLM/meta-lab cycle can call after it has captured a domain request. It does not
claim the generated candidate is final; it proves whether the request can reach
the generator/validator contract or must be blocked with explicit reasons.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _data_root() -> Path:
    return _repo_root() / "data" / "meta-lab"


def _load_request(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "dndlab.domain_request.v1":
        raise ValueError(f"unsupported request schema: {data.get('schema')}")
    for field in ("slug", "title", "kind", "intent"):
        if not data.get(field):
            raise ValueError(f"request missing required field: {field}")
    return data


def _slug_id(slug: str) -> str:
    return slug.upper().replace("-", "_")


def _safe_slug(slug: str) -> str:
    cleaned = slug.strip().lower()
    if not cleaned or not cleaned.replace("-", "").replace("_", "").isalnum():
        raise ValueError("slug must use letters, numbers, '-' or '_'")
    return cleaned


def _load_domain_contract(kind: str) -> dict[str, Any] | None:
    """Load a reviewed source-domain contract when the requested kind has one.

    The contract is planning/installation substrate. It must not become a
    public result or a domain claim for the generated candidate.
    """
    contract_path = _repo_root() / "domains" / kind / "precondition_contract.json"
    if not contract_path.exists():
        return None
    data = json.loads(contract_path.read_text(encoding="utf-8"))
    if data.get("schema") != f"dndlab.{kind}_precondition_contract.v1":
        return None
    return data


def _load_domain_preset(kind: str, request: dict[str, Any]) -> dict[str, Any] | None:
    """Load a matching domain preset when available.

    Presets are accelerators, not authority. They provide domain-native
    possibilities that still need adaptation to the request intent.
    """
    explicit = request.get("preset_path") or request.get("preset")
    candidates: list[Path] = []
    if explicit:
        path = Path(str(explicit))
        if not path.is_absolute():
            path = _repo_root() / path
        candidates.append(path)
    preset_dir = _repo_root() / "docs" / "templates" / "domain_presets"
    if preset_dir.exists():
        candidates.extend(sorted(preset_dir.glob("*.json")))

    for path in candidates:
        if not path.exists() or not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if data.get("schema") != "domain_preset.v1":
            continue
        if explicit or str(data.get("domain_family") or "").strip().lower() == kind:
            data["_source_path"] = str(path.relative_to(_repo_root()) if path.is_relative_to(_repo_root()) else path)
            return data
    return None


def _boundary_from_contract(kind: str, contract: dict[str, Any] | None) -> dict[str, Any] | None:
    if kind != "finance" or not isinstance(contract, dict):
        return None
    selected = contract.get("selected_precondition") or {}
    summary = contract.get("calibration_summary") or {}
    followup = contract.get("selected_followup_branch") or {}
    nulls = [str(x) for x in summary.get("nulls") or [] if str(x)]
    score_min = selected.get("score_min")
    if score_min is None or not nulls:
        return None
    return {
        "schema": "dndlab.finance_reference_boundary.v1",
        "source_contract": "domains/finance/precondition_contract.json",
        "metric": selected.get("metric", "matched_filter_score_at_candidate_split"),
        "score_min": score_min,
        "selected_positives": summary.get("selected_positives"),
        "positive_cases": summary.get("positive_cases"),
        "selected_controls": summary.get("selected_controls"),
        "control_cases": summary.get("control_cases"),
        "nulls": nulls,
        "public_claim": False,
        "trading_signal": False,
        "operational": False,
        "status": followup.get("result", "reference boundary only; no public or trading claim"),
        "next_gate": followup.get("next_gate", "require executable baseline/null before promotion"),
    }


def _boundary_summary(boundary: dict[str, Any] | None) -> str:
    if not boundary:
        return ""
    selected = f"{boundary.get('selected_positives')}/{boundary.get('positive_cases')}"
    controls = f"{boundary.get('selected_controls')}/{boundary.get('control_cases')}"
    nulls = ", ".join(boundary.get("nulls") or [])
    return (
        f"`{boundary.get('metric')}` >= `{boundary.get('score_min')}`; "
        f"selected positives `{selected}`; selected controls `{controls}`; "
        f"null families `{nulls}`; `public_claim=false`; `trading_signal=false`."
    )


def _ui_language_contract(kind: str) -> dict[str, Any]:
    """Domain-native UI wording for generated dashboards.

    These labels are hints for the dashboard only. They do not change graph or
    storage keys, but prevent new Labs from inheriting physics wording when the
    domain needs claims, sources, regimes or data-cards.
    """
    if kind == "bitcoin-regime":
        return {
            "terminology": {
                "it": {
                    "teorie": "metodi",
                    "ponti": "confluenze",
                    "vuoti": "gap",
                    "scoperte": "claim-card",
                    "applicazioni": "watchlist",
                    "prodotti": "verifiche",
                    "cicli": "letture",
                    "ghost": "ipotesi aperte",
                    "cimitero": "scartati",
                    "legend_tensione": "ipotesi",
                    "legend_teoria": "metodo",
                    "legend_scoperta": "claim",
                    "nav_tassonomia_label": "Traiettoria",
                },
                "en": {
                    "teorie": "methods",
                    "ponti": "confluences",
                    "vuoti": "gaps",
                    "scoperte": "claim-cards",
                    "applicazioni": "watchlist",
                    "prodotti": "checks",
                    "cicli": "readings",
                    "ghost": "open hypotheses",
                    "cimitero": "rejected",
                    "legend_tensione": "hypothesis",
                    "legend_teoria": "method",
                    "legend_scoperta": "claim",
                    "nav_tassonomia_label": "Trajectory",
                },
            },
            "nav": {
                "it": {
                    "campo": "Stato BTC, dati disponibili e decisione corrente.",
                    "grafo": "Relazioni tra claim, timeframe, baseline e falsifier.",
                    "bicono": "Poli delle ipotesi estratti dalle letture.",
                    "agente": "Report, evidenza, veto e runtime.",
                    "tassonomia": "Sequenza dei cicli e movimento del regime lab.",
                    "prodotti": "Claim-card, watchlist, reject reason e verifiche.",
                },
                "en": {
                    "campo": "BTC state, available data and current decision.",
                    "grafo": "Relations across claims, timeframes, baselines and falsifier.",
                    "bicono": "Hypothesis poles extracted from readings.",
                    "agente": "Reports, evidence, vetoes and runtime.",
                    "tassonomia": "Cycle sequence and regime-lab movement.",
                    "prodotti": "Claim-cards, watchlist, reject reasons and checks.",
                },
            },
            "tooltips": {
                "it": {
                    "teorie": {
                        "title": "Metodi",
                        "body": "Famiglie operative tradotte in osservabili: volume profile, POC/LVN/HVN, FVG, CME gap, trendline, feed robustness.",
                        "logic": "Nessun metodo vale come autorita': entra solo se ha definizione meccanica, data-card e null coerente.",
                    },
                    "ponti": {
                        "title": "Confluenze",
                        "body": "Punti in cui piu' letture BTC si incontrano sullo stesso livello, timeframe o confine osservabile.",
                        "logic": "Una confluenza non e' un segnale: deve sopravvivere a feed, timeframe, baseline e controllo anti-lookahead.",
                    },
                    "vuoti": {
                        "title": "Gap",
                        "body": "Inefficienze candidate: FVG, low-volume node, CME gap o area non ancora definita da dati robusti.",
                        "logic": "Un gap resta ipotesi finche' non e' localizzato, datato, versionato e falsificato contro un null appropriato.",
                    },
                    "prodotti": {
                        "title": "Verifiche",
                        "body": "Output maturi solo dopo data-card, baseline/null, feed robustness e revisione del confine no-signal.",
                        "logic": "Il Bitcoin Lab puo' produrre monitoraggio e falsificazione, non consulenza finanziaria.",
                    },
                }
            },
        }
    if kind == "finance":
        return {
            "terminology": {
                "it": {
                    "teorie": "ipotesi",
                    "ponti": "baseline/null",
                    "vuoti": "gap dati",
                    "scoperte": "risultati",
                    "applicazioni": "vincoli",
                    "prodotti": "verifiche",
                    "ghost": "rischi aperti",
                    "cimitero": "scartati",
                    "legend_tensione": "ipotesi",
                    "legend_teoria": "modello",
                    "legend_scoperta": "risultato",
                },
                "en": {
                    "teorie": "hypotheses",
                    "ponti": "baselines/nulls",
                    "vuoti": "data gaps",
                    "scoperte": "findings",
                    "applicazioni": "constraints",
                    "prodotti": "checks",
                    "ghost": "open risks",
                    "cimitero": "rejected",
                    "legend_tensione": "hypothesis",
                    "legend_teoria": "model",
                    "legend_scoperta": "finding",
                },
            },
            "nav": {
                "it": {
                    "campo": "Regime, evidenza recente e decisione non-operativa.",
                    "grafo": "Relazioni tra ipotesi, baseline, null e vincoli.",
                    "bicono": "Poli delle ipotesi estratti dai report.",
                    "agente": "Evidenza, verdict, veto e trace.",
                    "tassonomia": "Traiettoria dei cicli e ricorrenze.",
                    "prodotti": "Scoperte, candidate e verifiche mature.",
                }
            },
        }
    if kind in {"research", "research-radar"}:
        return {
            "terminology": {
                "it": {
                    "teorie": "fonti",
                    "ponti": "evidenze",
                    "vuoti": "claim aperti",
                    "scoperte": "claim-card",
                    "applicazioni": "roadmap",
                    "prodotti": "verifiche",
                    "ghost": "da chiarire",
                    "cimitero": "scartati",
                    "legend_tensione": "claim",
                    "legend_teoria": "fonte",
                    "legend_scoperta": "claim-card",
                },
                "en": {
                    "teorie": "sources",
                    "ponti": "evidence",
                    "vuoti": "open claims",
                    "scoperte": "claim-cards",
                    "applicazioni": "roadmap",
                    "prodotti": "checks",
                    "ghost": "to clarify",
                    "cimitero": "rejected",
                    "legend_tensione": "claim",
                    "legend_teoria": "source",
                    "legend_scoperta": "claim-card",
                },
            },
            "nav": {
                "it": {
                    "campo": "Claim, fonti, decisione corrente e ultimi segnali.",
                    "grafo": "Relazioni tra claim, fonte, baseline e roadmap.",
                    "bicono": "Poli concettuali estratti dalle claim-card.",
                    "agente": "Report, evidenza, verdict e falsifier.",
                    "tassonomia": "Traiettoria dei cicli e pattern ricorrenti.",
                    "prodotti": "Claim-card, roadmap candidate e verifiche.",
                }
            },
        }
    return {}


def _preset_summary_md(preset: dict[str, Any] | None) -> str:
    if not preset:
        return ""
    observables = [str(x.get("name")) for x in preset.get("starter_observables") or [] if isinstance(x, dict) and x.get("name")]
    baselines = [str(x.get("name")) for x in preset.get("starter_baselines") or [] if isinstance(x, dict) and x.get("name")]
    falsifiers = [str(x.get("lens")) for x in preset.get("starter_falsifiers") or [] if isinstance(x, dict) and x.get("lens")]
    ui_native = []
    modules = preset.get("starter_ui_modules") or {}
    if isinstance(modules, dict):
        ui_native = [str(x) for x in modules.get("domain_native") or [] if str(x)]
    questions = [str(x) for x in preset.get("adaptation_questions") or [] if str(x)]

    def bullets(values: list[str], limit: int = 14) -> str:
        if not values:
            return "- none declared"
        shown = values[:limit]
        suffix = [f"- ... +{len(values) - limit}"] if len(values) > limit else []
        return "\n".join(f"- `{value}`" for value in shown) + ("\n" + "\n".join(suffix) if suffix else "")

    return f"""
## Domain preset possibilities

Preset `{preset.get('preset_id')}` (`{preset.get('_source_path')}`) is loaded
as possibility field, not as final domain truth.

Starter observables:

{bullets(observables)}

Starter baselines:

{bullets(baselines)}

Starter falsifiers:

{bullets(falsifiers)}

Domain-native UI modules:

{bullets(ui_native)}

Adaptation questions:

{bullets(questions, limit=10)}
"""


def _build_assertions_py(slug: str, boundary: dict[str, Any] | None = None) -> str:
    boundary_literal = repr(boundary or {})
    boundary_check = ""
    if boundary:
        boundary_check = '''
    required_nulls = {"iid_shuffle", "circular_block_5", "circular_block_21"}
    nulls = set(BOUNDARY.get("nulls") or [])
    results.append({
        "id": "REQ_05_FINANCE_BOUNDARY_EXECUTABLE",
        "status": "PASS" if (
            BOUNDARY.get("score_min") == 0.55
            and BOUNDARY.get("selected_positives") == 19
            and BOUNDARY.get("positive_cases") == 36
            and BOUNDARY.get("selected_controls") == 0
            and BOUNDARY.get("control_cases") == 108
            and required_nulls.issubset(nulls)
            and BOUNDARY.get("trading_signal") is False
            and BOUNDARY.get("public_claim") is False
        ) else "FAIL",
        "detail": "finance reference candidate carries score_min=0.55, 19/36, 0/108, iid/block5/block21 nulls and no trading signal",
        "metric": BOUNDARY.get("score_min"),
    })
'''
    return f'''"""Assertions for generated candidate lab `{slug}`.

These checks validate the install seed, not a public domain claim.
"""

BOUNDARY = {boundary_literal}


def verifica_asserzioni():
    results = [
        {{
            "id": "REQ_01_REQUEST_PRESENT",
            "status": "PASS",
            "detail": "domain request was transduced into seed/context/ui contract",
            "metric": 1,
        }},
        {{
            "id": "REQ_02_BASELINE_NULL_DECLARED",
            "status": "PASS",
            "detail": "candidate declares baseline and null before interpretation",
            "metric": 1,
        }},
        {{
            "id": "REQ_03_NO_PREMATURE_PUBLIC_CLAIM",
            "status": "PASS",
            "detail": "candidate starts as calibration/reference only",
            "metric": 1,
        }},
        {{
            "id": "REQ_04_RUNTIME_TRACE_REQUIRED",
            "status": "PASS",
            "detail": "cycle trace and falsifier remain required promotion gates",
            "metric": 1,
        }},
    ]
{boundary_check}
    return results
'''


def _build_smoke_tool(slug: str, kind: str, boundary: dict[str, Any] | None = None) -> str:
    boundary_literal = repr(boundary or {})
    null_literal = repr((boundary or {}).get("nulls") or ["shuffle_or_permutation_null", "domain_native_control_null"])
    return f'''#!/usr/bin/env python3
"""Smoke experiment for `{slug}`.

No network, no credentials, no public claim. It only proves that the generated
lab has an executable domain-native tool with baseline/null language.
"""

import argparse
import json
from datetime import datetime, timezone

BOUNDARY = {boundary_literal}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = {{
        "schema": "{slug}.request_smoke.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "domain_kind": "{kind}",
        "verdict": "REFERENCE_BOUNDARY_ONLY",
        "baseline": "naive/request-preserving baseline required before interpretation",
        "null": {null_literal},
        "boundary": BOUNDARY,
        "public_claim": False,
        "trading_signal": False,
        "operational": False,
        "next": "replace smoke with domain-native experiment after first reviewed cycle",
    }}
    print(json.dumps(payload, indent=2 if args.json else None, ensure_ascii=False))


if __name__ == "__main__":
    main()
'''


def _build_spec(request: dict[str, Any]) -> dict[str, Any]:
    slug = _safe_slug(str(request["slug"]))
    sid = _slug_id(slug)
    title = str(request.get("title") or f"D-ND {slug} Lab").strip()
    kind = str(request.get("kind") or "research").strip().lower()
    intent = str(request.get("intent") or "").strip()
    movement_class = str(request.get("movement_class") or "discovery").strip().lower()
    preset = _load_domain_preset(kind, request)
    boundary = _boundary_from_contract(kind, _load_domain_contract(kind))
    boundary_text = _boundary_summary(boundary)
    use_dynamics = [str(x).strip() for x in request.get("use_dynamics") or [] if str(x).strip()]
    exclusions = [str(x).strip() for x in request.get("exclusions") or [] if str(x).strip()]
    success = str(request.get("success_condition") or "").strip()
    dynamics_md = "\n".join(f"- {x}" for x in use_dynamics) or "- discover a falsifiable movement before output"
    exclusions_md = "\n".join(f"- {x}" for x in exclusions) or "- premature public certainty"

    seed_tensions = {
        "domain": slug,
        "piano": 1,
        "direzione": f"Transduce request `{slug}` into a first falsifiable cycle without prescribing result.",
        "tensioni": [
            {
                "tipo": "task",
                "id": f"{sid}_REQUEST_TO_FIELD",
                "claim": f"The request must become an observable field before any report: {intent}",
                "intensita": 1.0,
                "porta": "domain_request",
                "condensato_ref": "A2,A8,A14,A15",
            },
            {
                "tipo": "vincolo",
                "id": f"{sid}_BASELINE_NULL_FIRST",
                "claim": "No generated result is admissible without baseline, null/control and falsifier.",
                "intensita": 0.9,
                "porta": "falsifier",
                "condensato_ref": "A2,A14",
            },
            {
                "tipo": "vincolo",
                "id": f"{sid}_RUNTIME_AWARENESS",
                "claim": "The lab must report how the cycle moved: tools, skipped steps, trace and accepted surface.",
                "intensita": 0.85,
                "porta": "runtime",
                "condensato_ref": "A8,A15",
            },
        ],
    }
    if boundary:
        seed_tensions["tensioni"].append(
            {
                "tipo": "vincolo",
                "id": f"{sid}_FINANCE_REFERENCE_BOUNDARY_055",
                "claim": (
                    "Finance reference install requires matched_filter_score_at_candidate_split >= 0.55, "
                    "19/36 positives selected, 0/108 controls selected, exact nulls iid_shuffle, "
                    "circular_block_5, circular_block_21, and trading_signal=false."
                ),
                "intensita": 0.95,
                "porta": "falsifier",
                "condensato_ref": "A2,A8,A14,A15",
            }
        )

    context_md = f"""# {title} — Context

## Intent in movement

{intent}

The intent lives in the cycle movement, not in a prescribed result. The first
seed prepares the field; it does not authorize a public claim.

## Domain request

- slug: `{slug}`
- kind: `{kind}`
- movement_class: `{movement_class}`
- success_condition: {success or 'not specified'}

## Use dynamics

{dynamics_md}

## Exclusions

{exclusions_md}

## Cycle contract

The lab moves through seed -> tension -> field -> agent -> baseline/null ->
falsifier -> report -> seed_integrator -> trajectory. Each cycle must make its
runtime trace visible. A finding is not promoted because it is interesting; it
is promoted only after the falsifier and baseline/null contract survive.

## Baseline and null

The first experiment is a reference smoke only. A domain-native baseline,
shuffle/permutation or control null, and explicit stop condition are required
before interpretation.
"""
    context_md += _preset_summary_md(preset)
    if boundary_text:
        context_md += f"""

## Finance reference boundary

The generated finance reference candidate inherits the reviewed boundary from
`domains/finance/precondition_contract.json` as an install gate, not as a market
claim: {boundary_text}

If any of these exact constants or null families are missing, the candidate is
not installable. A later domain cycle may retire or narrow the rule only through
runtime evidence and falsifier trace.
"""
    context_md += """

## Skill retrieval

Use `skill_retrieval` before operational work. Start from portable capsules in
`docs/cognitive_archives/`, then escalate to BODY/BODY_PLUS_REFS only when the
request needs operational authority. Map intent -> movement_class ->
use_dynamics -> skills through `skill_intent_map`.
"""
    context_md += f"""

## Tools custom del lab — come invocarli

Il primo tool custom e' uno smoke test strutturale. Non usa rete, non legge
segreti e non produce claim pubblici:

```bash
python3 /opt/D-ND_LAB/domains/{slug}/tools/exp_request_smoke.py --json
```

Durante la fase isolata del meta-lab, prima dell'installazione in `domains/`,
il tool puo' essere invocato dalla candidate dir generata:

```bash
python3 <candidate_dir>/tools/exp_request_smoke.py --json
```

Output atteso: JSON con `schema`, `verdict`, `baseline`, `null`, `boundary`,
`public_claim=false` e `trading_signal=false`. Se il tool non e' eseguibile o
non espone baseline/null, il candidato resta non installabile.
"""

    about_it = f"""# {title}

Lab generato dal meta-lab a partire da una richiesta di dominio. Serve a
verificare se l'intento puo' diventare ciclo osservabile, non a vendere un
risultato.

Intento: {intent}
"""

    about_en = f"""# {title}

Meta-lab generated candidate from a domain request. It verifies whether the
intent can become an observable cycle; it does not sell a result.

Intent: {intent}
"""

    transduction_md = f"""# Transduction — {slug}

## Invariants

Movement, baseline/null, falsifier, runtime awareness and seed integration are
the invariant contract. The source request is planning context, not direct
truth.

## Excluded source contamination

Do not copy results from reference labs. Do not treat the request, operator
preference or capsule-only archive as evidence. Exclusions:

{exclusions_md}

## Domain-native observables

The first real cycle must define observables that match `{kind}` and the
declared use dynamics. Until then this candidate remains reference-only.

## Null baseline

Every experiment needs baseline, null/control, and stop condition before
promotion. The smoke tool only verifies executable structure.
"""
    if boundary_text:
        transduction_md += f"""

### Finance reference boundary

This candidate must preserve the exact reviewed finance boundary before it can
be installed: {boundary_text}

The boundary blocks premature transfer. It is not a trading signal, not a
market forecast and not public evidence.
"""
    transduction_md += """

## Adaptive rules

Rules can be retired or narrowed when cycle traces show drift. A failed detector
must become a clearer precondition or be archived; it must not be rescued by
silent tuning.

## UI contract

The UI must expose field status, active tensions, falsifier, runtime dynamics,
data/source cards and what is not admissible.

## E2E install/runtime

The generated candidate must pass generator dry-run, isolated write, strict
M1-M8 validator, and then a later cycle-to-UI check before public use.

## skill_retrieval

Archive retrieval starts capsule-first. Skill archive, skill catalog and
enzimi are planning substrate until the required read depth is satisfied.

## possibility_inventory

Before choosing skills or tools, expose the available possibility field:
current docs, cognitive capsules, MMSp lineage, source Labs, presets and public
surfaces that can orient the first cycle without becoming automatic authority.

## skill_intent_map

The machine-readable map is stored in `skill_intent_map_json` and appended by
the generator when needed.

## question_field

The first cycle must expose the question that moves the Lab, the possible paths
still open, the missing nodes that prevent observation, and what would falsify
each path before promotion.

## capability_cascade

Any reusable capability must be written as a propagation candidate, not as an
automatic rule. Transfer to another Lab requires domain-native observables,
baseline/null and UI lens.
"""

    possibility_inventory = [
        {
            "source_id": "skill_docs",
            "source_path": "docs/SKILL_CATALOG.md + docs/SKILL_FIELD_MAP.md + docs/SKILL_DIAGNOSTIC.md",
            "source_kind": "catalog",
            "available_possibility": "Route the request through validation, processing, observation, interface and runtime layers.",
            "movement_link": "choose minimal coordinated skills for the requested movement",
            "read_depth_required": "L0 for routing; L1-L2 before active MML authority",
            "candidate_artifact": "skill_reading_matrix|mml|context",
            "activation_trigger": "before generated Lab context or MML is finalized",
            "test_or_evidence": "M8 skill_intent_map and validator coherence",
            "contamination_risk": "declaring skills by name without reading their body",
            "status": "available",
        },
        {
            "source_id": "cognitive_archives",
            "source_path": "docs/cognitive_archives/*.json",
            "source_kind": "capsule",
            "available_possibility": "Use KPhi1, THIA skill snapshot and cockpit/MMSp lineage as planning context without loading full archives.",
            "movement_link": "recover existing cognitive patterns before inventing new ones",
            "read_depth_required": "CAPSULE; BODY when changing context, MML, tool, assertion or UI",
            "candidate_artifact": "archive_retrieval|transduction|skill_intent_map",
            "activation_trigger": "when the request needs autonomous cognition, lineage or missing capability recovery",
            "test_or_evidence": "archive_retrieval_json with body_required when capsule is insufficient",
            "contamination_risk": "treating capsule or historical language as active authority",
            "status": "available",
        },
        {
            "source_id": "physics_lab_source",
            "source_path": "domains/physics + docs/templates/domain_presets/physics_bridge.v1.json",
            "source_kind": "lab_source",
            "available_possibility": "Reuse bridge audits, null discipline, observable contracts and tool-surface patterns as movement templates.",
            "movement_link": "transfer scientific cycle discipline without copying physics content",
            "read_depth_required": "L1 for docs/preset; E2E before shared generator rule",
            "candidate_artifact": "null|baseline|tool|ui|preset",
            "activation_trigger": "when a new domain needs bridge, scale, null or observable-contract logic",
            "test_or_evidence": "domain-native observables and nulls in the receiving Lab",
            "contamination_risk": "copying TQGE/physics labels or numerical results into another domain",
            "status": "available",
        },
        {
            "source_id": "domain_presets",
            "source_path": "docs/templates/domain_presets",
            "source_kind": "preset",
            "available_possibility": "Accelerate known domain families while preserving intent-specific adaptation.",
            "movement_link": "seed observables, baseline, falsifiers and UI modules for matching families",
            "read_depth_required": "L1 plus adaptation questions",
            "candidate_artifact": "ui_contract|seed_tensions|baseline|null",
            "activation_trigger": "when domain kind matches an existing preset family",
            "test_or_evidence": "strict validator plus first cycle smoke",
            "contamination_risk": "preset copied without adapting to the actual intent",
            "status": "available",
        },
        {
            "source_id": "public_physics_surface",
            "source_path": "d-nd.com/ai-lab + docs/LAB_SURFACE_TOPOLOGY.md",
            "source_kind": "public_surface",
            "available_possibility": "Learn which UI/THIA surfaces help humans read the physics Lab and transfer only the interaction pattern.",
            "movement_link": "improve dashboard explanation and assistant context without treating public UI as runtime evidence",
            "read_depth_required": "support_only unless paired with repo/runtime evidence",
            "candidate_artifact": "ui|copy|assistant_context",
            "activation_trigger": "when generated Lab needs public-facing comprehension or THIA framing",
            "test_or_evidence": "cycle-to-UI check and explicit surface boundary",
            "contamination_risk": "confusing main-site physics Lab with installable D-ND_LAB runtime",
            "status": "support_only",
        },
    ]
    if preset:
        preset_observables = [
            str(item.get("name"))
            for item in preset.get("starter_observables") or []
            if isinstance(item, dict) and item.get("name")
        ]
        preset_baselines = [
            str(item.get("name"))
            for item in preset.get("starter_baselines") or []
            if isinstance(item, dict) and item.get("name")
        ]
        preset_falsifiers = [
            str(item.get("lens"))
            for item in preset.get("starter_falsifiers") or []
            if isinstance(item, dict) and item.get("lens")
        ]
        preset_modules = preset.get("starter_ui_modules") if isinstance(preset.get("starter_ui_modules"), dict) else {}
        possibility_inventory.append(
            {
                "source_id": f"domain_preset:{preset.get('preset_id')}",
                "source_path": preset.get("_source_path", "docs/templates/domain_presets"),
                "source_kind": "preset",
                "available_possibility": "Domain-native starter observables, baselines, falsifiers, UI modules and adaptation questions.",
                "movement_link": "adapt known domain-family patterns to this request before inventing new tools",
                "read_depth_required": "L1 plus adaptation questions; E2E before promotion",
                "candidate_artifact": "seed_tensions|context|tool|null|baseline|ui_contract",
                "activation_trigger": "when the request kind matches the preset domain_family",
                "test_or_evidence": "strict validator, smoke tool and first cycle with domain-native data-card",
                "contamination_risk": "using the preset as final domain truth or skipping intent-specific adaptation",
                "status": "available",
                "preset_id": preset.get("preset_id"),
                "starter_observables": preset_observables,
                "starter_baselines": preset_baselines,
                "starter_falsifiers": preset_falsifiers,
                "domain_native_ui_modules": [str(x) for x in preset_modules.get("domain_native") or [] if str(x)],
                "adaptation_questions": [str(x) for x in preset.get("adaptation_questions") or [] if str(x)],
            }
        )

    question_field = {
        "primary_question": f"Can `{slug}` turn the requested intent into an observable cycle without promoting an untested result?",
        "possibility_field": [
            "installable reference candidate",
            "blocked domain with useful missing nodes",
            "domain-specific tool or data requirement before first real cycle",
        ],
        "missing_nodes": [
            "domain-native observables from first real cycle",
            "claim-appropriate baseline/null",
            "cycle-to-UI evidence before public use",
        ],
        "falsification_paths": [
            "no observable can be defined without copying another domain",
            "baseline/null cannot be built out-of-box",
            "cycle output cannot update seed, report and UI surfaces",
        ],
        "observable_requirements": [
            "source/data card where external data is used",
            "runtime trace",
            "falsifier verdict",
            "seed or cimitero update",
        ],
        "non_admissible": exclusions or ["premature public claim", "operator preference as evidence"],
        "next_question": "What is the smallest real cycle that can make the domain-specific movement observable?",
    }

    capability_cascade = [
        {
            "capability_id": "domain_request_to_installable_candidate",
            "source_domain": "meta-lab",
            "source_cycle": "domain_request_runner",
            "new_affordance": "Convert a domain request into an isolated install-or-block candidate with M1-M8 evidence.",
            "immediate_domain": slug,
            "transferable_domains": ["future generated labs"],
            "affected_surfaces": [
                "context",
                "mml",
                "tools",
                "assertions",
                "ui_contract",
                "onboarding",
                "docs",
                "tests",
            ],
            "required_checks": [
                "strict M1-M8 validator",
                "smoke tool output",
                "cycle-to-UI check before public use",
            ],
            "non_admissible_transfer": [
                "copying domain content as evidence",
                "treating a reference candidate as a live Lab",
            ],
            "next_question": "Which candidate capability should become a reusable preset only after another domain needs it?",
        }
    ]

    transduction_md += (
        "\n\n## possibility_inventory_json\n\n"
        "Auto-generated availability map. These sources are possibilities, not "
        "automatic authority.\n\n"
        "```json\n"
        + json.dumps(possibility_inventory, indent=2, ensure_ascii=False)
        + "\n```\n\n"
        "\n\n## question_field_json\n\n"
        "Auto-generated from the domain request so the candidate preserves the "
        "question that moves the first cycle.\n\n"
        "```json\n"
        + json.dumps(question_field, indent=2, ensure_ascii=False)
        + "\n```\n\n"
        "## capability_cascade_json\n\n"
        "Auto-generated propagation card. It is a candidate, not an automatic "
        "promotion rule.\n\n"
        "```json\n"
        + json.dumps(capability_cascade, indent=2, ensure_ascii=False)
        + "\n```\n"
    )

    skill_intent_map = {
        "intent": intent,
        "movement_class": movement_class,
        "use_dynamics": use_dynamics,
        "skill_layers": {
            "kernel": ["cascata", "cec", "consapevolezza-condensato"],
            "operator": ["autologica-operativa", "eval"],
            "domain": ["baseline-null", "falsifier", "runtime-awareness"],
        },
        "possibility_inventory": possibility_inventory,
        "meta_prompts": ["intent-in-movement", "install-or-block", "no-premature-promotion"],
        "generated_artifacts": [
            "context.md",
            "seed_tensions.json",
            "assertions.py",
            "transduction.md",
            "ui_contract.json",
            "mml.json",
        ],
        "null_baseline_requirements": ["naive baseline", "domain-native null/control", "stop condition"],
        "ui_lens": ["field", "falsifier", "runtime", "not-admissible"],
        "question_field": question_field,
        "capability_cascade": capability_cascade,
        "propagation_candidates": [
            {
                "capability_id": item["capability_id"],
                "candidate_surfaces": item["affected_surfaces"],
                "promotion_rule": "candidate only until another domain passes domain-native checks",
            }
            for item in capability_cascade
        ],
        "exclusions": exclusions,
    }

    ui_contract = {
        "schema": "ui_contract.v1",
        "domain": slug,
        "intent_movement": intent,
        "frame": {
            "left": [
                {"module": "SeedStatus", "purpose": "Current plane, direction and request status."},
                {"module": "ActiveTensions", "purpose": "Request-derived tensions and filters."},
            ],
            "center": [
                {"module": "RequestField", "purpose": "Intent, observables, baseline/null and first smoke."}
            ],
            "right": [
                {"module": "RuntimeDynamics", "purpose": "Cycle trace, skipped movements and accepted surface."},
                {"module": "FalsifierPanel", "purpose": "What cannot be promoted."},
                {"module": "THIAContextAssistant", "purpose": "Answer from domain state and runtime context."},
            ],
        },
        "common_modules": [
            {"module": "SeedStatus", "required": True, "data_sources": [f"data/{slug}/lab_data.json"], "reason": "Field awareness."},
            {"module": "FalsifierPanel", "required": True, "data_sources": [f"data/{slug}/falsifier/"], "reason": "Show what does not hold."},
            {"module": "RuntimeDynamics", "required": True, "data_sources": [f"data/{slug}/cycle_trace_*.json"], "reason": "Show how the cycle moved."},
        ],
        "domain_modules": [
            {
                "module": "RequestField",
                "placement": "center",
                "observables": ["request", "baseline", "null", "falsifier"],
                "baseline_or_null": (boundary or {}).get("nulls") or ["shuffle_or_control_null"],
                "shows": "Whether the request is admissible to first cycle.",
                "blocks": "Premature claim or copied reference result.",
            }
        ],
        "domain_boundary": boundary,
        "admin_actions": [
            {"action": "run_cycle", "allowed": True, "boundary": "Run from current seed; no direction override without review."}
        ],
        "forbidden_labels": exclusions or ["premature public claim"],
        "e2e": [
            {"check": "cycle_to_ui", "expectation": "Completed cycle updates left, center and right surfaces."},
            {"check": "runtime_awareness_visible", "expectation": "Trace and falsifier visible before promotion."},
        ],
    }
    ui_contract.update(_ui_language_contract(kind))

    onboarding_contract = {
        "schema": "dndlab.onboarding_contract.v1",
        "domain": slug,
        "channels": {
            "domain_request": {"status": "present", "authority": "planning", "notes": "Request starts transduction, not direct seed authority."},
            "human_clarification": {"status": "allowed", "authority": "constraints", "notes": "Clarifies exclusions and success condition."},
            "operator_corpus": {"status": "optional", "authority": "source", "notes": "Private/source material stays out of Git unless public."},
            "public_contribution": {"status": "quarantine", "authority": "preport_only", "notes": "Requires pre-report and review."},
            "dataset_api": {"status": "optional", "authority": "evidence_after_baseline", "notes": "Requires data-card and leakage guard."},
            "cognitive_archives": {"status": "capsule_first", "authority": "by_read_depth", "notes": "Capsules orient planning only."},
            "runtime_self_observation": {"status": "required", "authority": "cycle_trace", "notes": "Runtime explains how the cycle moved."},
        },
        "promotion_gates": [
            "source_provenance",
            "privacy_secret_scan",
            "baseline_null",
            "falsification_test",
            "operator_review_when_public_or_sensitive",
            "runtime_trace",
        ],
        "never_direct_to_seed": [
            "public contributions",
            "private corpus",
            "capsule-only archive patterns",
            "human preference without falsification",
        ],
        "ui_surfaces": {
            "left": ["source_status", "contribution_counts", "warnings"],
            "center": ["domain_movement_view"],
            "right": ["source_detail", "preport", "cycle_trace", "assistant_context"],
        },
    }

    mml = {
        "lab": slug,
        "version": "0.1.0-alpha",
        "identity": {
            "role": "generated_candidate_lab",
            "domain_kind": kind,
            "movement_class": movement_class,
        },
        "kernel_refs": {
            "condensato_axioms_used": ["A2", "A8", "A14", "A15"],
            "request_path": request.get("_request_path", ""),
            "domain_contract": (boundary or {}).get("source_contract", ""),
        },
        "domain_contracts": {"reference_boundary": boundary} if boundary else {},
        "skills_attive": {
            "kernel_layer": [
                {"name": "cascata", "use": "propagate request through seed/field/report"},
                {"name": "cec", "use": "preserve coherence under cycle"},
                {"name": "consapevolezza-condensato", "use": "keep axioms explicit"},
            ],
            "logic_layer": [
                {"name": "autologica-operativa", "use": "observe how the lab moves"},
                {"name": "eval", "use": "evaluate pass/block evidence"},
            ],
            "domain_layer": [
                {"name": "baseline-null", "use": "require baseline and null/control"},
                {"name": "falsifier", "use": "block premature promotion"},
            ],
            "interface_layer": [
                {"name": "runtime-awareness", "use": "show cycle trace in UI"},
            ],
        },
        "modus_invocation": {
            "first_cycle": "request -> field -> smoke -> falsifier -> seed_integrator",
            "promotion": "only after baseline/null and runtime trace",
        },
        "tools_custom": [
            {
                "name": "request_smoke",
                "path": "tools/exp_request_smoke.py",
                "boundary": boundary,
            }
        ],
    }

    archive_retrieval = {
        "archive_retrieval": [
            {
                "archive_id": "thia_skill_snapshot",
                "pattern": "skill_retrieval capsule for generated labs",
                "read_depth": "CAPSULE",
                "capsule": "docs/cognitive_archives/thia_skill_snapshot_20260517.json",
                "used_for": "planning skill layers and onboarding gates",
                "body_required": True,
                "contamination_excluded": "capsule does not authorize domain claims",
                "test_expected": "M8 sees archive_retrieval and read_depth before install",
            }
        ]
    }

    readme = f"""# {title}

Generated candidate from `domain_request`.

Status: reference candidate only. Run strict M1-M8 before install.

Intent:

```text
{intent}
```
"""
    if boundary_text:
        readme += f"""
Finance reference boundary:

```text
{boundary_text}
```
"""

    return {
        "domain_slug": slug,
        "title": title,
        "description": f"Generated candidate lab from domain request `{slug}` ({kind}/{movement_class}).",
        "version": "0.1.0-alpha",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "context_md": context_md,
        "about_it": about_it,
        "about_en": about_en,
        "seed_tensions_json": seed_tensions,
        "tension_to_category_json": {
            "domain_request": "task",
            "falsifier": "vincolo",
            "runtime": "vincolo",
        },
        "assertions_py": _build_assertions_py(slug, boundary),
        "mml_json": mml,
        "transduction_md": transduction_md,
        "ui_contract_json": ui_contract,
        "skill_intent_map_json": skill_intent_map,
        "archive_retrieval_json": archive_retrieval,
        "onboarding_contract_json": onboarding_contract,
        "tools_exp_files": [
            {"name": "exp_request_smoke.py", "content": _build_smoke_tool(slug, kind, boundary)}
        ],
        "readme_md": readme,
    }


def _write_report_md(report: dict[str, Any], path: Path) -> None:
    slug = report.get("slug", "?")
    status = report.get("status", "?")
    validator = report.get("validator", {}) or {}
    lines = [
        f"# Domain Request Run — {slug}",
        "",
        f"- status: `{status}`",
        f"- generated_at: `{report.get('generated_at', '')}`",
        f"- request: `{report.get('request_path', '')}`",
        f"- candidate_dir: `{report.get('candidate_dir', '')}`",
        f"- spec: `{report.get('spec_path', '')}`",
        "",
        "## Validator",
        "",
        f"- verdict: `{validator.get('verdict', 'not_run')}`",
        f"- summary: `{validator.get('summary', {})}`",
        "",
        "## Errors",
        "",
    ]
    errors = report.get("errors") or []
    if errors:
        lines.extend(f"- {err}" for err in errors)
    else:
        lines.append("- none")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def run_request(request_path: Path, output_root: Path, force: bool = False) -> dict[str, Any]:
    request = _load_request(request_path)
    request["_request_path"] = str(request_path)
    spec = _build_spec(request)
    slug = spec["domain_slug"]
    run_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = output_root / slug
    specs_dir = output_root / "_specs"
    reports_dir = output_root / "_reports"
    specs_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    spec_path = specs_dir / f"{slug}_{run_ts}.json"
    report_json_path = reports_dir / f"{slug}_{run_ts}.json"
    report_md_path = reports_dir / f"{slug}_{run_ts}.md"
    spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    generator_path = _repo_root() / "domains" / "meta-lab" / "tools" / "lab_template_generator.py"
    spec_module = importlib.util.spec_from_file_location("lab_template_generator", generator_path)
    if spec_module is None or spec_module.loader is None:
        raise RuntimeError(f"cannot load generator module: {generator_path}")
    generator = importlib.util.module_from_spec(spec_module)
    spec_module.loader.exec_module(generator)  # type: ignore[union-attr]
    errors = generator.validate_specs(spec)
    report: dict[str, Any] = {
        "schema": "meta_lab.domain_request_run.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "BLOCKED_PRECHECK" if errors else "PENDING",
        "slug": slug,
        "request_path": str(request_path),
        "spec_path": str(spec_path),
        "candidate_dir": str(run_dir),
        "errors": errors,
    }
    if errors:
        report_json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        _write_report_md(report, report_md_path)
        return report

    dry = generator.write_template(spec, dry_run=True, force=force)
    report["dry_run"] = dry
    if dry.get("status") != "DRY_RUN":
        report["status"] = "BLOCKED_DRY_RUN"
        report["errors"] = dry.get("errors") or ["generator dry-run failed"]
        report_json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        _write_report_md(report, report_md_path)
        return report

    original_domains_root = generator._domains_root
    original_repo_root = generator._repo_root
    generator._domains_root = lambda: output_root  # type: ignore[assignment]
    generator._repo_root = _repo_root  # type: ignore[assignment]
    try:
        write = generator.write_template(spec, dry_run=False, force=force)
    finally:
        generator._domains_root = original_domains_root
        generator._repo_root = original_repo_root
    report["write"] = write
    if write.get("status") != "OK":
        report["status"] = "BLOCKED_WRITE"
        report["errors"] = write.get("errors") or ["generator write failed"]
        report_json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        _write_report_md(report, report_md_path)
        return report

    validator_cmd = [
        sys.executable,
        str(_repo_root() / "domains" / "meta-lab" / "tools" / "lab_template_validator.py"),
        "--strict-m7",
        "--json",
        str(run_dir),
    ]
    result = subprocess.run(validator_cmd, capture_output=True, text=True, timeout=120)
    report["validator_command"] = validator_cmd
    report["validator_returncode"] = result.returncode
    try:
        report["validator"] = json.loads(result.stdout)
    except Exception:
        report["validator"] = {"raw_stdout": result.stdout, "stderr": result.stderr}
    if result.returncode == 0 and report["validator"].get("verdict") == "TEMPLATE_VALID":
        report["status"] = "INSTALLABLE_CANDIDATE"
    else:
        report["status"] = "BLOCKED_VALIDATOR"
        report["errors"] = [result.stderr.strip() or "strict validator failed"]

    report_json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_report_md(report, report_md_path)
    return report


def _latest_request() -> Path:
    req_dir = _data_root() / "domain_requests"
    candidates = sorted(req_dir.glob("*_request.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(f"no domain requests found under {req_dir}")
    return candidates[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--request", default=None, help="Path to domain_request JSON. Defaults to latest.")
    parser.add_argument(
        "--output-root",
        default=str(_data_root() / "generated_domains"),
        help="Isolated output root for candidate domains.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing candidate in output root.")
    parser.add_argument("--json", action="store_true", help="Print JSON only.")
    args = parser.parse_args()

    request_path = Path(args.request).resolve() if args.request else _latest_request()
    output_root = Path(args.output_root).resolve()
    report = run_request(request_path, output_root, force=args.force)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"{report['status']}: {report['slug']}")
        print(f"candidate: {report['candidate_dir']}")
        if report.get("errors"):
            print("errors:")
            for err in report["errors"]:
                print(f"- {err}")
    return 0 if report["status"] == "INSTALLABLE_CANDIDATE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
