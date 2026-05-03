#!/usr/bin/env python3
"""finding_promoter — promuove meta-finding REVIEW_REQUIRED a applicative_finding.

Pattern: quando trajectory_evaluator=CRYSTALLIZE high ma 0 finding eligible,
SSP pipeline resta transitional → niente Stage 4/5 → niente prodotto.
Spesso il cycle ha trovato qualcosa di solido ma il finding è meta-scientifico
(descrive il modello), non applicativo (non dà regola predittiva packageable).

Questo script prende ogni finding REVIEW_REQUIRED e chiede a un LLM:
"Questo meta-finding può essere riformulato come regola predittiva
applicativa? Se sì, fornisci regola + use case. Se no, motiva."

Se LLM dice yes con confidence alta → aggiorna finding_index.draft.json
marcando il finding promoted (application_eligible: true,
role: applicative_finding_promoted, promotion_reason: <LLM output>).

L'operatore review l'output, conferma, lancia manualmente application_designer
+ Stage 4 sui finding promossi.

CLI:
  python -m core.triggers.finding_promoter <cycle_ts> [--domain physics]
                                                       [--apply]
                                                       [--min-confidence high]

Dry run di default: stampa proposte, non modifica file.
--apply: scrive le promozioni in finding_index.draft.json.

Provider: claude-cli OAuth (gratis subscription).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
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
        "soluzioni": domain_dir / "soluzioni",
    }


PROMPT_TEMPLATE = """You are a research lab promoter. A scientific cycle produced a meta-finding marked REVIEW_REQUIRED by an automated eligibility gate. Your job: decide if this finding can be reformulated as an APPLICATIVE rule (a predictive operator with concrete input/output), or if it's purely descriptive/methodological.

Finding title:
{title}

Finding excerpt:
{excerpt}

Score signals (already computed):
- applicative: {appl_score}
- methodology_note: {meth_score}
- boundary_warning: {boundary_score}
- negative_result: {neg_score}
- literature_rediscovery: {lit_score}

Context:
- The lab produces installable Python packages (kernels) from applicative findings.
- A finding is APPLICATIVE if you can write a function: input X → output Y based on this rule.
- A finding is META if it only describes/constrains the model without giving a usable operator.

Respond ONLY with valid JSON, no other text:
{{
  "promotable": true | false,
  "confidence": "high" | "medium" | "low",
  "reasoning": "<2-3 sentences justifying the decision>",
  "applicative_rule": "<if promotable: 1-line predictive rule (input → output)>",
  "use_case": "<if promotable: 1-2 sentences of concrete application>",
  "kernel_name_suggestion": "<if promotable: snake_case name for the kernel>"
}}

