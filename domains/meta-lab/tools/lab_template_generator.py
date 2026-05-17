"""lab_template_generator.py — Scaffolding writer del meta-lab.

Trasforma uno **specs JSON** (output cognitivo dell'agent meta-lab) nel
file system tree completo di un lab di dominio nuovo, parallelo a
domains/physics/ e domains/editorial/.

Lo specs contiene:
{
  "domain_slug": "finance",
  "title": "D-ND Finance Lab",
  "description": "...",
  "version": "0.1.0-alpha",
  "context_md": "<full markdown of context.md prompt-system>",
  "about_it": "<full markdown of about.md visitor-facing IT>",
  "about_en": "<full markdown of about.en.md visitor-facing EN>",
  "seed_tensions_json": <dict of seed_tensions.json structure>,
  "tension_to_category_json": <dict of tension_to_category.json>,
  "assertions_py": "<full python source of assertions.py>",
  "transduction_md": "<full markdown with invariants, exclusions, baselines, UI and skill_intent_map>",
  "ui_contract_json": <dict matching docs/templates/ui_contract.v1.json>,
  "skill_intent_map_json": <dict: intent -> movement_class -> skill/meta-prompt/artifact/UI mapping>,
  "archive_retrieval_json": <optional list/dict: cognitive archive capsules/body read plan>,
  "tools_exp_files": [
    {"name": "exp_regime_shift.py", "content": "..."},
    ...
  ]
}

Il generator NON pensa — scrive ciò che l'agent meta-lab ha prodotto.
La separazione è netta: agent inferisce, generator esegue I/O.

Uso:
    python lab_template_generator.py <specs_json_path> [--dry-run] [--force]

Default: il generator rifiuta di sovrascrivere domini esistenti.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _domains_root() -> Path:
    """domains/ del repo D-ND_LAB (parent di meta-lab/tools)."""
    return Path(__file__).resolve().parents[2]


def _repo_root() -> Path:
    """Root del repo D-ND_LAB."""
    return _domains_root().parent


SLUG_FIELDS_REQUIRED = {
    "domain_slug",
    "title",
    "description",
    "version",
    "context_md",
    "about_it",
    "about_en",
    "seed_tensions_json",
    "tension_to_category_json",
    "assertions_py",
    "mml_json",  # Refactor P2.A.5: MML nasce con il lab dalla genesi
    "transduction_md",  # M7: transduzione domain-native obbligatoria
    "ui_contract_json",  # M7: contratto UI obbligatorio
    "skill_intent_map_json",  # M8: intento -> movimento -> skill/meta-prompt
}


def validate_specs(specs: dict[str, Any]) -> list[str]:
    """Verifica che lo specs abbia tutti i campi necessari prima di scrivere.
    Ritorna lista di errori (vuota se OK)."""
    errors: list[str] = []
    for field in SLUG_FIELDS_REQUIRED:
        if field not in specs:
            errors.append(f"missing field: {field}")
    slug = specs.get("domain_slug", "")
    if slug and not slug.replace("_", "").replace("-", "").isalnum():
        errors.append(f"invalid domain_slug '{slug}' (alphanumeric + _ - only)")
    if slug in ("meta-lab", "physics", "editorial"):
        errors.append(f"domain '{slug}' è riservato/esistente")
    # seed_tensions deve avere almeno 3 tensioni iniziali
    seed = specs.get("seed_tensions_json", {})
    if not isinstance(seed, dict):
        errors.append("seed_tensions_json deve essere dict")
    elif len(seed.get("tensioni", [])) < 3:
        errors.append("seed_tensions_json deve avere ≥3 tensioni iniziali")
    # mml_json deve avere campi minimi (refactor P2.A.5)
    mml = specs.get("mml_json", {})
    if not isinstance(mml, dict):
        errors.append("mml_json deve essere dict")
    else:
        for fld in ("lab", "version", "identity", "kernel_refs",
                    "skills_attive", "modus_invocation"):
            if fld not in mml:
                errors.append(f"mml_json manca campo richiesto: {fld}")
        if mml.get("lab") and slug and mml["lab"] != slug:
            errors.append(f"mml_json.lab='{mml.get('lab')}' != domain_slug='{slug}'")
        skills_attive = mml.get("skills_attive")
        if not isinstance(skills_attive, dict):
            errors.append("mml_json.skills_attive deve essere layered object (dict)")
        else:
            layer_count = sum(
                1 for key, value in skills_attive.items()
                if not str(key).startswith("_") and isinstance(value, list) and value
            )
            if layer_count < 3:
                errors.append("mml_json.skills_attive deve dichiarare almeno 3 layer non vuoti")
    transduction = specs.get("transduction_md", "")
    if not isinstance(transduction, str) or not transduction.strip():
        errors.append("transduction_md deve essere markdown non vuoto")
    else:
        t_lower = transduction.lower()
        for signal in ("skill", "baseline", "null", "ui"):
            if signal not in t_lower:
                errors.append(f"transduction_md manca segnale M7/M8: {signal}")
    ui_contract = specs.get("ui_contract_json", {})
    if not isinstance(ui_contract, dict):
        errors.append("ui_contract_json deve essere dict")
    else:
        frame = ui_contract.get("frame") if isinstance(ui_contract.get("frame"), dict) else {}
        if ui_contract.get("schema") != "ui_contract.v1":
            errors.append("ui_contract_json.schema deve essere ui_contract.v1")
        if not all(k in frame for k in ("left", "center", "right")):
            errors.append("ui_contract_json.frame deve contenere left, center, right")
    skill_intent_map = specs.get("skill_intent_map_json", {})
    if not isinstance(skill_intent_map, dict):
        errors.append("skill_intent_map_json deve essere dict")
    else:
        for fld in (
            "intent",
            "movement_class",
            "use_dynamics",
            "skill_layers",
            "meta_prompts",
            "generated_artifacts",
            "null_baseline_requirements",
            "ui_lens",
            "exclusions",
        ):
            if fld not in skill_intent_map:
                errors.append(f"skill_intent_map_json manca campo richiesto: {fld}")
    archive_retrieval = specs.get("archive_retrieval_json")
    if archive_retrieval is not None:
        archive_entries: list[Any]
        if isinstance(archive_retrieval, dict):
            archive_entries = archive_retrieval.get("archive_retrieval", [])
            if not isinstance(archive_entries, list):
                errors.append("archive_retrieval_json.archive_retrieval deve essere list")
                archive_entries = []
        elif isinstance(archive_retrieval, list):
            archive_entries = archive_retrieval
        else:
            errors.append("archive_retrieval_json deve essere list o dict")
            archive_entries = []

        required_archive_fields = {
            "archive_id",
            "pattern",
            "read_depth",
            "used_for",
            "body_required",
            "contamination_excluded",
            "test_expected",
        }
        valid_depths = {"CAPSULE", "BODY", "BODY_PLUS_REFS", "E2E"}
        for idx, entry in enumerate(archive_entries):
            if not isinstance(entry, dict):
                errors.append(f"archive_retrieval_json[{idx}] deve essere dict")
                continue
            missing = sorted(required_archive_fields - set(entry))
            if missing:
                errors.append(f"archive_retrieval_json[{idx}] manca campi: {missing}")
            depth = entry.get("read_depth")
            if depth and depth not in valid_depths:
                errors.append(f"archive_retrieval_json[{idx}].read_depth non valido: {depth}")
            capsule = entry.get("capsule")
            if capsule and isinstance(capsule, str) and not capsule.startswith(("/opt/", "http://", "https://")):
                capsule_path = _repo_root() / capsule
                if not capsule_path.exists():
                    errors.append(f"archive_retrieval_json[{idx}].capsule non esiste nel repo: {capsule}")
            if depth == "CAPSULE" and entry.get("body_required") is False:
                errors.append(
                    f"archive_retrieval_json[{idx}] usa read_depth=CAPSULE ma body_required=false"
                )
    return errors


def _ensure_skill_intent_map_in_transduction(
    transduction_md: str,
    skill_intent_map: dict[str, Any],
) -> tuple[str, bool]:
    """Garantisce che la transduzione contenga una sezione ispezionabile
    `skill_intent_map`.

    Il meta-lab agent dovrebbe scriverla gia' in linguaggio naturale. Il
    generator la appende in forma JSON se manca, cosi' M8 non dipende dalla
    memoria dell'agent e il Lab figlio conserva il ponte intento->skill.
    """
    if "skill_intent_map" in transduction_md.lower():
        return transduction_md, False
    block = (
        "\n\n## skill_intent_map\n\n"
        "Auto-generated from specs by `lab_template_generator.py`.\n\n"
        "```json\n"
        + json.dumps(skill_intent_map, indent=2, ensure_ascii=False)
        + "\n```\n"
    )
    return transduction_md.rstrip() + block, True


def _ensure_archive_retrieval_in_transduction(
    transduction_md: str,
    archive_retrieval: Any,
) -> tuple[str, bool]:
    """Appende una sezione `archive_retrieval` se lo specs usa capsule o
    archivi cognitivi e la transduction non li espone gia'.

    Serve a rendere M8 verificabile senza affidarsi alla memoria dell'agent:
    se un template ha letto solo capsule (`read_depth=CAPSULE`) o pianifica
    lettura di corpi esterni, il Lab figlio deve conservarne provenance e
    limiti d'uso.
    """
    if not archive_retrieval:
        return transduction_md, False
    if "archive_retrieval" in transduction_md.lower():
        return transduction_md, False
    block = (
        "\n\n## archive_retrieval\n\n"
        "Auto-generated from specs by `lab_template_generator.py`.\n"
        "Capsule are planning context, not active authority unless the body "
        "has been read at the required depth.\n\n"
        "```json\n"
        + json.dumps(archive_retrieval, indent=2, ensure_ascii=False)
        + "\n```\n"
    )
    return transduction_md.rstrip() + block, True


def _ensure_quick_reference_in_context(
    context_md: str,
    external_apis: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Phase 2.C.3: garantisce Quick Reference Table nel context.md se ci
    sono external_apis dichiarate nel MML.

    Pattern hermes (drug-discovery): l'agent del lab figlio ha bisogno di
    un manuale rapido Task→Endpoint→Notes per non googlare API durante
    il cycle. Questa funzione:
    - Se external_apis è vuoto → ritorna context_md invariato.
    - Se external_apis ha elementi E context_md contiene già una sezione
      'Quick Reference' (case insensitive) → ritorna invariato (l'agent
      ha rispettato il pattern, fiducia).
    - Se external_apis ha elementi E nessuna sezione esiste → appende
      una sezione minima generata dai dati MML in coda al context_md.
      Garanzia di coerenza, anche se l'agent l'ha dimenticata.

    Ritorna (context_md_finale, was_appended).
    """
    if not external_apis:
        return context_md, False
    lower = context_md.lower()
    if "quick reference" in lower or "external apis" in lower or "external_apis" in lower:
        return context_md, False

    rows: list[str] = []
    for api in external_apis:
        name = api.get("name", "?")
        base_url = api.get("base_url", "?")
        auth = "yes" if api.get("auth_required") else "no"
        purpose = api.get("purpose", "")
        rate = api.get("rate_limit_notes", "")
        notes_parts: list[str] = []
        if purpose:
            notes_parts.append(purpose)
        if rate:
            notes_parts.append(f"rate: {rate}")
        notes = "; ".join(notes_parts) or ""
        rows.append(f"| {name} | `{base_url}` | {auth} | {notes} |")

    section = (
        "\n\n## Quick Reference — External APIs\n\n"
        "Auto-generated from MML `external_apis` (Phase 2.C.3 generator helper).\n"
        "L'agent invoca queste API via `shell_exec` (curl o python3 -c \"import requests; ...\").\n\n"
        "| API | Base URL | Auth | Notes |\n"
        "|-----|----------|------|-------|\n"
        + "\n".join(rows)
        + "\n"
    )
    return context_md.rstrip() + section, True


