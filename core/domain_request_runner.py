"""Movement — domain_request_runner.

Meta-lab-only bridge from captured domain_request to an isolated
install-or-block candidate package.

It intentionally writes outside live `domains/`, under
`data/meta-lab/generated_domains/`, then validates the candidate with strict
M1-M8. This gives the cycle a concrete artifact before any install decision.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
from pathlib import Path
from typing import Any

from core import config as cfg
from core import paths
from core.lab_agent import CycleContext, register_movement

logger = logging.getLogger(__name__)


def _load_runner_module() -> Any:
    runner_path = (
        paths.domain_dir("meta-lab")
        / "tools"
        / "domain_request_runner.py"
    )
    spec = importlib.util.spec_from_file_location("domain_request_runner_tool", runner_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load domain request runner: {runner_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _active_request_path(ctx: CycleContext) -> Path | None:
    """Return the request path referenced by active seed tension/direction."""
    tensions = ctx.seed.get("tensioni") or []
    for tension in tensions:
        if not isinstance(tension, dict):
            continue
        request_path = tension.get("request_path")
        if request_path:
            path = Path(str(request_path)).resolve()
            if path.exists():
                return path
        marker = " ".join(
            str(tension.get(k, ""))
            for k in ("id", "porta", "claim")
        ).lower()
        if "domain_request" in marker:
            break

    # Fallback: only if the seed direction explicitly names domain request.
    direction = str(ctx.seed.get("direzione", "")).lower()
    if "domain request" not in direction and "domain_request" not in direction:
        return None

    req_dir = paths.domain_data_dir("meta-lab") / "domain_requests"
    candidates = sorted(
        req_dir.glob("*_request.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _append_result_to_field(ctx: CycleContext, report: dict[str, Any], report_path: str) -> None:
    """Append install-or-block result to the already-built live field.

    The movement runs after build_field and before agent. Without this append,
    the runner's artifact exists in the trace but the agent cannot see it.
    """
    field_path = paths.field_live_path(ctx.domain)
    if not field_path.exists():
        return
    validator = report.get("validator") if isinstance(report.get("validator"), dict) else {}
    summary = validator.get("summary", {}) if isinstance(validator, dict) else {}
    section = "\n".join([
        "",
        "## Domain request runner — install-or-block artifact",
        f"- status: `{report.get('status', 'UNKNOWN')}`",
        f"- slug: `{report.get('slug', '')}`",
        f"- request: `{report.get('request_path', '')}`",
        f"- candidate_dir: `{report.get('candidate_dir', '')}`",
        f"- report: `{report_path}`",
        f"- validator: `{validator.get('verdict', 'not_run')}`",
        f"- M1-M8: `{summary.get('pass', 0)} PASS / {summary.get('fail', 0)} FAIL / {summary.get('skip', 0)} SKIP`",
        "",
        "Use this artifact as the deterministic baseline. If the agent writes a richer spec, compare it against this candidate and keep the stricter install-or-block boundary.",
        "",
    ])
    with field_path.open("a", encoding="utf-8") as fh:
        fh.write(section)


def domain_request_runner(ctx: CycleContext) -> None:
    """Run install-or-block bridge for the active meta-lab domain request."""
    if ctx.domain != "meta-lab":
        ctx.metrics.setdefault("domain_request_runner", {}).update(
            status="skip_non_meta_lab",
        )
        return

    params = cfg.movement_params(ctx.config, "domain_request_runner")
    request_path = params.get("request_path") or os.environ.get("DND_DOMAIN_REQUEST_PATH")
    if request_path:
        request = Path(str(request_path)).resolve()
    else:
        request = _active_request_path(ctx)

    if request is None or not request.exists():
        ctx.metrics.setdefault("domain_request_runner", {}).update(
            status="skip_no_active_request",
        )
        logger.info("domain_request_runner: no active request")
        return

    output_root = Path(
        str(params.get("output_root") or (paths.domain_data_dir("meta-lab") / "generated_domains"))
    ).resolve()
    force = bool(params.get("force", True))

    runner = _load_runner_module()
    report = runner.run_request(request, output_root, force=force)
    reports_dir = output_root / "_reports"
    latest_report = ""
    if reports_dir.exists():
        reports = sorted(reports_dir.glob(f"{report.get('slug', '*')}_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        latest_report = str(reports[0]) if reports else ""

    status = report.get("status", "UNKNOWN")
    validator = report.get("validator") if isinstance(report.get("validator"), dict) else {}
    summary = validator.get("summary", {}) if isinstance(validator, dict) else {}
    ctx.metrics.setdefault("domain_request_runner", {}).update(
        status=status,
        request_path=str(request),
        candidate_dir=report.get("candidate_dir", ""),
        report_path=latest_report,
        validator=validator.get("verdict"),
        pass_=summary.get("pass"),
        fail=summary.get("fail"),
        skip=summary.get("skip"),
        appended_to_field=True,
    )
    _append_result_to_field(ctx, report, latest_report)
    logger.info(
        "domain_request_runner: %s for %s (validator=%s)",
        status,
        report.get("slug", request.name),
        validator.get("verdict"),
    )


register_movement("domain_request_runner", domain_request_runner)
