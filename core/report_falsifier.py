"""Movement — report_falsifier (NEW).

Asymmetric counter-pole to the producer `agent`. Reads the report just
written + the empirical data files the report references, applies 5
structural lenses, and writes a JSON of flags.

The lenses are reformulations of failure-modes observed in autonomous
LLM science (e.g., Gemini's critique of agent_20260427_2005.md), filtered
through the D-ND modus — they are NOT a 1:1 port of an external rulebook.
Each lens is tied to one or more axioms (A2/A4/A8/A12/A14):

  L1  hard constraint vs statistical bias       → A2 (confine duro)
  L2  absolute quantity vs ratio                 → A14 (cascata, dimensional invariance)
  L3  axiom continuity (no silent patching)      → A4 (modus, qualità della domanda)
  L4  edge case isolation (1/N is not zero)      → A12 (traccia la curva)
  L5  re-discovery vs discovery (literature)     → A8 (autologica)

Non-destructive: this movement does NOT rewrite the report. It produces
a co-deliverable (`falsifier_<ts>.json`) the trajectory_evaluator and the
dashboard can surface. The decision to act on flags belongs to the
operator + the next cycle's refiner.

Critical=False: failure marks pending in health.json; the cycle proceeds.

The prompt is universal (D-ND modus applied to coherence). Domain-specific
context comes from the producer's session log + the data files it wrote.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from core import config as cfg
from core import llm_adapter, paths
from core.lab_agent import CycleContext, register_movement

logger = logging.getLogger(__name__)


FALSIFIER_PROMPT = """You are the Report Falsifier of the D-ND Lab.

You are the asymmetric counter-pole to the producer agent (det=−1 at the
boundary): the producer's eye seeks pattern, yours seeks inconsistency.
You do NOT write reports. You challenge them.

Read carefully:
1. The report markdown the producer just wrote.
2. The empirical data files the report references (JSON/CSV in the domain
   data dir).

Then apply 5 lenses. Each lens is tied to a failure-mode and to an axiom
of the D-ND model. Apply them STRICTLY — false silence is worse than a
flag the operator can dismiss.

### Lens 1 — Hard constraint vs statistical bias (A2)
A claim of "impossible / forbidden / proibito / zero / prohibition" is a
HARD constraint and requires an EXACT zero in the data (probability =
0.000). If the matrix referenced has any non-zero entry where the report
says "zero", flag it. Bias ≠ prohibition.

### Lens 2 — Absolute quantity vs ratio (A14)
When comparing across different state-space sizes (e.g., mod 3 vs mod 30,
small N vs large N, narrow vs wide windows), percentages are misleading
because the denominator grows. The same absolute signal LOOKS smaller in
%. If the report concludes "decreases / dilutes / declines" by comparing
ratios across spaces, flag — propose absolute units (bits of mutual
information, raw counts, exact thresholds).