def _build_config(specs: dict[str, Any]) -> dict[str, Any]:
    """Costruisce config.json dal pattern D-ND_LAB neutro.

    Movement defaults coerenti con MOVEMENT_ORDER di core/lab_agent.py:
    - autopsy + trajectory_apply (Strato 2 A8+A15) + agent + falsifier +
      bicono + verify + integrator + trajectory_evaluator + ssp +
      bias_corrector enabled
    - structural_check + build_graph + sync + verify_endpoints +
      semantic_bridge + refresh_detector disabled (lab-specific opt-in)

    Specs può sovrascrivere via specs["movements_override"].
    """
    default_movements = {
        "autopsy":              {"enabled": True},
        "trajectory_apply":     {"enabled": True, "params": {"comment": "Loop A8+A15: applica log-only REDESIGN al seed prima di build_field"}},
        "build_field":          {"enabled": True},
        "agent":                {"enabled": True},
        "bias_corrector":       {"enabled": True},
        "report_falsifier":     {"enabled": True},
        "bicono_extractor":     {"enabled": True},
        "validate_seed":        {"enabled": True},
        "verify_assertions":    {"enabled": True},
        "structural_check":     {"enabled": False},
        "build_lab_data":       {"enabled": True},
        "build_graph":          {"enabled": False},
        "sync":                 {"enabled": False},
        "verify_endpoints":     {"enabled": False},
        "refiner":              {"enabled": True},
        "semantic_bridge":      {"enabled": False},
        "refresh_detector":     {"enabled": False},
        "seed_integrator":      {"enabled": True},
        "veritas_score":        {"enabled": True, "params": {"comment": "G2 termometro qualità ρ ∈ [0,1] da 3 vettori. Decision band SCARTO/SOSPENSIONE/COLLASSO."}},
        "trajectory_evaluator": {"enabled": True},
        "promotion_proposer":   {"enabled": True, "params": {"comment": "G3 estrae proposte di promozione finding → skill/hook/regola sistemica. Output in data/<lab>/promotions/. NO apply automatico."}},
        "ssp_pipeline":         {"enabled": False, "params": {"comment": "abilita per lab di dominio scoperta-prodotto; disable per lab di funzione"}},
        "notify":               {"enabled": True},
    }
    movements = specs.get("movements_override", default_movements)

    return {
        "$schema": "../../config.schema.json",
        "domain": specs["domain_slug"],
        "version": specs["version"],
        "title": specs["title"],
        "description": specs["description"],
        "model": {
            "context_file": "context.md",
            "tension_to_category": "tension_to_category.json",
            "seed_tensions": "seed_tensions.json"
        },
        "context": {
            "data_dir": specs["domain_slug"],
            "max_turns": specs.get("max_turns", 25),
            "timeout_seconds": specs.get("timeout_seconds", 1200)
        },
        "tools": [
            {"name": "filesystem", "type": "builtin"},
            {"name": "python_exec", "type": "builtin"},
            {"name": "shell_exec", "type": "builtin"}
        ],
        "movements": movements,
        "_generated_by": "meta-lab",
        "_generated_at": specs.get("generated_at", ""),
    }


