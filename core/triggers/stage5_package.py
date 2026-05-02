#!/usr/bin/env python3
"""stage5_package — Stage 5 SSP: PoC PASS → pacchetto Python installabile.

Differenza con Stage 4:
  - Stage 4 dimostra empiricamente il finding (poc.py + verification.json)
  - Stage 5 trasforma il PoC in modulo pubblicabile: setup.py, package code
    organizzato, tests, README con esempio, LICENSE, CHANGELOG.

Strategia (come Stage 4 — claude-cli OAuth scrive i file via Write tool):
  1. Carica product dir (deve avere verification.json verdict=PASS)
  2. claude-cli legge poc.py + manifest + verification + use_case e
     scrive i file del package nella sotto-dir package/
  3. Stage 5 runner verifica: package importable + tests pass
  4. Verdict: PACKAGED / INCOMPLETE / FAILED

Output (in LAB_DATA_DIR/<dom>/prodotti/<id>/package/):
  pyproject.toml              — metadata + build config
  src/<package_name>/__init__.py
  src/<package_name>/kernel.py        — codice estratto da poc.py refactored
  src/<package_name>/prompt_template.md  — prompt versionato (per type=kernel)
  tests/test_kernel.py        — test minimi (smoke + verification re-run)
  README.md                   — what/why/how, esempio, link al lab
  LICENSE                     — MIT default (override via env STAGE5_LICENSE)
  CHANGELOG.md                — entry iniziale con discovery_cycle_ts

Usage:
  stage5_package.py <product_id> [--use-case "..."] [--license MIT]
  stage5_package.py <cycle_ts> --auto    # primo product PASS del cycle
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _resolve_paths(domain: str | None = None) -> dict[str, Path]:
    lab_data = Path(os.environ.get("LAB_DATA_DIR", "/opt/D-ND_LAB/data"))
    dom = domain or os.environ.get("DOMAIN", "physics")
    domain_dir = lab_data / dom
    return {
        "domain": dom,
        "lab_data": lab_data,
        "domain_dir": domain_dir,
        "prodotti": domain_dir / "prodotti",
    }


_PATHS = _resolve_paths()


def find_product_dir(product_id: str) -> Path:
    p = _PATHS["prodotti"] / product_id
    if not p.is_dir():
        raise FileNotFoundError(f"Product {product_id} non trovato sotto {_PATHS['prodotti']}")
    return p


def find_first_pass_product(cycle_ts: str) -> Path:
    """Auto: primo product del cycle con verdict PASS."""
    matches = sorted(_PATHS["prodotti"].glob(f"{cycle_ts}_*"))
    if not matches:
        raise FileNotFoundError(f"Nessun product per cycle_ts={cycle_ts}")
    for p in matches:
        v = p / "verification.json"
        if not v.exists():
            continue
        try:
            data = json.loads(v.read_text())
            if data.get("verdict") == "PASS" or data.get("status") == "PASS":
                return p
        except (json.JSONDecodeError, OSError):
            continue
    raise ValueError(f"Nessun product con verdict=PASS per cycle_ts={cycle_ts}")


def load_product(prod_dir: Path) -> dict:
    manifest = json.loads((prod_dir / "manifest.json").read_text())
    verification = json.loads((prod_dir / "verification.json").read_text())
    poc_code = (prod_dir / "poc.py").read_text()
    return {
        "manifest": manifest,
        "verification": verification,
        "poc_code": poc_code,
        "prod_dir": str(prod_dir),
    }


def slugify_package_name(name: str) -> str:
    """Package Python name: lowercase, no special chars, underscore separator."""
    n = re.sub(r"[^a-z0-9_]+", "_", name.lower())
    n = re.sub(r"_+", "_", n).strip("_")
    # Python identifier: must start with letter
    if n and n[0].isdigit():
        n = "_" + n
    return n[:60] or "dnd_kernel"


def _claude_cli_available() -> bool:
    try:
        r = subprocess.run(["claude", "--version"], capture_output=True, timeout=5)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


PROMPT_TEMPLATE = """Sei un ricercatore D-ND. Hai un PoC verificato (Stage 4 PASS) e devi \
trasformarlo in pacchetto Python installabile (Stage 5 SSP).

CONTESTO PRODOTTO
=================
Product ID: {product_id}
Type: {product_type}                  # library / kernel / demo
Discovery cycle: {discovery_cycle_ts}
Finding: {finding_title}

