"""Movement 5 — structural_check.

The system observes itself. Scans Python files for structural anti-patterns
(numbers binding concepts, thresholds on qualitative states, weighted
aggregations of structural qualities) and injects META tensions into the
seed. The next cycle's agent reads the META tension and decides how to
resolve it where it passes — the system evolves organically.

Design principles preserved from the original:
  - Does NOT correct — surfaces. Correction is the agent's responsibility
    in the next cycle.
  - Patterns are extensible: domains can declare additional patterns via
    movements.structural_check.params.patterns_module
  - Severity-aware: 'alto' patterns flag intensity 0.85, 'medio' 0.65
  - Idempotent: removes previous STRUCTURAL_CHECK_* tensions before
    injecting the new one (only the most recent survives)

Universal patterns (kept in core):
  These are D-ND structural anti-patterns: any domain that models the
  system through dipoles, intensities, qualitative states, falls into
  the same trap if numbers are used as proxies for structure. Therefore
  the patterns belong in core, not in physics-specific.

Domain-specific patterns:
  A domain can declare patterns_module to add domain-specific anti-patterns
  (e.g. physics-only formula misuses, editorial-only voice violations).
  Phase 1: only universal patterns. Domain extensions are Phase 4+.
"""

from __future__ import annotations

import importlib
import json
import logging
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import config as cfg
from core import paths
from core.lab_agent import CycleContext, register_movement

logger = logging.getLogger(__name__)


# Universal D-ND structural anti-patterns. Any domain that uses intensity /
# maturity / confidence as concept-state risks these.
UNIVERSAL_PATTERNS: list[dict[str, Any]] = [
    {
        "id": "NUM_THRESHOLD_CONCEPT",
        "name": "Numeric threshold on conceptual state",
        "description": (
            "A float used as threshold to decide on a state that should be qualitative"
        ),
        "regex": r"if\s+(?:intensit[aà]|intensity|maturity|confidence|credibility)\s*[<>=]+\s*0\.\d",
        "severity": "alto",
    },
    {
        "id": "INTENSITY_FORMULA",
        "name": "Intensity computed by formula",
        "description": (
            "Intensity generated from a numeric formula instead of derived from structure"
        ),
        "regex": r"['\"]intensit[aà]['\"]:\s*(?:min|max)\s*\(",
        "severity": "alto",
    },
    {
        "id": "MATURITY_PROGRESS",
        "name": "Maturity as percentage progress",
        "description": (
            "Distance from a fixed point compressed in 0-1 scale as completion percentage"
        ),
        "regex": r"maturity\s*[<>=]+\s*0\.(?:9|8|7|5)",
        "severity": "alto",
    },
    {
        "id": "WEIGHTED_CONCEPT",
        "name": "Weighted aggregation of concepts",
        "description": (
            "Mean or weighted sum of qualities that do not aggregate numerically"
        ),
        "regex": r"(?:np\.mean|np\.average|sum)\s*\(\s*(?:\[.*intensit|.*maturit)",
        "severity": "medio",
    },
    {
        "id": "SCORE_FROM_RANK",
        "name": "Numeric score from conceptual ranking",
        "description": (
            "Score computed as linear combination of rank and intensity"
        ),
        "regex": r"score\s*=.*(?:rank|priority)\s*\*\s*\d+\s*\+\s*intensit",
        "severity": "medio",
    },
    {
        "id": "FLOAT_TO_CATEGORY",
        "name": "Float rebinned into category by threshold",
        "description": (
            "Number computed and then reconverted to category (HIGH/MEDIUM/LOW) "
            "via arbitrary thresholds"
        ),
        "regex": r"if\s+\w+\s*>\s*0\.\d+\s*:.*(?:ALTA|HIGH|alto)",
        "severity": "basso",
    },
]


