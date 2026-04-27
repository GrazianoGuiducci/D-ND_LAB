"""Movement 0 — autopsy.

Regressive autopsy of the previous run. Pure I/O — no LLM, no network.
Reads the previous run's session log + raw stdout + report file, classifies
the outcome, identifies the regressive node (where the relational condition
was missing), writes lab_health.json so the next cycle's build_field has it.

Design constraints:
  - Pure I/O. No LLM call, no network.
  - Idempotent: rerunning produces the same health.json.
  - Degrade graceful: if autopsy itself fails, writes
    status="autopsy_failed" so the cycle proceeds with no health context.
  - Timeout structurally impossible (runs in seconds).

Status categories:
  completed             — report exists AND tool_use == tool_result count
  timeout_during_tool   — unanswered tool_use at end (last 17/04 pattern)
  api_error             — explicit error entries in session
  no_start              — no session log found (launcher failure)
  report_missing        — session OK but report file absent
  unknown               — none of the above patterns matched
  autopsy_failed        — exception while running autopsy
  no_run_found          — no previous run to autopsy (first cycle)

Originally /opt/MM_D-ND/tools/lab_autopsy.py — refactored:
  - paths via core.paths instead of hardcoded /opt/MM_D-ND
  - session log directory via env var CLAUDE_SESSIONS_DIR
    (Phase 2 adds native Python agent log format)
  - registered as movement so the orchestrator dispatches it
"""

from __future__ import annotations

import glob
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import paths
from core.lab_agent import CycleContext, register_movement

logger = logging.getLogger(__name__)


def autopsy(ctx: CycleContext) -> None:
    """Read the previous run, classify outcome, write health.json.

    Mutates: ctx.health (loaded for build_field), ctx.metrics["autopsy"]
    """
    health_path = paths.health_path(ctx.domain)
    reports_dir = paths.reports_dir(ctx.domain)

    try:
        # Find the most recent run before this cycle's timestamp
        ts = _find_previous_run_ts(reports_dir, exclude_ts=ctx.timestamp)
        if ts is None:
            health = {
                "status": "no_run_found",
                "autopsy_run_at": datetime.now(timezone.utc).isoformat(),
            }
            health_path.parent.mkdir(parents=True, exist_ok=True)
            health_path.write_text(json.dumps(health, indent=2))
            ctx.health = health
            ctx.metrics.setdefault("autopsy", {}).update(status="no_run_found")
            return

        raw_log = reports_dir / f"agent_{ts}_raw.log"
        report_md = reports_dir / f"agent_{ts}.md"
        jsonl = _find_session_jsonl(ts)

        session = _parse_session(jsonl) if jsonl else None
        result = _classify(session, raw_log, report_md)

        health = {
            "run_timestamp": ts,
            "autopsy_run_at": datetime.now(timezone.utc).isoformat(),
            "jsonl_path": str(jsonl) if jsonl else None,
            "raw_log_bytes": raw_log.stat().st_size if raw_log.exists() else 0,
            "report_present": report_md.exists() and report_md.stat().st_size > 0,
            "session_stats": session,
            **result,
        }

        health_path.parent.mkdir(parents=True, exist_ok=True)
        health_path.write_text(json.dumps(health, indent=2, ensure_ascii=False))
        ctx.health = health
        ctx.metrics.setdefault("autopsy", {}).update(
            status=result["status"],
            regressive_node=result.get("regressive_node"),
        )
        logger.info("autopsy %s → %s", ts, result["status"])

    except Exception as e:
        # Degrade graceful — write failure health, do not crash the cycle
        fallback = {
            "status": "autopsy_failed",
            "error": str(e),
            "autopsy_run_at": datetime.now(timezone.utc).isoformat(),
            "regressive_node": (
                "autopsy script itself failed — investigate core/autopsy.py "
                "but lab_agent continues with no health context"
            ),
        }
        try:
            health_path.parent.mkdir(parents=True, exist_ok=True)
            health_path.write_text(json.dumps(fallback, indent=2))
        except Exception:
            pass
        ctx.health = fallback
        ctx.metrics.setdefault("autopsy", {}).update(status="autopsy_failed", error=str(e))
        logger.error("autopsy failed: %s", e)


# ─── Internals ──────────────────────────────────────────────────────


