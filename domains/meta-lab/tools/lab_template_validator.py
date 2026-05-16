"""lab_template_validator.py — CLI front-end del falsifier meta-lab.

Applica le meta-lenti M1-M7 (definite in domains/meta-lab/assertions.py)
a un template di lab dato come path. Invocabile da:
- pipeline lab_agent.sh (validation post-generazione)
- operatore in CLI (verifica manuale di un template prima dell'install)
- meta-lab agent stesso (auto-check su template appena prodotto)

Uso:
    python lab_template_validator.py <template_dir>
    python lab_template_validator.py --self-test   # gira su domains/physics/
    python lab_template_validator.py --strict-m7 <template_dir>

Exit code: 0 se nessun M_x è FAIL, 1 altrimenti.
Output: JSON con verdict + dettaglio ogni lente.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _meta_lab_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("template_dir", nargs="?", help="path al template da validare")
    ap.add_argument("--self-test", action="store_true",
                    help="gira il falsifier meta su domains/physics/ come ground truth")
    ap.add_argument("--strict-m7", action="store_true",
                    help="rende M7 bloccante anche per template legacy senza transduction.md")
    ap.add_argument("--json", action="store_true", help="output JSON pulito (no testo umano)")
    args = ap.parse_args()

    if args.self_test:
        physics = _meta_lab_dir().parent / "physics"
        if not physics.exists():
            print("self-test: domains/physics/ non trovato", file=sys.stderr)
            sys.exit(2)
        target = physics
    elif args.template_dir:
        target = Path(args.template_dir).resolve()
        if not target.exists():
            print(f"path non esistente: {target}", file=sys.stderr)
            sys.exit(2)
    else:
        ap.print_help()
        sys.exit(2)

    # Inietta path nel modulo assertions del meta-lab
    os.environ["META_LAB_TEMPLATE_PATH"] = str(target)
    if args.strict_m7:
        os.environ["META_LAB_STRICT_M7"] = "1"
    sys.path.insert(0, str(_meta_lab_dir()))
    import assertions  # type: ignore

    results = assertions.verifica_asserzioni()

    n_pass = sum(1 for r in results if r.get("status") == "PASS")
    n_fail = sum(1 for r in results if r.get("status") == "FAIL")
    n_skip = sum(1 for r in results if r.get("status") == "SKIP")

    # Verdict del meta-falsifier:
    # - 0 FAIL e ≥3 PASS → TEMPLATE_VALID
    # - 0 FAIL e <3 PASS (molti SKIP) → TEMPLATE_NEEDS_REFINEMENT
    # - ≥1 FAIL → DOMAIN_NOT_OF_LEVERAGE (o template buggy)
    if n_fail == 0 and n_pass >= 3:
        verdict = "TEMPLATE_VALID"
    elif n_fail == 0:
        verdict = "TEMPLATE_NEEDS_REFINEMENT"
    else:
        verdict = "DOMAIN_NOT_OF_LEVERAGE"

    output = {
        "target": str(target),
        "verdict": verdict,
        "summary": {"pass": n_pass, "fail": n_fail, "skip": n_skip, "total": len(results)},
        "lenses": results,
    }

    if args.json:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(f"Meta-falsifier su {target.name}: {verdict}")
        print(f"  {n_pass} PASS · {n_fail} FAIL · {n_skip} SKIP su {len(results)} lenti")
        for r in results:
            status = r.get("status", "?")
            symbol = "✓" if status == "PASS" else ("✗" if status == "FAIL" else "·")
            print(f"  [{symbol}] {r.get('id'):4s} {status:4s} — {r.get('detail', '')}")

    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
