"""Movement 14 — trajectory_evaluator (originally lab_valutatore.py).

Decides where the next cycle goes. Different from refiner: refiner OBSERVES
the step just concluded; trajectory_evaluator DECIDES the next move. Free
mandate — not a rule, an LLM agent with explicit decision space.

Decision space (guide, not limit):
  STOP_FOR_REVIEW  — produced something the operator should see
  NEXT_CYCLE       — same frame, another turn (default if uncertain)
  REDESIGN         — experiment ill-posed, propose new direction
  ESCALATE         — stuck, needs operator
  CRYSTALLIZE      — something matured enough to enter the condensate
  OTHER            — free-form (anything the system did not anticipate)

Safety:
  - log-only by default. Decisions written to trajectory_log.jsonl but
    NOT executed automatically. Operator reviews at next session.
  - To enable execution: movements.trajectory_evaluator.params.execute=true
  - Action whitelist: notify_operator, crystallize_note, modify_seme
    (direzione only, confidence=high), escalate_cowork. trigger_cycle
    is reserved for the operator (continuous mode = Approve).

Refactor changes from lab_valutatore.py:
  - TELOS, condensate, cimitero: paths via domain config + core.paths
  - Domain-specific enrichment sources (papers, bridges, parallel lab):
    pluggable via movements.trajectory_evaluator.params.sources_module —
    a Python module exposing build_sources_summary(ctx) -> str
  - subprocess to claude → llm_adapter.run_agent
  - All hardcoded /opt paths → core.paths
  - Webhook URL via env (NOTIFY_WEBHOOK_URL) instead of /api/notify
"""

from __future__ import annotations

import importlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import config as cfg
from core import llm_adapter, paths
from core.lab_agent import CycleContext, register_movement

logger = logging.getLogger(__name__)


VALUTATORE_PROMPT = """You are the Trajectory Evaluator of the D-ND Lab. Your role is to decide
where the next cycle goes — not observe what just concluded (the Refiner did that),
but decide the next move.

You have a free mandate. You are not bound to choose from predefined options —
you can propose actions the system authors did not anticipate.

## Decision space (guide, not limit)

- **STOP_FOR_REVIEW**: the cycle produced something the operator should see
  before continuing. Important crystallization, serious contradiction,
  unexpected falsification. Stopping is the choice when the next step has
  a dependency on the operator.

- **NEXT_CYCLE**: same frame, another turn. The current direction has
  potential left to extract. Nothing abnormal, continue.

- **REDESIGN**: the experiment was ill-posed or the direction is exhausted.
  Propose new direction or new tension to promote. Be specific: what to
  change in the seed for the next turn.

- **ESCALATE**: you are blocked, need the operator. Or there is an
  architectural choice only the operator can make.

- **CRYSTALLIZE**: something has matured enough to enter the condensate
  or a paper. Stable result, replicated, with clear interpretation.

- **OTHER**: if none of the above describe what you would do. Use this
  with your own words.

## Safety + confidence

- **high**: I have direct evidence from the context, the decision is clear.
- **medium**: reasonable but not certain.
- **low**: I hypothesize, the operator should confirm.

If in doubt, prefer NEXT_CYCLE (continue flow) over REDESIGN (interfere
with flow). Bias toward action has cost.

If the decision has side-effect (modify_seme, escalate_cowork, notify),
mark it clearly. By default the system is in log-only mode — actions are
recorded but NOT executed automatically.

## Output format (REQUIRED: valid JSON, nothing else)

```json
{
  "decision": "STOP_FOR_REVIEW|NEXT_CYCLE|REDESIGN|ESCALATE|CRYSTALLIZE|OTHER",
  "confidence": "high|medium|low",
  "reasoning": "2-3 sentences on why this decision now, with evidence from context",
  "action": {
    "type": "none|trigger_cycle|modify_seme|escalate_cowork|notify_operator|crystallize_note|other",
    "detail": {}
  },
  "notes": "free-form — if decision=OTHER describe here. Otherwise optional."
}
```

Action detail examples:
  - modify_seme: {"field": "direzione", "new_value": "...", "reason": "..."}
  - escalate_cowork: {"to": "operator", "subject": "...", "body": "..."}
  - notify_operator: {"message": "..."}
  - crystallize_note: {"target": "condensate|paper|memory", "content": "..."}

Respond with JSON ONLY. No explanations before or after, no markdown
fencing. The system consumes the JSON directly.

---

Context of the cycle just concluded:

{context}

---

Respond with the JSON:
"""