def _find_previous_run_ts(reports_dir: Path, exclude_ts: str | None = None) -> str | None:
    """Find the most recent run by parsing agent_*_raw.log filenames.

    Excludes the current cycle's timestamp (a run that is the current
    cycle would not be a 'previous' run to autopsy).
    """
    if not reports_dir.exists():
        return None
    raw_logs = sorted(
        reports_dir.glob("agent_*_raw.log"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for log in raw_logs:
        m = re.search(r"agent_(\d{8}_\d{4})_raw\.log", log.name)
        if m:
            ts = m.group(1)
            if ts != exclude_ts:
                return ts
    return None


def _find_session_jsonl(ts: str) -> Path | None:
    """Find the LLM session jsonl that corresponds to a run timestamp.

    Today: scans CLAUDE_SESSIONS_DIR (default ~/.claude/projects/...) for
    jsonls with first-message timestamp within 10 min of the run start.

    Phase 2: when the native Python agent runs, it will write its own
    structured log inside the domain data dir. This function will check
    that location first, falling back to Claude Code jsonl for legacy.
    """
    sessions_dir_env = os.environ.get("CLAUDE_SESSIONS_DIR")
    if sessions_dir_env:
        sessions_dir = Path(sessions_dir_env)
    else:
        # Default: ~/.claude/projects/<encoded-cwd>/ — Claude Code convention
        home_claude = Path.home() / ".claude" / "projects"
        if not home_claude.exists():
            return None
        # Best-effort: pick the dir that matches CWD
        cwd_encoded = "-" + str(Path.cwd()).replace("/", "-").lstrip("-")
        candidate = home_claude / cwd_encoded
        sessions_dir = candidate if candidate.exists() else home_claude

    if not sessions_dir.exists():
        return None

    try:
        run_dt = datetime.strptime(ts, "%Y%m%d_%H%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None

    candidates: list[tuple[float, Path]] = []
    for f in sessions_dir.rglob("*.jsonl"):
        try:
            with open(f) as fh:
                for line in fh:
                    try:
                        d = json.loads(line)
                    except Exception:
                        continue
                    t = d.get("timestamp", "")
                    if t:
                        try:
                            first = datetime.fromisoformat(t.replace("Z", "+00:00"))
                            delta = abs((first - run_dt).total_seconds())
                            if delta < 600:  # within 10 min
                                candidates.append((delta, f))
                        except Exception:
                            pass
                        break
        except Exception:
            continue
    if not candidates:
        return None
    return sorted(candidates)[0][1]


def _parse_session(jsonl: Path) -> dict[str, Any]:
    """Parse a session jsonl: count tool_use/result, extract last events."""
    tu = tr = th = tx = 0
    first_ts = last_ts = None
    last_tool_use = None
    last_text = None
    error_entries: list[str] = []
    tool_use_ids: list[str] = []
    tool_result_ids: set[str] = set()

    try:
        with open(jsonl) as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                t = d.get("timestamp", "")
                if t:
                    if not first_ts:
                        first_ts = t
                    last_ts = t

                msg = d.get("message", {})
                if not isinstance(msg, dict):
                    continue
                content = msg.get("content", [])
                if not isinstance(content, list):
                    continue

                for c in content:
                    if not isinstance(c, dict):
                        continue
                    ty = c.get("type", "")
                    if ty == "tool_use":
                        tu += 1
                        tool_use_ids.append(c.get("id", ""))
                        last_tool_use = {
                            "id": c.get("id", ""),
                            "name": c.get("name", ""),
                            "input_preview": str(c.get("input", ""))[:400],
                            "timestamp": t,
                        }
                    elif ty == "tool_result":
                        tr += 1
                        tool_result_ids.add(c.get("tool_use_id", ""))
                    elif ty == "thinking":
                        th += 1
                    elif ty == "text":
                        tx += 1
                        last_text = c.get("text", "")[:500]

                if d.get("type") == "error" or msg.get("type") == "error":
                    error_entries.append(t)
    except Exception:
        # File unreadable — return whatever we got so classify can decide
        pass

    unanswered_ids = [tid for tid in tool_use_ids if tid not in tool_result_ids]
    duration_s = None
    if first_ts and last_ts:
        try:
            a = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
            b = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            duration_s = int((b - a).total_seconds())
        except Exception:
            pass

    return {
        "tool_use": tu,
        "tool_result": tr,
        "thinking": th,
        "text": tx,
        "unanswered_tool_use": len(unanswered_ids),
        "last_tool_use": last_tool_use if unanswered_ids else None,
        "last_text": last_text,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "duration_s": duration_s,
        "error_entries": error_entries,
    }


def _classify(
    session: dict[str, Any] | None,
    raw_log: Path,
    report_md: Path,
) -> dict[str, Any]:
    """Classify run outcome from session + raw_log + report presence."""
    report_exists = report_md.exists() and report_md.stat().st_size > 0
    raw_log_size = raw_log.stat().st_size if raw_log.exists() else 0

    if session is None:
        return {
            "status": "no_start",
            "regressive_node": (
                "launcher: agent failed to initialize "
                "(auth, binary missing, or environment issue)"
            ),
            "recommendation": (
                "verify LLM_API_KEY, LLM_BASE_URL, LLM_MODEL env vars; "
                "test with `dndlab inspect --domain <name>`"
            ),
        }

    unans = session["unanswered_tool_use"]
    duration = session["duration_s"] or 0
    errors = session["error_entries"]

    if errors:
        return {
            "status": "api_error",
            "regressive_node": "upstream API failure during run",
            "recommendation": (
                "verify provider status; if recurrent, "
                "consider retry budget or backoff"
            ),
            "error_timestamps": errors[:3],
        }

    if report_exists and unans == 0:
        return {
            "status": "completed",
            "regressive_node": None,
            "duration_s": duration,
        }

    if unans > 0:
        last = session.get("last_tool_use") or {}
        tool_name = last.get("name", "?")
        preview = last.get("input_preview", "")
        return {
            "status": "timeout_during_tool",
            "regressive_node": (
                f"agent_field_live lacks pre-computed input for the chosen experiment; "
                f"the agent had to regenerate from scratch inside a single tool_use ({tool_name}) "
                f"that did not complete within residual budget. "
                f"Fix lives in the field_live missing condition, not the timeout value."
            ),
            "last_tool_use": {"name": tool_name, "input_preview": preview},
            "duration_s": duration,
            "recommendation": (
                "consider pre-computing the dataset the agent tends to rebuild "
                "and include a pointer in the next agent_field_live. "
                "Do NOT raise the timeout (det=+1)."
            ),
        }

    if not report_exists and unans == 0:
        return {
            "status": "report_missing",
            "regressive_node": (
                "agent finished tool sequence but did not emit final report file."
            ),
            "recommendation": (
                "ensure the prompt reinforces: after experiment, MUST write report "
                "to <data>/<domain>/reports/agent_{TS}.md as final step."
            ),
            "duration_s": duration,
        }

    return {
        "status": "unknown",
        "regressive_node": "autopsy could not classify this run from available signals",
        "duration_s": duration,
        "raw_log_size": raw_log_size,
    }


# ─── Movement registration ─────────────────────────────────────────

register_movement("autopsy", autopsy)
