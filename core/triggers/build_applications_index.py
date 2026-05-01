#!/usr/bin/env python3
"""build_applications_index — produce INDEX.draft.json per UI consumption.

Replica di /opt/MM_D-ND/tools/triggers/build_applications_index.py con
risoluzione path domain-agnostic.

Multi-domain mode: scansiona LAB_DATA_DIR/<*>/scoperte e LAB_DATA_DIR/<*>/soluzioni
oppure singolo dominio se DOMAIN env / --domain è settato.

Output: LAB_DATA_DIR/INDEX.draft.json (single multi-domain) o
        LAB_DATA_DIR/<domain>/INDEX.draft.json (singolo).

Boundary:
  - solo lettura
  - nessun publish, nessun deploy
  - rebuild on-demand: lo script gira dopo pipeline cycle o a mano
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
    dom = domain or os.environ.get("DOMAIN", None)
    return {
        "domain": dom,
        "lab_data": lab_data,
    }


def list_domains(lab_data: Path) -> list[str]:
    """Trova i domini disponibili: ogni subdir con scoperte/ o soluzioni/ è un dominio."""
    if not lab_data.exists():
        return []
    out = []
    for d in sorted(lab_data.iterdir()):
        if not d.is_dir():
            continue
        if (d / "scoperte").exists() or (d / "soluzioni").exists() or (d / "reports").exists():
            out.append(d.name)
    return out


def parse_front_matter(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text()
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return {}
    block = m.group(1)
    out = {}
    for line in block.splitlines():
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        if indent == 0 and ":" in stripped:
            k, _, v = stripped.partition(":")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            out[k] = v if v else None
    return out


def collect_scoperte(domain_dir: Path, domain: str) -> list[dict]:
    items = []
    scoperte_dir = domain_dir / "scoperte"
    if not scoperte_dir.exists():
        return items
    for d in sorted(scoperte_dir.iterdir()):
        if not d.is_dir():
            continue
        lab_note = d / "lab-note.draft.md"
        cycle_report = d / "cycle-report.draft.md"
        ln_meta = parse_front_matter(lab_note)
        cr_meta = parse_front_matter(cycle_report)
        parts = d.name.split("_")
        cycle_ts = None
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            cycle_ts = f"{parts[0]}_{parts[1]}"
        elif len(parts) >= 1 and parts[0].isdigit():
            cycle_ts = parts[0]
        web_lab_note = f"data/{domain}/scoperte/{d.name}/lab-note.draft.md" if lab_note.exists() else None
        web_cycle_report = f"data/{domain}/scoperte/{d.name}/cycle-report.draft.md" if cycle_report.exists() else None
        items.append({
            "dir": d.name,
            "domain": domain,
            "cycle_ts": cycle_ts or "",
            "lab_instance": ln_meta.get("lab_instance") or domain,
            "ssp_state": ln_meta.get("ssp_state") or cr_meta.get("ssp_state") or "scoperte",
            "status": ln_meta.get("status") or cr_meta.get("status") or "draft",
            "is_auto_scaffold": d.name.endswith("_auto"),
            "title_proposal": ln_meta.get("title_proposal") or "",
            "slug_proposal": ln_meta.get("slug_proposal") or "",
            "target_route_lab_note": ln_meta.get("target_route") or "",
            "target_route_cycle_report": cr_meta.get("target_route") or "",
            "web_path_lab_note": web_lab_note,
            "web_path_cycle_report": web_cycle_report,
        })
    return items


def collect_soluzioni(domain_dir: Path, domain: str) -> tuple[list[dict], list[dict], list[dict]]:
    candidates = []
    review = []
    non_app = []
    soluzioni_dir = domain_dir / "soluzioni"
    if not soluzioni_dir.exists():
        return candidates, review, non_app
    for d in sorted(soluzioni_dir.iterdir()):
        if not d.is_dir():
            continue
        manifest_path = d / "manifest.draft.json"
        finding_index_path = d / "finding_index.draft.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text())
        except json.JSONDecodeError:
            continue
        provenance = manifest.get("discovery_provenance", {})
        cycle_ts = provenance.get("cycle_ts", "unknown")
        lab_instance = provenance.get("lab_instance", domain)
        for app in manifest.get("applications_candidate", []):
            candidates.append({
                "dir": d.name,
                "domain": domain,
                "cycle_ts": cycle_ts,
                "lab_instance": lab_instance,
                "name": app.get("name", ""),
                "type": app.get("type", ""),
                "discovery_finding_idx": app.get("discovery_finding_idx"),
                "verifier_form": (app.get("verification_spec") or {}).get("verifier_form", ""),
                "status": "draft",
                "maturity": "transitional_candidate",
                "web_path_manifest": f"data/{domain}/soluzioni/{d.name}/manifest.draft.json",
                "web_path_finding_index": f"data/{domain}/soluzioni/{d.name}/finding_index.draft.json" if finding_index_path.exists() else None,
                "web_path_summary": f"data/{domain}/soluzioni/{d.name}/summary.draft.md",
            })
        for r in manifest.get("review_required_findings", []):
            review.append({
                "dir": d.name,
                "domain": domain,
                "cycle_ts": cycle_ts,
                "lab_instance": lab_instance,
                "finding_id": r.get("finding_id"),
                "title": r.get("title", ""),
                "reason": r.get("reason") or r.get("skip_reason", ""),
            })
        for n in manifest.get("non_application_findings", []):
            non_app.append({
                "dir": d.name,
                "domain": domain,
                "cycle_ts": cycle_ts,
                "lab_instance": lab_instance,
                "finding_id": n.get("finding_id"),
                "title": n.get("title", ""),
                "role": n.get("role", ""),
                "skip_reason": n.get("skip_reason", ""),
            })
    return candidates, review, non_app


def collect_prodotti(domain_dir: Path, domain: str) -> list[dict]:
    """Cerca prodotti maturi: dir con verification.json (non .spec)."""
    items = []
    prod_dir = domain_dir / "prodotti"
    if not prod_dir.exists():
        return items
    for d in prod_dir.iterdir():
        if not d.is_dir():
            continue
        verification = d / "verification.json"
        manifest = d / "manifest.json"
        if verification.exists() and manifest.exists():
            try:
                m = json.loads(manifest.read_text())
            except json.JSONDecodeError:
                continue
            items.append({
                "id": d.name,
                "domain": domain,
                "path": str(d.relative_to(domain_dir)),
                "type": m.get("type", ""),
                "lab_instance": m.get("lab_instance", domain),
                "status": "mature",
                "metrics": m.get("metrics", {}),
            })
    return items


def derive_filters(candidates: list[dict], domains: list[str]) -> dict:
    types = sorted({c.get("type") for c in candidates if c.get("type")})
    verifier_forms = sorted({c.get("verifier_form") for c in candidates if c.get("verifier_form")})
    maturities = sorted({c.get("maturity") for c in candidates if c.get("maturity")})
    return {
        "domain": domains,
        "type": list(types),
        "verifier_form": list(verifier_forms),
        "maturity": list(maturities),
        "sort_options": ["latest", "by_domain", "by_type", "by_maturity"],
    }


def build_index(lab_data: Path, target_domains: list[str]) -> dict:
    all_scoperte = []
    all_candidates = []
    all_review = []
    all_non_app = []
    all_prodotti = []
    for dom in target_domains:
        domain_dir = lab_data / dom
        all_scoperte.extend(collect_scoperte(domain_dir, dom))
        cand, rev, na = collect_soluzioni(domain_dir, dom)
        all_candidates.extend(cand)
        all_review.extend(rev)
        all_non_app.extend(na)
        all_prodotti.extend(collect_prodotti(domain_dir, dom))

    n_transitional = sum(1 for s in all_scoperte if s.get("status") == "transitional")
    n_draft = sum(1 for s in all_scoperte if s.get("status") == "draft")
    n_pre_discovery = sum(1 for s in all_scoperte if s.get("status") == "pre_discovery")
    n_archived = sum(1 for s in all_scoperte if s.get("status") == "archived")

    return {
        "schema_version": "0.2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "build_applications_index.py (D-ND_LAB)",
        "domains_indexed": target_domains,
        "summary": {
            "n_scoperte": len(all_scoperte),
            "n_scoperte_draft": n_draft,
            "n_scoperte_transitional": n_transitional,
            "n_scoperte_pre_discovery": n_pre_discovery,
            "n_scoperte_archived": n_archived,
            "n_applications_candidate": len(all_candidates),
            "n_review_required": len(all_review),
            "n_non_application": len(all_non_app),
            "n_prodotti_maturi": len(all_prodotti),
        },
        "value_for_all_cycles": {
            "description": "Patrimonio permanente. Vale per tutti i cicli, accumula nel tempo.",
            "scoperte_visible_n": n_draft + n_transitional + n_pre_discovery,
            "applications_candidate_n": len(all_candidates),
            "prodotti_maturi_n": len(all_prodotti),
        },
        "value_for_next_cycle": {
            "description": "Alimenta il prossimo lab cycle. Refinement, review, classificazioni.",
            "review_required_n": len(all_review),
            "non_application_n": len(all_non_app),
        },
        "filters": derive_filters(all_candidates, target_domains),
        "scoperte": all_scoperte,
        "applications_candidate": all_candidates,
        "review_required_findings": all_review,
        "non_application_findings": all_non_app,
        "prodotti_maturi": all_prodotti,
        "boundary": [
            "JSON di sola lettura per UI consumption",
            "Niente claim verified — tutti gli applications_candidate sono draft/transitional",
            "scoperte transitional/pre_discovery: pubblicate con visible_risks + disclaimer",
            "prodotti_maturi vuoto finché Stage 4 non gira con verification.json reale",
            "Rebuild a mano via questo script o post-pipeline trigger",
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None,
                    help="Path INDEX.draft.json. Default: LAB_DATA_DIR/INDEX.draft.json (multi) o LAB_DATA_DIR/<domain>/INDEX.draft.json (singolo)")
    ap.add_argument("--domain", default=None,
                    help="Limita a un singolo dominio. Default: tutti i domini sotto LAB_DATA_DIR")
    ap.add_argument("--pretty", action="store_true", default=True)
    args = ap.parse_args()

    paths = _resolve_paths(args.domain)
    lab_data = paths["lab_data"]
    explicit_dom = paths["domain"]

    if explicit_dom:
        target_domains = [explicit_dom]
        default_out = lab_data / explicit_dom / "INDEX.draft.json"
    else:
        target_domains = list_domains(lab_data)
        default_out = lab_data / "INDEX.draft.json"

    print(f"build_applications_index — domains={target_domains}")
    if not target_domains:
        print("  ERROR: nessun dominio trovato sotto LAB_DATA_DIR", file=sys.stderr)
        return 1

    index = build_index(lab_data, target_domains)

    s = index["summary"]
    print(f"  scoperte: {s['n_scoperte']} (draft={s['n_scoperte_draft']} transitional={s['n_scoperte_transitional']} pre_discovery={s['n_scoperte_pre_discovery']})")
    print(f"  applications_candidate: {s['n_applications_candidate']}")
    print(f"  review_required: {s['n_review_required']}")
    print(f"  non_application: {s['n_non_application']}")
    print(f"  prodotti maturi: {s['n_prodotti_maturi']}")

    out_path = Path(args.out) if args.out else default_out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    json_text = json.dumps(index, indent=2 if args.pretty else None)
    out_path.write_text(json_text)
    print(f"  WROTE {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