def trajectory_evaluator(ctx: CycleContext) -> None:
    """Run the evaluator. Reads cycle context, calls LLM, logs decision.

    Side-effect actions only execute if the domain config sets
    movements.trajectory_evaluator.params.execute=true.
    """
    params = cfg.movement_params(ctx.config, "trajectory_evaluator")
    execute = bool(params.get("execute", False))
    max_turns = int(params.get("max_turns", 3))
    timeout_s = int(params.get("timeout_seconds", 300))

    ts = ctx.timestamp
    context_md = _build_context(ctx, params)

    prompt = VALUTATORE_PROMPT.replace("{context}", context_md)

    log_path = paths.domain_data_dir(ctx.domain) / "trajectory_log.jsonl"

    try:
        adapter_config = llm_adapter.AdapterConfig.from_env()
        adapter_config.max_turns = max_turns
        adapter_config.timeout_seconds = timeout_s

        result = llm_adapter.run_agent(
            system_prompt="",
            user_message=prompt,
            tools=None,
            config=adapter_config,
        )
        raw = (result.final_text or "").strip()
        if not raw:
            _log_failure(log_path, ts, "empty_output", reasoning="no LLM output")
            ctx.metrics.setdefault("trajectory_evaluator", {}).update(status="empty")
            return

        decision = _parse_decision(raw)
        if decision is None:
            _log_failure(log_path, ts, "malformed", reasoning=raw[:500])
            ctx.metrics.setdefault("trajectory_evaluator", {}).update(status="malformed")
            return

        # Log decision (always, regardless of execute)
        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "cycle_ref": ts,
            "executed": execute,
            **decision,
        }
        _append_log(log_path, log_entry)

        # Execute side-effect action if enabled
        action_result = None
        if execute:
            action_result = _execute_action(ctx, decision)
            _append_log(log_path, {
                "ts_followup": datetime.now(timezone.utc).isoformat(),
                "cycle_ref": ts,
                "action_result": action_result,
            })

        ctx.metrics.setdefault("trajectory_evaluator", {}).update(
            decision=decision.get("decision"),
            confidence=decision.get("confidence"),
            executed=execute,
            action_type=(decision.get("action") or {}).get("type", "none"),
        )
        logger.info(
            "trajectory_evaluator: %s (confidence=%s, %s)",
            decision.get("decision"),
            decision.get("confidence", "?"),
            "EXECUTED" if execute else "log-only",
        )

    except NotImplementedError:
        _log_failure(log_path, ts, "llm_not_implemented",
                     reasoning="llm_adapter not implemented (Phase 2)")
        ctx.metrics.setdefault("trajectory_evaluator", {}).update(status="pending_llm")
    except Exception as e:
        _log_failure(log_path, ts, "exception", reasoning=str(e))
        ctx.metrics.setdefault("trajectory_evaluator", {}).update(status="error", error=str(e))


# ─── Context assembly ──────────────────────────────────────────────


