#!/usr/bin/env python3
"""stage4_poc_runner — Stage 4 SSP: PoC empirico A/B + verification reale.

Chiude il loop scoperta → prodotto. Differenza con Stage 2 (designer):
  - Stage 2: scaffold dichiarativo, status SPEC_ONLY, [TARGET] ovunque
  - Stage 4: codice eseguito, metriche reali, verdict PASS/FAIL/INCONCLUSIVE

Strategia (zero template hardcoded — claude-cli scrive il PoC):
  1. Carica manifest.draft.json del candidate
  2. Carica agent report + verification_spec
  3. claude-cli genera poc.py con baseline naive vs method informed-by-finding
  4. Eseguo poc.py con timeout, cattura metrics.json prodotto dallo script
  5. Confronta metrics vs success_criteria / falsification_criteria
  6. Scrive prodotti/<id>/{poc.py, poc.log, metrics.json, verification.json,
                          manifest.json}
  7. Verdict: PASS, FAIL, INCONCLUSIVE

Usage:
  stage4_poc_runner.py <cycle_ts> <finding_idx> [--candidate-type library|kernel|demo]
  stage4_poc_runner.py <cycle_ts> --auto    # primo applicative_finding eligible
"""
from __future__ import annotations

import argparse
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
        "reports": domain_dir / "reports",
        "scoperte": domain_dir / "scoperte",
        "soluzioni": domain_dir / "soluzioni",
        "prodotti": domain_dir / "prodotti",
    }


_PATHS = _resolve_paths()


def find_manifest(cycle_ts: str) -> tuple[Path, dict]:
    soluzioni = _PATHS["soluzioni"]
    matches = list(soluzioni.glob(f"{cycle_ts}_*"))
    if not matches:
        raise FileNotFoundError(f"Nessuna soluzione per cycle_ts={cycle_ts} sotto {soluzioni}")
    manifest_path = matches[0] / "manifest.draft.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest.draft.json mancante: {manifest_path} — esegui application_designer.py prima")
    return manifest_path, json.loads(manifest_path.read_text())


def find_candidate(manifest: dict, finding_idx: int, candidate_type: str | None) -> dict:
    candidates = manifest.get("applications_candidate", [])
    if not candidates:
        raise ValueError("manifest senza applications_candidate (pre_discovery/transitional?)")
    matches = [c for c in candidates if c.get("discovery_finding_idx") == finding_idx]
    if candidate_type:
        matches = [c for c in matches if c.get("type") == candidate_type]
    if not matches:
        raise ValueError(f"Nessun candidate finding_idx={finding_idx} type={candidate_type} nel manifest")
    return matches[0]


def find_first_eligible(cycle_ts: str) -> tuple[int, str]:
    """Auto: primo finding con application_eligible=True dal finding_index."""
    soluzioni = _PATHS["soluzioni"]
    matches = list(soluzioni.glob(f"{cycle_ts}_*"))
    if not matches:
        raise FileNotFoundError(f"Nessuna soluzione per cycle_ts={cycle_ts}")
    eligibility = matches[0] / "finding_index.draft.json"
    if not eligibility.exists():
        raise FileNotFoundError(f"finding_index.draft.json mancante — esegui finding_eligibility_gate.py prima")
    idx = json.loads(eligibility.read_text())
    eligible = [f for f in idx.get("findings", []) if f.get("application_eligible") is True]
    if not eligible:
        raise ValueError(f"cycle {cycle_ts}: nessun applicative_finding eligible (review_required={sum(1 for f in idx['findings'] if f['application_eligible']=='REVIEW_REQUIRED')}, skip={sum(1 for f in idx['findings'] if f['application_eligible'] is False)})")
    return eligible[0]["finding_id"], eligible[0]["title"]


def slugify(text: str) -> str:
    t = re.sub(r"[^\w\s-]", "", text.lower())
    t = re.sub(r"[\s_]+", "-", t)
    t = re.sub(r"-+", "-", t).strip("-")
    return "-".join(t.split("-")[:6])


