"""Movement — bias_corrector (NEW, 29/04).

Operatore (29/04, dopo 3 iterazioni del lab fisica MM_D-ND con bias persistente
"linguaggio assolutista su dati biased" che il falsifier ha catturato ma
l'agent continuava a riprodurre lateralmente):

> "Il bias persistente e' strutturale? ok mettiamo un sistema che comprende
> che succede, modifica la situazione e riprova senza il bias. Non dire cosa
> fare in quel punto del tempo futuro... fai in modo che ogni evento possa
> trovare la soluzione."

A8 autologica iterativa. Dopo che l'agent ha scritto il report, questo
movement applica le 5 lenti AL REPORT STESSO (con framing skeptical, opposto
al modo exploratory del producer). Riformula i claim che mostrano:

  L1: absolute language ('always', 'pure', 'zero', 'never', 'absent') on data
      that the report's own numbers show is non-zero.
  L3: silent patching — setup uses definition X, conclusion uses Y without
      declaring the falsification of X.
  L4: edge case rounded away — single counter-example acknowledged but
      conclusion still claims 'always'/'never'.

Position in flow: agent → bias_corrector (NEW) → report_falsifier (existing).

Pattern producer/critic (fork-mode v7 minimale): the producer wrote with the
exploratory framing; the critic reads with the skeptical framing. Same model
but different prompt → reduces correlated bias.

Non-destructive audit trail: if rewrites are made, saves report_<ts>.original.md
before overwriting report_<ts>.md. Operator can compare diff in the dashboard.

Fail-open: if the corrector itself fails (LLM error, parse error, timeout),
the original report passes through unchanged to report_falsifier. The
counter-pole still has the final word.

Critical=False: failure marks bias_corrector_status=pending in health.json.
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


CORRECTOR_PROMPT = """You are the Bias Corrector of the D-ND Lab.

You are A8 autologica applied internally — the asymmetric counter-pole INSIDE
the producer flow, before the external falsifier. Your job is to read the
report the producer just wrote and detect three specific failure-modes that
the model has shown to repeat structurally. Where you find them, you propose
a rewrite that preserves the data but corrects the framing.

You do NOT challenge the experiment design or the choice of tension. The
producer's exploratory framing is preserved. You only correct the LANGUAGE
of claims that contradict the report's own numerical evidence.

### What to look for (3 lenses, tied to D-ND axioms)

**L1 (A2) — Absolute language vs biased data.**
The report writes 'always', 'pure', 'zero', 'never', 'absent', 'forbidden',
'prohibition' but the report's own table or numbers show a non-zero value.
Examples observed in past runs:
- "Mod-3 self-transition zero confirming the prohibition" + table showing
  16.14% self-transitions → claim contradicts its own data.
- "Cramer is always pure Poisson (beta ~ 0.015)" → 0.015 is not 0.
- "T[1][1] = T[2][2] = 0.000 exactly" + acknowledged exception at p=3.

**Rewrite rule**: replace the absolute with a precise quantitative phrase
that names the bias correctly. 'Strong bias toward 0' if value < 0.05.
'Bias toward ordering' if value < 0.5. State the exact number.

**L3 (A4) — Silent patching.**
The setup ('Claim Under Test') uses one definition; the conclusion uses a
different one without declaring the falsification of the original.
Examples:
- Setup: "F2: gaps live in {2,4} mod 6" → Verdict: "gaps mod 6 live in
  {0,2,4}". The shift from {2,4} to {0,2,4} was never declared as a
  falsification of F2.
- Setup: "C1: primes are the only dynamic domain" → Verdict: "C1 is refined,
  not falsified" while the data shows GUE is also dynamic.

**Rewrite rule**: insert an explicit declaration. "C1 was falsified at this
cycle. The new claim that emerged is Z." Or: "F2 originally stated X; the
data shows Y; F2 is now archived with corrected scope Y."

**L4 (A12) — Edge case rounded away.**
The report writes 'always X' or 'never X' or '0 violations' while
acknowledging a single counter-example.
Examples:
- "0 violations on 12225 ... (1 case at p=3)" → 1 is not 0.

**Rewrite rule**: reformulate the perimeter. "For p > 3, X holds; the edge
case at p=3 shows Y." The counter-example is a feature, not noise.

### What you DO NOT touch

- The experiment design and methodology.
- The numerical values themselves.
- The choice of tension or framing of the question.
- Sections that already use precise quantitative language.
- The bicono section (radici / singolare / invariante / campo) — it is
  intentionally interpretive.

### Output

Return ONE JSON object. NO text outside the JSON. NO markdown fence.

Schema:

{
  "rewrites_applied": <int>,
  "rewrites": [
    {
      "lens": <int 1, 3, or 4>,
      "before": "<exact substring from the report>",
      "after": "<rewritten substring, preserving data>",
      "reason": "<why this corrects the bias>"
    }
  ],
  "summary": "<one sentence on what was corrected, or 'no rewrites needed' if clean>"
}

Rules:
- rewrites_applied=0, rewrites=[] if the report is already clean on L1/L3/L4.
- Each rewrite's "before" MUST be an exact substring of the report — used
  for safe text replacement.
- Preserve all numerical values exactly. Only the framing changes.
- If you are uncertain whether something is bias or genuine, leave it.
  False rewrites are worse than missed ones (the falsifier is downstream).
- Do NOT rewrite the same passage twice.

