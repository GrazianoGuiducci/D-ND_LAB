#!/usr/bin/env python3
"""promote_to_publish — sanitize draft scoperta → published/ (public-ready).

Pattern (operatore 03/05 sera): "facciamo le code fatte bene prima che
si complicano". Architettura draft/published separation:

  applications/
  ├── scoperte/           DRAFT — interno workflow, full markup
  │   └── <ts>_<slug>_auto/
  │       ├── lab-note.draft.md
  │       └── cycle-report.draft.md
  └── published/          PUBLIC — sanitized, propagato al sito
      └── <ts>_<slug>/    (no _auto suffix)
          ├── lab-note.md
          └── cycle-report.md

Sanitization: rimuove markup interno workflow che NON deve apparire al
pubblico:
  - prefisso "[TARGET — TM1 refinement]" da titoli
  - sezioni "## [TARGET — narrazione livello 1-2]"
  - sezioni "## [TARGET — gestione medium flag come rischi visibili]"
  - sezioni "## [TARGET — risultati dal report originale]"
  - placeholder "[TARGET — to fill]"
  - YAML keys interni: copy_authority, audience (con TM7 terminology rule)
  - inline notices "[SCAFFOLD AUTO-GENERATO]"
  - footer "Auto-scaffold da on_crystallize.py..."
  - reference workflow: "TM3 o agente narrativo", "TM7 review", etc.

Mantiene:
  - title scientifico pulito
  - banner status (transitional/pre_discovery/draft) — trasparenza pubblica
  - tension_explored, provenance (cycle_ts, falsifier_verdict)
  - falsifier audit summary
  - visible_risks (medium flags formattati per pubblico)
  - files links

CLI:
  python promote_to_publish.py <cycle_ts>           # singolo cycle
  python promote_to_publish.py --all                # tutti i cycle in scoperte/
  python promote_to_publish.py <ts> --force         # overwrite published/ esistente
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from pathlib import Path
from datetime import datetime, timezone


def _resolve_paths(domain: str | None = None) -> dict[str, Path]:
    """Compatibile MM_D-ND production e D-ND_LAB sandbox.

    MM_D-ND: /opt/MM_D-ND/applications/{scoperte,soluzioni} → published
    D-ND_LAB: /opt/D-ND_LAB/data/<domain>/{scoperte,soluzioni} → published
    """
    lab_data = os.environ.get("LAB_DATA_DIR")
    if lab_data:
        # D-ND_LAB style
        dom = domain or os.environ.get("DOMAIN", "physics")
        base = Path(lab_data) / dom
    else:
        # MM_D-ND production
        base = Path("/opt/MM_D-ND/applications")
    return {
        "scoperte": base / "scoperte",
        "soluzioni": base / "soluzioni",
        "published": base / "published",
    }


# === Sanitization patterns ===
# Ogni pattern è (regex, replacement). Applicati nell'ordine.
# Regex testate sui template di on_crystallize.py (D-ND_LAB + MM_D-ND).

YAML_LINE_PATTERNS = [
    # Strip YAML keys interni
    (re.compile(r'^audience:\s*.*\(TM7 terminology rule\)\s*$\n', re.M), ''),
    (re.compile(r'^copy_authority:\s*.*$\n', re.M), ''),
    (re.compile(r'^generated_by:\s*on_crystallize\.py\s*$\n', re.M), ''),
    (re.compile(r'^target_route:\s*.*$\n', re.M), ''),
    (re.compile(r'^target_cms_category:\s*.*$\n', re.M), ''),
    # Strip prefisso TM1 da title_proposal
    (re.compile(r'^title_proposal:\s*"\[TARGET — TM1 refinement\]\s*(.+?)"\s*$', re.M),
     r'title_proposal: "\1"'),
    # Strip placeholder addressed_in_artifact
    (re.compile(r'^\s*addressed_in_artifact:\s*"\[TARGET — to fill\]"\s*$\n', re.M), ''),
]

# Pattern per JSON manifest fields (recursive on string values).
# Strip prefisso "[TARGET]" e marker "[TARGET — to be assessed/to fill/...]"
JSON_VALUE_PATTERNS = [
    (re.compile(r'^\[TARGET\]\s+'), ''),
    (re.compile(r'^\[TARGET — [^\]]+\]\s*'), ''),
    (re.compile(r'^\[TO BE VERIFIED\]\s+'), ''),
]


def sanitize_json_value(value):
    """Recursively strip [TARGET] markers from JSON dict/list/str values."""
    if isinstance(value, str):
        for pat, repl in JSON_VALUE_PATTERNS:
            value = pat.sub(repl, value)
        return value
    if isinstance(value, list):
        return [sanitize_json_value(v) for v in value]
    if isinstance(value, dict):
        return {k: sanitize_json_value(v) for k, v in value.items()}
    return value


BODY_PATTERNS = [
    # Strip prefisso TM1 da title H1
    (re.compile(r'^# \[TARGET — TM1 refinement\] ', re.M), '# '),
    # Strip sezioni TARGET placeholder con body bracketed
    # Match: "## [TARGET — ...]" + paragrafo "[...]" + newlines
    (re.compile(
        r'^##\s+\[TARGET — narrazione livello 1-2\]\s*\n+\[[^\]]*\]\s*\n+',
        re.M
    ), ''),
    (re.compile(
        r'^##\s+\[TARGET — gestione medium flag come rischi visibili\]\s*\n+\[[^\]]*\]\s*\n+',
        re.M
    ), ''),
    (re.compile(
        r'^##\s+\[TARGET — risultati dal report originale\]\s*\n+\[[^\]]*\]\s*\n+',
        re.M
    ), ''),
    # Strip generic [TARGET — ...] sections (defensive)
    (re.compile(r'^##\s+\[TARGET —[^\]]+\]\s*\n+\[[^\]]*\]\s*\n+', re.M), ''),
    # Strip inline scaffold notices
    (re.compile(r'^>\s*\[SCAFFOLD AUTO-GENERATO\][^\n]*\n', re.M), ''),
    (re.compile(r'^>\s*Sorgente:[^\n]*\(TM7 terminology rule\)\.\s*\n', re.M), ''),
    (re.compile(r'^>\s*TM3 o agente tecnico[^\n]*\n', re.M), ''),
    (re.compile(r'^>\s*Body da scrivere a mano[^\n]*\n', re.M), ''),
    # Strip footer "Auto-scaffold ..." (italic line)
    (re.compile(
        r'\n*\*Auto-scaffold da [`\']on_crystallize\.py[`\'].*?\*\s*\n*$',
        re.S
    ), '\n'),
    # Strip TM-references in body lines (heuristic: "(TM7 terminology rule)" inline)
    (re.compile(r'\s*\(TM7 terminology rule\)', re.S), ''),
    # Collapse 3+ blank lines → 2
    (re.compile(r'\n{3,}'), '\n\n'),
]


def split_frontmatter(content: str) -> tuple[str, str]:
    """Split YAML front matter from body. Returns (yaml, body) or ('', content)."""
    if not content.startswith('---\n'):
        return '', content
    end = content.find('\n---\n', 4)
    if end == -1:
        return '', content
    yaml_block = content[4:end]
    body = content[end + 5:]
    return yaml_block, body


def sanitize_content(raw: str) -> str:
    """Apply YAML + body sanitization patterns. Return cleaned content."""
    yaml_block, body = split_frontmatter(raw)

    # Apply YAML patterns to yaml block
    for pat, repl in YAML_LINE_PATTERNS:
        yaml_block = pat.sub(repl, yaml_block)

    # Apply body patterns to body
    for pat, repl in BODY_PATTERNS:
        body = pat.sub(repl, body)

    if yaml_block:
        return f'---\n{yaml_block}\n---\n{body}'
    return body


def strip_auto_suffix(dirname: str) -> str:
    """Convert '20260503_0806_xxx_auto' → '20260503_0806_xxx'."""
    return re.sub(r'_auto$', '', dirname)


def find_soluzione_dir(scoperta_name: str, soluzioni_base: Path) -> Path | None:
    """Trova la soluzione corrispondente a una scoperta dir.

    Convenzione: scoperta '20260430_0330_<slug>_auto' → soluzione
    '20260430_0330_<slug>' (no _auto suffix). Match per prefix.
    """
    if not soluzioni_base.exists():
        return None
    pub_name = strip_auto_suffix(scoperta_name)
    direct = soluzioni_base / pub_name
    if direct.is_dir():
        return direct
    # Fallback: glob su prefisso (per cycle senza _auto)
    matches = list(soluzioni_base.glob(f"{pub_name}*"))
    return matches[0] if matches else None


import json as _json  # local alias to avoid shadowing in main


def promote_one(scoperta_dir: Path, published_base: Path,
                soluzioni_base: Path | None = None,
                force: bool = False) -> dict:
    """Promote single scoperta dir + matching soluzione to published.

    Pubblica:
      - lab-note.md + cycle-report.md (da scoperte/)
      - manifest.json + summary.md + finding_index.json (da soluzioni/)
    """
    pub_name = strip_auto_suffix(scoperta_dir.name)
    pub_dir = published_base / pub_name
    summary = {
        "scoperta": scoperta_dir.name,
        "published_as": pub_name,
        "files_promoted": [],
        "skipped": False,
        "skip_reason": None,
    }

    if pub_dir.exists() and not force:
        summary["skipped"] = True
        summary["skip_reason"] = "published/ exists (use --force)"
        return summary

    pub_dir.mkdir(parents=True, exist_ok=True)

    # Map: draft filename → published filename (from scoperte/)
    file_map = {
        "lab-note.draft.md": "lab-note.md",
        "cycle-report.draft.md": "cycle-report.md",
    }

    for draft_name, pub_filename in file_map.items():
        src = scoperta_dir / draft_name
        if not src.exists():
            continue
        raw = src.read_text(encoding='utf-8')
        cleaned = sanitize_content(raw)
        dst = pub_dir / pub_filename
        dst.write_text(cleaned, encoding='utf-8')
        summary["files_promoted"].append(pub_filename)

    # Soluzione corrispondente (se esiste): manifest + summary + finding_index
    if soluzioni_base is not None:
        sol_dir = find_soluzione_dir(scoperta_dir.name, soluzioni_base)
        if sol_dir:
            # manifest.draft.json: sanitize JSON values recursively (strip [TARGET])
            mf_src = sol_dir / "manifest.draft.json"
            if mf_src.exists():
                try:
                    raw_json = _json.loads(mf_src.read_text(encoding='utf-8'))
                    sanitized_json = sanitize_json_value(raw_json)
                    (pub_dir / "manifest.json").write_text(
                        _json.dumps(sanitized_json, indent=2, ensure_ascii=False),
                        encoding='utf-8'
                    )
                    summary["files_promoted"].append("manifest.json")
                except _json.JSONDecodeError as e:
                    summary["files_promoted"].append(f"manifest.json [SKIP: {e}]")

            # summary.draft.md: stesso sanitize body markdown + JSON_VALUE patterns
            sm_src = sol_dir / "summary.draft.md"
            if sm_src.exists():
                raw_md = sm_src.read_text(encoding='utf-8')
                cleaned_md = sanitize_content(raw_md)
                # Extra: strip [TARGET] inline anche dal body summary
                for pat, repl in JSON_VALUE_PATTERNS:
                    cleaned_md = pat.sub(repl, cleaned_md)
                # Strip generic [TARGET] markers in body (es. "[TARGET] X")
                cleaned_md = re.sub(r'\[TARGET\]\s+', '', cleaned_md)
                cleaned_md = re.sub(r'\[TARGET — [^\]]+\]\s*', '', cleaned_md)
                (pub_dir / "summary.md").write_text(cleaned_md, encoding='utf-8')
                summary["files_promoted"].append("summary.md")

            # finding_index.draft.json: già pulito ma copiamo per coerenza
            fi_src = sol_dir / "finding_index.draft.json"
            if fi_src.exists():
                try:
                    raw_json = _json.loads(fi_src.read_text(encoding='utf-8'))
                    sanitized_json = sanitize_json_value(raw_json)
                    (pub_dir / "finding_index.json").write_text(
                        _json.dumps(sanitized_json, indent=2, ensure_ascii=False),
                        encoding='utf-8'
                    )
                    summary["files_promoted"].append("finding_index.json")
                except _json.JSONDecodeError:
                    pass

    # Write meta.json with promotion provenance
    meta_path = pub_dir / "_promote_meta.json"
    meta_path.write_text(
        '{\n'
        f'  "promoted_at": "{datetime.now(timezone.utc).isoformat()}",\n'
        f'  "promoted_by": "promote_to_publish.py",\n'
        f'  "source_draft_dir": "{scoperta_dir.name}",\n'
        f'  "files": {summary["files_promoted"]}\n'
        '}\n'.replace("'", '"')
    )

    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cycle_ts", nargs="?")
    ap.add_argument("--all", action="store_true",
                    help="promuovi tutti i cycle presenti in scoperte/")
    ap.add_argument("--force", action="store_true",
                    help="overwrite published/ se esiste")
    ap.add_argument("--domain", default=None,
                    help="(D-ND_LAB only) override DOMAIN env")
    args = ap.parse_args()

    paths = _resolve_paths(args.domain)
    scoperte_dir = paths["scoperte"]
    soluzioni_base = paths["soluzioni"]
    published_base = paths["published"]

    if not scoperte_dir.exists():
        print(f"ERROR: scoperte/ non esiste: {scoperte_dir}", file=sys.stderr)
        return 2

    # Determina target dirs
    targets = []
    if args.all:
        targets = sorted([d for d in scoperte_dir.iterdir() if d.is_dir()])
    elif args.cycle_ts:
        # Match prefix
        matches = list(scoperte_dir.glob(f"{args.cycle_ts}_*"))
        if not matches:
            print(f"ERROR: nessuna scoperta per cycle {args.cycle_ts}", file=sys.stderr)
            return 2
        targets = [matches[0]]
    else:
        ap.print_help()
        return 2

    print(f"promote_to_publish · scoperte={scoperte_dir} · published={published_base}")
    print(f"  targets: {len(targets)}")

    promoted = 0
    skipped = 0
    for d in targets:
        s = promote_one(d, published_base, soluzioni_base=soluzioni_base, force=args.force)
        if s["skipped"]:
            print(f"  [skip] {d.name} — {s['skip_reason']}")
            skipped += 1
        else:
            files = ", ".join(s["files_promoted"]) or "(no files)"
            print(f"  [ok]   {s['published_as']} ← {d.name} ({files})")
            promoted += 1

    print(f"\nDone: {promoted} promoted, {skipped} skipped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