def _build_context(ctx: CycleContext, params: dict[str, Any]) -> str:
    """Assemble what the evaluator reads. Universal core + domain plugin.

    Sections:
      1. TELOS (from domains/<d>/telos.md if present)
      2. MODEL (from domains/<d>/context.md)
      3. CIMITERO (from <data>/<d>/cimitero.md)
      4. DOMAIN ENRICHMENT (optional, via params.sources_module)
      5. CURRENT CYCLE (report + evolution + seed delta + bridge + health)
      6. ACCUMULATED KNOWLEDGE (from <data>/<d>/conoscenza.json if present)
      7. TRAJECTORY (last 3 evaluator decisions from trajectory_log.jsonl)
    """
    parts: list[str] = []

    # 1. TELOS
    telos_path = paths.domain_dir(ctx.domain) / "telos.md"
    if telos_path.exists():
        parts.append(f"## TELOS (the lab's purpose)\n\n{telos_path.read_text()}\n")

    # 2. MODEL / context (already loaded by build_field, but provide directly)
    context_path = paths.domain_context_path(ctx.domain)
    if context_path.exists():
        parts.append(f"## MODEL — domain context\n\n{context_path.read_text()[:8000]}\n")

    # 3. CIMITERO
    cimitero_path = paths.cimitero_path(ctx.domain)
    if cimitero_path.exists():
        try:
            cim_text = cimitero_path.read_text()[:3000]
            parts.append(f"## CIMITERO (falsified claims — do not re-propose)\n\n{cim_text}\n")
        except Exception:
            pass

    # 4. Domain enrichment (optional, plugin)
    sources_module = params.get("sources_module")
    if sources_module:
        try:
            mod = importlib.import_module(sources_module)
            if hasattr(mod, "build_sources_summary"):
                enrichment = mod.build_sources_summary(ctx)
                if enrichment:
                    parts.append(enrichment)
        except Exception as e:
            logger.warning("sources_module %s failed: %s", sources_module, e)

    # 5. CURRENT CYCLE
    parts.append("## CURRENT CYCLE\n")
    report_md = paths.reports_dir(ctx.domain) / f"agent_{ctx.timestamp}.md"
    if report_md.exists():
        parts.append(f"### Agent report\n\n{report_md.read_text()[:5000]}\n")
    else:
        parts.append("### Agent report\n_Not present — cycle did not complete._\n")

    evo_md = paths.domain_data_dir(ctx.domain) / "evolution" / f"evolution_{ctx.timestamp}.md"
    if evo_md.exists():
        parts.append(f"### Evolution report (refiner)\n\n{evo_md.read_text()[:3000]}\n")

    # Seme delta
    seme_p = paths.seed_path(ctx.domain)
    seme_backup_p = paths.seed_backup_path(ctx.domain)
    if seme_p.exists() and seme_backup_p.exists():
        try:
            post = json.loads(seme_p.read_text())
            pre = json.loads(seme_backup_p.read_text())
            diff = _seme_diff(pre, post)
            parts.append(
                "### Seed delta\n```json\n" +
                json.dumps(diff, indent=2, ensure_ascii=False) + "\n```\n"
            )
        except Exception:
            pass

    if ctx.health:
        status = ctx.health.get("status", "?")
        regressive = ctx.health.get("regressive_node")
        duration = (ctx.health.get("session_stats") or {}).get("duration_s", "?")
        parts.append(
            f"### Health\n- status: {status}\n- duration: {duration}s\n"
            f"- regressive_node: {regressive or 'none'}\n"
        )

    # 6. Accumulated knowledge
    conoscenza_p = paths.domain_data_dir(ctx.domain) / "conoscenza.json"
    if conoscenza_p.exists():
        try:
            c = json.loads(conoscenza_p.read_text())
            il = c.get("insights_dal_lab", {})
            n_total = sum(len(v) for v in il.values() if isinstance(v, list))
            parts.append(f"## ACCUMULATED KNOWLEDGE\n- insights total: {n_total} on {len(il)} groups\n")
        except Exception:
            pass

    # 7. Trajectory (last 3 decisions)
    log_path = paths.domain_data_dir(ctx.domain) / "trajectory_log.jsonl"
    prev = _tail_jsonl(log_path, 3)
    if prev:
        parts.append("## TRAJECTORY — last 3 evaluator decisions\n")
        for d in prev:
            ts_p = d.get("ts", "?")
            dec = d.get("decision", "?")
            r = (d.get("reasoning") or "")[:100]
            parts.append(f"- {ts_p}: {dec} — {r}")

    return "\n".join(parts)


def _seme_diff(pre: dict, post: dict) -> dict:
    """Summarize seed changes without dumping everything."""
    d: dict[str, Any] = {}
    if pre.get("piano") != post.get("piano"):
        d["piano"] = f"{pre.get('piano')} -> {post.get('piano')}"
    if pre.get("direzione") != post.get("direzione"):
        d["direzione"] = {
            "was": (pre.get("direzione") or "")[:120],
            "now": (post.get("direzione") or "")[:120],
        }
    pre_ids = {t.get("id") for t in pre.get("tensioni", []) if isinstance(t, dict)}
    post_ids = {t.get("id") for t in post.get("tensioni", []) if isinstance(t, dict)}
    if pre_ids != post_ids:
        d["tensioni_resolved"] = sorted(pre_ids - post_ids)
        d["tensioni_new"] = sorted(post_ids - pre_ids)
    return d


def _tail_jsonl(path: Path, n: int = 3) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text().strip().split("\n")[-n:]
        return [json.loads(l) for l in lines if l.strip()]
    except Exception:
        return []


# ─── Decision parsing + logging ────────────────────────────────────


def _parse_decision(raw: str) -> dict[str, Any] | None:
    """Parse JSON decision from LLM output. Tolerates markdown fencing."""
    json_str = raw
    if "```" in raw:
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if m:
            json_str = m.group(1)
        else:
            json_str = raw.replace("```json", "").replace("```", "").strip()
    try:
        decision = json.loads(json_str)
    except json.JSONDecodeError:
        return None
    if "decision" not in decision:
        return None
    return decision


