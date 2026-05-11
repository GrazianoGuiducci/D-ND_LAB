"""CLI entry point — `dndlab` command.

Subcommands:
  dndlab run --domain <name>          # one-shot cycle
  dndlab list                          # list available domains
  dndlab inspect --domain <name>       # validate config + show movements
  dndlab schedule --domain <name>     # cron-mode loop (Phase 3)
  dndlab seed --domain <name>          # crystallize seed only (movement 13)
  dndlab autopsy --domain <name>       # autopsy of last run (movement 0)
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click

from core import config as cfg
from core import lab_agent

# Configure logging once for CLI invocations.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)


@click.group()
@click.version_option(prog_name="dndlab")
def main() -> None:
    """D-ND_LAB — autonomous research lab CLI."""


@main.command()
@click.option("--domain", required=True, help="Domain name (must exist under domains/).")
def run(domain: str) -> None:
    """Run one cycle for the given domain."""
    try:
        ctx = lab_agent.run_cycle(domain)
    except cfg.ConfigError as e:
        click.echo(f"Config error: {e}", err=True)
        sys.exit(2)
    except Exception as e:
        click.echo(f"Cycle aborted: {type(e).__name__}: {e}", err=True)
        sys.exit(1)

    # Summary
    click.echo("")
    click.echo(f"Cycle complete: domain={ctx.domain} ts={ctx.timestamp}")
    click.echo(f"  Total: {ctx.metrics.get('cycle_total_s', '?')}s")
    click.echo(f"  Errors: {len(ctx.errors)}")
    for movement in lab_agent.MOVEMENT_ORDER:
        status = ctx.movement_status.get(movement, "—")
        click.echo(f"  {movement:25} {status}")
    if ctx.errors:
        sys.exit(1)


@main.command(name="list")
def list_domains() -> None:
    """List available domains."""
    domains = cfg.list_domains()
    if not domains:
        click.echo("No domains found under domains/.")
        return
    click.echo("Available domains:")
    for d in domains:
        try:
            config = cfg.load_domain_config(d)
            title = config.get("title", "")
            version = config.get("version", "?")
            click.echo(f"  {d:15} v{version:12} {title}")
        except cfg.ConfigError as e:
            click.echo(f"  {d:15} (invalid: {e})")


@main.command()
@click.option("--domain", required=True)
def inspect(domain: str) -> None:
    """Validate a domain config + print enabled movements."""
    try:
        config = cfg.load_domain_config(domain)
    except cfg.ConfigError as e:
        click.echo(f"Config error: {e}", err=True)
        sys.exit(2)

    click.echo(f"Domain: {domain}")
    click.echo(f"Title: {config.get('title', '')}")
    click.echo(f"Version: {config.get('version', '?')}")
    click.echo(f"Description: {config.get('description', '')}")
    click.echo("")
    click.echo("Movements:")
    for movement in lab_agent.MOVEMENT_ORDER:
        enabled = cfg.is_movement_enabled(config, movement)
        impl = lab_agent.MOVEMENTS.get(movement)
        impl_status = "implemented" if impl else "not yet implemented"
        flag = "✓" if enabled else "✗"
        click.echo(f"  {flag} {movement:25} ({impl_status})")
    click.echo("")
    click.echo("Tools:")
    for tool in config.get("tools", []):
        click.echo(f"  - {tool.get('name')} ({tool.get('type')})")


@main.command()
@click.option("--domain", required=True)
def autopsy(domain: str) -> None:
    """Run autopsy of the last cycle (movement 0 only).

    Phase 1 stub — full implementation lands when core.autopsy module is registered.
    """
    impl = lab_agent.MOVEMENTS.get("autopsy")
    if impl is None:
        click.echo("autopsy not yet implemented (Phase 1).", err=True)
        sys.exit(2)
    # Phase 1: build a minimal context, dispatch only autopsy
    click.echo("autopsy — placeholder, will dispatch only this movement.")


@main.command(name="dry-run")
@click.option("--domain", required=True)
def dry_run(domain: str) -> None:
    """Run a cycle with the LLM agent disabled. Useful for testing config
    changes without spending API credits."""
    # Force agent disabled in this run
    try:
        config = cfg.load_domain_config(domain)
    except cfg.ConfigError as e:
        click.echo(f"Config error: {e}", err=True)
        sys.exit(2)

    movements = config.setdefault("movements", {})
    movements["agent"] = {"enabled": False, "params": {"comment": "disabled by dry-run"}}

    # Monkey-patch loader for this run only
    original = cfg.load_domain_config
    cfg.load_domain_config = lambda d: config  # type: ignore
    try:
        ctx = lab_agent.run_cycle(domain)
    finally:
        cfg.load_domain_config = original

    click.echo(f"\nDry-run complete: {ctx.timestamp}")
    click.echo(f"  Total: {ctx.metrics.get('cycle_total_s', '?')}s")
    click.echo(f"  Errors: {len(ctx.errors)}")
    for movement in lab_agent.MOVEMENT_ORDER:
        status = ctx.movement_status.get(movement, "—")
        click.echo(f"  {movement:25} {status}")
    if ctx.errors:
        sys.exit(1)


@main.command()
@click.option("--host", default=None, help="Bind host (default: 0.0.0.0). Override via DASHBOARD_HOST env.")
@click.option("--port", default=None, type=int, help="Port (default: 5000). Override via DASHBOARD_PORT env.")
def dashboard(host: str | None, port: int | None) -> None:
    """Run the web dashboard (FastAPI + single-page UI).

    Browser at http://localhost:5000 once started. Auth is disabled by
    default (set DASHBOARD_AUTH=enabled for protected mode). Required
    deps: fastapi, uvicorn — install with `pip install fastapi 'uvicorn[standard]'`.
    """
    if host:
        import os as _os
        _os.environ["DASHBOARD_HOST"] = host
    if port:
        import os as _os
        _os.environ["DASHBOARD_PORT"] = str(port)
    try:
        from core import api
        api.main()
    except SystemExit as e:
        click.echo(str(e), err=True)
        sys.exit(2)


@main.command()
@click.option("--domain", required=True, help="Domain to benchmark.")
@click.option("--models", required=True,
              help="Comma-separated list of model ids. Example: "
                   "anthropic/claude-opus-4.7,deepseek/deepseek-v4-pro,xiaomi/mimo-v2.5-pro")
def benchmark(domain: str, models: str) -> None:
    """Run the same cycle across N models. Produce cost/quality table.

    Phase 5+ feature — skeleton only. See core/benchmark.py for the contract.
    For now, set LLM_MODEL in env and run `dndlab run --domain X` per model.
    """
    from core import benchmark as bench
    model_list = [m.strip() for m in models.split(",") if m.strip()]
    if not model_list:
        click.echo("No models provided.", err=True)
        sys.exit(2)
    try:
        bench.run_benchmark(domain, model_list)
    except NotImplementedError as e:
        click.echo(f"benchmark not yet implemented:\n  {e}", err=True)
        sys.exit(2)


@main.command()
@click.option("--domain", required=True)
@click.option("--n", default=10, help="Number of recent cycles to show.")
def status(domain: str, n: int) -> None:
    """Show recent cycle reports + cumulative cost (from trajectory_log + reports)."""
    import json as _json
    from core import paths

    try:
        cfg.load_domain_config(domain)
    except cfg.ConfigError as e:
        click.echo(f"Config error: {e}", err=True)
        sys.exit(2)

    reports_dir = paths.reports_dir(domain)
    log_path = paths.domain_data_dir(domain) / "trajectory_log.jsonl"
    seed_path = paths.seed_path(domain)

    # Latest reports
    reports = []
    if reports_dir.exists():
        reports = sorted(
            reports_dir.glob("agent_*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:n]

    # Trajectory decisions (last n)
    decisions: list[dict[str, Any]] = []
    if log_path.exists():
        for line in log_path.read_text().strip().split("\n")[-n:]:
            try:
                decisions.append(_json.loads(line))
            except _json.JSONDecodeError:
                pass

    # Current seed snapshot
    piano = "?"
    direzione = "?"
    n_tensions = 0
    if seed_path.exists():
        try:
            s = _json.loads(seed_path.read_text())
            piano = s.get("piano", "?")
            direzione = (s.get("direzione") or "?")[:80]
            n_tensions = len(s.get("tensioni", []))
        except _json.JSONDecodeError:
            pass

    click.echo(f"Domain: {domain}")
    click.echo(f"Current seed: piano={piano}, tensions={n_tensions}")
    click.echo(f"Direction: {direzione}")
    click.echo("")
    click.echo(f"Recent reports ({len(reports)}):")
    for rp in reports:
        click.echo(f"  {rp.name}  ({rp.stat().st_size} bytes)")
    click.echo("")
    click.echo(f"Recent trajectory decisions ({len(decisions)}):")
    for d in decisions:
        ts = d.get("ts", "?")[:19]
        dec = d.get("decision", "?")
        click.echo(f"  {ts}  {dec}")


@main.group()
def contributions() -> None:
    """Review visitor contribution preports locally.

    This is intentionally CLI-only while dashboard auth is not implemented:
    public demo can collect sanitized preports, but review/promotion stays on
    the operator machine.
    """


@contributions.command(name="list")
@click.option("--domain", required=True, help="Domain name.")
@click.option("--status", "status_filter", default=None,
              help="Filter by effective status/verdict, e.g. preported, rejected, ACCEPT_CANDIDATE.")
@click.option("--limit", default=20, show_default=True, help="Max rows to show.")
def contributions_list(domain: str, status_filter: str | None, limit: int) -> None:
    """List recent contribution preports."""
    _validate_cli_domain(domain)
    rows = _load_contribution_rows(domain)
    if status_filter:
        needle = status_filter.lower()
        rows = [
            r for r in rows
            if needle in str(r.get("effective_status", "")).lower()
            or needle in str(r.get("verdict", "")).lower()
        ]
    rows = rows[:limit]
    if not rows:
        click.echo("No contribution preports found.")
        return
    click.echo(f"Contribution preports: domain={domain} rows={len(rows)}")
    for r in rows:
        click.echo(
            f"{r['created_at'][:19]}  {r['id']:<32} "
            f"{r['effective_status']:<20} {r['verdict']:<20} "
            f"S={r['signal_score']} N={r['noise_score']}  "
            f"{r['summary']}"
        )


@contributions.command(name="show")
@click.option("--domain", required=True, help="Domain name.")
@click.argument("contribution_id")
def contributions_show(domain: str, contribution_id: str) -> None:
    """Print one contribution preport Markdown."""
    _validate_cli_domain(domain)
    md_path = _contributions_dir(domain) / "preports" / f"{contribution_id}.md"
    if not md_path.exists():
        raise click.ClickException(f"preport not found: {contribution_id}")
    click.echo(md_path.read_text(encoding="utf-8", errors="replace"))
    events = _load_review_events(domain).get(contribution_id, [])
    if events:
        click.echo("\n## Review Events")
        for event in events:
            click.echo(
                f"- {event.get('created_at', '?')}: {event.get('decision', '?')}"
                f" — {event.get('note', '')}"
            )


@contributions.command(name="mark")
@click.option("--domain", required=True, help="Domain name.")
@click.option("--decision", required=True,
              type=click.Choice(["accepted", "rejected", "needs_clarification", "archived"]),
              help="Operator review decision.")
@click.option("--note", default="", help="Short operator note.")
@click.argument("contribution_id")
def contributions_mark(domain: str, decision: str, note: str, contribution_id: str) -> None:
    """Append an operator review event for a contribution."""
    _validate_cli_domain(domain)
    json_path = _contributions_dir(domain) / "preports" / f"{contribution_id}.json"
    if not json_path.exists():
        raise click.ClickException(f"preport not found: {contribution_id}")
    event = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "id": contribution_id,
        "decision": decision,
        "note": note.strip(),
    }
    events_path = _contributions_dir(domain) / "review_events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    click.echo(f"review event appended: {contribution_id} -> {decision}")


def _validate_cli_domain(domain: str) -> None:
    try:
        cfg.load_domain_config(domain)
    except cfg.ConfigError as e:
        raise click.ClickException(f"Config error: {e}") from e


def _contributions_dir(domain: str) -> Path:
    from core import paths
    return paths.domain_data_dir(domain) / "contributions"


def _load_contribution_rows(domain: str) -> list[dict[str, Any]]:
    base = _contributions_dir(domain)
    preports = base / "preports"
    if not preports.exists():
        return []
    review_events = _load_review_events(domain)
    rows: list[dict[str, Any]] = []
    for fp in sorted(preports.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        record = data.get("record") or {}
        preport = data.get("preport") or {}
        contribution_id = record.get("id") or fp.stem
        events = review_events.get(contribution_id, [])
        effective_status = (
            events[-1].get("decision")
            if events else record.get("status") or preport.get("status") or "unknown"
        )
        message = str(record.get("message") or "").replace("\n", " ")
        rows.append({
            "id": contribution_id,
            "created_at": record.get("created_at") or preport.get("created_at") or "?",
            "effective_status": effective_status,
            "verdict": preport.get("verdict") or "?",
            "signal_score": preport.get("signal_score") if preport.get("signal_score") is not None else "-",
            "noise_score": preport.get("noise_score") if preport.get("noise_score") is not None else "-",
            "summary": message[:90],
        })
    return rows


def _load_review_events(domain: str) -> dict[str, list[dict[str, Any]]]:
    events_path = _contributions_dir(domain) / "review_events.jsonl"
    out: dict[str, list[dict[str, Any]]] = {}
    if not events_path.exists():
        return out
    for line in events_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        contribution_id = event.get("id")
        if contribution_id:
            out.setdefault(contribution_id, []).append(event)
    return out


if __name__ == "__main__":
    main()