---

Report to correct:

{report_text}

---

Emit the JSON now (no markdown fence, no prose):
"""


def bias_corrector(ctx: CycleContext) -> None:
    """Apply A8 autologica internally: rewrite biased claims before the falsifier.

    Fail-open: any failure leaves the report unchanged and marks the movement
    as pending. The downstream report_falsifier still runs.
    """
    params = cfg.movement_params(ctx.config, "bias_corrector")
    max_turns = int(params.get("max_turns", 1))
    timeout_s = int(params.get("timeout_seconds", 180))
    enabled = bool(params.get("enabled", True))

    if not enabled:
        ctx.record_skipped("bias_corrector", "disabled in params")
        return

    # Only run if the agent produced a report this cycle.
    if ctx.movement_status.get("agent", "") != "ok":
        ctx.record_skipped("bias_corrector", "agent did not complete")
        return

    ts = ctx.timestamp
    report_path = paths.reports_dir(ctx.domain) / f"agent_{ts}.md"
    if not report_path.exists():
        ctx.record_skipped("bias_corrector", "no report at expected path")
        return

    try:
        report_text = report_path.read_text(errors="replace")
    except Exception as e:
        _mark_pending(ctx, ts, reason=f"report unreadable: {e}")
        return

    # Apply size guard: if the report is huge, sample it (rare case)
    max_input = int(params.get("max_input_bytes", 30_000))
    if len(report_text) > max_input:
        logger.warning(
            "bias_corrector: report %d bytes > cap %d, truncating context",
            len(report_text), max_input,
        )
        report_text = report_text[:max_input]

    prompt = CORRECTOR_PROMPT.replace("{report_text}", report_text)

    try:
        adapter_config = llm_adapter.AdapterConfig.from_env()
        adapter_config.max_turns = max_turns
        adapter_config.timeout_seconds = timeout_s
        # Allow override of model for the corrector — useful for cross-proof
        # (if producer used model A, corrector can use model B).
        corrector_model = params.get("model")
        if corrector_model:
            adapter_config.model = corrector_model

        result = llm_adapter.run_agent(
            system_prompt="",
            user_message=prompt,
            tools=None,
            config=adapter_config,
        )
        raw = (result.final_text or "").strip()
        parsed = _extract_json(raw)
        if parsed is None:
            _mark_pending(ctx, ts, reason="corrector output not JSON-parseable")
            (paths.reports_dir(ctx.domain) / f"corrector_{ts}.raw.txt").write_text(raw)
            return

        rewrites = parsed.get("rewrites", []) or []
        n_rewrites = len(rewrites)

        # Apply rewrites if any
        applied = 0
        skipped = 0
        if rewrites:
            current = report_path.read_text(errors="replace")
            for rw in rewrites:
                if not isinstance(rw, dict):
                    skipped += 1
                    continue
                before = rw.get("before") or ""
                after = rw.get("after") or ""
                if not before or not after or before == after:
                    skipped += 1
                    continue
                if before not in current:
                    # Fuzzy mismatch — LLM hallucinated the substring
                    skipped += 1
                    continue
                current = current.replace(before, after, 1)
                applied += 1

            if applied > 0:
                # Save audit trail
                audit_path = paths.reports_dir(ctx.domain) / f"agent_{ts}.original.md"
                audit_path.write_text(report_text)  # original
                report_path.write_text(current)     # corrected

        # Persist corrector record
        out_dir = paths.domain_data_dir(ctx.domain) / "corrector"
        out_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "domain": ctx.domain,
            "timestamp": ts,
            "report_file": report_path.name,
            "model": getattr(adapter_config, "model", None) or "unknown",
            "rewrites_proposed": n_rewrites,
            "rewrites_applied": applied,
            "rewrites_skipped": skipped,
            "rewrites": rewrites,
            "summary": parsed.get("summary", ""),
            "marked_at": datetime.now(timezone.utc).isoformat(),
        }
        (out_dir / f"corrector_{ts}.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False)
        )

        ctx.record_success(
            "bias_corrector",
            rewrites_proposed=n_rewrites,
            rewrites_applied=applied,
            rewrites_skipped=skipped,
        )
        logger.info(
            "bias_corrector: %d proposed, %d applied, %d skipped",
            n_rewrites, applied, skipped,
        )

    except NotImplementedError:
        _mark_pending(ctx, ts, reason="llm_adapter not implemented")
    except Exception as e:
        _mark_pending(ctx, ts, reason=f"corrector exception: {e}")


# ─── Internals ──────────────────────────────────────────────────────


def _extract_json(raw: str) -> dict | None:
    """Extract first JSON object from LLM output. Tolerates fenced blocks + prose."""
    if not raw:
        return None
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]+?\})\s*```", raw)
    candidate = fenced.group(1) if fenced else None
    if not candidate:
        start = raw.find("{")
        if start < 0:
            return None
        candidate = raw[start:]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        # Try to find balancing brace
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


def _mark_pending(ctx: CycleContext, ts: str, *, reason: str) -> None:
    logger.warning("bias_corrector pending (%s): %s", ts, reason)
    ctx.movement_status["bias_corrector"] = f"pending: {reason}"
    ctx.metrics.setdefault("bias_corrector", {}).update(
        status="pending",
        reason=reason,
    )


# ─── Movement registration ─────────────────────────────────────────

register_movement("bias_corrector", bias_corrector)
