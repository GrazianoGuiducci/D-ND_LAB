#!/usr/bin/env python3
"""finding_eligibility_gate — classifica i findings prima di application_designer.

Replica di /opt/MM_D-ND/tools/triggers/finding_eligibility_gate.py con
risoluzione path domain-agnostic (LAB_DATA_DIR + DOMAIN).

Distingue:
  - applicative_finding   → claim operativo con consequenza computabile
  - literature_rediscovery → riferimento a letteratura esistente, non nuovo
  - methodology_note      → riflessione sul metodo/framework, non operativa
  - boundary_warning      → vincolo/confine senza claim quantitativo
  - verdict_summary       → tag NEW/CONSTRAINT/CONFIRMED, riassunto
  - negative_result       → "X NON ha forma chiusa", "Y NON è famiglia"

Vincoli:
  - niente skip silenzioso (ogni finding finisce nell'index)
  - niente euristica single-string solo sul titolo
  - dubbio → REVIEW_REQUIRED (non application_eligible=true forzato)
  - tutto draft, scaffold, niente claim verified

Output: LAB_DATA_DIR/<domain>/soluzioni/<ts>_<slug>/finding_index.draft.json
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


# Multi-segnale signals per classificazione (lowercase substring match).
# Ogni signal ha peso che contribuisce al score della categoria.
SIGNALS = {
    "literature_rediscovery": [
        ("is implicit in", 3),
        ("what is not in", 3),
        ("re-discovery", 3),
        ("rediscovery check", 3),
        ("literature context", 3),
        ("lemke oliver", 2),
        ("soundararajan", 2),
        ("hardy-littlewood", 1),
        ("not in", 1),
        ("known consequence", 2),
        ("classical", 1),
        ("(2016)", 1),
        ("(20", 1),  # year citation
    ],
    "methodology_note": [
        ("meta refined", 3),
        ("decomposition is incomplete", 3),
        ("decomposition is", 2),
        ("framework", 1),
        ("lab should track", 2),
        ("structural observ", 1),
        ("not one category", 2),
        ("two kinds", 1),
        ("three kinds", 1),
        ("two layers", 1),
        ("three layers", 1),
        ("rather than", 1),
    ],
    "boundary_warning": [
        ("boundary", 1),
        ("limit", 1),
        ("invisible to", 2),
        ("must include", 1),
        ("constraint", 1),
        ("perimetro", 1),
    ],
    "verdict_summary": [
        ("new tag", 3),
        ("constraint on", 2),
        ("confirmed structure", 2),
        ("verdict", 2),
    ],
    "negative_result": [
        ("does not have", 3),
        ("is not", 1),
        ("not a family", 3),
        ("not a member", 2),
        ("has no", 2),
        ("non-monotonic", 1),
    ],
    "applicative": [
        (r"=\s*-?\d+\.\d+", 2, "regex"),
        (r"z\s*=\s*-?\d", 2, "regex"),
        (r"\d{3,}\s+(prime|gap|window)", 2, "regex"),
        ("verified on", 2),
        ("tested on", 2),
        ("zero violations", 2),
        ("0 violations", 2),
        ("exactly", 1),
        ("theorem", 2),
        ("forbidden", 2),
        ("prohibition", 2),
        ("predicts", 2),
        ("scaling law", 1),
        ("invariant", 1),
        ("scale-invariant", 2),
        ("self-transition", 2),
    ],
}


def score_category(text: str, category: str) -> tuple[int, list[str]]:
    score = 0
    matched = []
    for entry in SIGNALS[category]:
        if len(entry) == 3 and entry[2] == "regex":
            pattern, weight, _ = entry
            if re.search(pattern, text):
                score += weight
                matched.append(f"regex:{pattern}")
        else:
            substring, weight = entry[0], entry[1]
            if substring in text:
                score += weight
                matched.append(substring)
    return score, matched


def classify_finding(finding: dict) -> dict:
    text = (finding["title"] + " " + finding["body"]).lower()

    scores = {}
    matched = {}
    for cat in SIGNALS:
        s, m = score_category(text, cat)
        scores[cat] = s
        matched[cat] = m

    appl_score = scores["applicative"]
    lit_score = scores["literature_rediscovery"]
    meth_score = scores["methodology_note"]
    boundary_score = scores["boundary_warning"]
    verdict_score = scores["verdict_summary"]
    neg_score = scores["negative_result"]

    role = None
    application_eligible = None
    skip_reason = None

    if lit_score >= 3:
        role = "literature_rediscovery"
        application_eligible = False
        skip_reason = f"literature/rediscovery context (score={lit_score}); not a new operational finding"
    elif verdict_score >= 4:
        role = "verdict_summary"
        application_eligible = False
        skip_reason = f"verdict/summary tag (score={verdict_score}); not a discrete finding"
    elif meth_score >= 4 and appl_score < 3:
        role = "methodology_note"
        application_eligible = False
        skip_reason = f"methodology/framework reflection (score={meth_score}, appl={appl_score})"
    elif neg_score >= 3 and appl_score < 4:
        role = "negative_result"
        application_eligible = False
        skip_reason = f"negative result (score={neg_score}); no positive operational consequence"
    elif boundary_score >= 3 and appl_score < 3:
        role = "boundary_warning"
        application_eligible = False
        skip_reason = f"boundary/limit warning without quantitative claim (score={boundary_score})"
    elif appl_score >= 4:
        role = "applicative_finding"
        application_eligible = True
        skip_reason = None
    elif appl_score >= 2 and lit_score < 2 and meth_score < 2:
        role = "ambiguous"
        application_eligible = "REVIEW_REQUIRED"
        skip_reason = f"misto: appl={appl_score}, lit={lit_score}, meth={meth_score}, neg={neg_score}, boundary={boundary_score}"
    else:
        role = "ambiguous"
        application_eligible = "REVIEW_REQUIRED"
        skip_reason = f"insufficient signal: appl={appl_score}, lit={lit_score}, meth={meth_score}, neg={neg_score}, boundary={boundary_score}"

    level = "structural" if appl_score >= 3 else ("contextual" if lit_score >= 2 else "meta")

    return {
        "finding_id": finding["idx"],
        "title": finding["title"],
        "level": level,
        "role": role,
        "application_eligible": application_eligible,
        "skip_reason": skip_reason,
        "source_excerpt": finding["body"][:300],
        "scores": scores,
        "matched_signals": {k: v for k, v in matched.items() if v},
    }


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
        findings.append({"idx": idx, "title": title, "body": body[:800]})
    return findings


def find_scoperta_dir(cycle_ts: str) -> Path | None:
    if not SCOPERTE.exists():
        return None
    auto = list(SCOPERTE.glob(f"{cycle_ts}_*_auto"))
    if auto:
        return auto[0]
    manual = [d for d in SCOPERTE.glob(f"{cycle_ts}_*") if d.is_dir()]
    return manual[0] if manual else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cycle_ts")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--domain", default=None, help="override DOMAIN env")
    args = ap.parse_args()

    if args.domain:
        global _PATHS, REPORTS, SCOPERTE, SOLUZIONI
        _PATHS = _resolve_paths(args.domain)
        REPORTS = _PATHS["reports"]
        SCOPERTE = _PATHS["scoperte"]
        SOLUZIONI = _PATHS["soluzioni"]

    cycle_ts = args.cycle_ts
    print(f"finding_eligibility_gate cycle_ts={cycle_ts} domain={_PATHS['domain']}")

    agent_path = REPORTS / f"agent_{cycle_ts}.md"
    if not agent_path.exists():
        print(f"ERROR: {agent_path} non esiste", file=sys.stderr)
        return 2

    scoperta_dir = find_scoperta_dir(cycle_ts)
    if not scoperta_dir:
        print(f"ERROR: nessuna scoperta dir per {cycle_ts}", file=sys.stderr)
        return 2

    findings = parse_key_findings(agent_path.read_text())
    if not findings:
        print("ERROR: nessun finding parsato", file=sys.stderr)
        return 1

    print(f"  findings parsed: {len(findings)}")

    classified = [classify_finding(f) for f in findings]
    n_eligible = sum(1 for c in classified if c["application_eligible"] is True)
    n_review = sum(1 for c in classified if c["application_eligible"] == "REVIEW_REQUIRED")
    n_skip = sum(1 for c in classified if c["application_eligible"] is False)
    print(f"  eligible: {n_eligible} | review_required: {n_review} | skip: {n_skip}")

    for c in classified:
        flag = "✓" if c["application_eligible"] is True else ("?" if c["application_eligible"] == "REVIEW_REQUIRED" else "✗")
        print(f"    [{flag}] #{c['finding_id']} {c['role']:<25} | {c['title'][:65]}")

    parts = scoperta_dir.name.split("_", 2)
    slug = parts[2] if len(parts) >= 3 else "unknown"
    if slug.endswith("_auto"):
        slug = slug[:-5]

    out_dir = SOLUZIONI / f"{cycle_ts}_{slug}"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / "finding_index.draft.json"
    if out_path.exists() and not args.force:
        print(f"  SKIP {out_path} (esiste, --force per sovrascrivere)")
        return 0

    index_doc = {
        "schema_version": "0.1",
        "stage": "1.5",
        "stage_name": "finding_eligibility_gate",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "finding_eligibility_gate.py",
        "cycle_ts": cycle_ts,
        "domain": _PATHS["domain"],
        "summary": {
            "n_findings": len(findings),
            "n_application_eligible": n_eligible,
            "n_review_required": n_review,
            "n_skipped": n_skip,
        },
        "findings": classified,
        "boundary": [
            "Niente skip silenzioso — tutti i findings sono qui",
            "Classifier multi-segnale, non single-string sul titolo",
            "Dubbio → REVIEW_REQUIRED, non application_eligible forzato",
            "Application Designer userà SOLO findings con application_eligible=true",
            "Findings con REVIEW_REQUIRED richiedono operatore prima di Stage 2",
        ],
    }
    out_path.write_text(json.dumps(index_doc, indent=2))
    print(f"  WROTE {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