Verdict Stage 4: {verdict}
Metriche A/B:
  naive_score:    {naive_score}
  informed_score: {informed_score}
  delta:          {delta} (+{delta_pp}pp informed - naive)
  n_trials:       {n_trials}

Use case (operatore): {use_case}

PoC verificato (poc.py, {poc_lines} righe):
```python
{poc_excerpt}
```

VINCOLI DEL PACKAGE
===================
Package name: {package_name}
License: {license}
Version: 0.1.0

Genera questi file nella directory `{package_dir}` usando il tool Write:

1. `{package_dir}/pyproject.toml`
   - Build system: setuptools >= 68, build-backend = "setuptools.build_meta"
     (NON usare "setuptools.backends._legacy:_Backend" — non è API valida.
     Usa esattamente "setuptools.build_meta" come stringa, PEP 517 standard.)
   - Project metadata: name={package_name}, version=0.1.0, license={license}
   - Description sintetica (1 riga)
   - Authors: D-ND_LAB (auto)
   - URL repo: github.com/GrazianoGuiducci/D-ND_LAB
   - Python: >=3.10
   - Dependencies: solo stdlib se possibile (il PoC usa solo stdlib)
   - [tool.setuptools.packages.find] where = ["src"]

2. `{package_dir}/src/{package_name}/__init__.py`
   - Esporta le funzioni principali del kernel
   - __version__ = "0.1.0"

3. `{package_dir}/src/{package_name}/kernel.py`
   - Codice estratto da poc.py, refactored come libreria riusabile
   - Niente codice "if __name__ == '__main__'" — solo funzioni esportabili
   - method_naive(...) e method_informed(...) restano API pubbliche
   - Aggiungi una funzione di alto livello (es. KernelD_ND class) che
     incapsula uso pratico

4. `{package_dir}/src/{package_name}/prompt_template.md`     [SOLO se type=kernel]
   - Il prompt template versionato che incarna il modus del finding
   - Sezioni: ROLE, RULES (matrice di transizione strutturale del finding),
     INPUT, OUTPUT, EXAMPLES (1-2 mini esempi)

5. `{package_dir}/tests/test_kernel.py`
   - Almeno 2 test unittest:
     a) test_smoke: import + esecuzione method_informed senza errori
     b) test_informed_beats_naive: rerun A/B su sample piccolo, assert
        delta > 0 (replica del verdict Stage 4 a scala ridotta, deterministico)

6. `{package_dir}/README.md`
   - Title: {package_name}
   - 1 paragrafo: cosa fa, perché funziona (cita il finding)
   - Section "Use case": il use_case dichiarato dall'operatore
   - Section "Install": `pip install -e .` (locale per ora)
   - Section "Quick start": esempio Python in 5 righe
   - Section "Verification": replica delle metriche Stage 4 (delta, n_trials)
   - Section "License" + Section "Lineage" (link al cycle, lab D-ND)

7. `{package_dir}/LICENSE`
   - {license} testo standard

8. `{package_dir}/CHANGELOG.md`
   - 0.1.0 ({date}): Initial package from cycle {discovery_cycle_ts}
     Stage 4 verdict PASS, delta=+{delta_pp}pp.
     Use case: {use_case_short}.

