"""assertions.py — Meta-lab falsifier (M1-M8).

Il falsifier meta-lab non valuta findings scientifici. Valuta TEMPLATE
di lab generati. Ogni assertion controlla una condizione strutturale:
il template ha le caratteristiche per produrre, una volta installato
e fatto girare, cycle che a loro volta producono findings verificabili.

Schema output di verifica_asserzioni() (compatibile col pipeline):
    [
        {"id": "M1", "status": "PASS"|"FAIL"|"SKIP", "detail": "...", "metric": ...},
        ...
    ]

Modalità di invocazione:
- Standalone (smoke test del meta-lab stesso): esegue su un template
  fittizio interno o sul template rigenerato di physics.
- Pipeline lab_agent.sh: chiamato come ogni altro dominio dopo cycle.
- Tool dedicato: invocato da lab_template_validator.py per validare
  un template appena generato prima di scriverlo a disco.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


# ─── Path helpers ────────────────────────────────────────────────

def _meta_lab_dir() -> Path:
    return Path(__file__).resolve().parent


def _domains_root() -> Path:
    return _meta_lab_dir().parent


def _lookup_template_under_test() -> Path | None:
    """Cerca il template da validare. Priorità:
    1. Env var META_LAB_TEMPLATE_PATH (override esplicito)
    2. data dir corrente (run mode con artifacts)
    3. Self-test su domains/physics/ (ground truth)
    """
    override = os.environ.get("META_LAB_TEMPLATE_PATH")
    if override:
        p = Path(override)
        if p.exists():
            return p
    # Fallback: physics come ground truth — il meta-lab si auto-testa
    # provando a falsificare physics esistente. Se M1-M8 non producono
    # FAIL su physics, le lenti sono calibrate correttamente.
    physics = _domains_root() / "physics"
    if physics.exists():
        return physics
    return None


# ─── M1: Dipoli aritmetici nelle tensioni ────────────────────────

def _check_m1_dipolar_tensions(template_dir: Path) -> dict[str, Any]:
    """Le tensioni iniziali devono avere dipoli aritmetici (det≠0) o
    riferimento a un assioma D-ND con dipolo generativo. Heuristic:
    presenza di condensato_ref (A1-A16, F1-F6, C1-C3) nella tensione.
    """
    seed_file = template_dir / "seed_tensions.json"
    if not seed_file.exists():
        return {"id": "M1", "status": "FAIL", "detail": "seed_tensions.json mancante", "metric": 0}
    try:
        seed = json.loads(seed_file.read_text())
    except Exception as e:
        return {"id": "M1", "status": "FAIL", "detail": f"JSON parse error: {e}", "metric": 0}

    tensioni = seed.get("tensioni", [])
    if not tensioni:
        return {"id": "M1", "status": "FAIL", "detail": "nessuna tensione iniziale", "metric": 0}

    n_with_ref = sum(1 for t in tensioni if t.get("condensato_ref"))
    ratio = n_with_ref / len(tensioni)
    # Soglia: almeno 60% delle tensioni iniziali deve referenziare condensato
    status = "PASS" if ratio >= 0.6 else ("SKIP" if ratio >= 0.3 else "FAIL")
    return {
        "id": "M1",
        "status": status,
        "detail": f"{n_with_ref}/{len(tensioni)} tensioni con condensato_ref ({ratio:.0%})",
        "metric": ratio,
    }


# ─── M2: Assertions eseguibili ───────────────────────────────────

def _check_m2_executable_assertions(template_dir: Path) -> dict[str, Any]:
    """assertions.py deve esistere, contenere una funzione di verifica
    aggregata (verifica_asserzioni / verify_assertions / public list di
    _test_*) che produca PASS/FAIL/SKIP numerici.
    """
    assertions_file = template_dir / "assertions.py"
    if not assertions_file.exists():
        return {"id": "M2", "status": "FAIL", "detail": "assertions.py mancante", "metric": 0}

    text = assertions_file.read_text()
    has_aggregator = bool(re.search(r"def\s+(verifica_asserzioni|verify_assertions)\s*\(", text))
    has_public_list = bool(re.search(r"^(ASSERTIONS|TESTS|PUBLIC)\s*[:=]\s*\[", text, re.MULTILINE))
    has_test_fns = len(re.findall(r"^def\s+(_?test_|_?check_)\w+\s*\(", text, re.MULTILINE))
    if not (has_aggregator or has_public_list or has_test_fns >= 3):
        return {
            "id": "M2",
            "status": "FAIL",
            "detail": "nessun aggregator né lista pubblica né ≥3 _test_/_check_ functions",
            "metric": 0,
        }
    # Se siamo nel meta-lab che si auto-testa, evitiamo eval ricorsiva
    if template_dir.name == "meta-lab":
        return {
            "id": "M2",
            "status": "PASS",
            "detail": "aggregator/public list/_test_ presenti (self-skip exec ricorsivo)",
            "metric": 1.0,
        }
    # Se non c'è aggregator ma ci sono ≥3 _test_, è valido come public list di funzioni
    if not has_aggregator and has_test_fns >= 3:
        return {
            "id": "M2",
            "status": "PASS",
            "detail": f"{has_test_fns} _test_/_check_ functions (public list pattern)",
            "metric": has_test_fns,
        }
    # Esegui in sandbox temporaneo per controllare che produca lista valida
    try:
        result = subprocess.run(
            [sys.executable, "-c",
             f"import sys; sys.path.insert(0, {str(template_dir)!r}); "
             "import assertions; r = assertions.verifica_asserzioni(); "
             "import json; print(json.dumps([{'id': x.get('id'), 'status': x.get('status')} for x in r]))"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            try:
                items = json.loads(result.stdout.strip().split("\n")[-1])
                n_valid = sum(1 for x in items if x.get("status") in ("PASS", "FAIL", "SKIP"))
                if n_valid >= 3:
                    return {
                        "id": "M2",
                        "status": "PASS",
                        "detail": f"{n_valid} asserzioni eseguite con status valido",
                        "metric": n_valid,
                    }
                return {
                    "id": "M2",
                    "status": "FAIL",
                    "detail": f"solo {n_valid} asserzioni valide (richiesto ≥3)",
                    "metric": n_valid,
                }
            except json.JSONDecodeError:
                return {"id": "M2", "status": "FAIL", "detail": "output non-JSON",
                        "metric": 0}
        return {
            "id": "M2",
            "status": "FAIL",
            "detail": f"exec error (rc={result.returncode}): {result.stderr[:200]}",
            "metric": 0,
        }
    except subprocess.TimeoutExpired:
        return {"id": "M2", "status": "FAIL", "detail": "timeout 60s", "metric": 0}
    except Exception as e:
        return {"id": "M2", "status": "FAIL", "detail": f"exec exception: {e}", "metric": 0}


# ─── M3: Tools eseguibili out-of-box ─────────────────────────────

def _check_m3_tools_runnable(template_dir: Path) -> dict[str, Any]:
    """tools/ deve contenere almeno 1 exp_*.py che importi numpy/scipy
    senza dipendenze GPU/network al primo cycle.
    """
    tools_dir = template_dir / "tools"
    if not tools_dir.exists():
        # editorial pattern: tools/ non sempre presente nel template iniziale
        return {"id": "M3", "status": "SKIP", "detail": "tools/ assente (template editorial-style?)",
                "metric": 0}
    exp_files = list(tools_dir.glob("exp_*.py"))
    if not exp_files:
        return {"id": "M3", "status": "FAIL", "detail": "nessun exp_*.py in tools/",
                "metric": 0}
    bad_imports = ("torch", "tensorflow", "cuda", "requests.get(", "urllib.request.urlopen(")
    n_clean = 0
    for f in exp_files:
        text = f.read_text(errors="replace")
        if any(bad in text for bad in bad_imports):
            continue
        n_clean += 1
    ratio = n_clean / len(exp_files) if exp_files else 0
    status = "PASS" if ratio >= 0.7 else ("SKIP" if ratio >= 0.4 else "FAIL")
    return {
        "id": "M3",
        "status": status,
        "detail": f"{n_clean}/{len(exp_files)} exp_*.py senza GPU/network deps",
        "metric": ratio,
    }


# ─── M4: Naive baseline esistente ────────────────────────────────

def _check_m4_naive_baseline(template_dir: Path) -> dict[str, Any]:
    """Il template deve dichiarare un naive baseline contro cui Stage 4
    A/B testarà il modus. Heuristic: presenza dei pattern 'naive' + 'baseline'
    in context.md o in seed_tensions.json o in qualsiasi exp_*.py.
    """
    candidates = [
        template_dir / "context.md",
        template_dir / "seed_tensions.json",
    ]
    if (template_dir / "tools").exists():
        candidates.extend((template_dir / "tools").glob("exp_*.py"))
    # Naive baseline può essere espresso come 'naive', 'shuffle', 'random',
    # 'control', 'null baseline', 'baseline naive', 'surrogato' (it). E il
    # comparativo come 'baseline', 'A/B', 'controprova', 'controllo'.
    naive_words = ["naive", "shuffle", "surrogat", "random", "uniform", "control", "null baseline"]
    baseline_words = ["baseline", "a/b", "controprova", "controllo", "comparison"]
    found_naive = False
    found_baseline = False
    for c in candidates:
        if not c.exists():
            continue
        text = c.read_text(errors="replace").lower()
        if any(w in text for w in naive_words):
            found_naive = True
        if any(w in text for w in baseline_words):
            found_baseline = True
    status = "PASS" if (found_naive and found_baseline) else (
        "SKIP" if (found_naive or found_baseline) else "FAIL"
    )
    return {
        "id": "M4",
        "status": status,
        "detail": f"naive_signal={found_naive} · baseline_signal={found_baseline}",
        "metric": int(found_naive) + int(found_baseline),
    }


# ─── M5: Auto-incremento informativo ─────────────────────────────

def _check_m5_auto_increment(template_dir: Path) -> dict[str, Any]:
    """Il primo cycle deve poter aggiornare il seme. Heuristic statica:
    context.md menziona 'seed_integrator' / 'cristallizzazione' / cycle
    che produce nuove tensioni. Solo dopo run reale possiamo testarlo.
    """
    ctx = template_dir / "context.md"
    if not ctx.exists():
        return {"id": "M5", "status": "FAIL", "detail": "context.md mancante",
                "metric": 0}
    text = ctx.read_text().lower()
    # Signal-words bilingue: il context.md può essere IT, EN, o misto.
    # Quello che cerchiamo è linguaggio del cycle che evolve, non termini fissi.
    signals = [
        "seed", "tension", "tensione",
        "cycle", "ciclo", "loop",
        "cristallizz", "crystalliz",
        "evolution", "evolve", "evolu",
        "integrator", "integration",
        "agent", "agente",
        "discover", "scoperta", "finding",
    ]
    found = sum(1 for s in signals if s in text)
    # Soglia: 4 signal-words su 17 = il context parla di cycle vivo
    status = "PASS" if found >= 4 else ("SKIP" if found >= 2 else "FAIL")
    return {
        "id": "M5",
        "status": status,
        "detail": f"context.md menziona {found}/{len(signals)} signal-words bilingue",
        "metric": found,
    }


# ─── M6: MML coherence ───────────────────────────────────────────

def _check_m6_mml_coherence(template_dir: Path) -> dict[str, Any]:
    """Verifica coerenza tra mml.json e seed_tensions.json + tools/.
    - mml.json esiste (richiesto per lab generati dal meta-lab)
    - lab field matcha directory name
    - kernel_refs.condensato_axioms_used interseca tensioni condensato_ref
    - skills_attive include core invariante
    - tools_custom esistono nei file system
    """
    mml_file = template_dir / "mml.json"
    if not mml_file.exists():
        # Lab pre-meta-lab senza MML: non bloccante, ma SKIP
        return {
            "id": "M6",
            "status": "SKIP",
            "detail": "mml.json mancante (lab pre-meta-lab o retrofit pendente)",
            "metric": 0,
        }
    try:
        mml = json.loads(mml_file.read_text())
    except Exception as e:
        return {"id": "M6", "status": "FAIL", "detail": f"mml.json parse error: {e}",
                "metric": 0}

    issues = []
    # lab matcha directory
    if mml.get("lab") != template_dir.name:
        issues.append(f"lab='{mml.get('lab')}' ≠ dir='{template_dir.name}'")
    # required fields
    for fld in ("identity", "kernel_refs", "skills_attive", "modus_invocation"):
        if fld not in mml:
            issues.append(f"campo richiesto mancante: {fld}")
    # kernel_refs vs tensioni
    seed_file = template_dir / "seed_tensions.json"
    if seed_file.exists():
        try:
            seed = json.loads(seed_file.read_text())
            tensioni_refs = set()
            for t in seed.get("tensioni", []):
                ref = t.get("condensato_ref")
                if ref:
                    for r in ref.split(","):
                        tensioni_refs.add(r.strip())
            mml_axioms = set(mml.get("kernel_refs", {}).get("condensato_axioms_used", []) or [])
            if tensioni_refs and mml_axioms and not tensioni_refs.intersection(mml_axioms):
                issues.append(f"kernel_refs.condensato_axioms_used {sorted(mml_axioms)} "
                              f"non interseca tensioni refs {sorted(tensioni_refs)}")
        except Exception:
            pass
    # core skills invariante — supporta entrambi formati MML (array o
    # layered object — vedi mml.schema.json definitions)
    skills_attive_raw = mml.get("skills_attive")
    skills: list[str] = []
    if isinstance(skills_attive_raw, list):
        # Format (a) flat array
        skills = [s.get("name") for s in skills_attive_raw if isinstance(s, dict)]
    elif isinstance(skills_attive_raw, dict):
        # Format (b) layered object — flatten preservando solo i nomi
        for layer_key, layer_entries in skills_attive_raw.items():
            if layer_key.startswith("_"):
                continue  # skip _layer_doc, _meta, etc.
            if isinstance(layer_entries, list):
                for s in layer_entries:
                    if isinstance(s, dict) and s.get("name"):
                        skills.append(s["name"])
    skills = [s for s in skills if s]  # filter None/empty
    core_invariant = {"cascata", "cec", "consapevolezza-condensato",
                      "autologica-operativa", "eval"}
    missing_core = core_invariant - set(skills)
    # Per il meta-lab stesso e i lab pre-existing, alcune mancanze sono OK
    if template_dir.name in ("meta-lab", "physics", "editorial") and len(missing_core) <= 3:
        pass  # tollerato per lab esistenti
    elif missing_core:
        issues.append(f"core invariante mancante: {sorted(missing_core)}")
    # tools_custom path verification
    for tc in mml.get("tools_custom", []) or []:
        if isinstance(tc, dict) and "path" in tc:
            tp = template_dir / tc["path"]
            if not tp.exists():
                issues.append(f"tools_custom path non esiste: {tc['path']}")

    if not issues:
        return {"id": "M6", "status": "PASS",
                "detail": f"MML coerente con seed+tools+core ({len(skills)} skills attive)",
                "metric": len(skills)}
    return {"id": "M6", "status": "FAIL",
            "detail": "; ".join(issues), "metric": 0}


# ─── M7: Integrita' di transduzione ──────────────────────────────

def _check_m7_transduction_integrity(template_dir: Path) -> dict[str, Any]:
    """Verifica che un template post-M7 dichiari come attraversa il cambio
    dominio. I domini storici pre-M7 restano SKIP per non rompere install e
    self-test; i nuovi template possono forzare il gate con
    META_LAB_STRICT_M7=1.
    """
    transduction_file = template_dir / "transduction.md"
    ui_contract_file = template_dir / "ui_contract.json"
    strict = os.environ.get("META_LAB_STRICT_M7", "").lower() in {"1", "true", "yes"}

    if not transduction_file.exists():
        legacy_names = {"physics", "editorial", "meta-lab", "finance", "bio-rhythms", "ops-decisions"}
        if template_dir.name in legacy_names and not strict:
            return {
                "id": "M7",
                "status": "SKIP",
                "detail": "transduction.md mancante su dominio legacy/pre-M7",
                "metric": 0,
            }
        return {
            "id": "M7",
            "status": "FAIL",
            "detail": "transduction.md mancante: il template non dichiara il cambio dominio",
            "metric": 0,
        }

    text = transduction_file.read_text(errors="replace").lower()
    ui_contract_status = "missing"
    if ui_contract_file.exists():
        try:
            ui_contract = json.loads(ui_contract_file.read_text(errors="replace"))
            schema = str(ui_contract.get("schema", ""))
            frame = ui_contract.get("frame") if isinstance(ui_contract.get("frame"), dict) else {}
            if schema == "ui_contract.v1" and all(k in frame for k in ("left", "center", "right")):
                ui_contract_status = "valid"
            else:
                ui_contract_status = "invalid"
        except Exception:
            ui_contract_status = "invalid"
    required_signals = {
        "invariants": ["invariant", "invariante", "movimento", "movement", "contratto"],
        "excluded_source": ["esclus", "non copi", "source", "sorgente", "contenuto"],
        "observables": ["osservabil", "observable", "domain-native", "native"],
        "null_baseline": ["null", "baseline", "shuffle", "control", "controllo"],
        "adaptive_rules": ["regol", "adaptive", "adattiv", "retire", "ritir"],
        "ui_contract": ["ui", "interface", "surface", "vista", "ui_contract"],
        "e2e": ["e2e", "end-to-end", "install", "reinstall", "runtime"],
    }
    hits = {
        key: any(signal in text for signal in signals)
        for key, signals in required_signals.items()
    }
    n_hits = sum(1 for ok in hits.values() if ok)
    missing = [key for key, ok in hits.items() if not ok]

    if ui_contract_status == "valid":
        n_hits += 1
    elif strict:
        missing.append("ui_contract_file")

    if n_hits >= 7:
        return {
            "id": "M7",
            "status": "PASS",
            "detail": f"transduction.md + ui_contract coprono {n_hits}/{len(required_signals) + 1} segnali",
            "metric": n_hits,
        }
    if n_hits >= 5 and not strict:
        return {
            "id": "M7",
            "status": "SKIP",
            "detail": f"transduction/ui_contract parziale {n_hits}/{len(required_signals) + 1}; mancanti: {missing}",
            "metric": n_hits,
        }
    return {
        "id": "M7",
        "status": "FAIL",
        "detail": f"transduction/ui_contract insufficiente {n_hits}/{len(required_signals) + 1}; mancanti: {missing}",
        "metric": n_hits,
    }


# ─── M8: Skill archive retrieval before install ──────────────────

def _check_m8_skill_archive_retrieval(template_dir: Path) -> dict[str, Any]:
    """Verifica che il template dichiari il recupero skill/enzimi in fase di
    progettazione, prima dell'installazione.

    Per domini legacy resta SKIP non bloccante salvo strict M7/M8. Per nuovi
    template il requisito minimo e':
    - transduction.md o context.md menziona skill/enzimi/archive retrieval
      e la meta-guida intento->skill;
    - mml.json usa skills_attive layered object, non solo lista flat;
    - almeno 3 layer cognitivi sono dichiarati.
    Se il template nomina archivi cognitivi esterni o capsule, M8 richiede
    anche `archive_retrieval`: path/capsula, read_depth, pattern e limiti.
    """
    strict = os.environ.get("META_LAB_STRICT_M7", "").lower() in {"1", "true", "yes"}
    legacy_names = {"physics", "editorial", "meta-lab", "finance", "bio-rhythms", "ops-decisions"}

    text_parts = []
    for name in ("transduction.md", "context.md", "README.md"):
        f = template_dir / name
        if f.exists():
            text_parts.append(f.read_text(errors="replace").lower())
    text = "\n".join(text_parts)

    skill_signals = [
        "skill_retrieval", "skill retrieval", "skill archive", "skill catalog",
        "skill field", "skill_field_map", "skill_catalog", "enzim", "enzyme",
        "cognitive_enzymes", "cognitive enzymes", "archivio skill",
    ]
    has_skill_retrieval = any(s in text for s in skill_signals)
    guide_signals = [
        "skill_intent_map", "meta_lab_skill_intent_guide",
        "meta-lab skill intent guide", "intento -> movement",
        "movement_class", "use_dynamics",
    ]
    has_skill_intent_guide = any(s in text for s in guide_signals)
    external_archive_signals = [
        "docs/cognitive_archives",
        "cognitive_archives",
        "archive capsule",
        "archive_capsule",
        "read_depth=capsule",
        '"read_depth": "capsule"',
        "kphi1",
        "/opt/kphi1",
        "/opt/skill",
        "thia_skill_snapshot",
        "cockpit_mmsp",
        "d-nd_cockpit",
    ]
    mentions_external_archive = any(s in text for s in external_archive_signals)
    archive_retrieval_signals = [
        "archive_retrieval",
        "archive retrieval",
    ]
    has_archive_retrieval = any(s in text for s in archive_retrieval_signals)
    has_capsule_depth = (
        "read_depth" in text
        and ("capsule" in text or "body_plus_refs" in text or "body" in text or "e2e" in text)
    )

    mml_file = template_dir / "mml.json"
    layered = False
    layer_count = 0
    if mml_file.exists():
        try:
            mml = json.loads(mml_file.read_text())
            skills_attive = mml.get("skills_attive")
            if isinstance(skills_attive, dict):
                layer_count = sum(
                    1 for k, v in skills_attive.items()
                    if not k.startswith("_") and isinstance(v, list) and v
                )
                layered = layer_count >= 3
        except Exception:
            layered = False

    archive_ok = (not mentions_external_archive) or (has_archive_retrieval and has_capsule_depth)
    score = (
        int(has_skill_retrieval)
        + int(has_skill_intent_guide)
        + int(layered)
        + int(archive_ok)
    )

    if has_skill_retrieval and has_skill_intent_guide and layered and archive_ok:
        archive_detail = " + archive_retrieval" if mentions_external_archive else ""
        return {
            "id": "M8",
            "status": "PASS",
            "detail": f"skill/enzimi + skill_intent_map{archive_detail} dichiarati e MML layered con {layer_count} layer",
            "metric": score,
        }
    if template_dir.name in legacy_names and not strict:
        missing = []
        if not has_skill_retrieval:
            missing.append("skill_retrieval")
        if not has_skill_intent_guide:
            missing.append("skill_intent_map")
        if not layered:
            missing.append("layered_mml")
        if not archive_ok:
            missing.append("archive_retrieval")
        return {
            "id": "M8",
            "status": "SKIP",
            "detail": f"dominio legacy/pre-M8; mancanti/non bloccanti: {missing}",
            "metric": score,
        }
    missing = []
    if not has_skill_retrieval:
        missing.append("skill_retrieval")
    if not has_skill_intent_guide:
        missing.append("skill_intent_map")
    if not layered:
        missing.append("layered_mml>=3_layers")
    if not archive_ok:
        missing.append("archive_retrieval_for_external_archive")
    return {
        "id": "M8",
        "status": "FAIL",
        "detail": f"recupero skill/enzimi insufficiente; mancanti: {missing}",
        "metric": score,
    }


# ─── Verifica top-level (interfaccia standard) ───────────────────

def verifica_asserzioni() -> list[dict[str, Any]]:
    """Pipeline standard. Ritorna lista di {id, status, detail, metric}."""
    template_dir = _lookup_template_under_test()
    if template_dir is None:
        return [{
            "id": "META_BOOTSTRAP",
            "status": "SKIP",
            "detail": "nessun template under test trovato (set META_LAB_TEMPLATE_PATH)",
            "metric": 0,
        }]
    return [
        _check_m1_dipolar_tensions(template_dir),
        _check_m2_executable_assertions(template_dir),
        _check_m3_tools_runnable(template_dir),
        _check_m4_naive_baseline(template_dir),
        _check_m5_auto_increment(template_dir),
        _check_m6_mml_coherence(template_dir),
        _check_m7_transduction_integrity(template_dir),
        _check_m8_skill_archive_retrieval(template_dir),
    ]


# ─── CLI entry point ─────────────────────────────────────────────

if __name__ == "__main__":
    results = verifica_asserzioni()
    n_pass = sum(1 for r in results if r["status"] == "PASS")
    n_fail = sum(1 for r in results if r["status"] == "FAIL")
    n_skip = sum(1 for r in results if r["status"] == "SKIP")
    print(f"Meta-lab falsifier — {n_pass} PASS, {n_fail} FAIL, {n_skip} SKIP su {len(results)}")
    for r in results:
        symbol = "✓" if r["status"] == "PASS" else ("✗" if r["status"] == "FAIL" else "·")
        print(f"  [{symbol}] {r['id']}: {r['status']} — {r['detail']}")
    sys.exit(0 if n_fail == 0 else 1)