def write_template(specs: dict[str, Any], dry_run: bool = False, force: bool = False) -> dict[str, Any]:
    """Scrive il filesystem tree del nuovo dominio. Ritorna report."""
    errors = validate_specs(specs)
    if errors:
        return {"status": "FAIL", "errors": errors, "files_written": []}

    target_dir = _domains_root() / specs["domain_slug"]
    if target_dir.exists() and not force:
        return {
            "status": "FAIL",
            "errors": [f"directory {target_dir} esiste già (usa --force per sovrascrivere)"],
            "files_written": [],
        }

    files_to_write: list[tuple[Path, str]] = []
    files_to_write.append((target_dir / "config.json",
                           json.dumps(_build_config(specs), indent=2, ensure_ascii=False) + "\n"))
    # Phase 2.C.3: assicura Quick Reference Table nel context.md se MML
    # dichiara external_apis. Pattern hermes — surface le API come manuale
    # rapido pronto all'uso per l'agent del lab figlio.
    external_apis = specs.get("mml_json", {}).get("external_apis", []) or []
    context_md, qr_appended = _ensure_quick_reference_in_context(
        specs["context_md"], external_apis,
    )
    files_to_write.append((target_dir / "context.md", context_md))
    files_to_write.append((target_dir / "about.md", specs["about_it"]))
    files_to_write.append((target_dir / "about.en.md", specs["about_en"]))
    files_to_write.append((target_dir / "seed_tensions.json",
                           json.dumps(specs["seed_tensions_json"], indent=2, ensure_ascii=False) + "\n"))
    files_to_write.append((target_dir / "tension_to_category.json",
                           json.dumps(specs["tension_to_category_json"], indent=2, ensure_ascii=False) + "\n"))
    files_to_write.append((target_dir / "assertions.py", specs["assertions_py"]))
    transduction_md, skill_map_appended = _ensure_skill_intent_map_in_transduction(
        specs["transduction_md"],
        specs["skill_intent_map_json"],
    )
    transduction_md, archive_retrieval_appended = _ensure_archive_retrieval_in_transduction(
        transduction_md,
        specs.get("archive_retrieval_json"),
    )
    files_to_write.append((target_dir / "transduction.md", transduction_md))
    files_to_write.append((target_dir / "ui_contract.json",
                           json.dumps(specs["ui_contract_json"], indent=2, ensure_ascii=False) + "\n"))
    # mml.json (refactor P2.A.5: MML nasce con il lab dalla genesi)
    files_to_write.append((target_dir / "mml.json",
                           json.dumps(specs["mml_json"], indent=2, ensure_ascii=False) + "\n"))

    # Optional: tools/exp_*.py iniziali
    for exp in specs.get("tools_exp_files", []) or []:
        if "name" in exp and "content" in exp:
            files_to_write.append((target_dir / "tools" / exp["name"], exp["content"]))

    # Optional: README.md placeholder
    readme = specs.get("readme_md")
    if readme:
        files_to_write.append((target_dir / "README.md", readme))

    written: list[str] = []
    if dry_run:
        return {
            "status": "DRY_RUN",
            "would_write": [str(p) for p, _ in files_to_write],
            "files_written": [],
            "helpers_applied": {
                "quick_reference_appended": qr_appended,
                "skill_intent_map_appended": skill_map_appended,
                "archive_retrieval_appended": archive_retrieval_appended,
            },
        }

    for path, content in files_to_write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(str(path.relative_to(_domains_root())))

    return {
        "status": "OK",
        "errors": [],
        "files_written": written,
        "target_dir": str(target_dir),
        "helpers_applied": {
            "quick_reference_appended": qr_appended,
            "skill_intent_map_appended": skill_map_appended,
            "archive_retrieval_appended": archive_retrieval_appended,
        },
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("specs_path", help="path al JSON con la spec del template (output meta-lab)")
    ap.add_argument("--dry-run", action="store_true", help="mostra cosa scriverebbe senza scrivere")
    ap.add_argument("--force", action="store_true", help="sovrascrivi dominio esistente")
    args = ap.parse_args()

    specs = json.loads(Path(args.specs_path).read_text(encoding="utf-8"))
    report = write_template(specs, dry_run=args.dry_run, force=args.force)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(0 if report["status"] in ("OK", "DRY_RUN") else 1)


if __name__ == "__main__":
    main()