PROMPT_TEMPLATE = """Sei un ricercatore D-ND. Devi scrivere uno script Python autonomo che testa empiricamente \
un finding del lab tramite confronto A/B (metodo naive vs metodo informato dal finding).

CONTESTO DELLA SCOPERTA
=======================
Cycle: {cycle_ts}
Domain: {domain}

Finding (#{finding_idx}): {finding_title}

Excerpt dal report:
{finding_excerpt}

Verdict del cycle:
{verdict}

CANDIDATE APPLICATION
=====================
Tipo: {candidate_type}
Nome: {candidate_name}
Cosa dovrebbe fare: {candidate_what}

Verification spec (success/falsification criteria):
{verification_spec}

VINCOLI DELLO SCRIPT
====================
1. Scrivi UN SOLO file Python autonomo (no import locali, solo stdlib + opzionalmente numpy se serve).
2. Lo script DEVE definire due funzioni: `method_naive(...)` e `method_informed(...)`.
3. Lo script DEVE produrre alla fine `metrics.json` nella CWD con questa struttura minima:
   {{
     "naive_score": <float>,        // accuracy / performance del baseline
     "informed_score": <float>,     // accuracy / performance del metodo informato dal finding
     "delta": <float>,              // informed - naive (positivo = informed wins)
     "n_trials": <int>,             // numero di trial nel test
     "details": {{...}}              // qualunque dettaglio aggiuntivo (timing, p-value, ecc.)
   }}
4. Tempo di esecuzione MAX 60 secondi. Usa N piccolo se serve (1k-100k campioni, non 1M).
5. NESSUN network call, NESSUN filesystem access fuori da CWD, NESSUN subprocess.
6. Se il finding non è testabile via A/B (es. è un negative_result), scrivi metrics.json con
   `naive_score=0, informed_score=0, delta=0, details.untestable=true, details.reason="..."`.
7. Output finale: solo il codice Python, niente markdown fences, niente prefazioni, niente commenti finali.

REGOLA SCIENTIFICA
==================
Sii onesto. Se il metodo informato non batte il naive, scrivilo. Falsification è un risultato valido.
Lo scopo NON è dimostrare il finding ma testarlo. Se serve dato sintetico, generane in modo riproducibile (seed fissi).

Scrivi ora lo script Python."""


def _claude_cli_available() -> bool:
    try:
        r = subprocess.run(["claude", "--version"], capture_output=True, timeout=5)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def generate_poc_script(prompt: str, target_dir: Path, max_turns: int = 8, timeout: int = 300) -> str:
    """Chiama claude-cli per generare poc.py SCRIVENDOLO nella target_dir.

    Pattern lab_agent.sh: claude usa Write tool per scrivere poc.py in target_dir.
    Niente esecuzione (Bash disabilitato). Più affidabile di "rispondi solo testo"
    perché claude ha bisogno di turni iterativi per output lunghi senza tool.
    """
    if not _claude_cli_available():
        raise RuntimeError("claude-cli non disponibile — Stage 4 richiede OAuth claude")
    target_path = target_dir / "poc.py"
    # Aggiungi istruzione esplicita per Write
    full_prompt = (
        prompt + "\n\n" +
        "ISTRUZIONE FINALE: usa il tool Write per creare il file `" + str(target_path) + "` "
        "con il codice Python richiesto. NON eseguire Bash, NON leggere altri file, "
        "scrivi solo poc.py. Quando hai finito, rispondi solo 'DONE'."
    )
    # Solo Write — niente Bash, Edit, Read, ecc.
    allowed = "Write"
    cmd = [
        "claude", "-p", full_prompt,
        "--max-turns", str(max_turns),
        "--allowedTools", allowed,
        "--permission-mode", "acceptEdits",
        "--add-dir", str(target_dir),
    ]
    print(f"  invoking claude-cli (max-turns={max_turns}, timeout={timeout}s, allowed=Write only)...")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"claude-cli failed (rc={r.returncode}): {r.stderr[:800]}")
    if not target_path.exists():
        raise RuntimeError(
            f"claude-cli completed (rc=0) ma {target_path} non è stato scritto. "
            f"stdout tail: {r.stdout[-500:]!r}"
        )
    code = target_path.read_text()
    if len(code) < 200:
        raise RuntimeError(f"poc.py troppo corto ({len(code)} chars) — likely incomplete")
    return code


