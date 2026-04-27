"""Lightweight movements that are mostly file/IO operations.

Movements implemented here:
  3. validate_seed       — integrity check + restore from backup if corrupted
  4. verify_assertions   — run domain-declared assertions, mark PASS/FAIL
  6. build_lab_data      — snapshot piano + tensions + last report
  8. sync                — propagate state (filesystem mirror / external endpoints)
  9. verify_endpoints    — health-check downstream consumers
 15. notify              — webhook to operator

These are short, file-bound. Each registers itself.

Movement 2 (agent) is special — it calls the LLM. It lives in core/agent.py
and gets a real implementation in Phase 2 (when llm_adapter is wired).
For Phase 1 it remains a stub that raises NotImplementedError; the
orchestrator catches and skips with "not yet implemented".
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import shutil
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import config as cfg
from core import paths
from core.lab_agent import CycleContext, register_movement

logger = logging.getLogger(__name__)


# ─── 3. validate_seed ──────────────────────────────────────────────


def validate_seed(ctx: CycleContext) -> None:
    """Check seed integrity. If corrupted, restore from backup."""
    seed_path = paths.seed_path(ctx.domain)
    backup_path = paths.seed_backup_path(ctx.domain)

    if not seed_path.exists():
        ctx.metrics.setdefault("validate_seed", {}).update(status="absent")
        logger.info("validate_seed: no seed.json yet (first cycle)")
        return

    try:
        seed = json.loads(seed_path.read_text())
        if not isinstance(seed.get("tensioni"), list):
            raise ValueError("'tensioni' is not a list")
        if "piano" not in seed:
            raise ValueError("'piano' missing")
        # Re-write canonically to fix any formatting drift (idempotent)
        seed_path.write_text(json.dumps(seed, indent=2, ensure_ascii=False))
        ctx.seed = seed
        ctx.metrics.setdefault("validate_seed", {}).update(
            status="ok",
            piano=seed.get("piano"),
            n_tensions=len(seed["tensioni"]),
        )
    except Exception as e:
        logger.warning("seed corrupted: %s", e)
        if backup_path.exists():
            try:
                shutil.copy(backup_path, seed_path)
                ctx.seed = json.loads(seed_path.read_text())
                ctx.metrics.setdefault("validate_seed", {}).update(
                    status="restored_from_backup",
                    error=str(e),
                )
                logger.info("validate_seed: restored from backup")
            except Exception as e2:
                ctx.metrics.setdefault("validate_seed", {}).update(
                    status="restore_failed",
                    error=str(e2),
                )
        else:
            ctx.metrics.setdefault("validate_seed", {}).update(
                status="corrupted_no_backup",
                error=str(e),
            )


register_movement("validate_seed", validate_seed)


# ─── 4. verify_assertions ──────────────────────────────────────────


def verify_assertions(ctx: CycleContext) -> None:
    """Run domain-declared assertions. Each assertion is a callable in a
    Python module; the module is declared in params.assertions_module.

    Module contract: exposes ASSERTIONS = [(id, callable, claim), ...]
    Each callable returns one of: 'PASS', 'FAIL', 'SKIP'.

    Without a module, the movement marks 'no_module' and returns OK.
    """
    params = cfg.movement_params(ctx.config, "verify_assertions")
    module_name = params.get("assertions_module")
    if not module_name:
        ctx.metrics.setdefault("verify_assertions", {}).update(status="no_module")
        return

    try:
        mod = importlib.import_module(module_name)
    except ImportError as e:
        ctx.metrics.setdefault("verify_assertions", {}).update(
            status="import_failed", error=str(e)
        )
        logger.warning("verify_assertions: %s not importable: %s", module_name, e)
        return

    assertions = getattr(mod, "ASSERTIONS", [])
    results: list[dict[str, Any]] = []
    for entry in assertions:
        try:
            aid, fn, claim = entry
        except (ValueError, TypeError):
            continue
        try:
            status = fn(ctx)
        except Exception as e:
            status = "FAIL"
            logger.warning("assertion %s raised: %s", aid, e)
        results.append({"id": aid, "status": status, "claim": claim})

    p = sum(1 for r in results if r["status"] == "PASS")
    f = sum(1 for r in results if r["status"] == "FAIL")
    s = sum(1 for r in results if r["status"] == "SKIP")
    ctx.metrics.setdefault("verify_assertions", {}).update(
        total=len(results), pass_=p, fail=f, skip=s,
    )
    logger.info(
        "verify_assertions: %d PASS, %d FAIL, %d SKIP / %d total",
        p, f, s, len(results),
    )

    # Persist results so build_lab_data can include them
    ctx.metrics["verify_assertions"]["results"] = results


register_movement("verify_assertions", verify_assertions)


# ─── 6. build_lab_data ─────────────────────────────────────────────


def build_lab_data(ctx: CycleContext) -> None:
    """Snapshot piano + tensions + last report into <data>/<domain>/lab_data.json."""
    reports_dir = paths.reports_dir(ctx.domain)
    last_report_file = ""
    last_report_content = ""
    if reports_dir.exists():
        reports = sorted(
            reports_dir.glob("agent_*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if reports:
            last_report_file = reports[0].name
            try:
                last_report_content = reports[0].read_text()[:3000]
            except Exception:
                pass

    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "domain": ctx.domain,
        "piano": ctx.seed.get("piano", 0),
        "direzione": ctx.seed.get("direzione", ""),
        "cicli_totali": _count_reports(reports_dir),
        "tensioni": [
            {
                "id": t.get("id", "?"),
                "claim": (t.get("claim", "") or "")[:200],
                "potenziale": t.get("potenziale", ""),
                "stato": t.get("stato", ""),
                "porta": t.get("porta", ""),
            }
            for t in ctx.seed.get("tensioni", [])[:15]
            if isinstance(t, dict)
        ],
        "ultimo_report": {"file": last_report_file, "content": last_report_content},
        "verifica": ctx.metrics.get("verify_assertions", {}),
    }

    out_path = paths.lab_data_path(ctx.domain)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    ctx.metrics.setdefault("build_lab_data", {}).update(
        path=str(out_path),
        n_tensioni=len(data["tensioni"]),
    )
    logger.info("build_lab_data: written → %s", out_path)


def _count_reports(reports_dir: Path) -> int:
    if not reports_dir.exists():
        return 0
    return sum(1 for _ in reports_dir.glob("agent_*.md"))


register_movement("build_lab_data", build_lab_data)


# ─── 8. sync ────────────────────────────────────────────────────────


def sync(ctx: CycleContext) -> None:
    """Propagate state to declared targets (filesystem mirror, etc.).

    Targets declared in params.targets:
      [
        {"type": "copy", "src": "lab_data.json", "dst": "/path/to/lab_data.json"},
        {"type": "http_post", "url": "...", "headers": {...}, "body_file": "..."}
      ]
    """
    params = cfg.movement_params(ctx.config, "sync")
    targets = params.get("targets", [])
    if not targets:
        ctx.metrics.setdefault("sync", {}).update(status="no_targets")
        return

    results: list[dict[str, Any]] = []
    for target in targets:
        ttype = target.get("type")
        try:
            if ttype == "copy":
                src = paths.domain_data_dir(ctx.domain) / target["src"]
                dst = Path(target["dst"])
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                results.append({"type": "copy", "ok": True, "dst": str(dst)})
            elif ttype == "http_post":
                # Phase 1: minimal — POST file content to URL
                src = paths.domain_data_dir(ctx.domain) / target["body_file"]
                req = urllib.request.Request(
                    target["url"],
                    data=src.read_bytes(),
                    headers=target.get("headers", {}),
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as r:
                    results.append({"type": "http_post", "ok": True, "http": r.status})
            else:
                results.append({"type": ttype, "ok": False, "error": "unknown type"})
        except Exception as e:
            results.append({"type": ttype, "ok": False, "error": str(e)})

    ctx.metrics.setdefault("sync", {}).update(targets=len(targets), results=results)
    logger.info("sync: %d targets, %d ok",
                len(results), sum(1 for r in results if r.get("ok")))


register_movement("sync", sync)


# ─── 9. verify_endpoints ────────────────────────────────────────────


def verify_endpoints(ctx: CycleContext) -> None:
    """GET each declared endpoint, report status. params.endpoints = [{"url", "expect_status"}]."""
    params = cfg.movement_params(ctx.config, "verify_endpoints")
    endpoints = params.get("endpoints", [])
    if not endpoints:
        ctx.metrics.setdefault("verify_endpoints", {}).update(status="no_endpoints")
        return

    results = []
    for ep in endpoints:
        url = ep.get("url")
        expect = ep.get("expect_status", 200)
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                ok = r.status == expect
                results.append({"url": url, "status": r.status, "ok": ok})
        except urllib.error.URLError as e:
            results.append({"url": url, "ok": False, "error": str(e)})
        except Exception as e:
            results.append({"url": url, "ok": False, "error": str(e)})
    ctx.metrics.setdefault("verify_endpoints", {}).update(
        results=results,
        n_ok=sum(1 for r in results if r.get("ok")),
        n_total=len(results),
    )


register_movement("verify_endpoints", verify_endpoints)


# ─── 15. notify ─────────────────────────────────────────────────────


def notify(ctx: CycleContext) -> None:
    """POST a summary message to NOTIFY_WEBHOOK_URL (if set)."""
    webhook = os.environ.get("NOTIFY_WEBHOOK_URL", "")
    if not webhook:
        ctx.metrics.setdefault("notify", {}).update(status="no_webhook")
        return

    has_errors = bool(ctx.errors)
    icon = "⚠" if has_errors else "✓"
    msg = (
        f"{icon} D-ND_LAB cycle {ctx.domain} piano={ctx.seed.get('piano', '?')} "
        f"errors={len(ctx.errors)}"
    )
    if has_errors:
        msg += " | " + "; ".join(ctx.errors[:3])

    try:
        req = urllib.request.Request(
            webhook,
            data=json.dumps({"message": msg}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            ctx.metrics.setdefault("notify", {}).update(http=r.status, sent=True)
    except Exception as e:
        ctx.metrics.setdefault("notify", {}).update(sent=False, error=str(e))


register_movement("notify", notify)
