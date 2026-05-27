#!/usr/bin/env python3
"""Autonomous window/universe redesign for Finance Lab.

Reads the latest profit-readiness and recurrence-validation artifacts, then
builds a materially different scout plan. Optional execution writes a fresh
window/universe scout artifact. This is still diagnostic work: no paper,
sandbox, real orders or public advice.
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

from finance_window_universe_scout import build_payload as build_scout_payload  # noqa: E402
from finance_window_universe_scout import parse_universe, write_json_pair as write_scout_pair  # noqa: E402


SCHEMA = "dndlab.finance.window_universe_redesign.value.v1"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


ROOT = repo_root()
VALUE_DIR = ROOT / "data" / "finance" / "value"
REDESIGN_DIR = ROOT / "data" / "finance" / "window_universe_redesign"

CORE_ETF_UNIVERSE = [
    "SPY", "QQQ", "IWM", "DIA", "EFA", "EEM", "TLT", "IEF",
    "GLD", "SLV", "USO", "UUP", "FXE", "FXY", "BTC-USD", "ETH-USD",
]

SECTOR_AND_FACTOR_UNIVERSE = [
    "XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLRE",
    "XLC", "HYG", "LQD", "SHY", "VNQ", "DBC", "ARKK",
]


def rel(path: Path | None) -> str | None:
    if not path:
        return None
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path | None) -> dict[str, Any] | None:
    if not path or not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def summary(name: str) -> dict[str, Any]:
    data = load_json(VALUE_DIR / name) or {}
    item = data.get("summary")
    return item if isinstance(item, dict) else {}


def symbols_from(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).upper() for item in value if item]


def design_plan(*, mode: str, end: str, shuffles: int) -> dict[str, Any]:
    readiness = summary("finance_profit_readiness_latest.json")
    recurrence = summary("finance_recurrence_validation_cycle_latest.json")
    latest_scout = summary("finance_window_universe_scout_latest.json")
    previous_redesign = summary("finance_window_universe_redesign_latest.json")

    failed_local = set(symbols_from(recurrence.get("single_window_symbols")))
    failed_local.update(symbols_from(previous_redesign.get("excluded_failed_local_symbols")))
    previous_symbols = symbols_from(latest_scout.get("symbols"))
    previous_windows = latest_scout.get("windows_days") if isinstance(latest_scout.get("windows_days"), list) else []
    recurrence_label = str(recurrence.get("label") or "missing")
    next_action = str(readiness.get("next_action") or "unknown")

    if mode == "sector_rotation":
        universe = SECTOR_AND_FACTOR_UNIVERSE
        windows = [60, 120, 240, 360]
        rationale = "Move from broad ETF/local USO-EFA candidates into sector/factor assets and longer recurrence-friendly windows."
    elif mode == "long_memory":
        universe = [symbol for symbol in CORE_ETF_UNIVERSE if symbol not in failed_local] + SECTOR_AND_FACTOR_UNIVERSE[:8]
        windows = [120, 180, 270, 360]
        rationale = "Keep core assets but remove failed local candidates and add longer-memory windows."
    else:
        universe = [symbol for symbol in SECTOR_AND_FACTOR_UNIVERSE + CORE_ETF_UNIVERSE if symbol not in failed_local]
        windows = [60, 120, 240, 360]
        rationale = "Default redesign: avoid failed local candidates, expand sectors/factors and test non-overlapping windows."

    changes = {
        "excluded_failed_local_symbols": sorted(failed_local),
        "previous_symbols": previous_symbols,
        "new_symbols": universe,
        "previous_windows": previous_windows,
        "new_windows": windows,
        "changed_universe": universe != previous_symbols,
        "changed_windows": windows != previous_windows,
    }
    command = (
        "python3 domains/finance/tools/finance_window_universe_scout.py "
        f"--symbols {','.join(universe)} --windows {','.join(str(w) for w in windows)} "
        f"--end {end} --shuffles {shuffles} --write --json"
    )
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(UTC).isoformat(),
        "domain": "finance",
        "intent": "Redesign Finance scout universe/windows after local candidates fail recurrence.",
        "summary": {
            "decision": "execute_redesigned_scout",
            "mode": mode,
            "recurrence_label": recurrence_label,
            "profit_next_action": next_action,
            "symbols": universe,
            "windows_days": windows,
            "end": end,
            "shuffles": shuffles,
            "excluded_failed_local_symbols": sorted(failed_local),
            "paper_live_sim_allowed": False,
            "broker_sandbox_allowed": False,
            "real_execution_allowed": False,
            "next_gate": "Run redesigned scout, then recurrence validation only if robust/partial candidates emerge.",
        },
        "changes": changes,
        "rationale": rationale,
        "command": command,
        "boundary": {
            "operational": False,
            "public_claim": False,
            "trading_signal": False,
            "paper_live_sim": False,
        },
        "sources": {
            "profit_readiness": rel(VALUE_DIR / "finance_profit_readiness_latest.json"),
            "recurrence_validation": rel(VALUE_DIR / "finance_recurrence_validation_cycle_latest.json"),
            "previous_scout": rel(VALUE_DIR / "finance_window_universe_scout_latest.json"),
        },
        "cards": [
            {
                "claim_id": "finance_window_universe_redesign",
                "title": "Finance window/universe redesign",
                "decision": "redesign",
                "evidence": f"mode={mode}; excluded={','.join(sorted(failed_local)) or 'none'}; symbols={len(universe)}; windows={len(windows)}",
                "boundary": "Redesign changes the diagnostic scan only; it does not authorize paper or execution.",
            }
        ],
    }


def write_payload(payload: dict[str, Any]) -> dict[str, str]:
    REDESIGN_DIR.mkdir(parents=True, exist_ok=True)
    VALUE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    artifact = REDESIGN_DIR / f"finance_window_universe_redesign_{stamp}.json"
    stamped = VALUE_DIR / f"finance_window_universe_redesign_{stamp}.json"
    latest = VALUE_DIR / "finance_window_universe_redesign_latest.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    artifact.write_text(text, encoding="utf-8")
    stamped.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    return {
        "artifact": rel(artifact) or str(artifact),
        "stamped": rel(stamped) or str(stamped),
        "latest": rel(latest) or str(latest),
    }


def execute_scout(payload: dict[str, Any], *, seed: int) -> dict[str, Any]:
    summary_payload = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    symbols = parse_universe(",".join(summary_payload.get("symbols") or []))
    windows = [int(item) for item in summary_payload.get("windows_days") or []]
    scout = build_scout_payload(
        symbols,
        windows,
        str(summary_payload.get("end") or "2026-05-27"),
        seed,
        int(summary_payload.get("shuffles") or 512),
    )
    scout["redesign_source"] = {
        "schema": payload["schema"],
        "generated_at": payload["generated_at"],
        "mode": summary_payload.get("mode"),
        "excluded_failed_local_symbols": summary_payload.get("excluded_failed_local_symbols"),
    }
    scout["written"] = write_scout_pair(scout)
    return scout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["auto", "sector_rotation", "long_memory"], default="auto")
    parser.add_argument("--end", default="2026-05-27")
    parser.add_argument("--seed", type=int, default=142)
    parser.add_argument("--shuffles", type=int, default=512)
    parser.add_argument("--execute-scout", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = design_plan(mode=args.mode, end=args.end, shuffles=args.shuffles)
    if args.execute_scout:
        payload["executed_scout_summary"] = execute_scout(payload, seed=args.seed).get("summary")
    if args.write:
        payload["written"] = write_payload(payload)
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"status": "ok", "written": payload.get("written")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
