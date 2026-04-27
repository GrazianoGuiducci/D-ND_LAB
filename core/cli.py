"""CLI entry point — `dndlab` command.

Phase 0: skeleton only. Real implementation in Phase 1.

Subcommands (target):
  dndlab run --domain <name>          # one-shot cycle
  dndlab schedule --domain <name>     # cron-mode (loop with sleep)
  dndlab list                          # list available domains
  dndlab inspect --domain <name>       # validate config + show movements
  dndlab seed --domain <name>          # crystallize seed only (movement 13)
  dndlab autopsy --domain <name>       # autopsy of last run (movement 0)
"""

from __future__ import annotations

import sys

import click


@click.group()
@click.version_option(prog_name="dndlab")
def main() -> None:
    """D-ND_LAB — autonomous research lab CLI."""


@main.command()
@click.option("--domain", required=True, help="Domain name (must exist under domains/).")
@click.option("--config", default=None, help="Override config path. Defaults to domains/<domain>/config.json.")
def run(domain: str, config: str | None) -> None:
    """Run one cycle for the given domain."""
    click.echo(f"[Phase 0 stub] would run domain={domain} config={config}")
    click.echo("Implementation lands in Phase 1.")
    sys.exit(0)


@main.command(name="list")
def list_domains() -> None:
    """List available domains."""
    click.echo("[Phase 0 stub] would scan domains/ for valid configs.")
    sys.exit(0)


@main.command()
@click.option("--domain", required=True)
def inspect(domain: str) -> None:
    """Validate a domain config + print enabled movements."""
    click.echo(f"[Phase 0 stub] would validate domains/{domain}/config.json against schema.")
    sys.exit(0)


if __name__ == "__main__":
    main()