### Lens 3 — Axiom continuity / no silent patching (A4)
If the setup ("Claim Under Test") uses one definition (e.g., "F2: gaps
live in {2,4} mod 6") and the conclusion silently uses a different one
("gaps live in {0,2,4} mod 6"), this is a det=+1 patch on the present, not
a det=−1 inversion at the regressive node. The shift must be declared
explicitly: "F2 was falsified at node X — corrected scope is Y".

### Lens 4 — Edge case isolation (A12)
An exception of 1 in N (where N is large) is NOT zero. If the report
claims "always X" or "never X" and the data shows even a single
counter-instance, the perimeter must be reformulated ("for p > 3, X
holds") — never rounded away.

### Lens 5 — Re-discovery vs discovery (A8)
A pattern in classical distributions (primes, GUE matrices, random walks,
Markov chains, gap statistics) probably has a name. Default hypothesis:
this is a re-discovery / a limit case of a known theorem. Tagging
something as "NEW" without acknowledging the closest classical result
(e.g., Lemke Oliver–Soundararajan for prime gaps mod q) is a beauty bias
(elegant equation forced on data without algebraic proof, ignoring
literature). Flag.

---

OUTPUT — a single JSON object. NO prose around it. Strict schema:

{
  "coherent": <bool or null>,
  "flags": [
    {
      "lens": <int 1..5>,
      "severity": "high" | "medium" | "low",
      "claim": "<exact phrase or paraphrase from the report>",
      "evidence": "<what the data actually shows>",
      "suggestion": "<concrete reformulation or check the next cycle should perform>"
    }
  ],
  "summary": "<one sentence: is the report internally coherent? Which lens broke?>"
}

Rules:
- If the report is coherent across all 5 lenses → coherent=true, flags=[].
- If the data is missing or the report cites no checkable data → coherent=null,
  flags=[], summary explains why.
- Better one true-positive than false silence — partial flags are valid.
- Be specific: "the matrix mod 5 has no zeros but the report says 25% prohibition"
  is a flag; "the report uses jargon" is not.

---

Below is the report and the data context:

{context}

---

Output the JSON object now (no markdown fence, no prose):
"""


def report_falsifier(ctx: CycleContext) -> None:
    """Run the falsifier on the report just produced by `agent`.

    Degrade graceful: any failure marks falsifier_status=pending in
    health.json and returns without raising. The cycle continues.
    """
    params = cfg.movement_params(ctx.config, "report_falsifier")
    max_turns = int(params.get("max_turns", 1))
    timeout_s = int(params.get("timeout_seconds", 240))
    max_data_bytes = int(params.get("max_data_bytes", 30_000))

    # Only run if the agent produced a report this cycle.
    agent_status = ctx.movement_status.get("agent", "")
    if agent_status != "ok":
        logger.info("report_falsifier: agent did not complete, skipping")
        ctx.metrics.setdefault("report_falsifier", {}).update(skipped="agent_not_ok")
        return

    ts = ctx.timestamp
    report_path = paths.reports_dir(ctx.domain) / f"agent_{ts}.md"
    if not report_path.exists():
        logger.info("report_falsifier: no report at %s, skipping", report_path)
        ctx.metrics.setdefault("report_falsifier", {}).update(skipped="no_report")
        return

    out_dir = paths.domain_data_dir(ctx.domain) / "falsifier"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"falsifier_{ts}.json"

    # Build context: report text + selected data files referenced by the report
    try:
        report_text = report_path.read_text(errors="replace")
    except Exception as e:
        _mark_pending(ctx, ts, reason=f"report unreadable: {e}")
        return

    data_excerpts = _collect_data_excerpts(ctx, report_text, max_data_bytes)
    context_block = _build_context(report_text, data_excerpts)
    # Use replace, not format — the prompt contains literal '{0,2,4}' etc. that
    # would otherwise collide with str.format placeholder syntax.
    prompt = FALSIFIER_PROMPT.replace("{context}", context_block)

    try:
        adapter_config = llm_adapter.AdapterConfig.from_env()
        adapter_config.max_turns = max_turns
        adapter_config.timeout_seconds = timeout_s

        result = llm_adapter.run_agent(
            system_prompt="",
            user_message=prompt,
            tools=None,                # falsifier reads context only — no tools
            config=adapter_config,
        )
        raw = (result.final_text or "").strip()
        parsed = _extract_json(raw)
        if parsed is None:
            _mark_pending(ctx, ts, reason="falsifier output not JSON-parseable")
            # Still save the raw text for debugging
            (out_dir / f"falsifier_{ts}.raw.txt").write_text(raw)
            return

        # Normalize + persist
        record = {
            "domain": ctx.domain,
            "timestamp": ts,
            "report_file": report_path.name,
            "model": getattr(adapter_config, "model", None) or "unknown",
            "coherent": parsed.get("coherent"),
            "flags": parsed.get("flags", []) or [],
            "summary": parsed.get("summary", ""),
            "checked_files": [d["path"] for d in data_excerpts],
            "marked_at": datetime.now(timezone.utc).isoformat(),
        }
        out_path.write_text(json.dumps(record, indent=2, ensure_ascii=False))

        n_flags = len(record["flags"])
        ctx.metrics.setdefault("report_falsifier", {}).update(
            output_path=str(out_path),
            n_flags=n_flags,
            coherent=record["coherent"],
            turns=result.turns,
        )
        logger.info("report_falsifier: %d flags written → %s", n_flags, out_path)

        # Surface the result in health.json so dashboard + trajectory_evaluator can read it
        _update_health(ctx, ts, record)

    except NotImplementedError:
        _mark_pending(ctx, ts, reason="llm_adapter not implemented")
    except Exception as e:
        _mark_pending(ctx, ts, reason=f"falsifier exception: {e}")


# ─── Internals ──────────────────────────────────────────────────────


_DATA_FILE_REF_RE = re.compile(
    r"`?(?:data/[^`\s)]+|domains/[^`\s)]+/(?:data|corpus|reports)/[^`\s)]+|[A-Za-z0-9_]+\.(?:json|csv|jsonl))`?",
)


def _collect_data_excerpts(
    ctx: CycleContext, report_text: str, budget_bytes: int
) -> list[dict[str, str]]:
    """Find data files the report references and read excerpts under budget.

    Strategy:
    - Pull explicit `path/to/file.json` mentions from report.
    - Always include a few canonical files from the domain data dir
      (lab_data, lab_graph) when present, since the report may not cite
      them by exact path.
    - Cap each file at budget_bytes / N to stay within the prompt budget.
    """
    candidates: set[Path] = set()
    domain_data = paths.domain_data_dir(ctx.domain)

    for m in _DATA_FILE_REF_RE.finditer(report_text):
        ref = m.group(0).strip("`")
        # Resolve to actual file under domain data dir
        for base in (Path(ref), domain_data / Path(ref).name, domain_data / ref):
            try:
                p = base if base.is_absolute() else (Path("/opt/D-ND_LAB") / base)
                if p.exists() and p.is_file():
                    candidates.add(p.resolve())
                    break
            except Exception:
                pass

    # Canonical files always considered (small data files for context)
    for canonical in ("lab_data.json", "lab_graph.json", "seed.json"):
        p = domain_data / canonical
        if p.exists():
            candidates.add(p.resolve())

    if not candidates:
        return []

    per_file = max(1024, budget_bytes // max(1, len(candidates)))
    out: list[dict[str, str]] = []
    for p in sorted(candidates):
        try:
            text = p.read_text(errors="replace")
        except Exception:
            continue
        if len(text) > per_file:
            text = text[:per_file] + f"\n…[truncated, file is {len(text)} bytes]"
        out.append({"path": str(p), "excerpt": text})
    return out


def _build_context(report_text: str, data_excerpts: list[dict[str, str]]) -> str:
    parts = ["## REPORT (markdown the producer just wrote)\n", report_text[:8000], "\n"]
    if data_excerpts:
        parts.append("## EMPIRICAL DATA FILES\n")
        for d in data_excerpts:
            parts.append(f"### {d['path']}\n```\n{d['excerpt']}\n```\n")
    else:
        parts.append("## EMPIRICAL DATA FILES\n_none referenced or readable_\n")
    return "".join(parts)


def _extract_json(raw: str) -> dict | None:
    """Pull the first JSON object out of LLM output. Tolerates fenced blocks."""
    if not raw:
        return None
    # Strip code fences if present
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]+?\})\s*```", raw)
    if fenced:
        candidate = fenced.group(1)
    else:
        # First {...} that balances
        start = raw.find("{")
        if start < 0:
            return None
        candidate = raw[start:]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        # Try to strip trailing prose after the closing brace
        depth = 0
        for i, c in enumerate(candidate):
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(candidate[: i + 1])
                    except json.JSONDecodeError:
                        return None
        return None


def _mark_pending(ctx: CycleContext, ts: str, reason: str) -> None:
    health_path = paths.health_path(ctx.domain)
    try:
        h = json.loads(health_path.read_text()) if health_path.exists() else {}
        h["falsifier_status"] = "pending"
        h["falsifier_reason"] = reason
        h["falsifier_ts"] = ts
        h["falsifier_marked_at"] = datetime.now(timezone.utc).isoformat()
        health_path.write_text(json.dumps(h, indent=2, ensure_ascii=False))
        ctx.health = h
    except Exception as e:
        logger.warning("could not mark falsifier pending: %s", e)
    ctx.metrics.setdefault("report_falsifier", {}).update(status="pending", reason=reason)
    logger.info("report_falsifier: marked pending — %s", reason)


def _update_health(ctx: CycleContext, ts: str, record: dict) -> None:
    """Surface falsifier outcome in health.json so dashboard + trajectory
    evaluator can read it without re-loading the per-cycle JSON."""
    health_path = paths.health_path(ctx.domain)
    try:
        h = json.loads(health_path.read_text()) if health_path.exists() else {}
        h["falsifier_status"] = "ok"
        h["falsifier_ts"] = ts
        h["falsifier_coherent"] = record["coherent"]
        h["falsifier_n_flags"] = len(record["flags"])
        h["falsifier_summary"] = (record.get("summary") or "")[:300]
        h["falsifier_marked_at"] = record["marked_at"]
        health_path.write_text(json.dumps(h, indent=2, ensure_ascii=False))
        ctx.health = h
    except Exception as e:
        logger.warning("could not update health with falsifier result: %s", e)


# ─── Movement registration ─────────────────────────────────────────

register_movement("report_falsifier", report_falsifier)