def execute_poc(poc_path: Path, cwd: Path, timeout: int = 90) -> tuple[bool, str, dict | None]:
    """Esegue poc.py in cwd con timeout. Ritorna (ok, log, metrics)."""
    log_lines = [f"[stage4] executing {poc_path} in {cwd}"]
    try:
        r = subprocess.run(
            [sys.executable, str(poc_path)],
            cwd=str(cwd),
            capture_output=True, text=True,
            timeout=timeout,
        )
        log_lines.append(f"[stage4] exit code: {r.returncode}")
        log_lines.append(f"[stage4] stdout (first 4KB):\n{r.stdout[:4096]}")
        if r.stderr:
            log_lines.append(f"[stage4] stderr (first 4KB):\n{r.stderr[:4096]}")
        if r.returncode != 0:
            return False, "\n".join(log_lines), None
    except subprocess.TimeoutExpired:
        log_lines.append(f"[stage4] TIMEOUT after {timeout}s")
        return False, "\n".join(log_lines), None
    metrics_path = cwd / "metrics.json"
    if not metrics_path.exists():
        log_lines.append(f"[stage4] metrics.json NON prodotto")
        return False, "\n".join(log_lines), None
    try:
        metrics = json.loads(metrics_path.read_text())
    except json.JSONDecodeError as e:
        log_lines.append(f"[stage4] metrics.json non parseable: {e}")
        return False, "\n".join(log_lines), None
    log_lines.append(f"[stage4] metrics.json OK: naive={metrics.get('naive_score')}, informed={metrics.get('informed_score')}, delta={metrics.get('delta')}")
    return True, "\n".join(log_lines), metrics


def compute_verdict(metrics: dict, verification_spec: dict) -> tuple[str, str, list[str]]:
    """Confronta metrics vs success/falsification criteria.

    Ritorna (verdict, reason, criteria_results).
    Verdict: PASS | FAIL | INCONCLUSIVE | UNTESTABLE
    """
    if metrics.get("details", {}).get("untestable"):
        return "UNTESTABLE", metrics["details"].get("reason", "PoC ha dichiarato untestable"), []
    delta = metrics.get("delta")
    naive = metrics.get("naive_score")
    informed = metrics.get("informed_score")
    n_trials = metrics.get("n_trials", 0)
    notes = []
    if delta is None or naive is None or informed is None:
        return "INCONCLUSIVE", "metrics.json incompleto (mancano naive_score/informed_score/delta)", notes
    if n_trials < 10:
        notes.append(f"n_trials={n_trials} basso — risultato debole statisticamente")
    if delta > 0:
        # Informed batte naive: candidate validato
        if delta > 0.05:
            return "PASS", f"informed_score={informed:.4f} > naive_score={naive:.4f} (delta=+{delta:.4f}, > 0.05 threshold)", notes
        else:
            notes.append(f"delta=+{delta:.4f} marginale (< 0.05) — segnale debole")
            return "INCONCLUSIVE", f"informed batte naive ma con margine marginale (delta=+{delta:.4f})", notes
    elif delta < -0.05:
        return "FAIL", f"informed_score={informed:.4f} < naive_score={naive:.4f} (delta={delta:.4f}, < -0.05) — finding non porta vantaggio", notes
    else:
        notes.append(f"delta={delta:.4f} ≈ 0 — informed equivalente al naive")
        return "INCONCLUSIVE", f"nessuna differenza significativa (delta={delta:.4f})", notes


