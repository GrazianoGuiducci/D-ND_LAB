#!/usr/bin/env python3
"""btc_zone_denominator_sensitivity.py - compare BTC zone/denominator variants.

This artifact keeps the active daily_inefficiency policy unchanged. It reruns
the same deposit through a small grid of zone width, forward-window and fill
threshold variants so the Lab can see whether the next redesign belongs to
zone construction, denominator horizon, or neither.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from btc_artifact_lineage import write_json_artifact
from btc_daily_inefficiency_candidate import EXCHANGE_LATEST, build_daily_inefficiency_candidate


VERSION = "0.1.0"
DOMAIN = "bitcoin-regime-lab"
DOMAIN_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = DOMAIN_DIR.parents[1]
DATA_ROOT = Path(os.environ.get("LAB_DATA_DIR", REPO_ROOT / "data")).resolve()
DATA_DIR = DATA_ROOT / DOMAIN
VALUE_DIR = DATA_DIR / "value"

VARIANTS = (
    {
        "variant": "baseline",
        "axis": "baseline",
        "min_zone_width_pct": 0.15,
        "forward_window": 10,
        "fill_threshold": 0.5,
    },
    {
        "variant": "narrow_zone",
        "axis": "zone_construction",
        "min_zone_width_pct": 0.05,
        "forward_window": 10,
        "fill_threshold": 0.5,
    },
    {
        "variant": "wide_zone",
        "axis": "zone_construction",
        "min_zone_width_pct": 0.3,
        "forward_window": 10,
        "fill_threshold": 0.5,
    },
    {
        "variant": "short_denominator",
        "axis": "denominator_horizon",
        "min_zone_width_pct": 0.15,
        "forward_window": 5,
        "fill_threshold": 0.5,
    },
    {
        "variant": "long_denominator",
        "axis": "denominator_horizon",
        "min_zone_width_pct": 0.15,
        "forward_window": 20,
        "fill_threshold": 0.5,
    },
    {
        "variant": "shallow_fill",
        "axis": "fill_threshold",
        "min_zone_width_pct": 0.15,
        "forward_window": 10,
        "fill_threshold": 0.25,
    },
    {
        "variant": "deep_fill",
        "axis": "fill_threshold",
        "min_zone_width_pct": 0.15,
        "forward_window": 10,
        "fill_threshold": 0.75,
    },
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_for(spec: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    card = (payload.get("cards") or [{}])[0] if isinstance(payload.get("cards"), list) else {}
    zone_rate = metrics.get("zone_fill_rate")
    strict_rate = metrics.get("strict_control_fill_rate")
    edge = None
    if isinstance(zone_rate, (int, float)) and isinstance(strict_rate, (int, float)):
        edge = round(float(zone_rate) - float(strict_rate), 4)
    return {
        "variant": spec["variant"],
        "axis": spec["axis"],
        "min_zone_width_pct": spec["min_zone_width_pct"],
        "forward_window": spec["forward_window"],
        "fill_threshold": spec["fill_threshold"],
        "decision": card.get("decision"),
        "verdict": card.get("verdict"),
        "zones_total": metrics.get("zones_total"),
        "zones_evaluable": metrics.get("zones_evaluable"),
        "zones_pending": metrics.get("zones_pending"),
        "zones_filled": metrics.get("zones_filled"),
        "strict_controls_evaluable": metrics.get("strict_controls_evaluable"),
        "strict_controls_filled": metrics.get("strict_controls_filled"),
        "denominator_ready": metrics.get("denominator_ready"),
        "zone_fill_rate": zone_rate,
        "strict_control_fill_rate": strict_rate,
        "edge_vs_strict_null": edge,
    }


def build_sensitivity() -> dict[str, Any]:
    rows = []
    for spec in VARIANTS:
        payload = build_daily_inefficiency_candidate(
            input_path=EXCHANGE_LATEST,
            min_zone_width_pct=float(spec["min_zone_width_pct"]),
            forward_window=int(spec["forward_window"]),
            fill_threshold=float(spec["fill_threshold"]),
            fill_rule="wick",
        )
        rows.append(_row_for(spec, payload))

    ready_rows = [row for row in rows if row.get("denominator_ready")]
    positive_rows = [
        row for row in ready_rows
        if isinstance(row.get("edge_vs_strict_null"), (int, float))
        and float(row["edge_vs_strict_null"]) > 0
    ]
    best_row = None
    edge_rows = [row for row in ready_rows if isinstance(row.get("edge_vs_strict_null"), (int, float))]
    if edge_rows:
        best_row = max(edge_rows, key=lambda row: float(row["edge_vs_strict_null"]))
    positive_axes = sorted({str(row.get("axis")) for row in positive_rows})

    if not ready_rows:
        decision = "watch"
        verdict = "ZONE_DENOMINATOR_SENSITIVITY_DENOMINATOR_LOW"
        next_test = "Accumulate closed daily evidence before selecting a zone or denominator variant."
    elif positive_rows:
        decision = "test"
        verdict = "ZONE_DENOMINATOR_SENSITIVITY_HAS_EDGE"
        next_test = "Review the positive axis against ledger and contract before method-policy mutation."
    else:
        decision = "watch"
        verdict = "ZONE_DENOMINATOR_SENSITIVITY_STRICT_NULL_NOT_BEATEN"
        next_test = "No tested zone/denominator variant beats strict null; redesign event source or add a different null family next."

    return {
        "schema": "dndlab.bitcoin.zone_denominator_sensitivity.v1",
        "generated_at": _utc_now(),
        "domain": DOMAIN,
        "version": VERSION,
        "intent": "Compare daily_inefficiency zone construction and denominator variants without replacing active method policy.",
        "decision": decision,
        "verdict": verdict,
        "next_test": next_test,
        "input_artifacts": {
            "exchange_ohlcv": str(EXCHANGE_LATEST),
            "daily_inefficiency_builder": "domains/bitcoin-regime-lab/tools/btc_daily_inefficiency_candidate.py",
        },
        "variants": rows,
        "result": {
            "decision": decision,
            "verdict": verdict,
            "ready_variants": [row["variant"] for row in ready_rows],
            "positive_variants": [row["variant"] for row in positive_rows],
            "positive_axes": positive_axes,
            "best_variant": best_row["variant"] if best_row else None,
            "best_axis": best_row["axis"] if best_row else None,
            "best_edge_vs_strict_null": best_row["edge_vs_strict_null"] if best_row else None,
            "next_test": next_test,
        },
        "summary": {
            "observe": 1,
            "watch": 1 if decision == "watch" else 0,
            "test": 1 if decision == "test" else 0,
            "reject": 0,
            "variants_checked": len(rows),
            "ready_variants": len(ready_rows),
            "positive_variants": len(positive_rows),
            "trading_signal": False,
        },
        "cards": [
            {
                "claim_id": "btc_zone_denominator_sensitivity",
                "title": "BTC zone/denominator sensitivity",
                "decision": decision,
                "verdict": verdict,
                "evidence": "; ".join(
                    f"{row['variant']}: denom={row.get('zones_evaluable')} edge={row.get('edge_vs_strict_null')}"
                    for row in rows
                ),
                "next_test": next_test,
                "boundary": "Method sensitivity only: no entries, exits, price targets, advice or real orders.",
            }
        ],
        "boundary": {
            "public_claim": False,
            "trading_signal": False,
            "operational": False,
            "advice": False,
            "price_target": False,
            "entry_exit": False,
            "real_order_execution": False,
        },
    }


def write_artifact(payload: dict[str, Any]) -> dict[str, str]:
    return write_json_artifact(
        payload=payload,
        value_dir=VALUE_DIR,
        data_dir=DATA_DIR,
        repo_root=REPO_ROOT,
        tool_path=Path(__file__).resolve(),
        artifact_prefix="btc_zone_denominator_sensitivity",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build BTC zone/denominator sensitivity artifact.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = build_sensitivity()
    if args.write:
        payload["written"] = write_artifact(payload)
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"status": "OK", "files": payload.get("written"), "summary": payload["summary"]}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
