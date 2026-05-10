"""Web API for D-ND_LAB dashboard.

Single-file FastAPI service exposing the lab as REST + WebSocket.
The filesystem stays the source of truth — this layer reads from
data/<domain>/* and shells out to `python -m core.cli` for cycles.

Endpoints:
  GET  /api/health
  GET  /api/domains
  GET  /api/domains/{d}/seed
  GET  /api/domains/{d}/reports
  GET  /api/domains/{d}/reports/{filename}
  GET  /api/domains/{d}/trajectory
  GET  /api/domains/{d}/cost
  GET  /api/domains/{d}/cimitero
  POST /api/domains/{d}/run                  # async cycle, returns cycle_id
  WS   /api/cycles/{cycle_id}/log            # live log stream
  POST /api/domains/{d}/chat                 # chat agent (single-shot or streaming)
  POST /api/domains/{d}/inject_tension       # gated side-effect

Frontend (static HTML/JS) served from /static and /.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from html import escape as html_escape
from pathlib import Path
from typing import Any, Callable

try:
    from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, Response
    from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
except ImportError as e:
    raise SystemExit(
        "FastAPI not installed. Run: pip install 'fastapi>=0.115' 'uvicorn[standard]>=0.32'"
    ) from e

from core import config as cfg
from core import paths

logger = logging.getLogger(__name__)


# ─── Config ─────────────────────────────────────────────────────────


class Settings:
    """Resolved at app startup from env vars."""
    def __init__(self) -> None:
        self.auth_enabled: bool = os.environ.get("DASHBOARD_AUTH", "disabled").lower() == "enabled"
        self.host: str = os.environ.get("DASHBOARD_HOST", "0.0.0.0")
        self.port: int = int(os.environ.get("DASHBOARD_PORT", "5000"))
        self.demo_mode: bool = os.environ.get("DASHBOARD_DEMO_MODE", "false").lower() == "true"
        self.cycle_python: str = os.environ.get(
            "DASHBOARD_CYCLE_PYTHON",
            os.environ.get("PYTHON", "python3"),
        )

settings = Settings()


app = FastAPI(
    title="D-ND_LAB",
    description="Dashboard API for the autonomous research lab.",
    version="0.1.0-alpha",
)


# ─── Cycle registry (in-memory) ────────────────────────────────────
# Tracks running cycles started via the API. WebSocket consumers tail
# the log file. Phase 6 v2 may move this to Redis for multi-process.

_CYCLES: dict[str, dict[str, Any]] = {}


def _start_cycle(domain: str, direction_override: str | None = None) -> str:
    """Spawn a `dndlab run --domain X` subprocess. Returns cycle_id."""
    cycle_id = uuid.uuid4().hex[:12]
    log_path = paths.domain_data_dir(domain) / "cycle_logs" / f"{cycle_id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    if direction_override:
        env["LAB_DIRECTION_OVERRIDE"] = direction_override

    repo_root = paths._repo_root()
    cmd = [settings.cycle_python, "-m", "core.cli", "run", "--domain", domain]

    started_at = datetime.now(timezone.utc).isoformat()
    log_file = open(log_path, "w")
    proc = subprocess.Popen(
        cmd,
        cwd=str(repo_root),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )

    _CYCLES[cycle_id] = {
        "cycle_id": cycle_id,
        "domain": domain,
        "started_at": started_at,
        "pid": proc.pid,
        "proc": proc,
        "log_path": str(log_path),
        "direction_override": direction_override,
        "status": "running",
    }

    threading.Thread(target=_watch_cycle, args=(cycle_id,), daemon=True).start()
    logger.info("started cycle %s on domain %s (pid=%s)", cycle_id, domain, proc.pid)
    return cycle_id


def _watch_cycle(cycle_id: str) -> None:
    """Background thread: waits for the subprocess and updates status."""
    info = _CYCLES.get(cycle_id)
    if not info:
        return
    proc: subprocess.Popen = info["proc"]
    rc = proc.wait()
    info["status"] = "completed" if rc == 0 else "failed"
    info["return_code"] = rc
    info["finished_at"] = datetime.now(timezone.utc).isoformat()
    logger.info("cycle %s finished rc=%s", cycle_id, rc)


# ─── Models ─────────────────────────────────────────────────────────


class RunRequest(BaseModel):
    direction_override: str | None = None


class ChatMessage(BaseModel):
    role: str  # "user" / "assistant" / "system"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    session_id: str | None = None
    context_node: dict[str, Any] | None = None       # selected graph node, if any
    # Consapevolezza pagina (Atto UX 7) — il chat agent sa cosa l'utente sta guardando
    context_tab: str | None = None                   # 'grafo' | 'bicono' | 'agente' | 'incrocio' | 'prodotti' | 'info'
    context_scoperta: dict[str, Any] | None = None   # SSP scoperta selezionata in tab Prodotti
    context_prodotto: dict[str, Any] | None = None   # SSP prodotto maturo selezionato in tab Prodotti


class InjectTensionRequest(BaseModel):
    id: str
    claim: str
    intensita: float
    porta: str = "novità"
    tipo: str = "tensione_aperta"
    nota: str = ""


# ─── Auth (opt-in stub — Phase 6 v2 implements magic-link) ─────────


async def _check_auth(request: Request) -> None:
    """Phase 6 v1: auth is either disabled (allow) or enabled (placeholder).

    When `DASHBOARD_AUTH=enabled`, currently returns 503 — magic-link
    implementation lands in Phase 6 v2. Localhost binding (127.0.0.1)
    is the recommended security boundary for v1.
    """
    if not settings.auth_enabled:
        return
    if settings.demo_mode and request.method == "GET":
        return  # demo: read-only access without auth
    raise HTTPException(503, "Auth enabled but not yet implemented (Phase 6 v2). "
                             "Set DASHBOARD_AUTH=disabled and bind to 127.0.0.1.")


def _check_demo_writes(request: Request) -> None:
    """In demo mode, block all write operations regardless of auth."""
    if settings.demo_mode and request.method != "GET":
        raise HTTPException(403, "Demo mode is read-only.")


# ─── Endpoints ──────────────────────────────────────────────────────


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": "0.1.0-alpha",
        "auth_enabled": settings.auth_enabled,
        "demo_mode": settings.demo_mode,
        "data_dir": str(paths._data_dir()),
    }


@app.get("/api/domains")
async def list_domains_endpoint(request: Request) -> list[dict[str, Any]]:
    await _check_auth(request)
    out = []
    for d in cfg.list_domains():
        try:
            config = cfg.load_domain_config(d)
            seed = _read_json_safe(paths.seed_path(d), {})
            out.append({
                "id": d,
                "title": config.get("title", d),
                "version": config.get("version", "?"),
                "description": config.get("description", ""),
                "piano": seed.get("piano", 0),
                "n_tensions": len(seed.get("tensioni", []) or []),
                "n_reports": _count_reports(d),
                "direzione": (seed.get("direzione", "") or "")[:200],
                "direzione_en": (seed.get("direzione_en", "") or "")[:200],
            })
        except cfg.ConfigError as e:
            out.append({"id": d, "error": str(e)})
    return out


@app.get("/api/domains/{domain}/seed")
async def get_seed(domain: str, request: Request) -> dict[str, Any]:
    await _check_auth(request)
    _validate_domain(domain)
    return _read_json_safe(paths.seed_path(domain), {})


@app.get("/api/domains/{domain}/reports")
async def list_reports(domain: str, request: Request, limit: int = 50) -> list[dict[str, Any]]:
    await _check_auth(request)
    _validate_domain(domain)
    reports_dir = paths.reports_dir(domain)
    if not reports_dir.exists():
        return []
    falsifier_dir = paths.domain_data_dir(domain) / "falsifier"
    out = []
    for f in sorted(_agent_report_files(reports_dir), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        try:
            text = f.read_text(errors="replace")
        except Exception:
            continue
        title_m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        verdict_m = re.search(r"##\s*Verdict[^\n]*\n([^\n]+)", text)
        # v4.4 — annota con falsifier outcome se esiste, per badge nel list.
        # Cheap read: solo i campi che ci servono.
        n_flags = 0
        falsifier_coherent = None
        ts_match = re.search(r"agent_(\d{8}_\d{4})", f.name)
        if ts_match and falsifier_dir.exists():
            fp = falsifier_dir / f"falsifier_{ts_match.group(1)}.json"
            if fp.exists():
                try:
                    rec = json.loads(fp.read_text())
                    n_flags = len(rec.get("flags", []) or [])
                    falsifier_coherent = rec.get("coherent")
                except Exception:
                    pass
        out.append({
            "filename": f.name,
            "title": (title_m.group(1).strip() if title_m else f.name)[:200],
            "verdict": (verdict_m.group(1).strip() if verdict_m else "")[:200],
            "size": f.stat().st_size,
            "mtime": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
            "n_flags": n_flags,
            "falsifier_coherent": falsifier_coherent,
        })
    return out


@app.get("/api/domains/{domain}/reports/{filename}")
async def get_report(domain: str, filename: str, request: Request) -> dict[str, Any]:
    await _check_auth(request)
    _validate_domain(domain)
    if "/" in filename or ".." in filename:
        raise HTTPException(400, "invalid filename")
    fp = paths.reports_dir(domain) / filename
    if not fp.exists():
        raise HTTPException(404, "report not found")
    content = fp.read_text(errors="replace")

    # Parse bicono (4 fields) and verdict from the report markdown.
    # Reuses the existing parser in semantic_bridge so the dashboard
    # bicono visualization renders the SAME structure the lab uses
    # internally — no duplicated regex.
    from core import semantic_bridge as sb
    bicono = sb._extract_bicono(content)
    verdict_m = re.search(r"##\s*Verdict[^\n]*\n([^\n]+)", content)
    title_m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)

    return {
        "filename": filename,
        "content": content,
        "title": (title_m.group(1).strip() if title_m else "")[:200],
        "verdict": (verdict_m.group(1).strip() if verdict_m else "")[:200],
        "bicono": bicono,  # may be None if absent or unparseable
        "size": fp.stat().st_size,
        "mtime": datetime.fromtimestamp(fp.stat().st_mtime, tz=timezone.utc).isoformat(),
    }


@app.get("/api/domains/{domain}/taxonomy")
async def get_taxonomy(domain: str, request: Request) -> dict[str, Any]:
    """Taxonomic graph endpoint — il 'grafo d'insieme' richiesto dall'operatore.

    Aggrega i nodi del lab_graph in gruppi semanticamente coesi e calcola i
    bridge (numero di edge cross-group). Pillars (top-level groups) sono:

      - Per domini con teoria nodes (Q/T/G/E/R): le 5 teorie sono i pillar,
        ogni report/tensione viene clusterizzato sotto la teoria con cui
        condivide piu' lettere nell'id (defensive heuristic).
      - Per domini senza teoria: pillar = node.type (tensione/report/scoperta
        /ghost). Layout piatto.

    Output:
      {
        groups: [{id, label, color, count, members: [node_ids]}],
        bridges: [{source: groupA, target: groupB, weight: N}],
        nodes: [...lab_graph nodes...],   # passthrough per il render
        edges: [...lab_graph edges...],
        meta: {domain, n_groups, n_nodes, n_bridges, mode: 'pillars'|'flat'}
      }
    """
    await _check_auth(request)
    _validate_domain(domain)

    lab_graph_path = paths.domain_data_dir(domain) / "lab_graph.json"
    if not lab_graph_path.exists():
        return {"groups": [], "bridges": [], "nodes": [], "edges": [],
                "meta": {"domain": domain, "n_groups": 0, "n_nodes": 0, "n_bridges": 0, "mode": "empty"}}
    try:
        graph_data = json.loads(lab_graph_path.read_text())
    except Exception:
        raise HTTPException(500, "lab_graph.json corrupted")

    nodes = graph_data.get("graph", {}).get("nodes", []) or []
    edges = graph_data.get("graph", {}).get("edges", []) or []

    # Pillars: try theoria-first; fall back to type-based grouping.
    THEORY_LETTERS = ["Q", "T", "G", "E", "R"]
    THEORY_LABELS = {"Q": "Quantum", "T": "Topology", "G": "Geometry",
                     "E": "Entropy", "R": "Representation"}
    THEORY_COLORS = {"Q": "#a78bfa", "T": "#34d399", "G": "#22d3ee",
                     "E": "#fbbf24", "R": "#fb7185"}

    teoria_nodes = [n for n in nodes if n.get("type") == "teoria"]
    if teoria_nodes:
        # Theory pillar mode
        mode = "pillars"
        groups: list[dict[str, Any]] = []
        # Build pillars from existing teoria nodes
        for letter in THEORY_LETTERS:
            tn = next((t for t in teoria_nodes
                       if (t.get("id") or "").upper().startswith(letter)), None)
            if tn:
                groups.append({
                    "id": letter,
                    "label": tn.get("label") or THEORY_LABELS[letter],
                    "color": THEORY_COLORS[letter],
                    "letter": letter,
                    "count": 0,
                    "members": [tn["id"]],
                })
        # Cluster non-teoria nodes by which letters appear in their id+label
        def best_pillar(node: dict) -> str | None:
            haystack = (str(node.get("id", "")) + " " + str(node.get("label", ""))).upper()
            scores = {letter: haystack.count(letter) for letter in THEORY_LETTERS}
            top = max(scores.items(), key=lambda kv: kv[1])
            return top[0] if top[1] > 0 else None
        for n in nodes:
            if n.get("type") == "teoria":
                continue
            p = best_pillar(n)
            if p is None:
                continue
            for g in groups:
                if g["id"] == p:
                    g["members"].append(n["id"])
                    g["count"] += 1
                    break
    else:
        # Flat mode — group by node.type
        mode = "flat"
        TYPE_LABELS = {"tensione": "Tensioni", "report": "Reports",
                       "teoria": "Teorie", "scoperta": "Scoperte",
                       "ghost": "Ghosts", "ponte": "Ponti", "vuoto": "Vuoti"}
        TYPE_COLORS = {"tensione": "#22d3ee", "report": "#a78bfa",
                       "teoria": "#34d399", "scoperta": "#f472b6",
                       "ghost": "#fbbf24", "ponte": "#818cf8", "vuoto": "#fb7185"}
        type_groups: dict[str, dict[str, Any]] = {}
        for n in nodes:
            t = n.get("type") or "altro"
            if t not in type_groups:
                type_groups[t] = {
                    "id": t,
                    "label": TYPE_LABELS.get(t, t.title()),
                    "color": TYPE_COLORS.get(t, "#94a3b8"),
                    "letter": "",
                    "count": 0,
                    "members": [],
                }
            type_groups[t]["members"].append(n["id"])
            type_groups[t]["count"] += 1
        groups = list(type_groups.values())

    # Build node→group lookup for bridge computation
    node_group: dict[str, str] = {}
    for g in groups:
        for m in g["members"]:
            node_group[m] = g["id"]

    # Bridges = edges that cross distinct groups
    bridges_count: dict[tuple[str, str], int] = {}
    for e in edges:
        ga = node_group.get(e.get("source"))
        gb = node_group.get(e.get("target"))
        if not ga or not gb or ga == gb:
            continue
        key = tuple(sorted([ga, gb]))
        bridges_count[key] = bridges_count.get(key, 0) + 1
    bridges = [{"source": k[0], "target": k[1], "weight": v}
               for k, v in sorted(bridges_count.items(), key=lambda kv: -kv[1])]

    return {
        "groups": groups,
        "bridges": bridges,
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "domain": domain,
            "n_groups": len(groups),
            "n_nodes": len(nodes),
            "n_bridges": len(bridges),
            "mode": mode,
        },
    }


@app.get("/api/domains/{domain}/falsifier_summary")
async def get_falsifier_summary(domain: str, request: Request) -> dict[str, Any]:
    """Aggrega tutti i falsifier_*.json del dominio: conta flag per lens
    (L1..L5), severity distribution, e ultimi 3 flag come sample. Usato
    dalla dashboard per mostrare lo stato del counter-pole nel campo
    sidebar (meta-pattern: quale lens si attiva piu' spesso?)."""
    await _check_auth(request)
    _validate_domain(domain)
    falsifier_dir = paths.domain_data_dir(domain) / "falsifier"
    if not falsifier_dir.exists():
        return {
            "n_reports_checked": 0,
            "n_total_flags": 0,
            "by_lens": {f"L{i}": 0 for i in range(1, 6)},
            "by_severity": {"high": 0, "medium": 0, "low": 0},
            "recent_flags": [],
            "lens_labels": _LENS_LABELS,
        }

    by_lens: dict[str, int] = {f"L{i}": 0 for i in range(1, 6)}
    by_severity: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    recent: list[dict[str, Any]] = []
    n_reports = 0
    n_flags_total = 0

    for fp in sorted(falsifier_dir.glob("falsifier_*.json"),
                     key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            rec = json.loads(fp.read_text())
        except Exception:
            continue
        n_reports += 1
        flags = rec.get("flags") or []
        for fl in flags:
            n_flags_total += 1
            lens_n = fl.get("lens")
            if isinstance(lens_n, int) and 1 <= lens_n <= 5:
                by_lens[f"L{lens_n}"] += 1
            sev = (fl.get("severity") or "").lower()
            if sev in by_severity:
                by_severity[sev] += 1
            if len(recent) < 6:
                recent.append({
                    "report": rec.get("report_file"),
                    "ts": rec.get("timestamp"),
                    "lens": lens_n,
                    "severity": sev,
                    "claim": (fl.get("claim") or "")[:200],
                    "evidence": (fl.get("evidence") or "")[:200],
                })

    return {
        "n_reports_checked": n_reports,
        "n_total_flags": n_flags_total,
        "by_lens": by_lens,
        "by_severity": by_severity,
        "recent_flags": recent,
        "lens_labels": _LENS_LABELS,
    }


_LENS_LABELS = {
    "L1": "Hard constraint vs bias",
    "L2": "Quantita' vs ratio",
    "L3": "Axiom continuity",
    "L4": "Edge case",
    "L5": "Re-discovery",
}


@app.get("/api/domains/{domain}/falsifier/{filename}")
async def get_falsifier(domain: str, filename: str, request: Request) -> dict[str, Any]:
    """Return falsifier output for a specific cycle. Filename can be either
    the report name (agent_<ts>.md) or the falsifier file (falsifier_<ts>.json)
    or just the timestamp. Used by the dashboard to surface flags next to
    the report viewer."""
    await _check_auth(request)
    _validate_domain(domain)
    if "/" in filename or ".." in filename:
        raise HTTPException(400, "invalid filename")
    # Normalize to falsifier_<ts>.json
    ts_match = re.search(r"(\d{8}_\d{4})", filename)
    if not ts_match:
        raise HTTPException(400, "could not extract timestamp from filename")
    ts = ts_match.group(1)
    fp = paths.domain_data_dir(domain) / "falsifier" / f"falsifier_{ts}.json"
    if not fp.exists():
        # Not an error — falsifier may simply not have run for this report yet
        return {"present": False, "ts": ts}
    try:
        record = json.loads(fp.read_text())
        record["present"] = True
        return record
    except json.JSONDecodeError as e:
        raise HTTPException(500, f"falsifier file corrupted: {e}")


@app.get("/api/domains/{domain}/corrector_summary")
async def get_corrector_summary(domain: str, request: Request) -> dict[str, Any]:
    """Aggrega tutti i corrector_*.json del dominio: totale rewrites
    proposed/applied/skipped, distribuzione per lens (L1/L3/L4), e
    ultimi 6 rewrites come sample. Usato dalla dashboard per mostrare
    quanto il bias_corrector sta intervenendo + dove."""
    await _check_auth(request)
    _validate_domain(domain)
    corrector_dir = paths.domain_data_dir(domain) / "corrector"
    if not corrector_dir.exists():
        return {
            "n_reports_checked": 0,
            "n_total_proposed": 0,
            "n_total_applied": 0,
            "n_total_skipped": 0,
            "by_lens": {"L1": 0, "L3": 0, "L4": 0},
            "recent_rewrites": [],
        }

    by_lens: dict[str, int] = {"L1": 0, "L3": 0, "L4": 0}
    recent: list[dict[str, Any]] = []
    n_reports = 0
    proposed = 0
    applied = 0
    skipped = 0

    for fp in sorted(corrector_dir.glob("corrector_*.json"),
                     key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            rec = json.loads(fp.read_text())
        except Exception:
            continue
        n_reports += 1
        proposed += int(rec.get("rewrites_proposed", 0) or 0)
        applied += int(rec.get("rewrites_applied", 0) or 0)
        skipped += int(rec.get("rewrites_skipped", 0) or 0)
        for rw in rec.get("rewrites") or []:
            lens_n = rw.get("lens")
            key = f"L{lens_n}" if lens_n in (1, 3, 4) else None
            if key:
                by_lens[key] += 1
            if len(recent) < 6:
                recent.append({
                    "report": rec.get("report_file"),
                    "ts": rec.get("timestamp"),
                    "lens": lens_n,
                    "before": (rw.get("before") or "")[:240],
                    "after": (rw.get("after") or "")[:240],
                    "reason": (rw.get("reason") or "")[:240],
                })

    return {
        "n_reports_checked": n_reports,
        "n_total_proposed": proposed,
        "n_total_applied": applied,
        "n_total_skipped": skipped,
        "by_lens": by_lens,
        "recent_rewrites": recent,
    }


@app.get("/api/domains/{domain}/corrector/{filename}")
async def get_corrector(domain: str, filename: str, request: Request) -> dict[str, Any]:
    """Return bias_corrector output for a specific cycle. Filename can be
    report name, corrector file, or just timestamp. Mirrors get_falsifier."""
    await _check_auth(request)
    _validate_domain(domain)
    if "/" in filename or ".." in filename:
        raise HTTPException(400, "invalid filename")
    ts_match = re.search(r"(\d{8}_\d{4})", filename)
    if not ts_match:
        raise HTTPException(400, "could not extract timestamp from filename")
    ts = ts_match.group(1)
    fp = paths.domain_data_dir(domain) / "corrector" / f"corrector_{ts}.json"
    if not fp.exists():
        return {"present": False, "ts": ts}
    try:
        record = json.loads(fp.read_text())
        record["present"] = True
        return record
    except json.JSONDecodeError as e:
        raise HTTPException(500, f"corrector file corrupted: {e}")


@app.get("/api/domains/{domain}/report_diff/{filename}")
async def get_report_diff(domain: str, filename: str, request: Request) -> dict[str, Any]:
    """Return original vs corrected report for a cycle, when the bias_corrector
    has rewritten claims. Returns both texts so the UI can render the diff.

    If no .original.md exists, returns present=False (corrector found nothing
    to fix, or did not run, or the original was the corrected version itself).
    """
    await _check_auth(request)
    _validate_domain(domain)
    if "/" in filename or ".." in filename:
        raise HTTPException(400, "invalid filename")
    ts_match = re.search(r"(\d{8}_\d{4})", filename)
    if not ts_match:
        raise HTTPException(400, "could not extract timestamp from filename")
    ts = ts_match.group(1)
    reports_dir = paths.reports_dir(domain)
    original = reports_dir / f"agent_{ts}.original.md"
    corrected = reports_dir / f"agent_{ts}.md"
    if not original.exists():
        return {"present": False, "ts": ts}
    if not corrected.exists():
        return {"present": False, "ts": ts, "note": "corrected file missing"}
    try:
        return {
            "present": True,
            "ts": ts,
            "original": original.read_text(errors="replace"),
            "corrected": corrected.read_text(errors="replace"),
            "original_size": original.stat().st_size,
            "corrected_size": corrected.stat().st_size,
        }
    except Exception as e:
        raise HTTPException(500, f"diff read failed: {e}")


@app.get("/api/domains/{domain}/context_intro")
async def get_context_intro(domain: str, request: Request, lang: str = "it") -> dict[str, Any]:
    """Estrae la prima sezione 'identity'/'about' del file descrittivo del dominio.
    Usato dalla dashboard tab Info ('cosa fa questo lab' visitor-facing).

    Refactor 04/05 — fallback chain (priorità):
      1. domains/<d>/about.<lang>.md (es. about.en.md per lang=en)
      2. domains/<d>/about.md (it default visitor-facing)
      3. domains/<d>/context.md (legacy, contiene anche prompt agente)

    Il fallback a context.md è solo per retro-compat: i nuovi domini
    devono avere about.md per evitare di esporre il prompt agente in UI.

    Heuristic estrazione: cerca '## About' / '## Identity' / '## Chi sei' /
    '## Identita'; se assente, prende il primo paragrafo dopo il titolo H1.
    """
    await _check_auth(request)
    _validate_domain(domain)

    # Fallback chain: about.<lang>.md → about.md → context.md
    candidates = []
    if lang and lang != "it":
        candidates.append(paths.domain_about_path(domain, lang))
    candidates.append(paths.domain_about_path(domain, "it"))
    candidates.append(paths.domain_context_path(domain))

    ctx_path = next((p for p in candidates if p.exists()), None)
    if ctx_path is None:
        return {"intro": "", "title": ""}
    text = ctx_path.read_text(errors="replace")
    title_m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    title = title_m.group(1).strip() if title_m else domain
    # Try ## Identity / ## Chi sei / ## Identita / ## Identità sections first
    section_m = re.search(
        r"^##\s+(?:Identity|Chi\s+sei|Identità?|Identità|About|Cosa\s+e['’]?)[^\n]*\n+([\s\S]+?)(?=\n##\s|\Z)",
        text, re.MULTILINE | re.IGNORECASE,
    )
    if section_m:
        intro = section_m.group(1)
    else:
        # Fallback: paragraph after title, skipping blockquotes
        body = text[title_m.end():] if title_m else text
        # Skip blockquotes (lines starting with >)
        lines = body.split("\n")
        cleaned = [l for l in lines if not l.strip().startswith(">")]
        # Take until first ## or first blank line cluster
        intro_lines: list[str] = []
        for l in cleaned:
            if l.strip().startswith("##"):
                break
            intro_lines.append(l)
        intro = "\n".join(intro_lines)
    # Strip leading/trailing whitespace and limit length for top section
    intro = intro.strip()
    if len(intro) > 1200:
        intro = intro[:1200].rsplit(" ", 1)[0] + "…"
    return {"title": title, "intro": intro}


@app.get("/api/domains/{domain}/biconi")
async def list_biconi(domain: str, request: Request, limit: int = 50) -> list[dict[str, Any]]:
    """Return parsed bicono summary for every report. Used by the BICONO
    tab to render a mini-bicono gallery without N round-trips. Reports
    without a parseable bicono are returned with bicono=None so the
    frontend can show 'incompleto' state."""
    await _check_auth(request)
    _validate_domain(domain)
    from core import semantic_bridge as sb
    reports_dir = paths.reports_dir(domain)
    if not reports_dir.exists():
        return []
    out: list[dict[str, Any]] = []
    for f in sorted(_agent_report_files(reports_dir), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        try:
            text = f.read_text(errors="replace")
        except Exception:
            continue
        title_m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        out.append({
            "filename": f.name,
            "title": (title_m.group(1).strip() if title_m else f.name)[:200],
            "bicono": sb._extract_bicono(text),
            "mtime": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
        })
    return out


def _parse_narrative_file(path: Path) -> dict[str, Any]:
    """Read a narrative_<ts>.md file and split frontmatter from body.

    Returns dict with: cycle_ts, lab, word_count, verdict_band,
    aeternitas, trajectory_decision, body (markdown text).
    """
    text = path.read_text(errors="replace")
    front: dict[str, str] = {}
    body = text
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end > 0:
            for line in text[4:end].splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    front[k.strip()] = v.strip()
            body = text[end + 5:].lstrip()
    return {
        "cycle_ts": front.get("cycle_ts", ""),
        "lab": front.get("lab", ""),
        "word_count": int(front["word_count"]) if front.get("word_count", "").isdigit() else None,
        "verdict_band": front.get("verdict_band"),
        "aeternitas": front.get("aeternitas"),
        "trajectory_decision": front.get("trajectory_decision"),
        "body": body.strip(),
        "filename": path.name,
        "mtime": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
    }


@app.get("/api/domains/{domain}/narratives")
async def list_narratives(domain: str, request: Request, limit: int = 30) -> list[dict[str, Any]]:
    """Return parsed narrative summaries for the domain (most recent first).

    Each entry includes frontmatter fields (cycle_ts, verdict_band,
    aeternitas, trajectory_decision, word_count) + body. Used by the
    public-facing /n/<domain>/<ts> route and any external consumer
    (LinkedIn embed, social card generator, etc.).
    """
    await _check_auth(request)
    _validate_domain(domain)
    narr_dir = paths.domain_data_dir(domain) / "narratives"
    if not narr_dir.exists():
        return []
    files = sorted(narr_dir.glob("narrative_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    out: list[dict[str, Any]] = []
    for f in files:
        try:
            out.append(_parse_narrative_file(f))
        except Exception:
            continue
    return out


@app.get("/api/domains/{domain}/narratives/{cycle_ts}")
async def get_narrative(domain: str, cycle_ts: str, request: Request) -> dict[str, Any]:
    """Single narrative for one cycle. Used by frontend renderers."""
    await _check_auth(request)
    _validate_domain(domain)
    if not re.fullmatch(r"\d{8}_\d{4,6}", cycle_ts):
        raise HTTPException(400, "Invalid cycle_ts format")
    narr_path = paths.domain_data_dir(domain) / "narratives" / f"narrative_{cycle_ts}.md"
    if not narr_path.exists():
        raise HTTPException(404, f"No narrative for {domain}/{cycle_ts}")
    return _parse_narrative_file(narr_path)


# ─── i18n minimal per pagine /n (server-rendered FastAPI) ─────────────────
# Le pagine statiche di lab.d-nd.com usano translations.js + cookie i18nextLng.
# Le pagine /n sono server-rendered; replichiamo lo stesso pattern lato server:
# query param ?lang=en o cookie i18nextLng=en → render EN. Default 'it'.

_N_I18N: dict[str, dict[str, str]] = {
    "it": {
        "html_lang": "it",
        "og_locale": "it_IT",
        # Header nav
        "nav_brand_aria": "Lab D-ND home",
        "nav_sections_aria": "Sezioni Lab D-ND",
        "nav_external_aria": "Risorse esterne",
        "nav_cycle": "Cycle",
        "nav_scoperte": "Scoperte",
        "nav_applications": "Applicazioni",
        "nav_dashboard": "Dashboard",
        "nav_start": "Inizia",
        # Footer
        "footer_question": "Hai un dominio simile?",
        "footer_cta": "Crea il tuo Lab →",
        "footer_brand_subtitle": "sistemi cognitivi operativi",
        "footer_link_start": "Inizia",
        "footer_link_home": "Home Lab",
        "footer_link_dashboard": "Dashboard",
        # Master index /n/
        "master_meta_title": "Cycle dei lab · Lab D-ND",
        "master_meta_desc": "Stati e cycle narrati dei domini D-ND: physics è il master verificato, finance e bio-rhythms sono in collaudo.",
        "master_og_title": "Cycle dei lab D-ND",
        "master_og_desc": "Stati pubblici dei domini D-ND, con cycle narrati e verdetto strutturale.",
        "master_ctx_where": "Cycle dei lab D-ND",
        "master_ctx_purpose": "Log pubblico dei domini: cosa gira, cosa regge, cosa resta in collaudo.",
        "master_ctx_cta": "Lab simile sul tuo dominio? Inizia →",
        "master_eyebrow": "Cycle dei lab",
        "master_h1": "Cosa fanno i lab quando girano.",
        "master_lead": "Ogni cycle è un'iterazione di ricerca: il lab sceglie una domanda, prova una risposta, la mette sotto critica strutturale. Qui leggi cosa ha trovato e cosa non ha ancora diritto di diventare evidenza: physics è il master verificato, finance e bio-rhythms sono domini in collaudo.",
        "physics_master_label": "master · d-nd.com",
        "physics_master_h2": "physics",
        "physics_master_desc": "Master lab della fisica: dove il modello D-ND viene sviluppato e validato.",
        "physics_master_last": "Lab di ricerca privato, finding pubblicati su d-nd.com/ai-lab. Apri il master ↗",
        "card_no_narrative": "Nessun cycle narrato finora.",
        "card_pending_narrative": "Cycle in attesa di narrazione.",
        "card_default_desc": "Lab D-ND di dominio.",
        # Lab index /n/<domain>/
        "lab_meta_title_fmt": "Cycle del lab {lab} · Lab D-ND",
        "lab_og_title_fmt": "Cycle del lab {lab}",
        "lab_ctx_where_fmt": "Lab {lab}",
        "lab_ctx_purpose": "Tutti i cycle pubblici di questo lab. Ogni voce è un'iterazione narrata con verdetto.",
        "lab_eyebrow": "Cycle del lab",
        "lab_empty": "Nessun cycle narrato finora per questo lab.",
        "lab_words_unit": "parole",
        # Narrative single cycle /n/<domain>/<ts>
        "narr_meta_title_fmt": "{title} · Lab D-ND {lab}",
        "narr_ctx_where_fmt": "{lab} · cycle {cycle_ts}",
        "narr_ctx_purpose": "Una singola iterazione di ricerca, narrata. Verdetto strutturale e link al report tecnico.",
        "narr_eyebrow_fmt": "Lab D-ND · {lab}",
        "narr_prev_link": "← Cycle precedente",
        "narr_next_link": "Cycle successivo →",
        "narr_up_link_fmt": "↑ Tutti i cycle di {lab}",
        "narr_meta_cycle": "Cycle",
        "narr_meta_aeternitas": "Aeternitas",
        "narr_meta_veritas": "Veritas",
        "narr_meta_trajectory": "Trajectory",
        "narr_tech_report_pre": "Narrazione di un cycle tecnico del lab D-ND. Il ",
        "narr_tech_report_link": "report tecnico originale",
        "narr_tech_report_post": " con dati, falsifier flags e bicono resta consultabile.",
        "narr_default_title_fmt": "Cycle {cycle_ts} · {domain}",
        "narr_evidence_note_finance": "Stato corrente: questa è una narrativa storica del cycle. Il dominio finance resta in collaudo; nessun risultato è promosso come segnale di mercato finché non supera i gate su dati reali con controlli robusti.",
        "narr_evidence_note_bio-rhythms": "Stato corrente: questa è una narrativa storica del cycle. Il dominio bio-rhythms resta in collaudo; nessun risultato conta come evidenza biologica o clinica finché l'origine reale del dato non è verificata.",
        # Verdict labels (da _verdict_label)
        "verdict_falsificazione": "Falsificazione",
        "verdict_redesign": "Il sistema chiede di riprogettare",
        "verdict_collasso": "Lo schema regge",
        "verdict_sospensione": "Sospeso · onesto",
        "verdict_scarto": "Bassa qualità",
        "verdict_default": "Cycle completato",
        # Domain leads (descrizione brevi)
        "lead_bio-rhythms": "Bio-rhythms in collaudo: pipeline sintetica HRV validata, dati reali e claim clinici fuori perimetro finché il gate PhysioNet non regge.",
        "lead_finance": "Finance in collaudo: regime detection su mercati FX, crypto, equity; ultimo synthetic realistic in NO_DELTA, dati reali al gate successivo.",
        "lead_ops-decisions": "Friction operativa trasformata in regole strutturali.",
        "lead_editorial": "Distillazione dei contenuti che reggono il peso.",
        "lead_meta-lab": "Il lab che genera lab — produce semi cognitivi.",
        # Lang toggle
        "lang_toggle_en": "EN",
        "lang_toggle_it": "IT",
    },
    "en": {
        "html_lang": "en",
        "og_locale": "en_US",
        # Header nav
        "nav_brand_aria": "Lab D-ND home",
        "nav_sections_aria": "Lab D-ND sections",
        "nav_external_aria": "External resources",
        "nav_cycle": "Cycles",
        "nav_scoperte": "Findings",
        "nav_applications": "Applications",
        "nav_dashboard": "Dashboard",
        "nav_start": "Start",
        # Footer
        "footer_question": "Got a similar domain?",
        "footer_cta": "Create your Lab →",
        "footer_brand_subtitle": "operational cognitive systems",
        "footer_link_start": "Start",
        "footer_link_home": "Lab Home",
        "footer_link_dashboard": "Dashboard",
        # Master index /n/
        "master_meta_title": "Lab cycles · Lab D-ND",
        "master_meta_desc": "States and narrated cycles of D-ND domains: physics is the verified master, finance and bio-rhythms are under validation.",
        "master_og_title": "D-ND lab cycles",
        "master_og_desc": "Public states of D-ND domains, with narrated cycles and structural verdicts.",
        "master_ctx_where": "D-ND lab cycles",
        "master_ctx_purpose": "Public log of domains: what runs, what holds, what remains under validation.",
        "master_ctx_cta": "Similar lab on your domain? Start →",
        "master_eyebrow": "Lab cycles",
        "master_h1": "What labs do when they run.",
        "master_lead": "Every cycle is a research iteration: the lab picks a question, tries an answer, runs it through structural critique. Here you read what it found and what is not yet allowed to become evidence: physics is the verified master, finance and bio-rhythms are domains under validation.",
        "physics_master_label": "master · d-nd.com",
        "physics_master_h2": "physics",
        "physics_master_desc": "Physics master lab: where the D-ND model is developed and validated.",
        "physics_master_last": "Private research lab, findings published on d-nd.com/ai-lab. Open the master ↗",
        "card_no_narrative": "No narrated cycles yet.",
        "card_pending_narrative": "Cycle awaiting narrative.",
        "card_default_desc": "Domain D-ND lab.",
        # Lab index /n/<domain>/
        "lab_meta_title_fmt": "Cycles of lab {lab} · Lab D-ND",
        "lab_og_title_fmt": "Cycles of lab {lab}",
        "lab_ctx_where_fmt": "Lab {lab}",
        "lab_ctx_purpose": "All public cycles of this lab. Each entry is an iteration narrated with verdict.",
        "lab_eyebrow": "Lab cycles",
        "lab_empty": "No narrated cycles yet for this lab.",
        "lab_words_unit": "words",
        # Narrative single cycle /n/<domain>/<ts>
        "narr_meta_title_fmt": "{title} · Lab D-ND {lab}",
        "narr_ctx_where_fmt": "{lab} · cycle {cycle_ts}",
        "narr_ctx_purpose": "A single research iteration, narrated. Structural verdict and link to the technical report.",
        "narr_eyebrow_fmt": "Lab D-ND · {lab}",
        "narr_prev_link": "← Previous cycle",
        "narr_next_link": "Next cycle →",
        "narr_up_link_fmt": "↑ All cycles of {lab}",
        "narr_meta_cycle": "Cycle",
        "narr_meta_aeternitas": "Aeternitas",
        "narr_meta_veritas": "Veritas",
        "narr_meta_trajectory": "Trajectory",
        "narr_tech_report_pre": "Narrative of a technical D-ND lab cycle. The ",
        "narr_tech_report_link": "original technical report",
        "narr_tech_report_post": " with data, falsifier flags and bicono remains available.",
        "narr_default_title_fmt": "Cycle {cycle_ts} · {domain}",
        "narr_evidence_note_finance": "Current state: this is a historical cycle narrative. The finance domain remains under validation; no result is promoted as a market signal until it passes real-data gates with robust controls.",
        "narr_evidence_note_bio-rhythms": "Current state: this is a historical cycle narrative. The bio-rhythms domain remains under validation; no result counts as biological or clinical evidence until the real origin of the data is verified.",
        # Verdict labels
        "verdict_falsificazione": "Falsified",
        "verdict_redesign": "System asks to redesign",
        "verdict_collasso": "Schema holds",
        "verdict_sospensione": "Suspended · honest",
        "verdict_scarto": "Low quality",
        "verdict_default": "Cycle completed",
        # Domain leads
        "lead_bio-rhythms": "Bio-rhythms under validation: synthetic HRV pipeline validated, real data and clinical claims out of scope until the PhysioNet gate holds.",
        "lead_finance": "Finance under validation: regime detection on FX, crypto and equity markets; latest realistic synthetic run returned NO_DELTA, real data is the next gate.",
        "lead_ops-decisions": "Operational friction turned into structural rules.",
        "lead_editorial": "Distillation of content that holds weight.",
        "lead_meta-lab": "The lab that generates labs — produces cognitive seeds.",
        # Lang toggle
        "lang_toggle_en": "EN",
        "lang_toggle_it": "IT",
    },
}


def _resolve_lang(request) -> str:
    """Resolve current language: ?lang=en query param > cookie i18nextLng > 'it'.

    Same cookie name used by lab.d-nd.com static pages (translations.js client side),
    so toggling on / and on /n/ stays consistent across the surface.
    """
    try:
        q = (request.query_params.get("lang") or "").lower().strip()
        if q in _N_I18N:
            return q
        cookie = (request.cookies.get("i18nextLng") or "").lower().strip()
        if cookie.startswith("en"):
            return "en"
        if cookie.startswith("it"):
            return "it"
    except Exception:
        pass
    return "it"


def _t(lang: str, key: str, **fmt: Any) -> str:
    """Translate helper. Falls back to 'it' on missing key, then key itself."""
    pack = _N_I18N.get(lang) or _N_I18N["it"]
    val = pack.get(key) or _N_I18N["it"].get(key) or key
    if fmt:
        try:
            return val.format(**fmt)
        except (KeyError, IndexError):
            return val
    return val


def _lang_toggle_html(lang: str, current_path: str) -> str:
    """Render IT/EN toggle that preserves current path. Sets ?lang=xx (cookie persists via JS on click would be ideal, ma per ora query string è sufficiente — il cookie viene comunque settato dal sito statico)."""
    other = "en" if lang == "it" else "it"
    other_label = _t(lang, "lang_toggle_" + other)
    sep = "&" if "?" in current_path else "?"
    return (
        f'<a href="{html_escape(current_path)}{sep}lang={other}" '
        f'style="margin-left:14px;color:var(--muted);font-size:12px;font-weight:600;letter-spacing:.06em;" '
        f'aria-label="Switch to {other.upper()}">{html_escape(other_label)}</a>'
    )


def _render_lab_header(lang: str, cycle_active: bool, current_path: str = "/n/") -> str:
    """Render header HTML — replaces _LAB_HEADER_HTML constant with i18n + lang toggle."""
    active_attr = ' class="active"' if cycle_active else ''
    return (
        '<header class="site-header">\n'
        '  <div class="shell nav">\n'
        f'    <a class="brand" href="https://lab.d-nd.com/" aria-label="{_t(lang, "nav_brand_aria")}">\n'
        '      <img src="/assets/logos/logo_40px.jpg" alt="D-ND" />\n'
        '      <span>Lab D-ND</span>\n'
        '    </a>\n'
        f'    <nav class="page-nav" aria-label="{_t(lang, "nav_sections_aria")}">\n'
        f'      <a href="/n/"{active_attr}>{_t(lang, "nav_cycle")}</a>\n'
        f'      <a href="/scoperte.html">{_t(lang, "nav_scoperte")}</a>\n'
        f'      <a href="/applications.html">{_t(lang, "nav_applications")}</a>\n'
        f'      <a href="/dashboard/">{_t(lang, "nav_dashboard")}</a>\n'
        f'      <a href="/start.html">{_t(lang, "nav_start")}</a>\n'
        '    </nav>\n'
        '    <div class="nav-spacer"></div>\n'
        f'    <nav class="external-nav" aria-label="{_t(lang, "nav_external_aria")}">\n'
        '      <a href="https://d-nd.com" target="_blank" rel="noopener noreferrer">d-nd.com</a>\n'
        f'      {_lang_toggle_html(lang, current_path)}\n'
        '    </nav>\n'
        '  </div>\n'
        '</header>\n'
    )


def _render_lab_footer(lang: str) -> str:
    """Render footer HTML — replaces _LAB_FOOTER_HTML constant with i18n."""
    return (
        '<footer class="site-footer">\n'
        '  <div class="shell" style="padding: 18px 0; border-top: 1px solid rgba(34, 211, 238, 0.18); border-bottom: 1px solid rgba(34, 211, 238, 0.18); margin-bottom: 24px; text-align: center;">\n'
        f'    <span style="color: var(--ink, #f4f5fa); font-size: 15px;">{_t(lang, "footer_question")} &nbsp;</span>\n'
        f'    <a href="/start.html" style="display: inline-block; padding: 8px 16px; background: rgba(34, 211, 238, 0.12); border: 1px solid rgba(34, 211, 238, 0.55); border-radius: 6px; color: #22d3ee; font-weight: 600; text-decoration: none; font-size: 14px; margin-left: 6px;">{_t(lang, "footer_cta")}</a>\n'
        '  </div>\n'
        '  <div class="shell footer-row">\n'
        '    <div class="footer-brand">\n'
        '      <img src="/assets/logos/logo_40px.jpg" alt="D-ND" />\n'
        f'      <span><strong>Lab D-ND</strong> — {_t(lang, "footer_brand_subtitle")}</span>\n'
        '    </div>\n'
        '    <div>\n'
        f'      <a href="/start.html">{_t(lang, "footer_link_start")}</a> ·\n'
        f'      <a href="https://lab.d-nd.com/">{_t(lang, "footer_link_home")}</a> ·\n'
        f'      <a href="/dashboard/">{_t(lang, "footer_link_dashboard")}</a> ·\n'
        '      <a href="https://d-nd.com" target="_blank" rel="noopener noreferrer">d-nd.com</a>\n'
        '    </div>\n'
        '  </div>\n'
        '</footer>\n'
        '<!-- DOMUS chat widget (THIA esteso per consapevolezza dei cycle del lab) -->\n'
        '<script src="/assets/js/domus-widget.js" defer></script>\n'
    )


_LAB_BASE_STYLES = """\
  :root {{
    color-scheme: dark;
    --void: #08080c; --void-2: #0d0e14;
    --panel: #14151d; --panel-2: #1b1c25;
    --line: rgba(220, 222, 232, .14);
    --line-strong: rgba(220, 222, 232, .26);
    --ink: #f4f5fa; --text: #d8dbe7;
    --muted: #a5a9b9; --dim: #777d93;
    --cyan: #22d3ee; --purple: #a78bfa;
    --emerald: #34d399; --amber: #fbbf24;
    --sky: #38bdf8; --danger: #fb7185;
    --max: 1180px;
    --radius: 8px;
    --shadow: 0 24px 80px rgba(0, 0, 0, .48);
    --accent: {accent};
  }}
  /* Context bar — orientamento + uscita verso funnel /start.html */
  .lab-context-bar {{
    border-bottom: 1px solid var(--line);
    background: rgba(34, 211, 238, .04);
    padding: 12px 0; font-size: 13px;
  }}
  .lab-context-bar .ctx-shell {{
    display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
    width: min(var(--max), calc(100% - 44px)); margin: 0 auto;
  }}
  .lab-context-bar .ctx-where {{
    color: var(--ink); font-weight: 600;
    border-right: 1px solid var(--line); padding-right: 14px;
  }}
  .lab-context-bar .ctx-purpose {{ color: var(--muted); flex: 1; min-width: 200px; }}
  .lab-context-bar .ctx-cta {{
    color: var(--cyan); text-decoration: none; font-weight: 600;
    padding: 5px 12px; border-radius: 6px;
    border: 1px solid rgba(34, 211, 238, .42);
    transition: border-color .14s, background .14s, color .14s;
  }}
  .lab-context-bar .ctx-cta:hover {{
    border-color: var(--cyan); background: rgba(34, 211, 238, .1); color: var(--ink);
  }}
  @media (max-width: 760px) {{
    .lab-context-bar .ctx-where {{ border-right: none; padding-right: 0; }}
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html {{ scroll-behavior: smooth; }}
  body {{
    background:
      radial-gradient(circle at 16% 0%, rgba(34, 211, 238, .12), transparent 32rem),
      radial-gradient(circle at 88% 14%, rgba(167, 139, 250, .14), transparent 34rem),
      linear-gradient(180deg, #08080c 0%, #0b0c12 42%, #08080c 100%);
    color: var(--text);
    font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    line-height: 1.55;
    -webkit-font-smoothing: antialiased;
    min-height: 100vh;
  }}
  a {{ color: inherit; text-decoration: none; }}
  a:hover {{ color: var(--ink); }}
  .shell {{ width: min(var(--max), calc(100% - 44px)); margin: 0 auto; }}
"""


_LAB_HEADER_HTML = """\
<header class="site-header">
  <div class="shell nav">
    <a class="brand" href="https://lab.d-nd.com/" aria-label="Lab D-ND home">
      <img src="/assets/logos/logo_40px.jpg" alt="D-ND" />
      <span>Lab D-ND</span>
    </a>
    <nav class="page-nav" aria-label="Sezioni Lab D-ND">
      <a href="/n/"{cycle_active}>Cycle</a>
      <a href="/scoperte.html">Scoperte</a>
      <a href="/applications.html">Applicazioni</a>
      <a href="/dashboard/">Dashboard</a>
      <a href="/start.html">Inizia</a>
    </nav>
    <div class="nav-spacer"></div>
    <nav class="external-nav" aria-label="Risorse esterne">
      <a href="https://d-nd.com" target="_blank" rel="noopener noreferrer">d-nd.com</a>
    </nav>
  </div>
</header>
"""


_LAB_FOOTER_HTML = """\
<footer class="site-footer">
  <div class="shell" style="padding: 18px 0; border-top: 1px solid rgba(34, 211, 238, 0.18); border-bottom: 1px solid rgba(34, 211, 238, 0.18); margin-bottom: 24px; text-align: center;">
    <span style="color: var(--ink, #f4f5fa); font-size: 15px;">Hai un dominio simile? &nbsp;</span>
    <a href="/start.html" style="display: inline-block; padding: 8px 16px; background: rgba(34, 211, 238, 0.12); border: 1px solid rgba(34, 211, 238, 0.55); border-radius: 6px; color: #22d3ee; font-weight: 600; text-decoration: none; font-size: 14px; margin-left: 6px;">Crea il tuo Lab →</a>
  </div>
  <div class="shell footer-row">
    <div class="footer-brand">
      <img src="/assets/logos/logo_40px.jpg" alt="D-ND" />
      <span><strong>Lab D-ND</strong> — sistemi cognitivi operativi</span>
    </div>
    <div>
      <a href="/start.html">Inizia</a> ·
      <a href="https://lab.d-nd.com/">Home Lab</a> ·
      <a href="/dashboard/">Dashboard</a> ·
      <a href="https://d-nd.com" target="_blank" rel="noopener noreferrer">d-nd.com</a>
    </div>
  </div>
</footer>
<!-- DOMUS chat widget (THIA esteso per consapevolezza dei cycle del lab) -->
<script src="/assets/js/domus-widget.js" defer></script>
"""


_NARRATIVE_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="{html_lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{meta_title}</title>
<meta name="description" content="{meta_desc}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{meta_desc}">
<meta property="og:type" content="article">
<meta property="og:image" content="https://lab.d-nd.com/assets/logos/logo_90px.jpg">
<meta property="og:url" content="https://lab.d-nd.com/n/{lab}/{cycle_ts}">
<meta property="og:locale" content="{og_locale}">
<meta property="og:site_name" content="Lab D-ND">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{meta_desc}">
<meta name="twitter:image" content="https://lab.d-nd.com/assets/logos/logo_90px.jpg">
<link rel="icon" href="/assets/favicon.ico">
<link rel="preconnect" href="https://rsms.me/">
<link rel="stylesheet" href="https://rsms.me/inter/inter.css">
<link rel="stylesheet" href="/assets/css/nav.css">
<style>
""" + _LAB_BASE_STYLES + """\
  main.shell {{ padding: 56px 0 96px; max-width: 760px; }}
  .eyebrow {{
    color: var(--cyan); font-size: 12px;
    text-transform: uppercase; letter-spacing: 0.12em;
    margin-bottom: 20px;
  }}
  h1 {{
    color: var(--ink);
    font-size: clamp(28px, 5vw, 42px);
    font-weight: 700; letter-spacing: -0.02em;
    margin-bottom: 28px; line-height: 1.18;
  }}
  .verdict-pill {{
    display: inline-block; padding: 5px 14px;
    border-radius: 999px;
    background: var(--accent); color: var(--void);
    font-size: 11px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.08em;
    margin-bottom: 36px;
  }}
  .evidence-note {{
    border: 1px solid var(--line-strong);
    border-left: 3px solid var(--accent);
    border-radius: var(--radius);
    background: rgba(13, 14, 20, 0.64);
    color: var(--muted);
    font-size: 14px;
    line-height: 1.55;
    padding: 14px 16px;
    margin: -14px 0 30px;
  }}
  article p {{
    font-size: 17px; line-height: 1.65;
    margin-bottom: 18px; color: var(--text);
  }}
  article p:first-child::first-letter {{
    color: var(--accent);
    font-weight: 700;
  }}
  .cycle-nav {{
    display: flex; justify-content: space-between; gap: 16px;
    margin: 56px 0 16px; padding: 16px 0;
    border-top: 1px solid var(--line);
    border-bottom: 1px solid var(--line);
    font-size: 14px; color: var(--muted);
  }}
  .cycle-nav a {{ color: var(--muted); }}
  .cycle-nav a:hover {{ color: var(--cyan); }}
  .cycle-nav .nav-up {{ text-align: center; flex: 1; }}
  .cycle-meta {{
    margin-top: 32px; padding-top: 24px;
    border-top: 1px solid var(--line);
    font-size: 13px; color: var(--muted);
  }}
  .cycle-meta dl {{
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 6px 16px; margin-bottom: 18px;
  }}
  .cycle-meta dt {{ color: var(--dim); }}
  .cycle-meta dd {{ color: var(--text); }}
  .cycle-meta a {{
    color: var(--muted); text-decoration: underline;
    text-decoration-color: var(--line);
  }}
  .cycle-meta a:hover {{ color: var(--cyan); text-decoration-color: var(--cyan); }}
  .site-footer {{
    border-top: 1px solid var(--line);
    padding: 24px 0 32px; color: var(--dim); font-size: 13px;
  }}
  .footer-row {{ display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap; align-items: center; }}
  .footer-brand {{ display: flex; align-items: center; gap: 10px; }}
  .footer-brand img {{ width: 22px; height: 22px; border-radius: 4px; }}
  .site-footer a {{ color: var(--muted); }}
  .site-footer a:hover {{ color: var(--ink); }}
  @media (max-width: 760px) {{
    main.shell {{ padding: 32px 0 64px; }}
    article p {{ font-size: 16px; }}
  }}
""" + """
</style>
</head>
<body>
{header_html}
<div class="lab-context-bar">
  <div class="ctx-shell">
    <span class="ctx-where">{ctx_where}</span>
    <span class="ctx-purpose">{ctx_purpose}</span>
    <a href="/start.html" class="ctx-cta">{ctx_cta}</a>
  </div>
</div>
<main class="shell">
  <div class="eyebrow">{eyebrow}</div>
  <h1>{title}</h1>
  <div class="verdict-pill">{verdict_label}</div>
  {evidence_note_html}
  <article>
{body_html}
  </article>
  <nav class="cycle-nav">
    <span>{prev_link}</span>
    <span class="nav-up"><a href="/n/{lab}/">{up_link_label}</a></span>
    <span style="text-align:right">{next_link}</span>
  </nav>
  <div class="cycle-meta">
    <dl>
      <dt>{meta_label_cycle}</dt><dd>{cycle_ts}</dd>
      <dt>{meta_label_aeternitas}</dt><dd>{aeternitas}</dd>
      <dt>{meta_label_veritas}</dt><dd>{verdict_band}</dd>
      <dt>{meta_label_trajectory}</dt><dd>{trajectory_decision}</dd>
    </dl>
    <p>{tech_report_pre}<a href="/api/domains/{lab}/reports/agent_{cycle_ts}.md">{tech_report_link}</a>{tech_report_post}</p>
  </div>
</main>
{footer_html}
</body>
</html>
"""

_VERDICT_ACCENTS = {
    # Aeternitas → color
    ("PROCEED", "COLLASSO"):  "#34c759",   # verde — finding consolidato
    ("PROCEED", "SOSPENSIONE"): "#ffd60a", # giallo — onesto ma in sospeso
    ("PROCEED", "SCARTO"):    "#8e8e93",   # grigio — basso ρ
    ("WARN", "*"):            "#ff9500",   # ambra — passa con attenzione
    ("VETO", "*"):             "#ff453a",   # rosso — falsificazione
}


def _accent_for(aeternitas: str | None, band: str | None) -> str:
    if aeternitas == "VETO":
        return "#ff453a"
    if aeternitas == "WARN":
        return "#ff9500"
    if aeternitas == "PROCEED":
        if band == "COLLASSO":
            return "#34c759"
        if band == "SOSPENSIONE":
            return "#ffd60a"
        return "#8e8e93"
    return "#0a84ff"


def _verdict_label(aeternitas: str | None, band: str | None, traj: str | None, lang: str = "it") -> str:
    if aeternitas == "VETO":
        return _t(lang, "verdict_falsificazione")
    if traj == "REDESIGN":
        return _t(lang, "verdict_redesign")
    if band == "COLLASSO":
        return _t(lang, "verdict_collasso")
    if band == "SOSPENSIONE":
        return _t(lang, "verdict_sospensione")
    if band == "SCARTO":
        return _t(lang, "verdict_scarto")
    return _t(lang, "verdict_default")


def _evidence_note_html(domain: str, lang: str) -> str:
    key = f"narr_evidence_note_{domain}"
    pack = _N_I18N.get(lang) or _N_I18N["it"]
    if key not in pack and key not in _N_I18N["it"]:
        return ""
    return f'<aside class="evidence-note">{html_escape(_t(lang, key))}</aside>'


def _list_narrative_files(domain: str) -> list[Path]:
    narr_dir = paths.domain_data_dir(domain) / "narratives"
    if not narr_dir.exists():
        return []
    return sorted(narr_dir.glob("narrative_*.md"), key=lambda p: p.stem.replace("narrative_", ""), reverse=True)


def _adjacent_narratives(domain: str, cycle_ts: str) -> tuple[str | None, str | None]:
    """Return (prev_ts, next_ts) — older and newer cycles for this domain.

    'prev' means older (further back in time); 'next' means newer.
    """
    files = _list_narrative_files(domain)
    timestamps = [f.stem.replace("narrative_", "") for f in files]
    if cycle_ts not in timestamps:
        return None, None
    idx = timestamps.index(cycle_ts)
    # files sorted newest first → idx=0 is newest, higher idx is older
    newer = timestamps[idx - 1] if idx > 0 else None
    older = timestamps[idx + 1] if idx + 1 < len(timestamps) else None
    return older, newer


_LAB_INDEX_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="{html_lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{meta_title}</title>
<meta name="description" content="{lead}">
<meta property="og:title" content="{og_title}">
<meta property="og:description" content="{lead}">
<meta property="og:type" content="website">
<meta property="og:url" content="https://lab.d-nd.com/n/{lab}/">
<meta property="og:image" content="https://lab.d-nd.com/assets/logos/logo_90px.jpg">
<meta property="og:locale" content="{og_locale}">
<link rel="icon" href="/assets/favicon.ico">
<link rel="preconnect" href="https://rsms.me/">
<link rel="stylesheet" href="https://rsms.me/inter/inter.css">
<link rel="stylesheet" href="/assets/css/nav.css">
<style>
""" + _LAB_BASE_STYLES.replace("--accent: {accent};", "--accent: var(--cyan);") + """\
  main.shell {{ padding: 56px 0 96px; max-width: 800px; }}
  .eyebrow {{
    color: var(--cyan); font-size: 12px;
    text-transform: uppercase; letter-spacing: 0.12em;
    margin-bottom: 16px;
  }}
  h1 {{
    color: var(--ink);
    font-size: clamp(32px, 5vw, 48px);
    font-weight: 700; letter-spacing: -0.02em;
    margin-bottom: 14px; line-height: 1.1;
  }}
  .lead {{ color: var(--text); font-size: 17px; line-height: 1.6; margin-bottom: 56px; max-width: 640px; }}
  .cycle-list {{ list-style: none; }}
  .cycle-list li {{ border-top: 1px solid var(--line); padding: 24px 0; }}
  .cycle-list li:last-child {{ border-bottom: 1px solid var(--line); }}
  .cycle-list a {{ display: block; color: var(--text); }}
  .cycle-list a:hover h2 {{ color: var(--cyan); }}
  .cycle-list h2 {{ font-size: 18px; font-weight: 600; margin-bottom: 10px; line-height: 1.4; color: var(--ink); }}
  .cycle-meta {{ color: var(--muted); font-size: 13px; display: flex; gap: 14px; flex-wrap: wrap; align-items: center; }}
  .pill {{
    display: inline-block; padding: 3px 10px; border-radius: 999px;
    font-size: 10px; font-weight: 700; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--void);
  }}
  .empty {{ color: var(--dim); font-size: 15px; padding: 32px 0; }}
  .site-footer {{
    border-top: 1px solid var(--line);
    padding: 24px 0 32px; color: var(--dim); font-size: 13px;
  }}
  .footer-row {{ display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap; align-items: center; }}
  .footer-brand {{ display: flex; align-items: center; gap: 10px; }}
  .footer-brand img {{ width: 22px; height: 22px; border-radius: 4px; }}
  .site-footer a {{ color: var(--muted); }}
  .site-footer a:hover {{ color: var(--ink); }}
  @media (max-width: 760px) {{ main.shell {{ padding: 32px 0 64px; }} }}

</style>
</head>
<body>
{header_html}
<div class="lab-context-bar">
  <div class="ctx-shell">
    <span class="ctx-where">{ctx_where}</span>
    <span class="ctx-purpose">{ctx_purpose}</span>
    <a href="/start.html" class="ctx-cta">{ctx_cta}</a>
  </div>
</div>
<main class="shell">
  <div class="eyebrow">{eyebrow}</div>
  <h1>{lab}</h1>
  <p class="lead">{lead}</p>
  {body}
</main>
{footer_html}
</body>
</html>
"""


@app.get("/n/{domain}/", response_class=HTMLResponse)
@app.get("/n/{domain}", response_class=HTMLResponse)
async def public_lab_index(domain: str, request: Request) -> Any:
    """Public index of all narratives for a single lab."""
    if domain not in cfg.list_domains():
        raise HTTPException(404, "Unknown domain")
    lang = _resolve_lang(request)
    files = _list_narrative_files(domain)
    if not files:
        body_html = f"<p style='color:var(--muted)'>{html_escape(_t(lang, 'lab_empty'))}</p>"
    else:
        items: list[str] = []
        for f in files:
            parsed = _parse_narrative_file(f)
            ts = parsed["cycle_ts"]
            body_text = parsed["body"]
            first_sent = re.split(r"(?<=[.!?])\s+", body_text, maxsplit=1)[0].strip()
            title = (first_sent[:120] + "…") if len(first_sent) > 122 else first_sent
            label = _verdict_label(parsed.get("aeternitas"), parsed.get("verdict_band"), parsed.get("trajectory_decision"), lang)
            accent = _accent_for(parsed.get("aeternitas"), parsed.get("verdict_band"))
            ts_pretty = ts[:8] + " · " + ts[9:11] + ":" + ts[11:13] if len(ts) >= 13 else ts
            items.append(
                f"<li>"
                f"<a href='/n/{html_escape(domain)}/{html_escape(ts)}'>"
                f"<h2>{html_escape(title)}</h2>"
                f"<div class='cycle-meta'>"
                f"<span class='pill' style='background:{accent}'>{html_escape(label)}</span>"
                f"<span>{html_escape(ts_pretty)}</span>"
                f"<span>{parsed.get('word_count') or '—'} {html_escape(_t(lang, 'lab_words_unit'))}</span>"
                f"</div>"
                f"</a></li>"
            )
        body_html = "<ul class='cycle-list'>" + "\n".join(items) + "</ul>"

    lead = _t(lang, f"lead_{domain}") if f"lead_{domain}" in (_N_I18N.get(lang) or {}) else _t(lang, "card_default_desc")
    return HTMLResponse(_LAB_INDEX_HTML_TEMPLATE.format(
        html_lang=_t(lang, "html_lang"),
        og_locale=_t(lang, "og_locale"),
        meta_title=_t(lang, "lab_meta_title_fmt", lab=domain),
        og_title=_t(lang, "lab_og_title_fmt", lab=domain),
        ctx_where=_t(lang, "lab_ctx_where_fmt", lab=domain),
        ctx_purpose=_t(lang, "lab_ctx_purpose"),
        ctx_cta=_t(lang, "master_ctx_cta"),
        eyebrow=_t(lang, "lab_eyebrow"),
        header_html=_render_lab_header(lang, cycle_active=True, current_path=f"/n/{domain}/"),
        footer_html=_render_lab_footer(lang),
        lab=html_escape(domain), lead=html_escape(lead), body=body_html,
    ))


_MASTER_INDEX_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="{html_lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{meta_title}</title>
<meta name="description" content="{meta_desc}">
<meta property="og:title" content="{og_title}">
<meta property="og:description" content="{og_desc}">
<meta property="og:type" content="website">
<meta property="og:url" content="https://lab.d-nd.com/n/">
<meta property="og:image" content="https://lab.d-nd.com/assets/logos/logo_90px.jpg">
<meta property="og:locale" content="{og_locale}">
<link rel="icon" href="/assets/favicon.ico">
<link rel="preconnect" href="https://rsms.me/">
<link rel="stylesheet" href="https://rsms.me/inter/inter.css">
<link rel="stylesheet" href="/assets/css/nav.css">
<style>
""" + _LAB_BASE_STYLES.replace("--accent: {accent};", "--accent: var(--cyan);") + """\
  main.shell {{ padding: 56px 0 96px; max-width: 1080px; }}
  .eyebrow {{
    color: var(--cyan); font-size: 12px;
    text-transform: uppercase; letter-spacing: 0.12em;
    margin-bottom: 16px;
  }}
  h1 {{
    color: var(--ink);
    font-size: clamp(36px, 6vw, 54px);
    font-weight: 700; letter-spacing: -0.02em;
    margin-bottom: 18px; line-height: 1.06;
  }}
  .lead {{
    color: var(--text); font-size: 18px; line-height: 1.55;
    max-width: 680px; margin-bottom: 56px;
  }}
  .lab-grid {{
    display: grid; gap: 24px;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  }}
  .lab-card {{
    border: 1px solid var(--line); border-radius: var(--radius);
    background: rgba(13, 14, 20, 0.55);
    padding: 24px; transition: border-color 200ms, background 200ms;
  }}
  .lab-card:hover {{ border-color: var(--cyan); background: rgba(13, 14, 20, 0.85); }}
  .lab-card a {{ display: block; color: var(--text); }}
  .lab-card h2 {{ color: var(--ink); font-size: 19px; font-weight: 600; margin-bottom: 6px; }}
  .lab-card .desc {{ color: var(--muted); font-size: 14px; line-height: 1.5; margin-bottom: 18px; }}
  .lab-card .last {{
    font-size: 14px; line-height: 1.55;
    padding-top: 14px; border-top: 1px solid var(--line);
    color: var(--text);
  }}
  .lab-card .last-meta {{
    color: var(--muted); font-size: 12px;
    margin-top: 8px; display: flex; gap: 10px; flex-wrap: wrap; align-items: center;
  }}
  .pill {{
    display: inline-block; padding: 2px 10px; border-radius: 999px;
    font-size: 10px; font-weight: 700; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--void);
  }}
  .site-footer {{
    border-top: 1px solid var(--line);
    padding: 24px 0 32px; color: var(--dim); font-size: 13px;
    margin-top: 80px;
  }}
  .footer-row {{ display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap; align-items: center; }}
  .footer-brand {{ display: flex; align-items: center; gap: 10px; }}
  .footer-brand img {{ width: 22px; height: 22px; border-radius: 4px; }}
  .site-footer a {{ color: var(--muted); }}
  .site-footer a:hover {{ color: var(--ink); }}
  @media (max-width: 760px) {{ main.shell {{ padding: 32px 0 64px; }} }}

</style>
</head>
<body>
{header_html}
<div class="lab-context-bar">
  <div class="ctx-shell">
    <span class="ctx-where">{ctx_where}</span>
    <span class="ctx-purpose">{ctx_purpose}</span>
    <a href="/start.html" class="ctx-cta">{ctx_cta}</a>
  </div>
</div>
<main class="shell">
  <div class="eyebrow">{eyebrow}</div>
  <h1>{master_h1}</h1>
  <p class="lead">{lead}</p>
  <div class="lab-grid">
    {cards}
  </div>
</main>
{footer_html}
</body>
</html>
"""


@app.get("/n/", response_class=HTMLResponse)
@app.get("/n", response_class=HTMLResponse)
async def public_master_index(request: Request) -> Any:
    """Public master index — all labs with their latest narrative summary."""
    lang = _resolve_lang(request)
    # Master physics lab: vive su d-nd.com (sviluppo del modello D-ND).
    # Card statica esterna in testa, prima dei lab installabili dinamici.
    physics_card = (
        "<div class='lab-card'>"
        "<a href='https://d-nd.com/ai-lab' target='_blank' rel='noopener noreferrer'>"
        f"<h2>{html_escape(_t(lang, 'physics_master_h2'))} <span style='font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--purple);margin-left:8px;'>{html_escape(_t(lang, 'physics_master_label'))}</span></h2>"
        f"<div class='desc'>{html_escape(_t(lang, 'physics_master_desc'))}</div>"
        f"<div class='last' style='color:var(--muted);font-style:italic;'>{html_escape(_t(lang, 'physics_master_last'))}</div>"
        "</a></div>"
    )
    cards: list[str] = [physics_card]
    for domain in cfg.list_domains():
        files = _list_narrative_files(domain)
        last_html = ""
        if files:
            try:
                parsed = _parse_narrative_file(files[0])
                ts = parsed["cycle_ts"]
                body_text = parsed["body"]
                first_sent = re.split(r"(?<=[.!?])\s+", body_text, maxsplit=1)[0].strip()
                snippet = (first_sent[:140] + "…") if len(first_sent) > 142 else first_sent
                label = _verdict_label(parsed.get("aeternitas"), parsed.get("verdict_band"), parsed.get("trajectory_decision"), lang)
                accent = _accent_for(parsed.get("aeternitas"), parsed.get("verdict_band"))
                ts_pretty = ts[:8] + " · " + ts[9:11] + ":" + ts[11:13] if len(ts) >= 13 else ts
                last_html = (
                    f"<div class='last'>{html_escape(snippet)}"
                    f"<div class='last-meta'>"
                    f"<span class='pill' style='background:{accent}'>{html_escape(label)}</span>"
                    f"<span>{html_escape(ts_pretty)}</span>"
                    f"</div></div>"
                )
            except Exception:
                last_html = f"<div class='last' style='color:var(--muted)'>{html_escape(_t(lang, 'card_pending_narrative'))}</div>"
        else:
            last_html = f"<div class='last' style='color:var(--muted)'>{html_escape(_t(lang, 'card_no_narrative'))}</div>"
        desc_key = f"lead_{domain}"
        desc = _t(lang, desc_key) if desc_key in (_N_I18N.get(lang) or {}) else _t(lang, "card_default_desc")
        cards.append(
            f"<div class='lab-card'>"
            f"<a href='/n/{html_escape(domain)}/'>"
            f"<h2>{html_escape(domain)}</h2>"
            f"<div class='desc'>{html_escape(desc)}</div>"
            f"{last_html}"
            f"</a></div>"
        )
    return HTMLResponse(_MASTER_INDEX_HTML_TEMPLATE.format(
        html_lang=_t(lang, "html_lang"),
        og_locale=_t(lang, "og_locale"),
        meta_title=_t(lang, "master_meta_title"),
        meta_desc=_t(lang, "master_meta_desc"),
        og_title=_t(lang, "master_og_title"),
        og_desc=_t(lang, "master_og_desc"),
        ctx_where=_t(lang, "master_ctx_where"),
        ctx_purpose=_t(lang, "master_ctx_purpose"),
        ctx_cta=_t(lang, "master_ctx_cta"),
        eyebrow=_t(lang, "master_eyebrow"),
        master_h1=_t(lang, "master_h1"),
        lead=_t(lang, "master_lead"),
        header_html=_render_lab_header(lang, cycle_active=True, current_path="/n/"),
        footer_html=_render_lab_footer(lang),
        cards="\n".join(cards),
    ))


@app.get("/n/{domain}/{cycle_ts}", response_class=HTMLResponse)
async def public_narrative_page(domain: str, cycle_ts: str, request: Request) -> Any:
    """Public-facing narrative page — Apple-like styled, mobile-first.

    URL canonico shareable (es. su LinkedIn, Twitter, embed).
    No auth check (volutamente pubblico — se vuoi private, usa l'endpoint API).
    """
    if domain not in cfg.list_domains():
        raise HTTPException(404, "Unknown domain")
    if not re.fullmatch(r"\d{8}_\d{4,6}", cycle_ts):
        raise HTTPException(400, "Invalid cycle_ts format")
    narr_path = paths.domain_data_dir(domain) / "narratives" / f"narrative_{cycle_ts}.md"
    if not narr_path.exists():
        raise HTTPException(404, "No narrative for this cycle")
    parsed = _parse_narrative_file(narr_path)
    lang = _resolve_lang(request)

    accent = _accent_for(parsed.get("aeternitas"), parsed.get("verdict_band"))
    label = _verdict_label(parsed.get("aeternitas"), parsed.get("verdict_band"), parsed.get("trajectory_decision"), lang)

    # Title: derive from body's first sentence cap, or fallback
    body = parsed["body"]
    first_sent = re.split(r"(?<=[.!?])\s+", body, maxsplit=1)[0].strip()
    title = (first_sent[:90] + "…") if len(first_sent) > 92 else first_sent
    if not title:
        title = _t(lang, "narr_default_title_fmt", cycle_ts=cycle_ts, domain=domain)

    # Render body paragraphs as <p> (paragraphs split on blank lines)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    body_html = "\n".join(f"    <p>{html_escape(p)}</p>" for p in paragraphs)
    meta_desc = (paragraphs[0] if paragraphs else title)[:200]

    older, newer = _adjacent_narratives(domain, cycle_ts)
    prev_link = f"<a href='/n/{html_escape(domain)}/{older}'>{html_escape(_t(lang, 'narr_prev_link'))}</a>" if older else ""
    next_link = f"<a href='/n/{html_escape(domain)}/{newer}'>{html_escape(_t(lang, 'narr_next_link'))}</a>" if newer else ""

    return HTMLResponse(_NARRATIVE_HTML_TEMPLATE.format(
        html_lang=_t(lang, "html_lang"),
        og_locale=_t(lang, "og_locale"),
        meta_title=_t(lang, "narr_meta_title_fmt", title=title, lab=domain),
        ctx_where=_t(lang, "narr_ctx_where_fmt", lab=domain, cycle_ts=cycle_ts),
        ctx_purpose=_t(lang, "narr_ctx_purpose"),
        ctx_cta=_t(lang, "master_ctx_cta"),
        eyebrow=_t(lang, "narr_eyebrow_fmt", lab=domain),
        up_link_label=_t(lang, "narr_up_link_fmt", lab=domain),
        meta_label_cycle=_t(lang, "narr_meta_cycle"),
        meta_label_aeternitas=_t(lang, "narr_meta_aeternitas"),
        meta_label_veritas=_t(lang, "narr_meta_veritas"),
        meta_label_trajectory=_t(lang, "narr_meta_trajectory"),
        tech_report_pre=_t(lang, "narr_tech_report_pre"),
        tech_report_link=_t(lang, "narr_tech_report_link"),
        tech_report_post=_t(lang, "narr_tech_report_post"),
        header_html=_render_lab_header(lang, cycle_active=True, current_path=f"/n/{domain}/{cycle_ts}"),
        footer_html=_render_lab_footer(lang),
        title=html_escape(title),
        meta_desc=html_escape(meta_desc),
        accent=accent,
        lab=html_escape(domain),
        verdict_label=html_escape(label),
        evidence_note_html=_evidence_note_html(domain, lang),
        body_html=body_html,
        cycle_ts=html_escape(cycle_ts),
        aeternitas=html_escape(parsed.get("aeternitas") or "—"),
        verdict_band=html_escape(parsed.get("verdict_band") or "—"),
        trajectory_decision=html_escape(parsed.get("trajectory_decision") or "—"),
        prev_link=prev_link,
        next_link=next_link,
    ))


@app.get("/api/domains/{domain}/trajectory")
async def get_trajectory(domain: str, request: Request, limit: int = 20) -> list[dict[str, Any]]:
    await _check_auth(request)
    _validate_domain(domain)
    log_path = paths.domain_data_dir(domain) / "trajectory_log.jsonl"
    if not log_path.exists():
        return []
    lines = log_path.read_text().strip().split("\n")[-limit:]
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


@app.get("/api/domains/{domain}/cost")
async def get_cost(domain: str, request: Request) -> dict[str, Any]:
    await _check_auth(request)
    _validate_domain(domain)
    lab_data_path = paths.lab_data_path(domain)
    if not lab_data_path.exists():
        return {"cumulative_usd": 0.0, "n_cycles": 0, "history": []}
    data = _read_json_safe(lab_data_path, {})
    return {
        "cumulative_usd": _sum_costs_from_reports(domain),
        "n_cycles": data.get("cicli_totali", 0),
        "history": [],  # Phase 6 v2: parse per-cycle costs
    }


@app.get("/api/domains/{domain}/lab_graph")
async def get_lab_graph(domain: str, request: Request) -> dict[str, Any]:
    """Knowledge graph (nodes + edges + stats) produced by build_graph
    movement. Used by the dashboard graph visualization."""
    await _check_auth(request)
    _validate_domain(domain)
    p = paths.lab_graph_path(domain)
    if not p.exists():
        return {"graph": {"nodes": [], "edges": []}, "stats": {}, "domain": domain}
    return _read_json_safe(p, {"graph": {"nodes": [], "edges": []}, "stats": {}, "domain": domain})


@app.get("/api/domains/{domain}/cimitero")
async def get_cimitero(domain: str, request: Request) -> dict[str, str]:
    await _check_auth(request)
    _validate_domain(domain)
    p = paths.cimitero_path(domain)
    if not p.exists():
        return {"content": ""}
    return {"content": p.read_text(errors="replace")}


@app.get("/api/domains/{domain}/scoperte")
async def list_scoperte(domain: str, request: Request) -> list[dict[str, Any]]:
    """Lista scoperte (lab-note + cycle-report drafts) per il dominio.

    Output di on_crystallize.py — letto live, no cache. Read-only OK in demo mode.
    """
    await _check_auth(request)
    _validate_domain(domain)
    # Refactor 03/05: scoperte/ è draft interno workflow (con markup TM1/[TARGET]),
    # published/ è source pubblica (sanitized). Dashboard demo-mode = pubblico.
    published_dir = paths.domain_data_dir(domain) / "published"
    if not published_dir.exists():
        return []
    items = []
    for d in sorted(published_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        lab_note = d / "lab-note.md"
        cycle_report = d / "cycle-report.md"
        if not lab_note.exists():
            continue
        ln_text = lab_note.read_text(errors="replace")
        fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", ln_text, re.S)
        meta = {}
        if fm_match:
            for line in fm_match.group(1).splitlines():
                if line.strip() and ":" in line and not line.startswith(" "):
                    k, _, v = line.strip().partition(":")
                    meta[k.strip()] = v.strip().strip('"').strip("'")
        parts = d.name.split("_")
        cycle_ts = f"{parts[0]}_{parts[1]}" if len(parts) >= 2 and parts[0].isdigit() else ""
        items.append({
            "dir": d.name,
            "domain": domain,
            "cycle_ts": cycle_ts,
            "title_proposal": meta.get("title_proposal", ""),
            "slug_proposal": meta.get("slug_proposal", ""),
            "status": meta.get("status", "draft"),
            "ssp_state": meta.get("ssp_state", "scoperte"),
            "is_auto_scaffold": False,
            "has_cycle_report": cycle_report.exists(),
            "modified_at": datetime.fromtimestamp(d.stat().st_mtime).isoformat(),
        })
    return items


@app.get("/api/domains/{domain}/scoperte/{slug_dir}")
async def get_scoperta_detail(domain: str, slug_dir: str, request: Request) -> dict[str, Any]:
    """Dettaglio singola scoperta — ritorna il markdown + metadata.

    Refactor 03/05: legge da published/ (sanitized). Per accesso draft
    interno: filesystem direct (non esposto via API).
    """
    await _check_auth(request)
    _validate_domain(domain)
    if "/" in slug_dir or ".." in slug_dir:
        raise HTTPException(status_code=400, detail="Invalid slug_dir")
    scoperta_dir = paths.domain_data_dir(domain) / "published" / slug_dir
    if not scoperta_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Scoperta {slug_dir} non trovata")
    lab_note = scoperta_dir / "lab-note.md"
    cycle_report = scoperta_dir / "cycle-report.md"
    return {
        "dir": slug_dir,
        "domain": domain,
        "lab_note_md": lab_note.read_text(errors="replace") if lab_note.exists() else "",
        "cycle_report_md": cycle_report.read_text(errors="replace") if cycle_report.exists() else "",
    }


@app.get("/api/seed/lookup/{candidate_name}")
async def lookup_seed_package(candidate_name: str, request: Request) -> dict[str, Any]:
    """Cerca un kernel nel d-nd-seed/kernels/ che corrisponde al candidate name.

    Step C-1 (operatore 03/05 sera): "Open in seed repo" del modale.
    Match fuzzy: strip suffix tipo (-lib/-kernel/-demo) + match per nome dir
    (kebab→snake compat) contro stage5_verification.json esistenti.

    Ritorna: {found, package_name, url_github, url_local} o {found: false}.
    """
    await _check_auth(request)
    seed_kernels_dir = Path("/opt/d-nd-seed/kernels")
    if not seed_kernels_dir.exists():
        return {"found": False, "reason": "d-nd-seed/kernels/ non disponibile su questo nodo"}

    # Strip type suffix dal candidate name
    base = re.sub(r'-(?:lib|kernel|demo)$', '', candidate_name)
    base_norm = base.lower().replace('-', '').replace('_', '')

    for d in sorted(seed_kernels_dir.iterdir()):
        if not d.is_dir():
            continue
        if not (d / "stage5_verification.json").exists():
            continue
        dir_norm = d.name.lower().replace('_', '').replace('-', '')
        # match: candidate slug è contenuto nel package name (o viceversa)
        if base_norm in dir_norm or dir_norm.replace('dndkernel', '') in base_norm:
            return {
                "found": True,
                "package_name": d.name,
                "url_github": f"https://github.com/GrazianoGuiducci/d-nd-seed/tree/main/kernels/{d.name}",
                "url_local": str(d),
            }
    return {"found": False, "reason": f"no kernel matching '{base}' in seed"}


@app.get("/api/domains/{domain}/verification/{slug_dir}/{candidate_type}")
async def get_verification_detail(domain: str, slug_dir: str, candidate_type: str,
                                   request: Request) -> dict[str, Any]:
    """Step C-2 (operatore 03/05 sera): "View Stage 4 verification".

    Cerca il prodotto maturo corrispondente al cycle+type+slug e ritorna
    verification.json. La dir naming convenzione di Stage 4 PoC runner:
      <cycle_ts>_finding<N>_<type>_<slug-without-suffix>
    """
    await _check_auth(request)
    _validate_domain(domain)
    if "/" in slug_dir or ".." in slug_dir or candidate_type not in ("library", "kernel", "demo"):
        raise HTTPException(status_code=400, detail="invalid params")

    prodotti_dir = paths.domain_data_dir(domain) / "prodotti"
    if not prodotti_dir.exists():
        return {"verified": False, "reason": "prodotti/ non disponibile"}

    # Estrai cycle_ts dalla slug_dir (formato: 20260501_1256_xxx)
    parts = slug_dir.split("_")
    if len(parts) < 2 or not parts[0].isdigit() or not parts[1].isdigit():
        return {"verified": False, "reason": f"cycle_ts non parsable da {slug_dir}"}
    cycle_ts = f"{parts[0]}_{parts[1]}"

    # Cerca dir prodotto matching cycle_ts + type
    for d in prodotti_dir.iterdir():
        if not d.is_dir():
            continue
        if not (d.name.startswith(cycle_ts) and f"_{candidate_type}_" in d.name):
            continue
        verification_path = d / "verification.json"
        if not verification_path.exists():
            continue
        try:
            v = json.loads(verification_path.read_text())
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=500, detail=f"verification parse: {e}")
        return {
            "verified": True,
            "product_id": d.name,
            "verification": v,
        }
    return {"verified": False, "reason": f"no verified product per cycle {cycle_ts} type {candidate_type}"}


@app.get("/api/domains/{domain}/blueprint/{slug_dir}/{candidate_type}")
async def get_blueprint(domain: str, slug_dir: str, candidate_type: str,
                        request: Request) -> Response:
    """Genera blueprint markdown per un candidate (library/kernel/demo).

    Operatore 03/05 sera: "report o blueprint che lo realizzi (in uno step
    successivo)". Step B: download markdown self-contained per
    implementatore umano.
    """
    await _check_auth(request)
    _validate_domain(domain)
    if candidate_type not in ("library", "kernel", "demo"):
        raise HTTPException(status_code=400,
                            detail="candidate_type must be library/kernel/demo")
    if "/" in slug_dir or ".." in slug_dir:
        raise HTTPException(status_code=400, detail="Invalid slug_dir")
    pub_dir = paths.domain_data_dir(domain) / "published" / slug_dir
    manifest_path = pub_dir / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404,
                            detail=f"manifest non trovato per {slug_dir}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"manifest parse: {e}")
    candidates = manifest.get("applications_candidate", [])
    target = next((c for c in candidates if c.get("type") == candidate_type), None)
    if not target:
        raise HTTPException(status_code=404,
                            detail=f"nessun candidate type={candidate_type}")

    # Import lazily per evitare cycle import in caso di refactor
    from core.triggers.blueprint_generator import render_blueprint
    source_meta = manifest.get("discovery_provenance", {}) or {}
    md = render_blueprint(manifest, target, source_meta)

    name = target.get("name", "blueprint")
    filename = f"BLUEPRINT_{name}.md"
    return Response(
        content=md,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/domains/{domain}/manifest/{slug_dir}")
async def get_manifest_detail(domain: str, slug_dir: str, request: Request) -> dict[str, Any]:
    """Manifest completo (sanitized) per una soluzione: usato dal modale UI.

    Refactor 03/05 sera: source published/<slug>/manifest.json.
    Ritorna anche summary + finding_index per esposizione completa modale.
    """
    await _check_auth(request)
    _validate_domain(domain)
    if "/" in slug_dir or ".." in slug_dir:
        raise HTTPException(status_code=400, detail="Invalid slug_dir")
    pub_dir = paths.domain_data_dir(domain) / "published" / slug_dir
    if not pub_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Manifest {slug_dir} non trovato")
    manifest_path = pub_dir / "manifest.json"
    summary_path = pub_dir / "summary.md"
    finding_index_path = pub_dir / "finding_index.json"
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=500, detail=f"manifest parse error: {e}")
    finding_index = {}
    if finding_index_path.exists():
        try:
            finding_index = json.loads(finding_index_path.read_text())
        except json.JSONDecodeError:
            pass
    return {
        "dir": slug_dir,
        "domain": domain,
        "manifest": manifest,
        "summary_md": summary_path.read_text(errors="replace") if summary_path.exists() else "",
        "finding_index": finding_index,
    }


@app.get("/api/domains/{domain}/applications")
async def list_applications(domain: str, request: Request) -> dict[str, Any]:
    """Lista applications candidate (output application_designer.py).

    Refactor 03/05: aggrega published/<dir>/manifest.json (sanitized,
    no [TARGET] markers). Demo mode = pubblico.
    """
    await _check_auth(request)
    _validate_domain(domain)
    published_dir = paths.domain_data_dir(domain) / "published"
    if not published_dir.exists():
        return {"domain": domain, "candidates": [], "review_required": [], "non_application": []}
    candidates = []
    review_required = []
    non_application = []
    for d in sorted(published_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        manifest_path = d / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text())
        except json.JSONDecodeError:
            continue
        provenance = manifest.get("discovery_provenance", {})
        cycle_ts = provenance.get("cycle_ts", "")
        for app in manifest.get("applications_candidate", []):
            candidates.append({
                "dir": d.name,
                "domain": domain,
                "cycle_ts": cycle_ts,
                "name": app.get("name", ""),
                "type": app.get("type", ""),
                "discovery_finding_idx": app.get("discovery_finding_idx"),
                "discovery_finding_title": app.get("discovery_finding_title", ""),
                "verifier_form": (app.get("verification_spec") or {}).get("verifier_form", ""),
                "status": "draft",
                "maturity": "transitional_candidate",
            })
        for r in manifest.get("review_required_findings", []):
            review_required.append({
                "dir": d.name, "domain": domain, "cycle_ts": cycle_ts,
                "finding_id": r.get("finding_id"),
                "title": r.get("title", ""),
                "reason": r.get("reason") or r.get("skip_reason", ""),
            })
        for n in manifest.get("non_application_findings", []):
            non_application.append({
                "dir": d.name, "domain": domain, "cycle_ts": cycle_ts,
                "finding_id": n.get("finding_id"),
                "title": n.get("title", ""),
                "role": n.get("role", ""),
                "skip_reason": n.get("skip_reason", ""),
            })
    return {
        "domain": domain,
        "summary": {
            "n_candidates": len(candidates),
            "n_review_required": len(review_required),
            "n_non_application": len(non_application),
        },
        "candidates": candidates,
        "review_required": review_required,
        "non_application": non_application,
    }


@app.get("/api/domains/{domain}/cycle_traces")
async def list_cycle_traces(domain: str, request: Request, limit: int = 20) -> list[dict[str, Any]]:
    """Lista riassuntiva dei cycle_trace_*.json del dominio (per dropdown timeline)."""
    await _check_auth(request)
    _validate_domain(domain)
    domain_dir = paths.domain_data_dir(domain)
    if not domain_dir.exists():
        return []
    items = []
    for f in sorted(domain_dir.glob("cycle_trace_*.json"),
                    key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        try:
            data = json.loads(f.read_text())
            items.append({
                "cycle_ts": data.get("cycle_ts", ""),
                "domain": domain,
                "total_s": data.get("total_s"),
                "n_movements": data.get("n_movements"),
                "n_ok": data.get("n_ok"),
                "n_skipped": data.get("n_skipped"),
                "n_errors": data.get("n_errors"),
                "ssp_pipeline_status": data.get("ssp_pipeline_status"),
            })
        except (json.JSONDecodeError, OSError):
            continue
    return items


@app.get("/api/domains/{domain}/cycle_trace/{cycle_ts}")
async def get_cycle_trace(domain: str, cycle_ts: str, request: Request) -> dict[str, Any]:
    """Dettaglio cycle_trace: sequenza movements + duration + status + metrics + errori."""
    await _check_auth(request)
    _validate_domain(domain)
    if "/" in cycle_ts or ".." in cycle_ts:
        raise HTTPException(status_code=400, detail="Invalid cycle_ts")
    trace_path = paths.domain_data_dir(domain) / f"cycle_trace_{cycle_ts}.json"
    if not trace_path.exists():
        raise HTTPException(status_code=404, detail=f"cycle_trace per {cycle_ts} non trovato")
    return json.loads(trace_path.read_text())


@app.get("/api/domains/{domain}/prodotti")
async def list_prodotti(domain: str, request: Request) -> list[dict[str, Any]]:
    """Lista prodotti maturi (post Stage 4 PoC runner).

    Un prodotto maturo ha sia manifest.json che verification.json reale
    (NON .spec) — distintivo di Stage 4 eseguito con metriche concrete.
    Vuoto finché non gira stage4_poc_runner.py.
    """
    await _check_auth(request)
    _validate_domain(domain)
    prodotti_dir = paths.domain_data_dir(domain) / "prodotti"
    if not prodotti_dir.exists():
        return []
    items = []
    for d in sorted(prodotti_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        verification = d / "verification.json"
        manifest = d / "manifest.json"
        if not (verification.exists() and manifest.exists()):
            continue
        try:
            m = json.loads(manifest.read_text())
            v = json.loads(verification.read_text())
        except json.JSONDecodeError:
            continue
        # Sanitize on-the-fly: strip [TARGET] prefix da name (safety per
        # manifest.json dei prodotti pre-refactor 03/05).
        raw_name = m.get("name", d.name)
        clean_name = re.sub(r'^\[TARGET\]\s+', '', raw_name)
        clean_name = re.sub(r'^\[TARGET — [^\]]+\]\s*', '', clean_name)
        items.append({
            "id": d.name,
            "domain": domain,
            "type": m.get("type", ""),
            "name": clean_name,
            "status": v.get("status", "unknown"),
            "verifier_form": v.get("verifier_form", ""),
            "metrics": v.get("metrics", {}),
            "discovery_cycle_ts": m.get("discovery_cycle_ts", ""),
            "discovery_finding_idx": m.get("discovery_finding_idx"),
            "verified_at": v.get("verified_at", ""),
            "modified_at": datetime.fromtimestamp(d.stat().st_mtime).isoformat(),
        })
    return items


@app.get("/api/domains/{domain}/prodotti/{product_id}")
async def get_prodotto_detail(domain: str, product_id: str, request: Request) -> dict[str, Any]:
    """Dettaglio prodotto: manifest + verification + script + log."""
    await _check_auth(request)
    _validate_domain(domain)
    if "/" in product_id or ".." in product_id:
        raise HTTPException(status_code=400, detail="Invalid product_id")
    prod_dir = paths.domain_data_dir(domain) / "prodotti" / product_id
    if not prod_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Prodotto {product_id} non trovato")
    manifest = prod_dir / "manifest.json"
    verification = prod_dir / "verification.json"
    poc_script = prod_dir / "poc.py"
    poc_log = prod_dir / "poc.log"
    return {
        "id": product_id,
        "domain": domain,
        "manifest": json.loads(manifest.read_text()) if manifest.exists() else {},
        "verification": json.loads(verification.read_text()) if verification.exists() else {},
        "poc_script": poc_script.read_text(errors="replace") if poc_script.exists() else "",
        "poc_log": poc_log.read_text(errors="replace") if poc_log.exists() else "",
    }


@app.post("/api/domains/{domain}/run")
async def run_cycle_endpoint(domain: str, body: RunRequest, request: Request) -> dict[str, str]:
    await _check_auth(request)
    _check_demo_writes(request)
    _validate_domain(domain)
    cycle_id = _start_cycle(domain, body.direction_override)
    return {"cycle_id": cycle_id, "domain": domain, "status": "running"}


@app.get("/api/cycles/{cycle_id}")
async def cycle_status(cycle_id: str, request: Request) -> dict[str, Any]:
    await _check_auth(request)
    info = _CYCLES.get(cycle_id)
    if not info:
        raise HTTPException(404, "cycle not found")
    return {
        k: v for k, v in info.items()
        if k not in ("proc",)  # don't serialize the Popen object
    }


@app.websocket("/api/cycles/{cycle_id}/log")
async def cycle_log_ws(websocket: WebSocket, cycle_id: str) -> None:
    """Stream the cycle log file to the client. Tails the file until
    the cycle completes, then closes the WS."""
    await websocket.accept()
    info = _CYCLES.get(cycle_id)
    if not info:
        await websocket.send_json({"error": "cycle not found"})
        await websocket.close()
        return

    log_path = Path(info["log_path"])
    if not log_path.exists():
        log_path.touch()

    pos = 0
    try:
        while True:
            try:
                size = log_path.stat().st_size
            except FileNotFoundError:
                break
            if size > pos:
                with log_path.open() as f:
                    f.seek(pos)
                    chunk = f.read()
                    pos = f.tell()
                if chunk:
                    await websocket.send_json({
                        "type": "log",
                        "data": chunk,
                    })
            if info["status"] != "running":
                # Cycle ended — send a final status frame and close
                await websocket.send_json({
                    "type": "status",
                    "status": info["status"],
                    "return_code": info.get("return_code"),
                    "finished_at": info.get("finished_at"),
                })
                break
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ─── Chat agent ─────────────────────────────────────────────────────


@app.post("/api/domains/{domain}/chat")
async def chat_endpoint(domain: str, body: ChatRequest, request: Request) -> dict[str, Any]:
    """Multi-turn chat con tools (Phase 6 v5).

    Tools categorizzati:
      - READ tools (eseguiti server-side immediatamente, risultato torna al
        modello che continua il ragionamento): list_reports, read_report,
        read_falsifier, read_seed_tension, list_cimitero.
      - PROPOSAL tools (NON eseguiti — ritornano una pending_action che il
        frontend renderizza come confirm card; user click → endpoint dedicato):
        propose_inject_tension, propose_run_cycle. Pattern: il chat agent
        descrive cosa farebbe, l'operatore conferma esplicitamente.
    """
    await _check_auth(request)
    _check_demo_writes(request)
    _validate_domain(domain)

    from core import llm_adapter

    system_prompt = _build_chat_system_prompt(domain)

    if body.context_node:
        node = body.context_node
        node_md = (
            f"\n\n## CURRENT FOCUS — graph node selected by the user\n"
            f"- id: `{node.get('id', '?')}`\n"
            f"- type: `{node.get('type', '?')}`\n"
            f"- label: {node.get('label', '?')}\n"
        )
        for key in ("claim", "verdict", "intensity", "stato", "porta", "title"):
            if node.get(key):
                node_md += f"- {key}: {str(node[key])[:300]}\n"
        node_md += (
            "\nThe user's question is most likely about this node. Answer in "
            "context of it; cite the corresponding report or seed entry if "
            "relevant; if the question is broader, expand from there.\n"
        )
        system_prompt += node_md

    # Consapevolezza pagina (Atto UX 7): tab attiva + selezione SSP.
    # Pattern bot sito: il chat sa dove l'utente è e cosa sta guardando,
    # può suggerire CTA ('vai al tab Prodotti', 'apri questa scoperta').
    if body.context_tab:
        tab_label = {
            "grafo": "Grafo (knowledge graph)",
            "bicono": "Bicono (galleria scoperte 4-poli)",
            "agente": "Agente (lista cicli + verdict + falsifier flags)",
            "incrocio": "Tassonomia (grafo aggregato + Trajectory timeline)",
            "prodotti": "Prodotti (pipeline SSP: scoperte / applicazioni / prodotti maturi)",
            "info": "Info (context.md domain + Pipeline SSP spiegata + reference)",
        }.get(body.context_tab, body.context_tab)
        system_prompt += f"\n\n## CURRENT TAB — user is viewing: {tab_label}\n"
        system_prompt += (
            "When relevant, suggest concrete CTAs like 'Apri tab Info → Pipeline SSP per "
            "il dettaglio', 'Vai su tab Prodotti per vedere i prodotti maturi', "
            "'Cerca nella Sidebar Dettaglio (destra)'. Be a guide, not just a Q&A.\n"
        )

    if body.context_scoperta:
        s = body.context_scoperta
        system_prompt += (
            "\n\n## SCOPERTA SELEZIONATA — user is inspecting in tab Prodotti\n"
            f"- title: {s.get('title_proposal', s.get('dir', '?'))[:200]}\n"
            f"- cycle_ts: {s.get('cycle_ts', '?')}\n"
            f"- status: {s.get('status', '?')} (mature/transitional/pre_discovery/draft)\n"
            f"- ssp_state: {s.get('ssp_state', 'scoperte')}\n"
            "Answer focused on this scoperta. If status is pre_discovery/transitional, "
            "explain why no products have been generated yet (gate strict).\n"
        )

    if body.context_prodotto:
        p = body.context_prodotto
        m = p.get("metrics", {}) or {}
        system_prompt += (
            "\n\n## PRODOTTO SELEZIONATO — user is inspecting in tab Prodotti\n"
            f"- name: {p.get('name', p.get('id', '?'))[:200]}\n"
            f"- type: {p.get('type', '?')} (library / kernel / demo)\n"
            f"- verdict: {p.get('status', '?')} (PASS / FAIL / INCONCLUSIVE / UNTESTABLE)\n"
            f"- discovery_cycle_ts: {p.get('discovery_cycle_ts', '?')}\n"
            f"- finding_idx: #{p.get('discovery_finding_idx', '?')}\n"
            f"- metrics: naive={m.get('naive_score')} informed={m.get('informed_score')} delta={m.get('delta')} n_trials={m.get('n_trials')}\n"
            "Answer about what was actually verified and what the metrics mean. "
            "If asked, suggest reading poc.py via the read_report tool or detail endpoint.\n"
        )

    # Augment system prompt with chat tools usage hint
    system_prompt += (
        "\n\n## TOOLS AVAILABLE\n"
        "You have read tools (list_reports, read_report, read_falsifier, "
        "read_seed_tension, list_cimitero) — call them when the user asks "
        "about specific reports, flags, or tensions. Don't guess; lookup.\n"
        "You also have PROPOSAL tools (propose_inject_tension, propose_run_cycle): "
        "calling them does NOT execute the action — it returns a structured "
        "proposal the user must confirm via the UI. Use them when the user "
        "explicitly asks to add a tension or run a cycle.\n"
    )

    user_messages = [{"role": m.role, "content": m.content} for m in body.messages]

    config = llm_adapter.AdapterConfig.from_env()
    config.timeout_seconds = 240
    try:
        config.validate()
    except ValueError as e:
        raise HTTPException(503, f"LLM not configured: {e}")

    try:
        import openai
    except ImportError:
        raise HTTPException(503, "openai package not installed")

    client = openai.OpenAI(base_url=config.base_url, api_key=config.api_key)
    schemas, fn_map, mutation_names = _chat_tools(domain)

    messages = [{"role": "system", "content": system_prompt}, *user_messages]
    pending_actions: list[dict[str, Any]] = []
    tool_trace: list[dict[str, Any]] = []
    cumulative_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    final_text = ""
    max_iterations = 6  # safety cap
    for _ in range(max_iterations):
        try:
            response = client.chat.completions.create(
                model=config.model,
                messages=messages,
                tools=schemas if schemas else None,
                timeout=config.timeout_seconds,
            )
        except openai.APIError as e:
            raise HTTPException(502, f"LLM API error: {e}")

        choice = response.choices[0]
        msg = choice.message
        if response.usage:
            cumulative_usage["prompt_tokens"] += response.usage.prompt_tokens
            cumulative_usage["completion_tokens"] += response.usage.completion_tokens
            cumulative_usage["total_tokens"] += response.usage.total_tokens

        tool_calls = msg.tool_calls or []
        if not tool_calls:
            final_text = msg.content or ""
            break

        # Append assistant message with tool calls (must precede tool messages)
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                } for tc in tool_calls
            ],
        })

        # Dispatch each tool call
        for tc in tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_trace.append({"name": name, "args": args})

            if name in mutation_names:
                # Proposal — register as pending_action, return placeholder to LLM
                action = {"type": name, "args": args, "tool_call_id": tc.id}
                pending_actions.append(action)
                tool_result = json.dumps({
                    "ok": True,
                    "status": "proposed",
                    "note": "User must confirm in UI before this executes.",
                })
            else:
                fn = fn_map.get(name)
                if not fn:
                    tool_result = json.dumps({"error": f"unknown tool {name}"})
                else:
                    try:
                        tool_result = fn(**args)
                    except Exception as e:
                        tool_result = json.dumps({"error": str(e)[:200]})
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": tool_result,
            })

        # If we collected mutation proposals, stop the loop — frontend handles them
        if pending_actions:
            # One more LLM turn to give a coherent final answer mentioning the proposals
            try:
                response = client.chat.completions.create(
                    model=config.model,
                    messages=messages,
                    timeout=config.timeout_seconds,
                )
                final_text = response.choices[0].message.content or ""
                if response.usage:
                    cumulative_usage["prompt_tokens"] += response.usage.prompt_tokens
                    cumulative_usage["completion_tokens"] += response.usage.completion_tokens
                    cumulative_usage["total_tokens"] += response.usage.total_tokens
            except openai.APIError:
                final_text = "Proposta pronta — conferma via UI."
            break

    return {
        "session_id": body.session_id or uuid.uuid4().hex[:12],
        "reply": final_text,
        "tool_trace": tool_trace,
        "pending_actions": pending_actions,
        "usage": cumulative_usage,
        "model": config.model,
    }


# ─── Chat tools (Phase 6 v5) ───────────────────────────────────────


def _chat_tools(domain: str) -> tuple[list[dict[str, Any]], dict[str, Callable], set[str]]:
    """Return (schemas, fn_map, mutation_names) for chat tool dispatch.
    fn_map contains only read-tool callables. Mutation tools are returned
    as PROPOSALS by the chat endpoint loop (no execution server-side)."""

    def list_reports(limit: int = 10) -> str:
        reports_dir = paths.reports_dir(domain)
        if not reports_dir.exists():
            return json.dumps([])
        out = []
        for f in sorted(_agent_report_files(reports_dir),
                        key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
            try:
                text = f.read_text(errors="replace")
            except Exception:
                continue
            title_m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
            verdict_m = re.search(r"##\s*Verdict[^\n]*\n([^\n]+)", text)
            out.append({
                "filename": f.name,
                "title": (title_m.group(1).strip() if title_m else f.name)[:200],
                "verdict": (verdict_m.group(1).strip() if verdict_m else "")[:200],
                "mtime": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
            })
        return json.dumps(out, ensure_ascii=False)

    def read_report(filename: str) -> str:
        if "/" in filename or ".." in filename:
            return json.dumps({"error": "invalid filename"})
        fp = paths.reports_dir(domain) / filename
        if not fp.exists():
            return json.dumps({"error": "not found"})
        try:
            content = fp.read_text(errors="replace")
        except Exception as e:
            return json.dumps({"error": str(e)})
        if len(content) > 8000:
            content = content[:8000] + "\n…[truncated]"
        return content

    def read_falsifier(filename: str) -> str:
        if "/" in filename or ".." in filename:
            return json.dumps({"error": "invalid filename"})
        ts_match = re.search(r"(\d{8}_\d{4})", filename)
        if not ts_match:
            return json.dumps({"error": "could not extract timestamp"})
        ts = ts_match.group(1)
        fp = paths.domain_data_dir(domain) / "falsifier" / f"falsifier_{ts}.json"
        if not fp.exists():
            return json.dumps({"present": False, "ts": ts, "note": "falsifier not run for this report"})
        try:
            return fp.read_text(errors="replace")
        except Exception as e:
            return json.dumps({"error": str(e)})

    def read_seed_tension(tension_id: str) -> str:
        seed = _read_json_safe(paths.seed_path(domain), {})
        for t in seed.get("tensioni", []) or []:
            if isinstance(t, dict) and t.get("id") == tension_id:
                return json.dumps(t, ensure_ascii=False)
        return json.dumps({"error": f"tension {tension_id} not found"})

    def list_cimitero(limit: int = 20) -> str:
        """Reports che il falsifier ha incoerentificato O verdict negativi."""
        reports_dir = paths.reports_dir(domain)
        falsifier_dir = paths.domain_data_dir(domain) / "falsifier"
        out = []
        if not reports_dir.exists():
            return json.dumps([])
        for f in sorted(_agent_report_files(reports_dir),
                        key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                text = f.read_text(errors="replace")
            except Exception:
                continue
            verdict_m = re.search(r"##\s*Verdict[^\n]*\n([^\n]+)", text)
            verdict = (verdict_m.group(1).strip() if verdict_m else "").upper()
            is_negative_verdict = any(k in verdict for k in
                ("REFUTE", "FALSIFY", "FALSIFIED", "NULL_RESULT", "NEGATIVE"))
            falsifier_incoherent = False
            n_flags = 0
            ts_match = re.search(r"agent_(\d{8}_\d{4})", f.name)
            if ts_match and falsifier_dir.exists():
                fp = falsifier_dir / f"falsifier_{ts_match.group(1)}.json"
                if fp.exists():
                    try:
                        rec = json.loads(fp.read_text())
                        n_flags = len(rec.get("flags") or [])
                        if rec.get("coherent") is False:
                            falsifier_incoherent = True
                    except Exception:
                        pass
            if is_negative_verdict or falsifier_incoherent or n_flags > 0:
                title_m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
                out.append({
                    "filename": f.name,
                    "title": (title_m.group(1).strip() if title_m else f.name)[:200],
                    "verdict": (verdict_m.group(1).strip() if verdict_m else "")[:200],
                    "n_flags": n_flags,
                    "incoherent": falsifier_incoherent,
                })
            if len(out) >= limit:
                break
        return json.dumps(out, ensure_ascii=False)

    fn_map = {
        "list_reports": list_reports,
        "read_report": read_report,
        "read_falsifier": read_falsifier,
        "read_seed_tension": read_seed_tension,
        "list_cimitero": list_cimitero,
    }

    schemas = [
        {"type": "function", "function": {
            "name": "list_reports",
            "description": "List recent reports of this lab domain with title + verdict + mtime.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "default": 10}},
            },
        }},
        {"type": "function", "function": {
            "name": "read_report",
            "description": "Read full markdown content of a report by filename (e.g. 'agent_20260427_2005.md').",
            "parameters": {
                "type": "object",
                "properties": {"filename": {"type": "string"}},
                "required": ["filename"],
            },
        }},
        {"type": "function", "function": {
            "name": "read_falsifier",
            "description": "Read the falsifier output (counter-pole flags) for a report. Accepts report filename or timestamp.",
            "parameters": {
                "type": "object",
                "properties": {"filename": {"type": "string"}},
                "required": ["filename"],
            },
        }},
        {"type": "function", "function": {
            "name": "read_seed_tension",
            "description": "Get full detail of a tension in the current seed by id.",
            "parameters": {
                "type": "object",
                "properties": {"tension_id": {"type": "string"}},
                "required": ["tension_id"],
            },
        }},
        {"type": "function", "function": {
            "name": "list_cimitero",
            "description": "List reports in the cimitero (falsifier-incoherent OR negative verdict OR ≥1 flag from counter-pole).",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "default": 20}},
            },
        }},
        # PROPOSAL tools — DO NOT execute, return a pending action
        {"type": "function", "function": {
            "name": "propose_inject_tension",
            "description": "PROPOSE adding a new tension to the seed. Does NOT execute — returns a proposal the user must confirm in UI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tension_id": {"type": "string", "description": "Uppercase id, e.g. 'NEW_BOUNDARY'"},
                    "claim": {"type": "string", "description": "The tension claim (one sentence)"},
                    "intensity": {"type": "number", "description": "0.0..1.0", "default": 0.5},
                },
                "required": ["tension_id", "claim"],
            },
        }},
        {"type": "function", "function": {
            "name": "propose_run_cycle",
            "description": "PROPOSE running a new cycle. Does NOT execute — returns a proposal.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction_override": {"type": "string", "description": "Optional override of the seed direction"},
                },
            },
        }},
    ]
    mutation_names = {"propose_inject_tension", "propose_run_cycle"}
    return schemas, fn_map, mutation_names


def _build_chat_system_prompt(domain: str) -> str:
    """Compose the chat agent's system prompt: domain model + lab state."""
    parts: list[str] = []
    parts.append(
        "You are the chat interface of the D-ND_LAB. The same lab whose "
        "nightly cycle produced the reports below now answers questions "
        "about its state, decisions, and findings. Be precise; cite "
        "specific reports / tensions / cimitero entries when relevant. "
        "Do not invent data. If asked to do something that requires a "
        "side-effect (inject tension, run cycle, modify seed), describe "
        "what would happen and tell the user to use the corresponding UI "
        "action — you do not have those tools in chat mode."
    )
    parts.append("")

    # Domain model + anti-patterns
    ctx_path = paths.domain_context_path(domain)
    if ctx_path.exists():
        parts.append("## DOMAIN MODEL")
        parts.append(ctx_path.read_text()[:4000])
        parts.append("")

    # Current seed
    seed = _read_json_safe(paths.seed_path(domain), {})
    parts.append(f"## CURRENT SEED — domain={domain}")
    parts.append(f"Piano: {seed.get('piano', '?')}")
    parts.append(f"Direction: {(seed.get('direzione', '') or '?')[:300]}")
    tensions = seed.get("tensioni", []) or []
    parts.append(f"Active tensions ({len(tensions)}):")
    for t in tensions[:10]:
        if isinstance(t, dict):
            tid = t.get("id", "?")
            i = t.get("intensità", t.get("intensita", "?"))
            claim = (t.get("claim", "") or "")[:200]
            parts.append(f"  [{tid}] ({i}) {claim}")
    parts.append("")

    # Last 3 reports (compressed)
    reports_dir = paths.reports_dir(domain)
    if reports_dir.exists():
        reports = sorted(
            _agent_report_files(reports_dir),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:3]
        if reports:
            parts.append("## LAST 3 REPORTS (titles + verdicts)")
            for r in reports:
                try:
                    text = r.read_text()
                    title_m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
                    verdict_m = re.search(r"##\s*Verdict[^\n]*\n([^\n]+)", text)
                    parts.append(f"- {r.name}")
                    if title_m:
                        parts.append(f"  title: {title_m.group(1).strip()[:200]}")
                    if verdict_m:
                        parts.append(f"  verdict: {verdict_m.group(1).strip()[:150]}")
                except Exception:
                    pass
            parts.append("")

    # Cimitero (last claims)
    cim = paths.cimitero_path(domain)
    if cim.exists():
        try:
            cim_text = cim.read_text()[:1500]
            parts.append("## CIMITERO (recent falsified claims)")
            parts.append(cim_text)
        except Exception:
            pass

    # SSP pipeline summary (Atto UX 7 — consapevolezza dei prodotti)
    domain_dir = paths.domain_data_dir(domain)
    scoperte_dir = domain_dir / "scoperte"
    soluzioni_dir = domain_dir / "soluzioni"
    prodotti_dir = domain_dir / "prodotti"
    n_scoperte = sum(1 for d in scoperte_dir.iterdir() if d.is_dir()) if scoperte_dir.exists() else 0
    n_soluzioni = sum(1 for d in soluzioni_dir.iterdir() if d.is_dir()) if soluzioni_dir.exists() else 0
    n_prodotti_pass = 0
    n_prodotti_fail = 0
    if prodotti_dir.exists():
        for p in prodotti_dir.iterdir():
            if not p.is_dir():
                continue
            v = p / "verification.json"
            if v.exists():
                try:
                    data = json.loads(v.read_text())
                    s = data.get("status", data.get("verdict", ""))
                    if s == "PASS":
                        n_prodotti_pass += 1
                    elif s == "FAIL":
                        n_prodotti_fail += 1
                except (json.JSONDecodeError, OSError):
                    pass
    parts.append("")
    parts.append("## SSP PIPELINE — current state")
    parts.append(f"- Scoperte (Stage 1, lab-note drafts): {n_scoperte}")
    parts.append(f"- Soluzioni con manifest (Stage 2): {n_soluzioni}")
    parts.append(f"- Prodotti maturi (Stage 4 verified): {n_prodotti_pass} PASS, {n_prodotti_fail} FAIL")
    parts.append("Pipeline auto: cycle → on_crystallize → eligibility_gate → "
                 "(if mature) application_designer → (if eligible) stage4_poc_runner → verification.json reale.")

    return "\n".join(parts)


# ─── Inject tension (gated side-effect) ─────────────────────────────


@app.post("/api/domains/{domain}/inject_tension")
async def inject_tension(domain: str, body: InjectTensionRequest, request: Request) -> dict[str, Any]:
    """Manual tension injection by the operator (after UI confirm). Adds
    to the current seed with `manuale=true` and `porta='sessione_interattiva'`
    so seed_integrator preserves it across cycles."""
    await _check_auth(request)
    _check_demo_writes(request)
    _validate_domain(domain)

    seed_path = paths.seed_path(domain)
    if not seed_path.exists():
        raise HTTPException(404, "seed not initialized — run a cycle first")
    seed = _read_json_safe(seed_path, {})
    tensions = seed.get("tensioni", []) or []

    if any(t.get("id") == body.id for t in tensions if isinstance(t, dict)):
        raise HTTPException(409, f"tension id '{body.id}' already exists")

    new = {
        "tipo": body.tipo,
        "id": body.id,
        "claim": body.claim,
        "intensita": body.intensita,
        "porta": "sessione_interattiva",
        "potenziale": "medio",
        "stato": "aperto",
        "manuale": True,
        "nota": body.nota or f"Injected via dashboard chat at {datetime.now(timezone.utc).isoformat()}",
    }
    tensions.insert(0, new)
    seed["tensioni"] = tensions
    seed_path.write_text(json.dumps(seed, indent=2, ensure_ascii=False))

    return {"ok": True, "tension": new, "n_tensions": len(tensions)}


# ─── Static frontend ────────────────────────────────────────────────


def _frontend_dir() -> Path:
    return paths._repo_root() / "dashboard"


@app.get("/", response_class=HTMLResponse)
async def root() -> Any:
    index = _frontend_dir() / "index.html"
    if index.exists():
        return FileResponse(index)
    return HTMLResponse(
        "<h1>D-ND_LAB API is running</h1>"
        "<p>Frontend not built. See <code>/api/health</code>.</p>",
        status_code=200,
    )


# Mount static AFTER the routes above so /api/* and / are not shadowed
def mount_static() -> None:
    static_dir = _frontend_dir() / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    # Also serve the dashboard directory itself for index.html
    if _frontend_dir().exists():
        app.mount("/dashboard", StaticFiles(directory=str(_frontend_dir()), html=True), name="dashboard")

mount_static()


# ─── Helpers ────────────────────────────────────────────────────────


def _validate_domain(domain: str) -> None:
    if domain not in cfg.list_domains():
        raise HTTPException(404, f"domain '{domain}' not found")


def _agent_report_files(reports_dir: Path) -> list[Path]:
    """Lista i report del agent escludendo i backup .original.md (audit trail
    pre-bias_corrector). I .original.md restano sul filesystem per ispezione
    ma non vanno mostrati nella UI come report distinti.
    """
    if not reports_dir.exists():
        return []
    return [f for f in reports_dir.glob("agent_*.md") if ".original." not in f.name]


def _read_json_safe(p: Path, default: Any) -> Any:
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return default


def _count_reports(domain: str) -> int:
    rd = paths.reports_dir(domain)
    if not rd.exists():
        return 0
    return sum(1 for _ in _agent_report_files(rd))


def _sum_costs_from_reports(domain: str) -> float:
    """Phase 6 v1: cost per cycle is in lab_data.json after the cycle.
    Phase 6 v2 will keep a per-cycle cost log for proper history."""
    return 0.0  # placeholder — real impl reads metrics from per-cycle artifacts


# ─── CLI entry point ────────────────────────────────────────────────


def main() -> None:
    """Run via: python -m core.api  or  dndlab dashboard"""
    try:
        import uvicorn
    except ImportError:
        raise SystemExit(
            "uvicorn not installed. Run: pip install 'uvicorn[standard]>=0.32'"
        )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    logger.info(
        "Starting dashboard on %s:%d (auth=%s, demo=%s)",
        settings.host, settings.port,
        "enabled" if settings.auth_enabled else "disabled",
        settings.demo_mode,
    )
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