def _run_one_candidate(cycle_ts: str, finding_idx: int, finding_title: str,
                       candidate: dict, agent_path: Path, finding_excerpt: str,
                       verdict_text: str, args) -> dict:
    """Process un singolo candidate (library / kernel / demo) → genera prodotto.

    Ritorna dict con: type, verdict, reason, prod_dir, skipped (bool).
    """
    product_id = f"{cycle_ts}_finding{finding_idx}_{candidate['type']}_{slugify(finding_title)}"
    prod_dir = _PATHS["prodotti"] / product_id
    if prod_dir.exists() and not args.force:
        print(f"  [{candidate['type']}] SKIP {product_id} (esiste, --force per riesecuzione)")
        return {"type": candidate["type"], "verdict": "SKIP", "reason": "exists",
                "prod_dir": str(prod_dir), "skipped": True}
    prod_dir.mkdir(parents=True, exist_ok=True)
    print(f"  [{candidate['type']}] product dir: {prod_dir}")

    prompt = PROMPT_TEMPLATE.format(
        cycle_ts=cycle_ts,
        domain=_PATHS["domain"],
        finding_idx=finding_idx,
        finding_title=finding_title,
        finding_excerpt=finding_excerpt or "(no excerpt found)",
        verdict=verdict_text,
        candidate_type=candidate["type"],
        candidate_name=candidate["name"],
        candidate_what=candidate.get("what_it_does", "")[:300],
        verification_spec=json.dumps(candidate.get("verification_spec", {}), indent=2)[:2000],
    )
    (prod_dir / "prompt.txt").write_text(prompt)

    try:
        poc_code = generate_poc_script(prompt, target_dir=prod_dir,
                                       max_turns=args.max_turns, timeout=args.gen_timeout)
    except (RuntimeError, subprocess.TimeoutExpired) as e:
        print(f"  [{candidate['type']}] ERROR generating poc.py: {e}", file=sys.stderr)
        (prod_dir / "stage4_error.txt").write_text(f"GENERATION FAILED: {e}\n")
        return {"type": candidate["type"], "verdict": "FAIL", "reason": f"generation: {e}",
                "prod_dir": str(prod_dir), "skipped": False}

    print(f"  [{candidate['type']}] generated poc.py: {len(poc_code)} chars")

    started_at = datetime.now(timezone.utc)
    ok, log, metrics = execute_poc(prod_dir / "poc.py", prod_dir, timeout=args.exec_timeout)
    finished_at = datetime.now(timezone.utc)
    (prod_dir / "poc.log").write_text(log)

    if not ok or metrics is None:
        verdict = "FAIL"
        reason = "PoC failed to execute or produce metrics.json"
        criteria_notes = []
    else:
        verdict, reason, criteria_notes = compute_verdict(metrics, candidate.get("verification_spec", {}))

    print(f"  [{candidate['type']}] verdict: {verdict} — {reason[:120]}")

    verification = {
        "schema_version": "0.1",
        "stage": 4,
        "stage_name": "poc_runner",
        "verdict": verdict,
        "reason": reason,
        "criteria_notes": criteria_notes,
        "verifier_form": (candidate.get("verification_spec") or {}).get("verifier_form", "benchmark"),
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_s": round((finished_at - started_at).total_seconds(), 2),
        "metrics": metrics or {},
        "status": verdict,
        "verified_at": finished_at.isoformat(),
    }
    (prod_dir / "verification.json").write_text(json.dumps(verification, indent=2))

    product_manifest = {
        "schema_version": "0.1",
        "id": product_id,
        "type": candidate["type"],
        "name": candidate["name"],
        "domain": _PATHS["domain"],
        "lab_instance": f"D-ND_LAB/{_PATHS['domain']}",
        "discovery_cycle_ts": cycle_ts,
        "discovery_finding_idx": finding_idx,
        "discovery_finding_title": finding_title,
        "what_it_does": candidate.get("what_it_does", ""),
        "stack_proposed": candidate.get("stack_proposed", ""),
        "produced_at": finished_at.isoformat(),
        "produced_by": "stage4_poc_runner.py",
        "boundary": [
            "Prodotto generato automaticamente da Stage 4 PoC runner.",
            "verification.json contiene metriche reali (NON .spec).",
            "Verdict empirico — può essere PASS / FAIL / INCONCLUSIVE / UNTESTABLE.",
        ],
    }
    (prod_dir / "manifest.json").write_text(json.dumps(product_manifest, indent=2))

    return {"type": candidate["type"], "verdict": verdict, "reason": reason,
            "prod_dir": str(prod_dir), "skipped": False, "metrics": metrics or {}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cycle_ts")
    ap.add_argument("finding_idx", nargs="?", type=int, default=None,
                    help="finding id (1-based dal report). Omettere con --auto")
    ap.add_argument("--auto", action="store_true",
                    help="Seleziona automaticamente il primo applicative_finding eligible")
    # Multi-candidate (NEW 01/05): default genera tutti e 3 i tipi (library/kernel/demo)
    # per lo stesso finding. Operatore poi sceglie quale promuovere a prodotto.
    ap.add_argument("--candidate-types", default="library,kernel,demo",
                    help="Comma-separated lista di tipi da testare. Default: tutti.")
    # Legacy alias singolo (backward-compat)
    ap.add_argument("--candidate-type", default=None, choices=["library", "kernel", "demo", None],
                    help="DEPRECATED — usa --candidate-types. Singolo tipo (per compat).")
    ap.add_argument("--domain", default=None)
    ap.add_argument("--max-turns", type=int, default=8)
    ap.add_argument("--gen-timeout", type=int, default=300, help="Timeout per claude generation")
    ap.add_argument("--exec-timeout", type=int, default=90, help="Timeout per poc.py execution")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if args.domain:
        global _PATHS
        _PATHS = _resolve_paths(args.domain)

    cycle_ts = args.cycle_ts
    print(f"stage4_poc_runner cycle_ts={cycle_ts} domain={_PATHS['domain']}")

    # Resolve candidate types list (legacy --candidate-type prevale per compat)
    if args.candidate_type:
        types_to_run = [args.candidate_type]
        print(f"  legacy --candidate-type={args.candidate_type} (single)")
    else:
        types_to_run = [t.strip() for t in args.candidate_types.split(",") if t.strip()]
    print(f"  candidate types: {types_to_run}")

    # 1. Pick finding
    if args.auto or args.finding_idx is None:
        finding_idx, finding_title = find_first_eligible(cycle_ts)
        print(f"  auto-selected finding #{finding_idx}: {finding_title[:80]}")
    else:
        finding_idx = args.finding_idx
        finding_title = ""

    # 2. Carica manifest una volta
    manifest_path, manifest = find_manifest(cycle_ts)

    # 3. Carica agent report una volta — excerpt + verdict condivisi tra i 3 PoC
    agent_path = _PATHS["reports"] / f"agent_{cycle_ts}.md"
    if not agent_path.exists():
        print(f"  ERROR: agent report mancante {agent_path}", file=sys.stderr)
        return 2
    agent_text = agent_path.read_text()
    finding_excerpt = ""
    m = re.search(rf"^\s*{finding_idx}\.\s+(\*\*[^\n]+(?:\n(?!\s*\d+\.\s).*)*)", agent_text, re.M)
    if m:
        finding_excerpt = m.group(1)[:1500]
    verdict_m = re.search(r"##\s+[Vv]erdict\s*\n(.+?)(?=\n##\s+|\Z)", agent_text, re.S)
    verdict_text = (verdict_m.group(1).strip()[:600]) if verdict_m else "(no verdict section)"

    # 4. Loop sui types — uno PoC per type (compute parallelo possibile in futuro)
    results = []
    for candidate_type in types_to_run:
        try:
            candidate = find_candidate(manifest, finding_idx, candidate_type)
        except ValueError as e:
            print(f"  [{candidate_type}] SKIP: {e}", file=sys.stderr)
            results.append({"type": candidate_type, "verdict": "SKIP",
                            "reason": "no candidate in manifest", "skipped": True})
            continue

        # Update finding_title from candidate (in case auto did not set it)
        if not finding_title:
            finding_title = candidate.get("discovery_finding_title", "")

        result = _run_one_candidate(cycle_ts, finding_idx, finding_title,
                                    candidate, agent_path, finding_excerpt,
                                    verdict_text, args)
        results.append(result)

    # 5. Riepilogo aggregato
    print()
    print(f"════ STAGE 4 SUMMARY — finding #{finding_idx} on cycle {cycle_ts} ════")
    n_pass = sum(1 for r in results if r["verdict"] == "PASS")
    n_fail = sum(1 for r in results if r["verdict"] == "FAIL")
    n_skip = sum(1 for r in results if r.get("skipped"))
    n_other = len(results) - n_pass - n_fail - n_skip
    for r in results:
        flag = {"PASS": "✓", "FAIL": "✗", "SKIP": "−"}.get(r["verdict"], "?")
        delta = ""
        if r.get("metrics") and r["metrics"].get("delta") is not None:
            d = r["metrics"]["delta"]
            delta = f" Δ={('+' if d>0 else '')}{d:.4f}"
        print(f"  [{flag}] {r['type']:<8} {r['verdict']:<13}{delta}  — {r['reason'][:80]}")
    print(f"  totals: {n_pass} PASS · {n_fail} FAIL · {n_skip} SKIP · {n_other} other")
    return 0 if (n_pass + n_skip) == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