def _append_log(log_path: Path, entry: dict[str, Any]) -> None:
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning("trajectory_evaluator: log append failed: %s", e)


def _log_failure(log_path: Path, ts: str, failure_type: str, **extra: Any) -> None:
    _append_log(log_path, {
        "ts": datetime.now(timezone.utc).isoformat(),
        "cycle_ref": ts,
        "decision": "FAILURE",
        "failure_type": failure_type,
        **extra,
    })


# ─── Side-effect actions ───────────────────────────────────────────


def _execute_action(ctx: CycleContext, decision: dict[str, Any]) -> dict[str, Any]:
    """Execute the action attached to a decision. Whitelist + safety gates.

    Only called when execute=true is in the domain config.
    """
    import os
    import urllib.request

    action = decision.get("action") or {}
    action_type = action.get("type", "none")
    detail = action.get("detail") or {}

    if action_type == "none":
        return {"type": "none", "ok": True}

    if action_type == "notify_operator":
        msg = (detail.get("message") or decision.get("reasoning", ""))[:500]
        webhook = os.environ.get("NOTIFY_WEBHOOK_URL", "")
        if not webhook:
            return {"type": "notify_operator", "ok": False, "error": "NOTIFY_WEBHOOK_URL not set"}
        try:
            req = urllib.request.Request(
                webhook,
                data=json.dumps({"message": f"[TRAJECTORY] {msg}"}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                return {"type": "notify_operator", "ok": True, "http": r.status}
        except Exception as e:
            return {"type": "notify_operator", "ok": False, "error": str(e)}

    if action_type == "crystallize_note":
        target = detail.get("target", "memory")
        content = detail.get("content", "")
        try:
            crystal_file = paths.domain_data_dir(ctx.domain) / "trajectory_crystallize.md"
            ts_now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            with crystal_file.open("a") as f:
                f.write(f"\n---\n## {ts_now} (target: {target})\n\n{content}\n")
            return {"type": "crystallize_note", "ok": True, "file": str(crystal_file)}
        except Exception as e:
            return {"type": "crystallize_note", "ok": False, "error": str(e)}

    if action_type == "modify_seme":
        # Whitelist: only direzione, only if confidence=high
        field = detail.get("field")
        if field != "direzione":
            return {"type": "modify_seme", "ok": False,
                    "error": f"only 'direzione' field is allowed (got: {field})"}
        if decision.get("confidence") != "high":
            return {"type": "modify_seme", "ok": False,
                    "error": "modify_seme requires confidence=high"}
        try:
            seme_p = paths.seed_path(ctx.domain)
            s = json.loads(seme_p.read_text())
            old = s.get("direzione", "")
            s["direzione"] = str(detail.get("new_value", ""))[:400]
            s["timestamp"] = datetime.now(timezone.utc).isoformat()
            backup = (paths.domain_data_dir(ctx.domain) /
                      f"seed_backup_evaluator_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json")
            backup.write_text(json.dumps({"direzione_was": old}, indent=2))
            seme_p.write_text(json.dumps(s, indent=2, ensure_ascii=False))
            return {"type": "modify_seme", "ok": True,
                    "old": old[:100], "new": str(detail.get("new_value", ""))[:100]}
        except Exception as e:
            return {"type": "modify_seme", "ok": False, "error": str(e)}

    if action_type == "escalate_cowork":
        try:
            esc_file = paths.domain_data_dir(ctx.domain) / "trajectory_escalations.md"
            ts_now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            with esc_file.open("a") as f:
                f.write(
                    f"\n---\n## {ts_now}\n"
                    f"To: {detail.get('to', '?')}\n"
                    f"Subject: {detail.get('subject', '?')}\n\n"
                    f"{detail.get('body', '')}\n"
                )
            return {"type": "escalate_cowork", "ok": True, "file": str(esc_file)}
        except Exception as e:
            return {"type": "escalate_cowork", "ok": False, "error": str(e)}

    if action_type == "trigger_cycle":
        # Reserved for operator authorization — continuous mode is Approve
        return {"type": "trigger_cycle", "ok": False,
                "error": "continuous mode reserved for operator authorization"}

    return {"type": action_type, "ok": False, "error": "unknown action type"}


# ─── Movement registration ─────────────────────────────────────────

register_movement("trajectory_evaluator", trajectory_evaluator)
