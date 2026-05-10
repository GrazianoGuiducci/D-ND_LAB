"""Domain config loading + validation.

Each domain ships a config.json under domains/<name>/ that wires the
13 movements, tools, and metadata. This module loads it and validates
against config.schema.json.

The loader is strict: a missing required field fails loud, not silent.
A domain without a valid config will not run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

from core import paths


class ConfigError(Exception):
    """Raised when a domain config is missing, invalid, or inconsistent."""


def load_domain_config(domain: str) -> dict[str, Any]:
    """Load and validate the config.json for a domain.

    Raises:
        ConfigError: missing file, invalid JSON, schema violation, or
                     mismatch between config['domain'] and the directory name.

    Returns:
        Validated config dict.
    """
    config_path = paths.domain_config_path(domain)
    if not config_path.exists():
        raise ConfigError(
            f"Domain '{domain}' has no config.json at {config_path}. "
            f"Either the domain doesn't exist or the directory is incomplete."
        )

    try:
        config = json.loads(config_path.read_text())
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in {config_path}: {e}") from e

    schema_path = paths.schema_path()
    if schema_path.exists():
        try:
            schema = json.loads(schema_path.read_text())
            jsonschema.validate(instance=config, schema=schema)
        except jsonschema.ValidationError as e:
            raise ConfigError(
                f"Config {config_path} fails schema validation: {e.message} "
                f"(at {'.'.join(str(p) for p in e.absolute_path)})"
            ) from e

    if config.get("domain") != domain:
        raise ConfigError(
            f"Config domain mismatch: file says '{config.get('domain')}', "
            f"directory is '{domain}'. They must match."
        )

    return config


def list_domains() -> list[str]:
    """Discover available domains by scanning domains/ directory.

    Returns the list of directory names that contain a config.json.
    Does not validate the configs — call load_domain_config to do that.

    Skip rules (2026-05-05):
    - Directory che iniziano con `_` sono escluse: convenzione per
      strumenti che vivono in `domains/` ma non sono lab di dominio
      (es. `_meta-prototyper/`, `_archive/`).
    """
    repo_root = paths._repo_root()
    domains_dir = repo_root / "domains"
    if not domains_dir.exists():
        return []
    return sorted(
        d.name for d in domains_dir.iterdir()
        if d.is_dir()
        and not d.name.startswith("_")
        and (d / "config.json").exists()
    )


def is_movement_enabled(config: dict[str, Any], movement: str) -> bool:
    """Check if a movement is enabled in the domain config.

    A movement is enabled by default if not mentioned in config.
    To disable, the domain must explicitly set enabled=false.
    """
    movements = config.get("movements", {})
    spec = movements.get(movement, {})
    return spec.get("enabled", True)


def movement_params(config: dict[str, Any], movement: str) -> dict[str, Any]:
    """Get the params dict for a movement (empty dict if none specified)."""
    movements = config.get("movements", {})
    spec = movements.get(movement, {})
    return spec.get("params", {})


def domain_path_or_none(config: dict[str, Any], key: str) -> Path | None:
    """Resolve a path declared in config['model'][key] relative to domain dir.

    Returns None if the key is not set in the config.
    Raises ConfigError if the path is set but doesn't exist.
    """
    model = config.get("model", {})
    rel = model.get(key)
    if not rel:
        return None
    domain = config["domain"]
    full = paths.domain_dir(domain) / rel
    if not full.exists():
        raise ConfigError(
            f"Domain '{domain}' config references {key}={rel} but the file "
            f"doesn't exist at {full}."
        )
    return full