def structural_check(ctx: CycleContext) -> None:
    """Run the scan + optional META tension injection.

    Mutates: ctx.metrics["structural_check"] (findings_count, by_severity)
    Side effect: if inject_meta_tensions=true in params, modifies seed.json
    """
    params = cfg.movement_params(ctx.config, "structural_check")
    inject = bool(params.get("inject_meta_tensions", True))

    patterns = list(UNIVERSAL_PATTERNS)
    domain_patterns_module = params.get("patterns_module")
    if domain_patterns_module:
        try:
            mod = importlib.import_module(domain_patterns_module)
            if hasattr(mod, "PATTERNS"):
                patterns.extend(mod.PATTERNS)
                logger.debug("Loaded %d domain patterns", len(mod.PATTERNS))
        except ImportError as e:
            logger.warning("patterns_module %s not importable: %s", domain_patterns_module, e)

    # Files to scan: from params or from git diff (if repo)
    explicit_files = params.get("scan_files", [])
    if explicit_files:
        files = [Path(f) for f in explicit_files if Path(f).exists()]
    else:
        files = _modified_files()

    if not files:
        ctx.metrics.setdefault("structural_check", {}).update(
            files_scanned=0, findings=0
        )
        logger.info("structural_check: no files to scan")
        return

    findings: list[dict[str, Any]] = []
    for fp in files:
        findings.extend(_scan_file(fp, patterns))

    by_severity: dict[str, int] = {}
    for f in findings:
        by_severity[f["severity"]] = by_severity.get(f["severity"], 0) + 1

    ctx.metrics.setdefault("structural_check", {}).update(
        files_scanned=len(files),
        findings=len(findings),
        by_severity=by_severity,
    )

    logger.info(
        "structural_check: %d findings in %d files (%s)",
        len(findings), len(files),
        ", ".join(f"{k}={v}" for k, v in by_severity.items()) or "none",
    )

    if findings and inject:
        if _inject_tension(ctx, findings):
            ctx.metrics["structural_check"]["meta_injected"] = True


def _modified_files() -> list[Path]:
    """Files changed in last git commit (if repo). Otherwise empty.

    Original used `git diff HEAD~1`; we keep that behavior. Phase 4
    domains may want a different policy (scan all .py in domain dir).
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1"],
            capture_output=True, text=True, cwd=str(Path.cwd()),
        )
        candidates = [
            Path(f) for f in result.stdout.strip().split("\n")
            if f.endswith(".py")
        ]
        return [c for c in candidates if c.exists()]
    except Exception:
        return []


def _scan_file(filepath: Path, patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Scan a single file, return list of findings."""
    try:
        content = filepath.read_text()
    except Exception:
        return []
    findings = []
    for i, line in enumerate(content.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        for pattern in patterns:
            if re.search(pattern["regex"], line):
                findings.append({
                    "file": str(filepath),
                    "line": i,
                    "pattern_id": pattern["id"],
                    "pattern_name": pattern["name"],
                    "severity": pattern["severity"],
                    "code": line.strip()[:120],
                    "description": pattern["description"],
                })
    return findings


def _inject_tension(ctx: CycleContext, findings: list[dict[str, Any]]) -> bool:
    """Inject a META tension into the seed if findings exist.

    The tension uses the schema expected by the seed_integrator and
    build_field downstream. Idempotent: removes previous STRUCTURAL_CHECK_*
    tensions before injecting (only the latest survives).
    """
    seed_path = paths.seed_path(ctx.domain)
    if not seed_path.exists():
        logger.warning("seed.json not found, cannot inject META tension")
        return False
    try:
        seed = json.loads(seed_path.read_text())
    except json.JSONDecodeError:
        logger.warning("seed.json invalid JSON, cannot inject META tension")
        return False

    tensioni = [
        t for t in seed.get("tensioni", [])
        if not str(t.get("id", "")).startswith("STRUCTURAL_CHECK")
    ]

    alto = [f for f in findings if f["severity"] == "alto"]
    files_involved = sorted({Path(f["file"]).name for f in findings})
    patterns_found = sorted({f["pattern_id"] for f in findings})

    claim = (
        f"{len(findings)} structural anti-patterns in {len(files_involved)} files: "
        f"{', '.join(patterns_found[:3])}. "
        f"Files: {', '.join(files_involved[:5])}. "
        f"Fix where you pass — the system evolves organically."
    )

    tension = {
        "tipo": "scoperta",
        "id": f"STRUCTURAL_CHECK_{datetime.now(timezone.utc).strftime('%Y%m%d')}",
        "claim": claim,
        "intensita": 0.85 if alto else 0.65,
        "porta": "auto-evolution",
        "potenziale": "alto" if alto else "medio",
        "stato": "aperto",
        "findings": [{
            "file": Path(f["file"]).name,
            "line": f["line"],
            "pattern": f["pattern_name"],
            "code": f["code"],
        } for f in findings[:10]],
    }
    tensioni.append(tension)
    seed["tensioni"] = tensioni
    ctx.seed = seed

    try:
        seed_path.write_text(json.dumps(seed, indent=2, ensure_ascii=False))
        return True
    except Exception as e:
        logger.warning("could not write seed: %s", e)
        return False


# ─── Movement registration ─────────────────────────────────────────

register_movement("structural_check", structural_check)
