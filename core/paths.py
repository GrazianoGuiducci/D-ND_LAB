"""Path resolution — central module for all filesystem locations.

The original lab hardcoded /opt/MM_D-ND, /opt/THIA, etc. This module
resolves paths from environment variables and the active domain config,
so the same code runs on:

  - VPS host filesystem (current production)
  - Docker container (/data + /app)
  - Developer laptop (any directory)

Resolution order:
  1. Explicit override (function argument)
  2. Environment variable
  3. Default relative to LAB_DATA_DIR (or CWD if unset)

Domains can register their own subdirectories via the config; this module
exposes the canonical roots.
"""

from __future__ import annotations

import os
from pathlib import Path


def _data_dir() -> Path:
    """Lab data root. Inside Docker: /data. Standalone: $LAB_DATA_DIR or ./data."""
    return Path(os.environ.get("LAB_DATA_DIR", "./data")).resolve()


def domain_data_dir(domain: str) -> Path:
    """Per-domain data subdir: <data>/<domain>/."""
    return _data_dir() / domain


def reports_dir(domain: str) -> Path:
    """Where agent reports are written: <data>/<domain>/reports/."""
    return domain_data_dir(domain) / "reports"


def seed_path(domain: str) -> Path:
    """Active seed for the domain: <data>/<domain>/seed.json."""
    return domain_data_dir(domain) / "seed.json"


def seed_backup_path(domain: str) -> Path:
    """Pre-cycle seed backup: <data>/<domain>/seed_backup_pre_run.json."""
    return domain_data_dir(domain) / "seed_backup_pre_run.json"


def health_path(domain: str) -> Path:
    """Lab health snapshot from autopsy: <data>/<domain>/lab_health.json."""
    return domain_data_dir(domain) / "lab_health.json"


def field_live_path(domain: str) -> Path:
    """Live agent field (built per cycle): <data>/<domain>/agent_field_live.md."""
    return domain_data_dir(domain) / "agent_field_live.md"


def lab_data_path(domain: str) -> Path:
    """Snapshot for downstream consumers: <data>/<domain>/lab_data.json."""
    return domain_data_dir(domain) / "lab_data.json"


def lab_graph_path(domain: str) -> Path:
    """Knowledge graph: <data>/<domain>/lab_graph.json."""
    return domain_data_dir(domain) / "lab_graph.json"


def cimitero_path(domain: str) -> Path:
    """Falsified claims memory: <data>/<domain>/cimitero.md."""
    return domain_data_dir(domain) / "cimitero.md"


def domain_dir(domain: str) -> Path:
    """Domain config + tools + context: <repo_root>/domains/<domain>/."""
    return _repo_root() / "domains" / domain


def domain_config_path(domain: str) -> Path:
    """The domain's wiring file: <repo_root>/domains/<domain>/config.json."""
    return domain_dir(domain) / "config.json"


def domain_context_path(domain: str) -> Path:
    """Domain content (axioms, condensate, anti-patterns)."""
    return domain_dir(domain) / "context.md"


def domain_tools_dir(domain: str) -> Path:
    """Domain-specific tools: <repo_root>/domains/<domain>/tools/."""
    return domain_dir(domain) / "tools"


def core_template_path() -> Path:
    """Universal context template (placeholders populated per domain)."""
    return _repo_root() / "core" / "lab_context_template.md"


def schema_path() -> Path:
    """JSON Schema for domain configs."""
    return _repo_root() / "config.schema.json"


def _repo_root() -> Path:
    """Repository root. Resolved by walking up from this file."""
    return Path(__file__).resolve().parent.parent


def ensure_domain_dirs(domain: str) -> None:
    """Create the per-domain data subdirs if they don't exist.

    Idempotent. Safe to call at every cycle start.
    """
    for p in (domain_data_dir(domain), reports_dir(domain)):
        p.mkdir(parents=True, exist_ok=True)
