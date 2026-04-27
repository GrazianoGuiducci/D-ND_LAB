"""Movement 1 — build_field.

Assembles the "live agent field" — the markdown document the LLM agent
reads at the start of each cycle. The field combines:

  - Reference to the domain context (model, axioms, anti-patterns)
  - Autopsy of the previous run (regressive node, recommendation)
  - Current piano + direction from the seed
  - Active tensions
  - Convergence map (where multiple tensions point at the same thing)
  - Last 3 agent reports (so the cycle does not repeat what was found)
  - Operator observations (optional, domain-specific path)
  - Last interactive session resultant (optional, from lab_registro.json)
  - Unprocessed videos / external inputs (optional)
  - Projector output (optional, domain-specific module)
  - Knowledge graph topology (universal — reads lab_graph.json)
  - Task instructions (domain-specific, from config)

Originally /opt/MM_D-ND/tools/build_agent_field.py — refactored here so
the scheletro is universal and the domain content is plugged in via
the domain config.

Plugin contract (declared in domain config under
movements.build_field.params):
  observations_path:    optional string — markdown file with operator
                        observations (parsed for sections + quotes)
  projector_module:     optional string — Python import path that
                        exposes a ScenarioProjector-compatible class
  task_section_path:    optional string — markdown file appended at the
                        end ("Cosa fare" — domain-specific task list)
  registro_path:        optional string — JSON file with lab_registro
                        (interactive session resultants)
  video_feed_path:      optional string — JSON file with video feed
"""

from __future__ import annotations

import glob
import importlib
import itertools
import json
import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from core import config as cfg
from core import paths
from core.lab_agent import CycleContext, register_movement

logger = logging.getLogger(__name__)


# ─── Movement entry point ───────────────────────────────────────────


def build_field(ctx: CycleContext) -> None:
    """Assemble the live field for this cycle. Writes to <data>/<domain>/agent_field_live.md.

    Mutates: ctx.metrics["build_field"]["bytes"], ["sections"]
    """
    params = cfg.movement_params(ctx.config, "build_field")

    parts: list[str] = []
    sections_written: list[str] = []

    # 1. Static context link — points to the domain context.md
    parts.append(_intro_section(ctx.domain))
    sections_written.append("intro")

    # 2. Autopsy of previous run (Riparazione Regressiva)
    if ctx.health:
        autopsy_md = _autopsy_section(ctx.health)
        if autopsy_md:
            parts.append(autopsy_md)
            sections_written.append("autopsy_summary")

    # 3. Piano + direction
    parts.append(_seed_header_section(ctx.seed))
    sections_written.append("seed_header")

    # 4. Active tensions
    parts.append(_tensions_section(ctx.seed))
    sections_written.append("tensions")

    # 5. Convergence map
    conv = _convergence_section(ctx.seed)
    if conv:
        parts.append(conv)
        sections_written.append("convergence")

    # 6. Last N reports
    n_reports = int(params.get("recent_reports_n", 3))
    reports_md = _recent_reports_section(paths.reports_dir(ctx.domain), n=n_reports)
    if reports_md:
        parts.append(reports_md)
        sections_written.append("recent_reports")

    # 7. Operator observations (optional, domain-specific)
    obs_path = params.get("observations_path")
    if obs_path:
        obs_md = _observations_section(ctx.seed, _resolve_domain_path(ctx.domain, obs_path))
        if obs_md:
            parts.append(obs_md)
            sections_written.append("observations")

    # 8. Lab registro (optional)
    registro_path = params.get("registro_path")
    if registro_path:
        reg_md = _registro_section(_resolve_domain_path(ctx.domain, registro_path))
        if reg_md:
            parts.append(reg_md)
            sections_written.append("registro")

    # 9. Video feed (optional)
    video_path = params.get("video_feed_path")
    if video_path:
        video_md = _video_feed_section(_resolve_domain_path(ctx.domain, video_path))
        if video_md:
            parts.append(video_md)
            sections_written.append("video_feed")

    # 10. Projector output (optional, domain-specific module)
    projector_module = params.get("projector_module")
    if projector_module:
        proj_md = _projector_section(projector_module)
        if proj_md:
            parts.append(proj_md)
            sections_written.append("projector")

    # 11. Topology (universal — reads lab_graph.json if it exists)
    topo_md = _topology_section(paths.lab_graph_path(ctx.domain))
    if topo_md:
        parts.append(topo_md)
        sections_written.append("topology")

    # 12. Task section (domain-specific, from config or default)
    task_path = params.get("task_section_path")
    task_md = _task_section(_resolve_domain_path(ctx.domain, task_path) if task_path else None)
    parts.append(task_md)
    sections_written.append("task")

    # Assemble + write
    field_text = "\n".join(parts)
    field_path = paths.field_live_path(ctx.domain)
    field_path.parent.mkdir(parents=True, exist_ok=True)
    field_path.write_text(field_text)

    ctx.metrics.setdefault("build_field", {}).update(
        bytes=len(field_text.encode()),
        sections=sections_written,
        path=str(field_path),
    )
    logger.info(
        "build_field: %d bytes, %d sections written to %s",
        len(field_text.encode()), len(sections_written), field_path,
    )


