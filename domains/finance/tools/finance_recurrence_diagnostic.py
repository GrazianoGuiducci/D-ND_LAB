#!/usr/bin/env python3
"""Exact-window recurrence diagnostic for the D-ND finance lab.

The transfer diagnostic asks "does one window transfer across assets?". This
tool asks the next question: "does the remaining local signal recur across
adjacent exact windows for the same asset under the same null battery?".
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from finance_transfer_diagnostic import run_symbol  # noqa: E402


DEFAULT_WINDOWS = [
    {"label": "current", "start": "2026-02-09", "end": "2026-05-09"},
    {"label": "prev_1", "start": "2025-11-10", "end": "2026-02-10"},
    {"label": "prev_2", "start": "2025-08-11", "end": "2025-11-11"},
    {"label": "prev_3", "start": "2025-05-12", "end": "2025-08-12"},
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_output_dir() -> Path:
    return repo_root() / "data" / "finance" / "diagnostics"


def parse_windows(raw: str | None) -> list[dict[str, str]]:
    if not raw:
        return list(DEFAULT_WINDOWS)
    windows = []
    for idx, item in enumerate(raw.split(","), start=1):
        item = item.strip()
        if not item:
            continue
        try:
            start, end = item.split("..", 1)
        except ValueError as exc:
            raise ValueError(f"window {item!r} must be START..END") from exc
        windows.append({"label": f"custom_{idx}", "start": start, "end": end})
    return windows


def classify(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok_rows = [r for r in rows if r.get("status") == "OK"]
    review_rows = [r for r in rows if r.get("status") != "OK"]
    robust = [r for r in ok_rows if r.get("robust_all_nulls")]
    iid_pass = [r for r in ok_rows if r.get("iid", {}).get("verdict") == "DND_DELTA"]
    block21_pass = [r for r in ok_rows if r.get("block21", {}).get("verdict") == "DND_DELTA"]
    current = next((r for r in ok_rows if r.get("label") == "current"), None)

    if len(robust) >= 2:
        label = "recurring_candidate"
        reason = "At least two exact windows pass iid, block5 and block21."
    elif robust:
        label = "single_robust_window"
        reason = "Only one exact window passes all nulls; recurrence is not established."
    elif current and current.get("iid", {}).get("verdict") == "DND_DELTA":
        label = "current_iid_partial"
        reason = "The current window passes iid but not the full block-preserving contract."
    elif iid_pass:
        label = "historical_iid_partial"
        reason = "Some window passes iid only; no robust recurrence is present."
    else:
        label = "no_recurrence_delta"
        reason = "No exact window passes the recurrence diagnostic."

    return {
        "label": label,
        "reason": reason,
        "n_windows": len(rows),
        "iid_pass_windows": [r["label"] for r in iid_pass],
        "block21_pass_windows": [r["label"] for r in block21_pass],
        "robust_all_null_windows": [r["label"] for r in robust],
        "review_required_windows": [r["label"] for r in review_rows],
        "operational": False,
        "public_claim": False,
        "trading_signal": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    c = payload["classification"]
    lines = [
        "# Finance Recurrence Diagnostic - Exact Windows",
        "",
        f"Generated: {payload['generated_at']}",
        f"Symbol: `{payload['symbol']}`",
        f"Seed: `{payload['seed']}`",
        f"Shuffles per null: `{payload['shuffles']}`",
        "",
        "## Executive Read",
        "",
        f"Recurrence class: `{c['label']}`.",
        c["reason"],
        "",
        "This is a recurrence diagnostic, not a trading signal or public finance claim.",
        "",
        "## Window Table",
        "",
        "| Label | Actual dates | n | iid | z_iid | block5 | z_b5 | block21 | z_b21 | robust |",
        "|---|---|---:|---|---:|---|---:|---|---:|---|",
    ]
    for r in payload["rows"]:
        if r.get("status") != "OK":
            lines.append(f"| {r['label']} | REVIEW_REQUIRED | 0 | error | 0 | error | 0 | error | 0 | false |")
            continue
        lines.append(
            "| {label} | {dates} | {n} | `{iid}` | {zi:.3f} | `{b5}` | {zb5:.3f} | "
            "`{b21}` | {zb21:.3f} | `{robust}` |".format(
                label=r["label"],
                dates=f"{r.get('actual_start') or '?'}..{r.get('actual_end') or '?'}",
                n=r["n"],
                iid=r["iid"]["verdict"],
                zi=r["iid"]["effect_z"] or 0.0,
                b5=r["block5"]["verdict"],
                zb5=r["block5"]["effect_z"] or 0.0,
                b21=r["block21"]["verdict"],
                zb21=r["block21"]["effect_z"] or 0.0,
                robust=str(bool(r["robust_all_nulls"])).lower(),
            )
        )
    lines.extend(["", "## Boundary", ""])
    lines.extend(
        [
            "- Operational: `false`",
            "- Public claim: `false`",
            "- Trading signal: `false`",
            "- Promotion requires robust recurrence plus independent transfer.",
            "",
            "## Provenance",
            "",
        ]
    )
    for r in payload["rows"]:
        if r.get("status") != "OK":
            lines.append(f"- `{r['label']}`: REVIEW_REQUIRED - {r.get('error')}")
            continue
        card = r.get("data_card") or {}
        lines.append(
            f"- `{r['label']}`: {card.get('source_url') or 'source unavailable'}; "
            f"retrieved `{card.get('retrieval_ts') or 'unknown'}`; "
            f"era `{card.get('era_hint') or 'unknown'}`"
        )
    lines.append("")
    return "\n".join(lines)


def write_outputs(payload: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"finance_recurrence_diagnostic_{payload['generated_at_compact']}"
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    payload["outputs"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="SPY")
    parser.add_argument(
        "--windows",
        help="Comma-separated windows as START..END. Defaults to current plus three previous 3-month windows.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--shuffles", type=int, default=1024)
    parser.add_argument("--output-dir", type=Path, default=default_output_dir())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    windows = parse_windows(args.windows)
    generated = datetime.now(UTC)
    rows = []
    for spec in windows:
        row = run_symbol(
            args.symbol,
            start=spec["start"],
            end=spec["end"],
            seed=args.seed,
            shuffles=args.shuffles,
        )
        row["label"] = spec["label"]
        rows.append(row)

    payload = {
        "schema": "finance_recurrence_diagnostic.v1",
        "generated_at": generated.isoformat(),
        "generated_at_compact": generated.strftime("%Y%m%d_%H%M%S"),
        "domain": "finance",
        "kind": "recurrence_diagnostic",
        "symbol": args.symbol,
        "windows": windows,
        "seed": args.seed,
        "shuffles": args.shuffles,
        "nulls": ["iid_shuffle", "block_permutation_5", "block_permutation_21"],
        "rows": rows,
        "classification": classify(rows),
        "boundary": {
            "operational": False,
            "public_claim": False,
            "trading_signal": False,
        },
    }
    write_outputs(payload, args.output_dir)

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Recurrence class: {payload['classification']['label']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