If not promotable, leave applicative_rule/use_case/kernel_name_suggestion empty strings.
"""


# Provider chain (refactor 03/05 sera, operatore decision):
# codex-cli (TM7 ChatGPT account) → claude-cli (OAuth subscription)
# → openrouter (paid HTTP). Override via LLM_PROVIDER_CHAIN env var.
LLM_PROVIDER_CHAIN = [
    p.strip()
    for p in os.environ.get("LLM_PROVIDER_CHAIN", "codex-cli,claude-cli,openrouter").split(",")
    if p.strip()
]
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LLM_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL") or os.environ.get("LLM_MODEL", "deepseek/deepseek-v4-pro")


def _via_codex_cli(prompt: str, timeout: int) -> str | None:
    if not shutil.which("codex"):
        return None
    try:
        r = subprocess.run(
            ["codex", "exec", "-", "--non-interactive"],
            input=prompt, capture_output=True, text=True, timeout=timeout,
        )
        if r.returncode == 0 and (r.stdout or "").strip():
            return r.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def _via_claude_cli(prompt: str, timeout: int) -> str | None:
    if not shutil.which("claude"):
        return None
    try:
        r = subprocess.run(
            ["claude", "-p", prompt, "--max-turns", "1",
             "--permission-mode", "acceptEdits", "--allowedTools", ""],
            capture_output=True, text=True, timeout=timeout,
        )
        if r.returncode == 0 and (r.stdout or "").strip():
            return r.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def _via_openrouter(prompt: str, timeout: int) -> str | None:
    if not OPENROUTER_API_KEY:
        return None
    import urllib.request
    import urllib.error
    payload = json.dumps({
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 2000,
    }).encode("utf-8")
    req = urllib.request.Request(
        OPENROUTER_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except (urllib.error.HTTPError, urllib.error.URLError, KeyError):
        return None


_PROVIDERS = {
    "codex-cli": _via_codex_cli,
    "claude-cli": _via_claude_cli,
    "openrouter": _via_openrouter,
}


def call_llm_chain(prompt: str, timeout: int = 300) -> str:
    """Provider chain dispatcher: codex → claude → openrouter (default)."""
    for name in LLM_PROVIDER_CHAIN:
        fn = _PROVIDERS.get(name)
        if not fn:
            continue
        out = fn(prompt, timeout)
        if out:
            print(f"      [provider: {name} OK]", file=sys.stderr)
            return out
        print(f"      [provider: {name} unavailable, next]", file=sys.stderr)
    raise RuntimeError(f"all providers in chain {LLM_PROVIDER_CHAIN} failed")


def extract_json(raw: str) -> dict:
    """Best-effort JSON extraction from LLM output."""
    raw = raw.strip()
    if raw.startswith("```"):
        m = re.search(r"```(?:json)?\s*(.+?)\s*```", raw, re.S)
        if m:
            raw = m.group(1)
    m = re.search(r"\{.+\}", raw, re.S)
    if not m:
        raise ValueError(f"no JSON object in output: {raw[:200]}")
    return json.loads(m.group(0))


def evaluate_finding(finding: dict) -> dict:
    """Ask LLM to decide if finding is promotable. Return decision dict."""
    scores = finding.get("scores", {})
    prompt = PROMPT_TEMPLATE.format(
        title=finding.get("title", ""),
        excerpt=finding.get("source_excerpt", "")[:600],
        appl_score=scores.get("applicative", 0),
        meth_score=scores.get("methodology_note", 0),
        boundary_score=scores.get("boundary_warning", 0),
        neg_score=scores.get("negative_result", 0),
        lit_score=scores.get("literature_rediscovery", 0),
    )

    raw = call_llm_chain(prompt)
    try:
        decision = extract_json(raw)
    except (ValueError, json.JSONDecodeError) as e:
        decision = {
            "promotable": False,
            "confidence": "low",
            "reasoning": f"LLM output non parseabile: {e}",
            "applicative_rule": "",
            "use_case": "",
            "kernel_name_suggestion": "",
            "_raw": raw[:500],
        }
    return decision


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cycle_ts")
    ap.add_argument("--domain", default=None)
    ap.add_argument("--apply", action="store_true",
                    help="scrivi promozioni in finding_index.draft.json (default: dry-run)")
    ap.add_argument("--min-confidence", default="medium",
                    choices=["low", "medium", "high"],
                    help="confidence minima per applicare la promozione")
    args = ap.parse_args()

    paths = _resolve_paths(args.domain)
    cycle_ts = args.cycle_ts

    print(f"finding_promoter cycle_ts={cycle_ts} domain={paths['domain']} "
          f"apply={args.apply} min_confidence={args.min_confidence}")

    soluzione_dirs = list(paths["soluzioni"].glob(f"{cycle_ts}_*"))
    if not soluzione_dirs:
        print(f"ERROR: no soluzione dir per cycle {cycle_ts}", file=sys.stderr)
        return 2
    sol_dir = soluzione_dirs[0]
    index_path = sol_dir / "finding_index.draft.json"
    if not index_path.exists():
        print(f"ERROR: {index_path} non esiste", file=sys.stderr)
        return 2

    index = json.loads(index_path.read_text())
    findings = index.get("findings", [])
    review_required = [
        f for f in findings if f.get("application_eligible") == "REVIEW_REQUIRED"
    ]

    if not review_required:
        print(f"  no REVIEW_REQUIRED finding — niente da promuovere")
        return 0

    print(f"  evaluating {len(review_required)} REVIEW_REQUIRED finding(s)...")

    confidence_rank = {"low": 0, "medium": 1, "high": 2}
    threshold = confidence_rank[args.min_confidence]

    promotions = []
    for finding in review_required:
        fid = finding.get("finding_id", "?")
        title = finding.get("title", "")[:80]
        print(f"  [{fid}] {title}")
        try:
            decision = evaluate_finding(finding)
        except Exception as e:
            print(f"      LLM error: {e}", file=sys.stderr)
            continue

        promotable = decision.get("promotable", False)
        conf = decision.get("confidence", "low")
        rule = decision.get("applicative_rule", "")
        reasoning = decision.get("reasoning", "")[:120]

        if promotable and confidence_rank.get(conf, 0) >= threshold:
            mark = "[PROMOTE]"
            promotions.append((finding, decision))
        elif promotable:
            mark = f"[skip-low-conf:{conf}]"
        else:
            mark = "[NO]"

        print(f"      {mark} {conf} | {reasoning}")
        if promotable:
            print(f"        rule: {rule[:140]}")

    if not promotions:
        print(f"\n  no promotion above {args.min_confidence} confidence")
        return 0

    print(f"\n  {len(promotions)} promotion(s) proposed:")
    for f, d in promotions:
        print(f"    - finding {f.get('finding_id')}: {d.get('kernel_name_suggestion', '?')}")

    if not args.apply:
        print("\n  dry-run (no file written). Re-run with --apply to persist.")
        return 0

    promoted_ids = {f["finding_id"] for f, _ in promotions}
    decision_map = {f["finding_id"]: d for f, d in promotions}
    for f in findings:
        fid = f.get("finding_id")
        if fid in promoted_ids:
            d = decision_map[fid]
            f["application_eligible"] = True
            f["role"] = "applicative_finding_promoted"
            f["promotion_reason"] = d.get("reasoning", "")
            f["applicative_rule"] = d.get("applicative_rule", "")
            f["use_case"] = d.get("use_case", "")
            f["kernel_name_suggestion"] = d.get("kernel_name_suggestion", "")
            f["promoted_at"] = datetime.now(timezone.utc).isoformat()
            f["promoted_by"] = "finding_promoter.py (LLM-driven)"

    summary = index.setdefault("summary", {})
    summary["n_application_eligible"] = sum(
        1 for f in findings if f.get("application_eligible") is True
    )
    summary["n_review_required"] = sum(
        1 for f in findings if f.get("application_eligible") == "REVIEW_REQUIRED"
    )
    summary["n_promoted"] = len(promoted_ids)
    index["last_promotion_at"] = datetime.now(timezone.utc).isoformat()

    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False))
    print(f"\n  WROTE {index_path} ({len(promoted_ids)} promotion(s))")
    print(f"  Next: lancia application_designer + stage4_poc_runner sui finding promossi")

    return 0


if __name__ == "__main__":
    sys.exit(main())