# ─── Section builders (universal — work on any domain) ─────────────


def _intro_section(domain: str) -> str:
    """Reference to domain context. The agent reads context.md for axioms,
    anti-patterns, bicono examples — domain-specific content stays there."""
    rel = f"domains/{domain}/context.md"
    return (
        f"Read {rel} for the domain model, condensate, structures, rules, "
        f"and errors to avoid. The cycle's context lives there — this field "
        f"is the live state, not the static knowledge.\n"
    )


def _autopsy_section(health: dict[str, Any]) -> str | None:
    """Render autopsy summary of previous run."""
    if not health:
        return None
    parts = []
    status = health.get("status", "unknown")
    if status == "completed":
        duration = health.get("duration_s", "?")
        parts.append(f"## Previous run: completed ({duration}s) — start from the consecutio.\n")
    elif status in ("timeout_during_tool", "api_error", "report_missing", "no_start", "autopsy_failed"):
        parts.append("## ATTENTION — previous run did not complete")
        parts.append(f"- Status: **{status}**")
        if rn := health.get("regressive_node"):
            parts.append(f"- Regressive node: {rn}")
        if rec := health.get("recommendation"):
            parts.append(f"- Recommendation: {rec}")
        if last_tu := health.get("last_tool_use"):
            preview = str(last_tu.get("input_preview", ""))[:200]
            parts.append(f"- Last tool interrupted: {last_tu.get('name')} — input: `{preview}`")
        parts.append("")
        parts.append(
            "Apply Regressive Repair: do NOT repeat the same form of failure. "
            "If the regressive node is 'live field without precomputed data', "
            "do NOT regenerate from scratch inside a single tool_use. "
            "If the node is 'scope too wide for budget', reduce scope, "
            "do not extend time.\n"
        )
    if health.get("affinatore_status") == "pending":
        reason = health.get("affinatore_reason", "?")
        parts.append(f"_Refiner of previous run: pending ({reason})_\n")
    return "\n".join(parts) if parts else None


def _seed_header_section(seme: dict[str, Any]) -> str:
    piano = seme.get("piano", "?")
    direzione = (seme.get("direzione", "?") or "?")[:100]
    return f"## Plan {piano} — {direzione}\n"


def _tensions_section(seme: dict[str, Any]) -> str:
    parts = ["## Active tensions"]
    for t in seme.get("tensioni", [])[:8]:
        # Support both 'intensità' (Italian original) and 'intensita' (ASCII)
        i = t.get("intensità", t.get("intensita", "?"))
        tid = t.get("id", "?")
        claim = (t.get("claim", "") or "")[:150]
        parts.append(f"- [{tid}] ({i}) {claim}")
    parts.append("")
    return "\n".join(parts)


def _convergence_section(seme: dict[str, Any]) -> str | None:
    """Where do multiple tensions point at the same thing? Universal."""
    tensioni = seme.get("tensioni", [])
    if len(tensioni) < 2:
        return None

    clusters: dict[str, list[str]] = {}
    for t in tensioni:
        claim = (t.get("claim", "") or "").lower()
        tid = t.get("id", "?")
        words = {w for w in claim.split() if len(w) > 4}
        for w in words:
            clusters.setdefault(w, []).append(tid)

    convergences = {w: tids for w, tids in clusters.items() if len(set(tids)) >= 2}
    if not convergences:
        return None

    sorted_conv = sorted(convergences.items(), key=lambda x: len(set(x[1])), reverse=True)[:5]
    parts = ["## Convergence — where multiple tensions point at the same thing"]
    for word, tids in sorted_conv:
        unique = sorted(set(tids))
        parts.append(f'  "{word}" → {", ".join(unique)}')
    parts.append("This is where potential concentrates. Do not ignore it.\n")
    return "\n".join(parts)


def _recent_reports_section(reports_dir: Path, n: int = 3) -> str | None:
    """Last N agent reports — what was found, what was opened. Universal parser."""
    if not reports_dir.exists():
        return None
    pattern = str(reports_dir / "agent_*.md")
    files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)[:n]
    if not files:
        return None

    parts = [f"## Last {len(files)} runs — where you start"]
    for fp in files:
        try:
            content = Path(fp).read_text()
        except Exception:
            continue
        title = ""
        findings = ""
        verdict = ""
        # Title = first level-1 heading
        for line in content.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        # Sections
        for s in content.split("## "):
            if s.startswith("Key Findings") or s.startswith("Findings"):
                findings = s.split("\n", 1)[1][:500] if "\n" in s else ""
            elif s.startswith("Verdict"):
                verdict = s.split("\n", 1)[1][:200] if "\n" in s else ""

        parts.append(f"### {title or os.path.basename(fp)}")
        if findings.strip():
            parts.append(f"Found: {findings.strip()[:300]}")
        if verdict.strip():
            parts.append(f"Verdict: {verdict.strip()[:150]}")
        parts.append("")

    parts.append("Do not repeat these experiments. Continue from where they arrived — the consecutio.\n")
    return "\n".join(parts)


