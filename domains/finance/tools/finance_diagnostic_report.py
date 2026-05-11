#!/usr/bin/env python3
"""Generate an internal diagnostic report for D-ND finance experiments.

The report is intentionally conservative: it translates ordered-vs-shuffle
results into maturity labels without promoting market or trading claims.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from exp_regime_shift import run_experiment  # noqa: E402
from market_data import fetch  # noqa: E402


DEFAULT_WINDOWS = [
    {
        "asset": "SPY",
        "provider": "yfinance",
        "symbol": "SPY",
        "label": "current_3mo",
        "start": "2026-02-09",
        "end": "2026-05-09",
    },
    {
        "asset": "SPY",
        "provider": "yfinance",
        "symbol": "SPY",
        "label": "shifted_3mo_prev_1",
        "start": "2025-11-10",
        "end": "2026-02-10",
    },
    {
        "asset": "SPY",
        "provider": "yfinance",
        "symbol": "SPY",
        "label": "shifted_3mo_prev_2",
        "start": "2025-08-11",
        "end": "2025-11-11",
    },
    {
        "asset": "SPY",
        "provider": "yfinance",
        "symbol": "SPY",
        "label": "shifted_3mo_prev_3",
        "start": "2025-05-12",
        "end": "2025-08-12",
    },
]


MATURITY_ORDER = ["observation", "candidate", "local_robust", "recurring", "operational"]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_output_dir() -> Path:
    return _repo_root() / "data" / "finance" / "diagnostics"


def _finite(value: float) -> float | None:
    return value if math.isfinite(value) else None


def run_window(spec: dict[str, str], shuffles: int, seed: int) -> dict[str, Any]:
    if spec["provider"] != "yfinance":
        raise ValueError("finance_diagnostic_report currently supports yfinance windows")
    data = fetch(
        spec["provider"],
        spec["symbol"],
        start=spec["start"],
        end=spec["end"],
    )
    result = run_experiment(
        shuffles=shuffles,
        seed=seed,
        real_returns=np.asarray(data["returns"], dtype=float),
        real_meta=data["data_card"],
    )
    card = result.get("data_card") or {}
    actual_dates = card.get("dates", {}) if isinstance(card.get("dates"), dict) else {}
    actual_start = actual_dates.get("first") or card.get("first_date")
    actual_end = actual_dates.get("last") or card.get("last_date")
    return {
        "asset": spec["asset"],
        "provider": spec["provider"],
        "symbol": spec["symbol"],
        "label": spec["label"],
        "requested_start": spec["start"],
        "requested_end": spec["end"],
        "actual_start": actual_start,
        "actual_end": actual_end,
        "n": result["n"],
        "seed": seed,
        "shuffles": shuffles,
        "verdict": result["verdict"],
        "effect_z": _finite(float(result["effect_z"])),
        "ordered": _finite(float(result["ordered"])),
        "shuffle_mean": _finite(float(result["shuffle_mean"])),
        "shuffle_std": _finite(float(result["shuffle_std"])),
        "var_95": _finite(float(result["var_95"])),
        "realized_vol": _finite(float(result["realized_vol"])),
        "cassini_residue": _finite(float(result["cassini_residue"])),
        "source_url": card.get("source_url"),
        "retrieval_ts": card.get("retrieval_ts"),
        "era_hint": card.get("era_hint"),
    }


def classify_maturity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    current = next((r for r in rows if r["label"] == "current_3mo"), None)
    shifted = [r for r in rows if r["label"].startswith("shifted_3mo")]
    dnd_count = sum(1 for r in rows if r["verdict"] == "DND_DELTA")
    shifted_dnd = sum(1 for r in shifted if r["verdict"] == "DND_DELTA")

    if not current:
        level = "observation"
        reason = "No current reference window was present."
    elif current["verdict"] != "DND_DELTA":
        level = "observation"
        reason = "The current reference window did not pass the DND_DELTA gate."
    elif shifted and shifted_dnd == 0:
        level = "local_robust"
        reason = (
            "The current window passes, while adjacent shifted windows reject. "
            "This supports a local method observation, not recurrence."
        )
    elif shifted and shifted_dnd == len(shifted):
        level = "recurring"
        reason = "All shifted windows pass the same gate. This would support recurrence."
    else:
        level = "candidate"
        reason = "Some support exists, but shifted windows are mixed or incomplete."

    return {
        "level": level,
        "rank": MATURITY_ORDER.index(level),
        "dnd_delta_count": dnd_count,
        "no_delta_count": len(rows) - dnd_count,
        "reason": reason,
        "operational": False,
        "public_claim": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    rows = payload["windows"]
    maturity = payload["maturity"]
    lines = [
        "# Finance Diagnostic Report - SPY Shifted Windows",
        "",
        f"Generated: {payload['generated_at']}",
        f"Seed: `{payload['seed']}`",
        f"Shuffles: `{payload['shuffles']}`",
        "",
        "## Executive Read",
        "",
        (
            "The D-ND finance gate detects a recent SPY 3-month ordered-vs-shuffle "
            "separation, then rejects the three adjacent non-overlapping 3-month "
            "windows. This is useful method evidence, but not an operational market "
            "signal."
        ),
        "",
        "## Maturity",
        "",
        f"- Level: `{maturity['level']}`",
        f"- DND_DELTA windows: `{maturity['dnd_delta_count']}`",
        f"- NO_DELTA windows: `{maturity['no_delta_count']}`",
        f"- Reason: {maturity['reason']}",
        "- Operational: `false`",
        "- Public/trading claim: `false`",
        "",
        "## Window Table",
        "",
        "| Label | Actual dates | Verdict | effect_z | ordered | shuffle mean | shuffle std | realized vol | VaR 95 |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        dates = f"{r.get('actual_start') or '?'}..{r.get('actual_end') or '?'}"
        lines.append(
            "| {label} | {dates} | `{verdict}` | {effect_z:.4f} | {ordered:.8f} | "
            "{shuffle_mean:.8f} | {shuffle_std:.8f} | {realized_vol:.4f} | {var_95:.5f} |".format(
                label=r["label"],
                dates=dates,
                verdict=r["verdict"],
                effect_z=r["effect_z"] or 0.0,
                ordered=r["ordered"] or 0.0,
                shuffle_mean=r["shuffle_mean"] or 0.0,
                shuffle_std=r["shuffle_std"] or 0.0,
                realized_vol=r["realized_vol"] or 0.0,
                var_95=r["var_95"] or 0.0,
            )
        )

    lines.extend(
        [
            "",
            "## Perceived Value",
            "",
            (
                "This report makes the value legible: the system does not only emit a "
                "verdict, it shows where the verdict survives and where it collapses."
            ),
            "",
            "Useful for:",
            "",
            "- internal method validation;",
            "- explaining D-ND as a falsification workflow;",
            "- feeding a future diagnostic dashboard card.",
            "",
            "Not useful for:",
            "",
            "- trading decisions;",
            "- public finance claims;",
            "- claiming that the finance module is operational.",
            "",
            "## Provenance",
            "",
        ]
    )
    for r in rows:
        lines.append(
            f"- `{r['label']}`: {r.get('source_url') or 'source unavailable'}; "
            f"retrieved `{r.get('retrieval_ts') or 'unknown'}`; era `{r.get('era_hint') or 'unknown'}`"
        )
    lines.extend(
        [
            "",
            "## Next Gate",
            "",
            (
                "Before promotion, define an operational criterion that includes "
                "out-of-sample windows, scan-aware nulls, and explicit risk framing."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(payload: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"finance_diagnostic_{payload['generated_at_compact']}"
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    payload["outputs"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    md_path.write_text(render_markdown(payload))
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--shuffles", type=int, default=4096)
    parser.add_argument("--output-dir", type=Path, default=_default_output_dir())
    parser.add_argument("--json", action="store_true", help="print payload JSON to stdout")
    args = parser.parse_args()

    generated = datetime.now(UTC)
    windows = [run_window(spec, shuffles=args.shuffles, seed=args.seed) for spec in DEFAULT_WINDOWS]
    payload = {
        "generated_at": generated.isoformat(),
        "generated_at_compact": generated.strftime("%Y%m%d_%H%M%S"),
        "domain": "finance",
        "kind": "diagnostic_report",
        "seed": args.seed,
        "shuffles": args.shuffles,
        "maturity": classify_maturity(windows),
        "windows": windows,
        "boundary": {
            "operational": False,
            "public_claim": False,
            "trading_signal": False,
        },
    }
    json_path, md_path = write_outputs(payload, args.output_dir)

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Wrote JSON: {json_path}")
        print(f"Wrote Markdown: {md_path}")
        print(f"Maturity: {payload['maturity']['level']}")


if __name__ == "__main__":
    main()