REGOLE
======
- Niente network call nel codice runtime
- Niente subprocess, niente filesystem fuori da CWD del package
- Tests devono essere riproducibili (seed fissi)
- README onesto: cita il limite operativo ('verificato su {n_trials} trial,
  generalizzazione a domini diversi richiede re-verifica')
- Output: solo file. Quando hai finito, rispondi solo 'DONE'.
"""


def generate_package(prompt: str, package_dir: Path, max_turns: int = 12,
                     timeout: int = 600) -> tuple[bool, str]:
    """Lancia claude-cli con Write-only allowed per generare i file del package."""
    if not _claude_cli_available():
        raise RuntimeError("claude-cli non disponibile — Stage 5 richiede OAuth claude")

    full_prompt = prompt + (
        "\n\nISTRUZIONE FINALE: usa SOLO il tool Write per creare i file richiesti "
        f"sotto `{package_dir}`. NON eseguire Bash, NON leggere altri file, "
        "NON usare Edit. Quando hai scritto tutti i file, rispondi solo 'DONE'."
    )
    cmd = [
        "claude", "-p", full_prompt,
        "--max-turns", str(max_turns),
        "--permission-mode", "acceptEdits",
        "--allowedTools", "Write",
        "--add-dir", str(package_dir),
    ]
    print(f"  invoking claude-cli (max-turns={max_turns}, timeout={timeout}s, allowed=Write only)")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT dopo {timeout}s"
    if r.returncode != 0:
        return False, f"claude-cli rc={r.returncode} stderr={r.stderr[:500]}"
    return True, r.stdout[:2000]


def verify_package(package_dir: Path) -> tuple[str, list[str], dict]:
    """Verifica: file presenti + import OK + tests pass.

    Ritorna (verdict, issues, details).
    Verdict: PACKAGED | INCOMPLETE | FAILED
    """
    issues = []
    expected_files = [
        "pyproject.toml",
        "README.md",
        "LICENSE",
        "CHANGELOG.md",
    ]
    for f in expected_files:
        if not (package_dir / f).exists():
            issues.append(f"missing: {f}")

    src_dir = package_dir / "src"
    pkg_dirs = [d for d in src_dir.iterdir() if d.is_dir()] if src_dir.exists() else []
    if not pkg_dirs:
        issues.append("missing: src/<package>/ directory")
        return "FAILED", issues, {}
    pkg_dir = pkg_dirs[0]
    pkg_name = pkg_dir.name

    if not (pkg_dir / "__init__.py").exists():
        issues.append(f"missing: src/{pkg_name}/__init__.py")
    if not (pkg_dir / "kernel.py").exists():
        issues.append(f"missing: src/{pkg_name}/kernel.py")

    tests_dir = package_dir / "tests"
    test_files = list(tests_dir.glob("test_*.py")) if tests_dir.exists() else []
    if not test_files:
        issues.append("missing: tests/test_*.py")

    # Try import via subprocess + PYTHONPATH (pattern equivalente a `pip install -e .`).
    # Niente spec_from_file_location: rompe gli import relativi `from .kernel import ...`
    # perché non setta __package__ correttamente.
    import_ok = False
    import_error = None
    try:
        r = subprocess.run(
            [sys.executable, "-c", f"import {pkg_name}; print('ok', getattr({pkg_name}, '__version__', '?'))"],
            capture_output=True, text=True, timeout=15,
            env={**os.environ, "PYTHONPATH": str(package_dir / "src")},
        )
        if r.returncode == 0 and "ok" in r.stdout:
            import_ok = True
        else:
            import_error = (r.stderr or r.stdout)[:300]
            issues.append(f"import failed: {import_error}")
    except subprocess.TimeoutExpired:
        import_error = "import timeout"
        issues.append(import_error)

    # Try running tests via unittest discover
    tests_ok = None
    tests_output = ""
    if test_files and import_ok:
        try:
            r = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", str(tests_dir), "-v"],
                capture_output=True, text=True, timeout=60,
                env={**os.environ, "PYTHONPATH": str(package_dir / "src")},
            )
            tests_output = (r.stdout + r.stderr)[:2000]
            tests_ok = r.returncode == 0
            if not tests_ok:
                issues.append(f"tests failed (rc={r.returncode})")
        except subprocess.TimeoutExpired:
            issues.append("tests timeout (>60s)")
            tests_ok = False

    details = {
        "package_name": pkg_name,
        "import_ok": import_ok,
        "import_error": import_error,
        "tests_found": len(test_files),
        "tests_ok": tests_ok,
        "tests_output_excerpt": tests_output[-800:] if tests_output else "",
        "files_found": sorted([str(f.relative_to(package_dir)) for f in package_dir.rglob("*") if f.is_file()]),
    }

    if not issues:
        return "PACKAGED", [], details
    if import_ok and (tests_ok is True):
        # File mancanti ma core funziona — INCOMPLETE
        return "INCOMPLETE", issues, details
    return "FAILED", issues, details


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="product_id OPPURE cycle_ts (con --auto)")
    ap.add_argument("--auto", action="store_true",
                    help="Se target è un cycle_ts, seleziona il primo product PASS")
    ap.add_argument("--use-case", default="kernel cognitivo D-ND riusabile in altri domini",
                    help="Use case dichiarato dall'operatore (entra in README + CHANGELOG)")
    ap.add_argument("--license", default="MIT", choices=["MIT", "Apache-2.0", "BSD-3-Clause"])
    ap.add_argument("--package-name", default=None,
                    help="Override package name (default: auto da finding title)")
    ap.add_argument("--domain", default=None)
    ap.add_argument("--max-turns", type=int, default=12)
    ap.add_argument("--gen-timeout", type=int, default=600)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if args.domain:
        global _PATHS
        _PATHS = _resolve_paths(args.domain)

    print(f"stage5_package target={args.target} domain={_PATHS['domain']}")

    # Resolve product
    if args.auto:
        prod_dir = find_first_pass_product(args.target)
        print(f"  auto-selected: {prod_dir.name}")
    else:
        prod_dir = find_product_dir(args.target)

    product = load_product(prod_dir)
    manifest = product["manifest"]
    verification = product["verification"]

    if verification.get("verdict") != "PASS" and verification.get("status") != "PASS":
        print(f"  ERROR: product verdict != PASS (got {verification.get('verdict')}). "
              f"Stage 5 packaging riservato a prodotti verificati.", file=sys.stderr)
        return 2

    # Compute package name
    if args.package_name:
        pkg_name = slugify_package_name(args.package_name)
    else:
        # Default: dnd_<type>_<short_slug>
        finding_title = manifest.get("discovery_finding_title", "")
        short = re.sub(r"[^a-z0-9]+", "_", finding_title.lower())[:30].strip("_")
        pkg_name = slugify_package_name(f"dnd_{manifest.get('type','kernel')}_{short}")
    print(f"  package name: {pkg_name}")

    package_dir = prod_dir / "package"
    if package_dir.exists() and not args.force:
        print(f"  SKIP {package_dir} (esiste, --force per riesecuzione)")
        return 0
    package_dir.mkdir(parents=True, exist_ok=True)

    # Build prompt
    poc_code = product["poc_code"]
    poc_lines = poc_code.count("\n") + 1
    poc_excerpt = poc_code[:6000] + ("\n# ... (truncated)" if len(poc_code) > 6000 else "")

    metrics = verification.get("metrics", {})
    delta = float(metrics.get("delta", 0))

    prompt = PROMPT_TEMPLATE.format(
        product_id=manifest.get("id", prod_dir.name),
        product_type=manifest.get("type", "kernel"),
        discovery_cycle_ts=manifest.get("discovery_cycle_ts", "?"),
        finding_title=manifest.get("discovery_finding_title", "?"),
        verdict=verification.get("verdict", "?"),
        naive_score=metrics.get("naive_score"),
        informed_score=metrics.get("informed_score"),
        delta=delta,
        delta_pp=round(delta * 100, 2),
        n_trials=metrics.get("n_trials", "?"),
        use_case=args.use_case,
        use_case_short=args.use_case[:80],
        poc_lines=poc_lines,
        poc_excerpt=poc_excerpt,
        package_name=pkg_name,
        package_dir=str(package_dir),
        license=args.license,
        date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    )
    (package_dir / "_prompt.txt").write_text(prompt)
    print(f"  prompt: {len(prompt)} chars (saved → _prompt.txt)")

    # Generate via claude-cli
    started_at = datetime.now(timezone.utc)
    ok, out = generate_package(prompt, package_dir,
                                max_turns=args.max_turns, timeout=args.gen_timeout)
    if not ok:
        print(f"  ERROR generating package: {out[:500]}", file=sys.stderr)
        (package_dir / "_stage5_error.txt").write_text(f"GENERATION FAILED:\n{out}\n")
        return 3
    finished_at = datetime.now(timezone.utc)

    # Verify
    print(f"  generation OK ({(finished_at - started_at).total_seconds():.1f}s)")
    print(f"  verifying package...")
    verdict, issues, details = verify_package(package_dir)

    print(f"  verdict: {verdict}")
    if issues:
        for issue in issues[:10]:
            print(f"    · {issue}")

    # Write stage5_verification.json
    stage5_v = {
        "schema_version": "0.1",
        "stage": 5,
        "stage_name": "package_runner",
        "verdict": verdict,
        "package_name": pkg_name,
        "license": args.license,
        "use_case": args.use_case,
        "issues": issues,
        "details": details,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_s": round((finished_at - started_at).total_seconds(), 2),
    }
    (package_dir / "stage5_verification.json").write_text(json.dumps(stage5_v, indent=2))

    print(f"DONE → {package_dir}")
    print(f"  package: {pkg_name}")
    print(f"  files: pyproject.toml, src/{pkg_name}/, tests/, README.md, LICENSE, CHANGELOG.md")
    print(f"  install (locale): pip install -e {package_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