def _topology_section(graph_path: Path) -> str | None:
    """Knowledge graph topology — degrees, voids, ghost generators.

    Reads lab_graph.json. Generic to any domain that produces a graph
    with nodes (some typed 'teoria', some 'ghost') and edges. The semantics
    of node types are domain-specific but the structural surfacing is universal.
    """
    if not graph_path.exists():
        return None
    try:
        g = json.loads(graph_path.read_text())
    except json.JSONDecodeError:
        return None
    if not g or "graph" not in g:
        return None

    nodes = g["graph"].get("nodes", [])
    edges = g["graph"].get("edges", [])
    stats = g.get("stats", {})

    nd = {n["id"]: n for n in nodes}
    theories = [n["id"] for n in nodes if n.get("type") == "teoria"]

    deg: dict[str, int] = defaultdict(int)
    for e in edges:
        deg[e["source"]] += 1
        deg[e["target"]] += 1

    theory_deg = {t: deg[t] for t in theories}

    ghost_sources: dict[str, int] = defaultdict(int)
    for e in edges:
        s, t = e["source"], e["target"]
        if nd.get(s, {}).get("type") == "ghost":
            ghost_sources[t] += 1
        if nd.get(t, {}).get("type") == "ghost":
            ghost_sources[s] += 1
    generatrici = sorted(
        ((nid, cnt) for nid, cnt in ghost_sources.items() if cnt >= 2),
        key=lambda x: -x[1],
    )[:3]

    parts = ["## Field topology — the shape of the graph"]
    if theory_deg:
        ordered = sorted(theory_deg.items(), key=lambda x: -x[1])
        parts.append("Theory degrees: " + ", ".join(f"{t}={d}" for t, d in ordered))
        max_d = ordered[0][1] if ordered else 0
        dormant = [t for t, d in ordered if d <= max(4, max_d // 3)]
        if dormant and len(dormant) < len(ordered):
            parts.append(f"Dormant (low discovery anchoring): {', '.join(dormant)}")
    parts.append(
        f"Structure: {stats.get('ponti', 0)} bridges, {stats.get('vuoti', 0)} void(s), "
        f"{stats.get('scoperte', 0)} discoveries, {stats.get('cicli', 0)} cycles."
    )
    if stats.get("ghost_high_urgency"):
        parts.append(
            f"High-urgency ghosts: {stats['ghost_high_urgency']} — mature connections "
            "awaiting crystallization (not to be generated, to be recognized)."
        )
    if generatrici:
        parts.append("Generators (nodes emitting ≥2 ghost connections):")
        for nid, cnt in generatrici:
            lbl = nd.get(nid, {}).get("label", nid)[:70]
            parts.append(f"  {nid} ({cnt} ghosts): {lbl}")
        parts.append(
            "A generator with dense ghosts = a discovery the system is still "
            "passing through. Premature closure if marked 'resolved' in the seed."
        )
    parts.append(
        "The combo recognizes asymmetry. The dipole lives across all bridges — "
        "not only where the lab has already measured.\n"
    )
    return "\n".join(parts)


# ─── Domain plugins (loaded via config) ─────────────────────────────


def _observations_section(seme: dict[str, Any], obs_path: Path) -> str | None:
    """Operator observations resonant with active tensions.

    Domain provides the markdown file. Format: sections separated by '## ',
    each with a leading title and at least one '> ' quote line.
    """
    if not obs_path.exists():
        return None
    try:
        raw = obs_path.read_text()
    except Exception:
        return None

    sections = raw.split("\n## ")[1:]
    observations = []
    for s in sections:
        lines = s.strip().split("\n")
        title = lines[0] if lines else ""
        quote = ""
        for line in lines:
            if line.startswith("> "):
                quote = line[2:][:300]
                break
        if title and quote:
            observations.append({"title": title, "text": quote})

    # Find resonant: those mentioning concepts in active tensions
    tensioni_text = " ".join(
        (t.get("claim", "") or "") for t in seme.get("tensioni", [])
    ).lower()
    keywords = {w for w in tensioni_text.split() if len(w) > 4}
    if not keywords:
        return None

    relevant = []
    for obs in observations:
        text = (obs["title"] + obs["text"]).lower()
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            relevant.append({**obs, "score": score})
    relevant.sort(key=lambda x: x["score"], reverse=True)

    if not relevant:
        return None

    parts = ["## Operator observations (resonant with the tensions)"]
    for o in relevant[:3]:
        parts.append(f"**{o['title']}**: {o['text']}")
    parts.append("")
    return "\n".join(parts)


def _registro_section(registro_path: Path) -> str | None:
    """Latest interactive session resultant, if domain provides a registro."""
    if not registro_path.exists():
        return None
    try:
        reg = json.loads(registro_path.read_text())
    except json.JSONDecodeError:
        return None
    sessioni = reg.get("sessioni", [])
    if not sessioni:
        return None
    latest = sessioni[-1]
    risultante = latest.get("risultante_sessione")
    if not risultante:
        return None
    return f"## Resultant of last interactive session\n{risultante[:300]}\n"


def _video_feed_section(feed_path: Path) -> str | None:
    if not feed_path.exists():
        return None
    try:
        feed = json.loads(feed_path.read_text())
    except json.JSONDecodeError:
        return None
    videos = [v for v in feed.get("videos", []) if not v.get("processed")]
    if not videos:
        return None
    parts = ["## Videos from operator (unprocessed)"]
    for v in videos:
        parts.append(f"**{v.get('title', '?')}**: {(v.get('content') or '')[:200]}")
        for c in v.get("coupling", [])[:2]:
            parts.append(f"  Coupling: {c[:100]}")
    parts.append(
        "After using a video, mark processed=true in the feed file.\n"
    )
    return "\n".join(parts)


def _projector_section(projector_module: str) -> str | None:
    """Optional projector output. The domain provides a Python module path
    that exposes a class with risultante_projection() and
    highest_information_experiment() methods (ScenarioProjector-compatible).

    If the import fails or the module raises, we degrade gracefully — the
    field is still useful without the projector.
    """
    try:
        mod = importlib.import_module(projector_module)
    except ImportError as e:
        logger.warning("projector_module %s not importable: %s", projector_module, e)
        return None

    # Look for a ScenarioProjector class or a build_projection() function
    if hasattr(mod, "ScenarioProjector"):
        try:
            sp = mod.ScenarioProjector()
            ris = sp.risultante_projection()
            experiments = sp.highest_information_experiment()
        except Exception as e:
            logger.warning("projector failed: %s", e)
            return None
    elif hasattr(mod, "build_projection"):
        try:
            ris = mod.build_projection()
            experiments = ris.get("experiments", [])
        except Exception as e:
            logger.warning("build_projection failed: %s", e)
            return None
    else:
        logger.warning(
            "projector_module %s has neither ScenarioProjector class nor build_projection()",
            projector_module,
        )
        return None

    parts = ["## Projection — where the resultant points"]
    r = ris.get("risultante") or {}
    parts.append(f"Resultant: R={r.get('value', '?')} (h={r.get('h', '?')}). {r.get('interpretation', '')}")
    conv = ris.get("convergence") or {}
    if "orizzonte" in conv:
        parts.append(f"Horizon: {conv['orizzonte']}")
    if conv.get("spread_decades") is not None:
        coh = "coherent" if conv.get("coherent") else "not coherent"
        parts.append(f"Spread: {conv['spread_decades']} decades ({coh})")
    for p in (ris.get("projections") or [])[:3]:
        parts.append(f"  {p.get('id')}: {p.get('target', p.get('slope', p.get('type', '')))}")

    if experiments:
        ex = experiments[0]
        parts.append(f"\n**Highest-information experiment:** {ex.get('id')} (score={ex.get('score')})")
        parts.append(f"  {ex.get('reason', '')}")
    parts.append("")
    return "\n".join(parts)


def _task_section(task_path: Path | None) -> str:
    """Final task instructions — domain-specific.

    If the domain provides a task_section_path, read it. Otherwise emit a
    minimal universal task: pick a tension, run, write report, update seed.
    """
    if task_path and task_path.exists():
        try:
            return task_path.read_text()
        except Exception:
            pass
    return (
        "## What to do\n"
        "1. Read the active tensions and pick one with high discriminating power.\n"
        "2. Formulate one question that, if answered, changes the system state.\n"
        "3. Run the experiment. Record numbers + null baseline.\n"
        "4. Write the report following the format in the domain context.md, "
        "including the bicono section.\n"
        "5. Update the seed: add a tension or constraint based on what you found.\n"
    )


# ─── Helpers ────────────────────────────────────────────────────────


def _resolve_domain_path(domain: str, rel: str) -> Path:
    """Resolve a path that's relative to the domain directory."""
    if Path(rel).is_absolute():
        return Path(rel)
    return paths.domain_dir(domain) / rel


# ─── Movement registration ─────────────────────────────────────────

register_movement("build_field", build_field)
