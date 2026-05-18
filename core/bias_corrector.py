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
report the producer just wrote AND the empirical data files it references,
detect three specific failure-modes that the model has shown to repeat
structurally, and propose rewrites that preserve the data but correct the
framing.

You do NOT challenge the experiment design or the choice of tension. The
producer's exploratory framing is preserved. You only correct the LANGUAGE
of claims that contradict the report's own numerical evidence OR the data
files it references.

### What to look for (3 lenses, tied to D-ND axioms — domain-agnostic)

**L1 (A2) — Absolute language vs biased data.**
The report writes 'always', 'pure', 'zero', 'never', 'absent', 'forbidden',
'prohibition' but the report's own table, numbers, OR the empirical data
files show a non-zero value. The lens is universal: a hard constraint
requires an exact zero in the data.

**Rewrite rule**: replace the absolute with a precise quantitative phrase
that names the bias correctly. State the exact number. 'Strong bias toward
0' if value < 0.05. 'Bias toward [direction]' if value within (0.05, 0.5).

**L3 (A4) — Silent patching.**
The setup ('Claim Under Test') uses one definition; the conclusion uses a
different one without declaring the falsification of the original. This
includes cases where the data file shows a value that contradicts the
setup but the report says the claim is "refined" instead of "falsified".

**Rewrite rule**: insert an explicit declaration. "Claim X was falsified
at this cycle. The new claim that emerged is Y." Never write "refined"
when the original claim is contradicted.

**L4 (A12) — Edge case rounded away.**
The report writes 'always X' or 'never X' or '0 violations' while
acknowledging a single counter-example, OR while a data file shows the
counter-example exists.

**Rewrite rule**: reformulate the perimeter. "For [conditioned scope], X
holds; the edge case at [exception] shows Y." The counter-example is a
feature, not noise.

{domain_examples}

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

{context}

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

    if _is_runtime_repair_report(report_text):
        _record_runtime_repair_skip(ctx, ts, report_path)
        return

    # Apply size guard: if the report is huge, sample it (rare case)
    max_input = int(params.get("max_input_bytes", 30_000))
    if len(report_text) > max_input:
        logger.warning(
            "bias_corrector: report %d bytes > cap %d, truncating context",
            len(report_text), max_input,
        )
        report_text = report_text[:max_input]

    # Build context: report + domain data files + (optional) domain examples.
    # Mirrors report_falsifier._collect_data_excerpts so the corrector can see
    # L3 setup-vs-data discrepancies (the setup is in the report, the data
    # often lives in JSON files referenced but not quoted).
    max_data_bytes = int(params.get("max_data_bytes", 20_000))
    data_excerpts = _collect_data_excerpts(ctx, report_text, max_data_bytes)
    context_block = _build_context(report_text, data_excerpts)
    domain_examples_block = _load_domain_examples(ctx.domain)

    prompt = (CORRECTOR_PROMPT
              .replace("{context}", context_block)
              .replace("{domain_examples}", domain_examples_block))

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


def _is_runtime_repair_report(report_text: str) -> bool:
    """Runtime repair reports are control artifacts, not domain claims.

    The downstream falsifier should still read them, but this movement must
    not rewrite them as if they were agent-produced scientific reports.
    """
    markers = (
        "CYCLE_REPAIR_NO_CLAIM",
        "Agent Runtime Repair Report",
        "not a scientific finding",
        "not a domain result",
    )
    return any(marker in report_text for marker in markers[:2]) and all(
        marker in report_text for marker in markers[2:]
    )


def _record_runtime_repair_skip(
    ctx: CycleContext, ts: str, report_path: Path
) -> None:
    reason = "runtime repair report is a control artifact"
    ctx.record_skipped("bias_corrector", reason)
    ctx.metrics.setdefault("bias_corrector", {}).update(
        status="skipped_runtime_repair_report",
        reason=reason,
        report_file=report_path.name,
    )

    out_dir = paths.domain_data_dir(ctx.domain) / "corrector"
    out_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "domain": ctx.domain,
        "timestamp": ts,
        "report_file": report_path.name,
        "rewrites_proposed": 0,
        "rewrites_applied": 0,
        "rewrites_skipped": 0,
        "status": "skipped_runtime_repair_report",
        "reason": reason,
        "marked_at": datetime.now(timezone.utc).isoformat(),
    }
    (out_dir / f"corrector_{ts}.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False)
    )


# ─── Data context collection (mirror of report_falsifier pattern) ──


_DATA_FILE_REF_RE = re.compile(
    r"`?(?:data/[^`\s)]+|domains/[^`\s)]+/(?:data|corpus|reports)/[^`\s)]+|[A-Za-z0-9_]+\.(?:json|csv|jsonl))`?",
)


def _collect_data_excerpts(
    ctx: CycleContext, report_text: str, budget_bytes: int
) -> list[dict[str, str]]:
    """Find data files the report references and read excerpts under budget.

    Mirrors report_falsifier._collect_data_excerpts so the corrector can
    catch L3 setup-vs-data discrepancies where the setup lives in the report
    but the contradicting data lives in a JSON file. Domain-agnostic.
    """
    candidates: set[Path] = set()
    domain_data = paths.domain_data_dir(ctx.domain)

    for m in _DATA_FILE_REF_RE.finditer(report_text):
        ref = m.group(0).strip("`")
        for base in (Path(ref), domain_data / Path(ref).name, domain_data / ref):
            try:
                p = base if base.is_absolute() else (Path("/opt/D-ND_LAB") / base)
                if p.exists() and p.is_file():
                    candidates.add(p.resolve())
                    break
            except Exception:
                pass

    # Canonical files always considered
    for canonical in ("lab_data.json", "lab_graph.json", "seed.json"):
        p = domain_data / canonical
        if p.exists():
            candidates.add(p.resolve())

    # Computation trace (artifacts) from this cycle
    artifact_dir = domain_data / "artifacts" / ctx.timestamp
    if artifact_dir.exists() and artifact_dir.is_dir():
        for p in sorted(artifact_dir.glob("call_*.json")):
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
        parts.append("\n## EMPIRICAL DATA FILES (the substrate the report references)\n")
        for d in data_excerpts:
            parts.append(f"### {d['path']}\n```\n{d['excerpt']}\n```\n")
    else:
        parts.append("\n## EMPIRICAL DATA FILES\n_none referenced or readable_\n")
    return "".join(parts)


def _load_domain_examples(domain: str) -> str:
    """Optional per-domain bias examples loaded from domains/<domain>/bias_examples.md.

    Domain-agnostic by design: if the file is absent, the prompt uses only
    the universal lens definitions (no domain-specific illustrations).
    Each domain (physics, finance, biology, ...) can ship its own collection
    of past biases as concrete reference for the corrector LLM.

    The file is expected to be markdown with sections like '### L1 ...',
    '### L3 ...', '### L4 ...'. The whole file is injected as-is.
    """
    examples_path = paths.domain_dir(domain) / "bias_examples.md" \
        if hasattr(paths, "domain_dir") else None
    # Fallback: try the standard layout
    if examples_path is None or not examples_path.exists():
        examples_path = Path("/opt/D-ND_LAB") / "domains" / domain / "bias_examples.md"
    if not examples_path.exists():
        return ""
    try:
        text = examples_path.read_text(errors="replace")
        if not text.strip():
            return ""
        return f"\n### Domain-specific bias examples (from {domain}/bias_examples.md)\n\n{text.strip()}\n"
    except Exception:
        return ""


# ─── Movement registration ─────────────────────────────────────────

register_movement("bias_corrector", bias_corrector)
