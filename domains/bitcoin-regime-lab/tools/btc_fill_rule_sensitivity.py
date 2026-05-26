#!/usr/bin/env python3
"""btc_fill_rule_sensitivity.py - compare BTC daily inefficiency fill rules.

This artifact does not replace the active daily_inefficiency method. It runs
the same deposit through alternative fill rules so the Lab can see whether the
current result depends on the wick/close/full-traversal assumption.
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
RULES = ("wick", "close", "full_traversal")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_for(rule: str, payload: dict[str, Any]) -> dict[str, Any]:
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    card = (payload.get("cards") or [{}])[0] if isinstance(payload.get("cards"), list) else {}
    zone_rate = metrics.get("zone_fill_rate")
    strict_rate = metrics.get("strict_control_fill_rate")
    edge = None
    if isinstance(zone_rate, (int, float)) and isinstance(strict_rate, (int, float)):
        edge = round(float(zone_rate) - float(strict_rate), 4)
    return {
        "fill_rule": rule,
        "decision": card.get("decision"),
        "verdict": card.get("verdict"),
        "zones_total": metrics.get("zones_total"),
        "zones_evaluable": metrics.get("zones_evaluable"),
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
    for rule in RULES:
        payload = build_daily_inefficiency_candidate(input_path=EXCHANGE_LATEST, fill_rule=rule)
        rows.append(_row_for(rule, payload))

    ready_rows = [row for row in rows if row.get("denominator_ready")]
    positive_rows = [
        row for row in ready_rows
        if isinstance(row.get("edge_vs_strict_null"), (int, float))
        and float(row["edge_vs_strict_null"]) > 0
    ]
    decisions = {str(row.get("decision")) for row in rows}
    verdicts = {str(row.get("verdict")) for row in rows}
    invariant = len(decisions) == 1 and len(verdicts) == 1
    if not ready_rows:
        decision = "watch"
        verdict = "FILL_RULE_SENSITIVITY_DENOMINATOR_LOW"
        next_test = "Accumulate closed daily evidence before selecting or mutating a fill rule."
    elif positive_rows:
        decision = "test"
        verdict = "FILL_RULE_SENSITIVITY_HAS_RULE_EDGE"
        next_test = "Review the positive fill rule against ledger and contract before method-policy mutation."
    elif invariant:
        decision = "watch"
        verdict = "FILL_RULE_SENSITIVITY_INVARIANT_NULL_NOT_BEATEN"
        next_test = "The fill rule is not the active source of edge; inspect zone construction or denominator next."
    else:
        decision = "watch"
        verdict = "FILL_RULE_SENSITIVITY_RULE_DEPENDENT_NO_EDGE"
        next_test = "The method is sensitive to fill semantics, but no rule beats strict null; keep as watch."

    return {
        "schema": "dndlab.bitcoin.fill_rule_sensitivity.v1",
        "generated_at": _utc_now(),
        "domain": DOMAIN,
        "version": VERSION,
        "intent": "Compare daily_inefficiency fill rules without replacing the active method policy.",
        "decision": decision,
        "verdict": verdict,
        "next_test": next_test,
        "input_artifacts": {
            "exchange_ohlcv": str(EXCHANGE_LATEST),
            "daily_inefficiency_builder": "domains/bitcoin-regime-lab/tools/btc_daily_inefficiency_candidate.py",
        },
        "rules": rows,
        "result": {
            "decision": decision,
            "verdict": verdict,
            "invariant_across_rules": invariant,
            "ready_rules": [row["fill_rule"] for row in ready_rows],
            "positive_rules": [row["fill_rule"] for row in positive_rows],
            "next_test": next_test,
        },
        "summary": {
            "observe": 1,
            "watch": 1 if decision == "watch" else 0,
            "test": 1 if decision == "test" else 0,
            "reject": 0,
            "rules_checked": len(rows),
            "positive_rules": len(positive_rows),
            "trading_signal": False,
        },
        "cards": [
            {
                "claim_id": "btc_fill_rule_sensitivity",
                "title": "BTC fill rule sensitivity",
                "decision": decision,
                "verdict": verdict,
                "evidence": "; ".join(
                    f"{row['fill_rule']}: edge={row.get('edge_vs_strict_null')} verdict={row.get('verdict')}"
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
        artifact_prefix="btc_fill_rule_sensitivity",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build BTC fill-rule sensitivity artifact.")
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
