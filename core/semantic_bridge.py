"""Movement 11 — semantic_bridge.

Bridges numeric findings of the lab to semantic annotations on a
knowledge structure (e.g. theory pairs). Reads the cycle's agent_report,
extracts source_tension + maturity + bicono, looks up the domain's
tension_to_category mapping, generates insights on the corresponding
pair(s), and appends to conoscenza.json (idempotent dedup).

This is a contractor between two universes:
  - the per-cycle agent output (numeric findings on specific tensions)
  - the long-lived knowledge structure (theory crossings, paired concepts)

Originally /opt/MM_D-ND/tools/semantic_bridge.py — refactored:
  - paths via core.paths
  - mapping path from domain config (tension_to_category)
  - conoscenza path standardized to <data>/<domain>/conoscenza.json
  - sync to external endpoint dropped from core (Phase 1 — handled by
    movement 'sync' if domain enables it)
  - QA validation kept minimal here; complex domain-specific QA can
    plug in via params.qa_module

Phase 1 scope: process the current cycle's agent report. Extra sources
(evolution reports, multi-cycle backfill) are Phase 4 if domains need them.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import config as cfg
from core import paths
from core.lab_agent import CycleContext, register_movement

logger = logging.getLogger(__name__)


# Maturity classification keywords (universal — derived from D-ND verdict types)
MATURITY_A = {"CONFIRMED", "CONSTRAINT", "FALSIFIED", "REJECTED"}
MATURITY_F = {"PARTIAL", "EMERGING", "CANDIDATE", "UNDERDETERMINED"}


def semantic_bridge(ctx: CycleContext) -> None:
    """Process the current cycle's agent report → conoscenza.json.

    Mutates: conoscenza.json on disk; ctx.metrics["semantic_bridge"]
    """
    try:
        mapping_path = cfg.domain_path_or_none(ctx.config, "tension_to_category")
    except cfg.ConfigError as e:
        # File declared but missing — common during Phase 1 (domain not populated)
        ctx.metrics.setdefault("semantic_bridge", {}).update(
            skipped=f"mapping file missing: {e}"
        )
        logger.info("semantic_bridge: %s", e)
        return
    if mapping_path is None or not mapping_path.exists():
        ctx.metrics.setdefault("semantic_bridge", {}).update(
            skipped="no tension_to_category mapping"
        )
        logger.info("semantic_bridge: no mapping configured, skipping")
        return

    mapping = _load_json(mapping_path) or {}
    if not mapping:
        ctx.metrics.setdefault("semantic_bridge", {}).update(skipped="empty mapping")
        return

    report_md = paths.reports_dir(ctx.domain) / f"agent_{ctx.timestamp}.md"
    if not report_md.exists():
        ctx.metrics.setdefault("semantic_bridge", {}).update(
            skipped="no current report (agent may have been skipped)"
        )
        return

    try:
        report_text = report_md.read_text()
    except Exception as e:
        ctx.metrics.setdefault("semantic_bridge", {}).update(error=f"read failed: {e}")
        return

    # Extract structured info from report
    source_tension = _extract_source_tension(report_text)
    if not source_tension:
        ctx.metrics.setdefault("semantic_bridge", {}).update(
            skipped="no source_tension in report"
        )
        return

    maturity = _extract_maturity(report_text)
    bicono = _extract_bicono(report_text)
    title = _extract_title(report_text) or f"Cycle {ctx.timestamp}"

    # Map tension → categories (e.g. theories involved)
    categories = mapping.get(source_tension, [])
    if isinstance(categories, str):
        categories = [categories]
    if len(categories) < 2:
        ctx.metrics.setdefault("semantic_bridge", {}).update(
            skipped=f"tension '{source_tension}' touches <2 categories",
            categories=categories,
        )
        logger.info(
            "semantic_bridge: tension %s maps to %d categories, need ≥2",
            source_tension, len(categories),
        )
        return

    # Generate insights on pairs of categories
    conoscenza_path = paths.domain_data_dir(ctx.domain) / "conoscenza.json"
    conoscenza = _load_json(conoscenza_path) or {"insights_dal_lab": {}}
    insights_root = conoscenza.setdefault("insights_dal_lab", {})

    new_count = 0
    pairs_touched: list[str] = []
    from itertools import combinations
    for a, b in combinations(sorted(categories), 2):
        pair = f"{a}x{b}"
        pair_insights = insights_root.setdefault(pair, [])
        # Dedup: same date + tension already present
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        already = any(
            i.get("date") == date_str and i.get("source_tension") == source_tension
            for i in pair_insights
            if isinstance(i, dict)
        )
        if already:
            continue
        insight = {
            "date": date_str,
            "cycle": ctx.timestamp,
            "source_tension": source_tension,
            "title": title[:200],
            "maturity": maturity,
            "report": report_md.name,
        }
        if bicono:
            insight["bicono"] = bicono
        pair_insights.append(insight)
        # Cap per pair to keep file bounded
        cap = 10
        if len(pair_insights) > cap:
            insights_root[pair] = pair_insights[-cap:]
        new_count += 1
        pairs_touched.append(pair)

    if new_count == 0:
        ctx.metrics.setdefault("semantic_bridge", {}).update(
            skipped="all insights already present (dedup)"
        )
        return

    try:
        conoscenza_path.parent.mkdir(parents=True, exist_ok=True)
        conoscenza_path.write_text(json.dumps(conoscenza, indent=2, ensure_ascii=False))
    except Exception as e:
        ctx.metrics.setdefault("semantic_bridge", {}).update(error=f"write failed: {e}")
        return

    # QA: minimal validation
    issues = _validate_insights(insights_root, pairs_touched)
    if issues:
        issues_log = paths.domain_data_dir(ctx.domain) / "bridge_issues.jsonl"
        with issues_log.open("a") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                "cycle_ref": ctx.timestamp,
                "n_issues": len(issues),
                "issues": issues,
            }, ensure_ascii=False) + "\n")

    ctx.metrics.setdefault("semantic_bridge", {}).update(
        new_insights=new_count,
        pairs=pairs_touched,
        qa_issues=len(issues),
    )
    logger.info(
        "semantic_bridge: %d new insights across %d pair(s), %d QA issues",
        new_count, len(pairs_touched), len(issues),
    )


# ─── Extractors ────────────────────────────────────────────────────


def _extract_source_tension(text: str) -> str | None:
    """Find the tension ID this cycle explored.

    Looks for patterns like:
      **Tension explored**: ID (intensity)
      Tension: ID
      [TENSION_ID]
    """
    m = re.search(
        r"\*\*Tension(?:\s+explored)?\*\*:\s*([A-Z_][A-Z0-9_]*)",
        text,
    )
    if m:
        return m.group(1)
    m = re.search(r"Tension:\s*([A-Z_][A-Z0-9_]*)", text)
    if m:
        return m.group(1)
    m = re.search(r"\[([A-Z][A-Z0-9_]{2,})\]", text)
    if m:
        return m.group(1)
    return None


def _extract_maturity(text: str) -> str:
    """Verdict → A (anchored, do not evict) / F (floating) / C (unknown, default)."""
    verdict_match = re.search(r"##\s*Verdict[^\n]*\n(.*?)(?=\n##|\Z)", text,
                              re.DOTALL | re.IGNORECASE)
    scan = (verdict_match.group(1) if verdict_match else text[:1500]).upper()
    for kw in MATURITY_A:
        if re.search(r"\b" + kw + r"\b", scan):
            return "A"
    for kw in MATURITY_F:
        if re.search(r"\b" + kw + r"\b", scan):
            return "F"
    return "C"


def _extract_bicono(text: str) -> dict[str, str] | None:
    """Extract the Bicono della scoperta section if present.

    Format expected (from lab_context_template.md):
      ## Bicono della scoperta
      - **Two roots** (...): <text>
      - **Singular** (...): <text>
      - **Invariant of passage** (...): <text>
      - **Field of possibility**: ...
    """
    sec = re.search(
        r"##\s*Bicono\s+della\s+scoperta[^\n]*\n(.*?)(?=\n##|\Z)",
        text, re.DOTALL,
    )
    if not sec:
        return None
    body = sec.group(1)

    def find_field(*keys: str) -> str | None:
        for key in keys:
            m = re.search(
                rf"-\s*\*\*{re.escape(key)}[^*]*\*\*[^:]*:\s*(.+?)(?=\n-\s*\*\*|\Z)",
                body, re.DOTALL | re.IGNORECASE,
            )
            if m:
                return m.group(1).strip()[:400]
        return None

    out: dict[str, str] = {}
    if v := find_field("Two roots", "Due radici", "Roots"):
        out["roots"] = v
    if v := find_field("Singular", "Singolare"):
        out["singular"] = v
    if v := find_field("Invariant", "Invariante"):
        out["invariant"] = v
    if v := find_field("Field", "Campo"):
        out["field"] = v
    return out if out else None


def _extract_title(text: str) -> str | None:
    """First level-1 heading."""
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else None


# ─── QA ─────────────────────────────────────────────────────────────


def _validate_insights(
    insights_root: dict[str, list[Any]],
    pairs: list[str],
) -> list[dict[str, Any]]:
    """Minimal QA: flag insights with missing required fields."""
    issues: list[dict[str, Any]] = []
    for pair in pairs:
        for ins in insights_root.get(pair, []):
            if not isinstance(ins, dict):
                continue
            if not ins.get("title"):
                issues.append({
                    "severity": "warn",
                    "pair": pair,
                    "kind": "missing_title",
                    "message": "insight has no title",
                })
            if not ins.get("source_tension"):
                issues.append({
                    "severity": "error",
                    "pair": pair,
                    "kind": "missing_source_tension",
                    "message": "insight has no source_tension",
                })
    return issues


# ─── Helpers ────────────────────────────────────────────────────────


def _load_json(p: Path) -> dict[str, Any] | None:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


# ─── Movement registration ─────────────────────────────────────────

register_movement("semantic_bridge", semantic_bridge)
