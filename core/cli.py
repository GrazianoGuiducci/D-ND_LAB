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


if __name__ == "__main__":
    main()
