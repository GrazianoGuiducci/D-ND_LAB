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
from pathlib import Path
from typing import Any

try:
    from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
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
    context_node: dict[str, Any] | None = None  # selected graph node, if any


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
    for f in sorted(reports_dir.glob("agent_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
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


@app.get("/api/domains/{domain}/context_intro")
async def get_context_intro(domain: str, request: Request) -> dict[str, Any]:
    """Estrae la prima sezione 'identity' del context.md del dominio.
    Usato dalla sezione descrittiva top della dashboard ('cosa accade qui').
    Heuristic: cerca '## Identity' / '## Chi sei' / '## Identita'; se assente,
    prende il primo paragrafo dopo il titolo H1 (non blockquote)."""
    await _check_auth(request)
    _validate_domain(domain)
    ctx_path = paths.domain_context_path(domain)
    if not ctx_path.exists():
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
    for f in sorted(reports_dir.glob("agent_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
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
    """Single-shot chat. The agent has read-only context awareness:
    domain context.md + current seed + last reports + cimitero. Tools
    that mutate state are NOT called from here — they go through their
    own gated endpoints (e.g. /inject_tension) after UI confirmation.

    Phase 6 v1: single-shot non-streaming. Phase 6 v2 may add SSE for streaming.
    """
    await _check_auth(request)
    _check_demo_writes(request)
    _validate_domain(domain)

    from core import llm_adapter

    # Build system prompt: domain context + lab state snapshot
    system_prompt = _build_chat_system_prompt(domain)

    # If the user selected a graph node, inject it as additional context
    # so the agent's reply is anchored to that specific point.
    if body.context_node:
        node = body.context_node
        node_md = (
            f"\n\n## CURRENT FOCUS — graph node selected by the user\n"
            f"- id: `{node.get('id', '?')}`\n"
            f"- type: `{node.get('type', '?')}`\n"
            f"- label: {node.get('label', '?')}\n"
        )
        # Include any extra fields present (claim, verdict, intensity, ...)
        for key in ("claim", "verdict", "intensity", "stato", "porta", "title"):
            if node.get(key):
                node_md += f"- {key}: {str(node[key])[:300]}\n"
        node_md += (
            "\nThe user's question is most likely about this node. Answer in "
            "context of it; cite the corresponding report or seed entry if "
            "relevant; if the question is broader, expand from there.\n"
        )
        system_prompt += node_md

    # Map ChatMessage list to OpenAI message format
    user_messages = [{"role": m.role, "content": m.content} for m in body.messages]

    # Single-shot call (no tools — Phase 6 v1)
    config = llm_adapter.AdapterConfig.from_env()
    config.max_turns = 1  # chat is single-shot per request
    config.timeout_seconds = 120
    try:
        config.validate()
    except ValueError as e:
        raise HTTPException(503, f"LLM not configured: {e}")

    try:
        import openai
    except ImportError:
        raise HTTPException(503, "openai package not installed")

    client = openai.OpenAI(base_url=config.base_url, api_key=config.api_key)
    messages = [{"role": "system", "content": system_prompt}, *user_messages]

    try:
        response = client.chat.completions.create(
            model=config.model,
            messages=messages,
            timeout=config.timeout_seconds,
        )
    except openai.APIError as e:
        raise HTTPException(502, f"LLM API error: {e}")

    msg = response.choices[0].message
    usage = response.usage

    return {
        "session_id": body.session_id or uuid.uuid4().hex[:12],
        "reply": msg.content or "",
        "usage": {
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
            "total_tokens": usage.total_tokens if usage else 0,
        },
        "model": config.model,
    }


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
            reports_dir.glob("agent_*.md"),
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
    return sum(1 for _ in rd.glob("agent_*.md"))


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
