"""exp_regenerate_physics.py — Primo test del meta-lab: rigenerare physics.

Falsifier oggettivo del meta-lab: dato il corpus interno (memoria
operatore + esperienza accumulata + condensato D-ND), il meta-lab agent
produce un seme cognitivo per il dominio "physics". Lo confrontiamo
con domains/physics/ esistente.

Tre esiti:
1. **STRUCTURAL_MATCH** — il seme rigenerato corrisponde sostantivamente
   all'originale (tensioni equivalenti, assiomi proiettati gli stessi,
   assertions coprono A1-A5+F1+C1-C3+G1+G2). Meta-lab valido.
2. **STRUCTURAL_DIVERGENCE** — il seme rigenerato è diverso. Cristallizza:
   forse il meta-lab vede physics in modo nuovo, o forse il context.md
   del meta-lab non è ben calibrato.
3. **STRUCTURAL_LOSS** — il seme rigenerato manca di proprietà fondamentali
   del physics originale. Meta-lab buggy o corpus insufficiente.

Questo script NON invoca un agent LLM (sarebbe un cycle vero del meta-lab).
Quello che fa qui è preparare la **specifica di test**: il prompt e il
ground truth, in modo che quando l'agent del meta-lab gira, abbia
un riferimento contro cui confrontarsi.

Uso:
    python exp_regenerate_physics.py [--report]
        --report: solo emette ground truth strutturato in stdout (no exec).

Quando il meta-lab cycle vero gira, l'agent legge questa spec come
istruzione iniziale del primo cycle.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _domains_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_physics_ground_truth() -> dict[str, Any]:
    """Estrae il ground truth strutturale dal lab physics esistente."""
    physics = _domains_root() / "physics"
    if not physics.exists():
        raise FileNotFoundError("domains/physics/ non trovato")

    seed = json.loads((physics / "seed_tensions.json").read_text())
    config = json.loads((physics / "config.json").read_text())
    cat = json.loads((physics / "tension_to_category.json").read_text())

    # Estrai signature del context.md (contare topic, non testo letterale)
    ctx_text = (physics / "context.md").read_text()

    # Conta funzioni di test in assertions.py
    import re
    assertions_text = (physics / "assertions.py").read_text()
    test_fns = re.findall(r"^def\s+(_?test_\w+)\s*\(", assertions_text, re.MULTILINE)

    # Estrai tutti i condensato_ref usati nelle tensioni
    refs = set()
    for t in seed.get("tensioni", []):
        ref = t.get("condensato_ref")
        if ref:
            for r in ref.split(","):
                refs.add(r.strip())

    return {
        "domain_slug": "physics",
        "title": config.get("title"),
        "version": config.get("version"),
        "n_tensioni_iniziali": len(seed.get("tensioni", [])),
        "tensioni_ids": [t.get("id") for t in seed.get("tensioni", [])],
        "tensioni_tipi": list(set(t.get("tipo") for t in seed.get("tensioni", []))),
        "condensato_refs_usati": sorted(refs),
        "n_categories": len(cat.get("categories", {})),
        "category_labels": [c.get("label") for c in cat.get("categories", {}).values()],
        "n_test_functions": len(test_fns),
        "test_function_names": test_fns,
        "context_md_length": len(ctx_text),
        "context_md_signal_words": _count_signal_words(ctx_text),
    }


def _count_signal_words(text: str) -> dict[str, int]:
    """Conta signal-words D-ND nel testo (per confronto strutturale)."""
    text_lower = text.lower()
    signals = [
        "phi", "f(x)", "det", "dipolo", "matrice", "punto fisso",
        "cycle", "tensione", "scoperta", "assioma", "falsifier",
        "cimitero", "naive", "baseline", "condensato",
    ]
    return {s: text_lower.count(s) for s in signals}


def build_regeneration_spec() -> dict[str, Any]:
    """Costruisce la spec del test: cosa l'agent meta-lab deve produrre."""
    ground_truth = _read_physics_ground_truth()

    spec = {
        "task": "regenerate_physics_seed",
        "description": (
            "Primo test del meta-lab: dato il corpus interno del sistema "
            "(memoria + esperienza + condensato D-ND), produrre un seme "
            "cognitivo per il dominio 'physics' equivalente all'originale."
        ),
        "input": {
            "domain_slug": "physics",
            "domain_request": (
                "Rigenera il seme cognitivo per il lab di matematica/fisica "
                "fondamentale del sistema D-ND. Concentrati su: prime gaps, "
                "dynamics di Markov, struttura dipolare, punti fissi relazionali, "
                "teoria crossing TQGE+R."
            ),
            "corpus_paths": [
                "/opt/MM_D-ND/CONDENSATO.md",
                "/opt/MM_D-ND/KERNEL_SEED.md",
                "/opt/MM_D-ND/method/DND_METHOD_AXIOMS.md",
            ],
            "reference_domain": "physics",
        },
        "expected_structure": {
            "n_tensioni_iniziali_min": max(3, ground_truth["n_tensioni_iniziali"] - 2),
            "n_tensioni_iniziali_max": ground_truth["n_tensioni_iniziali"] + 3,
            "must_reference_axioms": ground_truth["condensato_refs_usati"],
            "expected_tipi": ground_truth["tensioni_tipi"],
            "n_test_functions_min": max(5, ground_truth["n_test_functions"] - 1),
            "expected_signals_present": [
                s for s, c in ground_truth["context_md_signal_words"].items() if c >= 2
            ],
        },
        "ground_truth_signature": ground_truth,
        "scoring": {
            "M1_dipolar_tensions": "75%+ tensioni con condensato_ref",
            "M2_executable_assertions": "≥3 _test_ functions importable",
            "M3_tools_runnable": "exp_*.py senza GPU/network deps",
            "M4_naive_baseline": "naive_signal AND baseline_signal in context",
            "M5_auto_increment": "≥4/18 signal-words bilingue in context",
            "STRUCTURAL_MATCH_threshold": (
                "M1+M2+M5 PASS AND condensato_refs ⊇ {A2, A10}"
            ),
        },
    }
    return spec


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--report", action="store_true",
                    help="emette ground truth strutturato in stdout (no exec test)")
    ap.add_argument("--out", default=None,
                    help="scrive spec in JSON al path indicato")
    args = ap.parse_args()

    spec = build_regeneration_spec()

    if args.report:
        print(json.dumps(spec["ground_truth_signature"], indent=2, ensure_ascii=False))
        return

    output = json.dumps(spec, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"spec scritta in {args.out}")
    else:
        print(output)


if __name__ == "__main__":
    main()
