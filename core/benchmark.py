"""Model benchmark — compare LLMs on a standardized cycle.

Phase 5+ feature. The full implementation runs the same domain cycle
across multiple models and produces a cost/quality matrix:

  | model                    | turns | tokens | cost  | success | report_quality |
  |--------------------------|-------|--------|-------|---------|----------------|
  | deepseek/deepseek-v4-pro | 9     | 152K   | $0.07 | ok      | 4.5/5          |
  | anthropic/claude-opus-4.7| 8     | 145K   | $0.55 | ok      | 4.8/5          |
  | tencent/hy3-preview:free | 25    | 320K   | $0.00 | timeout | -              |

Quality scoring is via a separate LLM (the "judge") that reads the report
+ refiner output and scores against rubric criteria.

Phase 4 ships the SKELETON of this module so the CLI command exists and
the contract is documented. Implementation lands in Phase 5+ when the
public release benefits from a comparison table in the README.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """One model × one domain × one cycle."""
    model: str
    domain: str
    timestamp: str
    success: bool
    turns: int = 0
    total_tokens: int = 0
    cost_usd: float | None = None
    duration_s: float = 0.0
    report_bytes: int = 0
    error: str = ""
    quality_score: float | None = None  # filled by judge LLM in Phase 5+
    notes: str = ""


@dataclass
class BenchmarkRun:
    """A full benchmark — N models, 1 domain, fixed seed."""
    domain: str
    started_at: str
    finished_at: str = ""
    results: list[BenchmarkResult] = field(default_factory=list)


def run_benchmark(
    domain: str,
    models: list[str],
    out_dir: Path | None = None,
) -> BenchmarkRun:
    """Run the same cycle across multiple models, collect metrics.

    Phase 5+ implementation will:
      1. For each model:
         a. Set LLM_MODEL env override
         b. Run a fresh cycle (clean data dir, identical seed_tensions)
         c. Capture: success/fail, turns, tokens, cost, duration, report bytes
         d. (Phase 6+) Score report quality via a separate judge LLM
      2. Aggregate into BenchmarkRun
      3. Write JSON + markdown table to out_dir

    Phase 4: NotImplementedError — the contract is fixed, the
    implementation is held until Phase 5+ public release work makes the
    comparison table directly useful.
    """
    raise NotImplementedError(
        "benchmark is Phase 5+. The skeleton documents the contract. "
        "To benchmark a single model now, simply run `dndlab run --domain <X>` "
        "with LLM_MODEL=<model_id> set in your env, then check the cycle's "
        "metrics in <data>/<domain>/lab_data.json."
    )


def write_benchmark_report(run: BenchmarkRun, out_dir: Path) -> Path:
    """Serialize a BenchmarkRun as JSON + a human-readable markdown table.

    Phase 5+ will fill this. Stub returns a placeholder.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"benchmark_{run.started_at}.json"
    md_path = out_dir / f"benchmark_{run.started_at}.md"
    payload = {
        "domain": run.domain,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "results": [r.__dict__ for r in run.results],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    md_path.write_text(_format_markdown(run))
    return md_path


def _format_markdown(run: BenchmarkRun) -> str:
    lines = [f"# Benchmark — domain={run.domain}", ""]
    lines.append(f"Started: {run.started_at}")
    lines.append(f"Finished: {run.finished_at}")
    lines.append("")
    lines.append("| model | success | turns | tokens | cost USD | duration s | report b |")
    lines.append("|-------|---------|-------|--------|----------|------------|----------|")
    for r in run.results:
        cost = f"${r.cost_usd:.4f}" if r.cost_usd is not None else "?"
        success = "ok" if r.success else "fail"
        lines.append(
            f"| `{r.model}` | {success} | {r.turns} | {r.total_tokens:,} | "
            f"{cost} | {r.duration_s:.1f} | {r.report_bytes:,} |"
        )
    return "\n".join(lines) + "\n"
