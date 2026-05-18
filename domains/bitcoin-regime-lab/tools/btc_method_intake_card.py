#!/usr/bin/env python3
"""btc_method_intake_card.py - Alipio/Rea method-intake cards.

This tool turns human BTC chart language into structured method cards. It does
not calculate levels, targets or signals. Its job is to make missing
definitions visible before POC/FVG/MM52/trendline language can enter a cycle.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VERSION = "0.1.0"
DOMAIN_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = DOMAIN_DIR.parents[1]
DATA_ROOT = Path(os.environ.get("LAB_DATA_DIR", REPO_ROOT / "data")).resolve()
DATA_DIR = DATA_ROOT / "bitcoin-regime-lab"
VALUE_DIR = DATA_DIR / "value"
TIMEFRAME_LATEST = VALUE_DIR / "btc_timeframe_matrix_latest.json"
FIRST_HYPOTHESIS_LATEST = VALUE_DIR / "btc_first_hypothesis_latest.json"


METHODS: list[dict[str, Any]] = [
    {
        "method_id": "volume_profile_poc",
        "title": "POC del Volume Profile",
        "human_phrase": "le linee rosse sono i POC del volume profile",
        "candidate_observable": "computed POC level in a declared profile window",
        "required_definitions": [
            "exchange/source",
            "profile_window_start_end",
            "volume_source_real_or_proxy",
            "binning_rule",
            "touch_tolerance",
        ],
        "data_requirement": "OHLCV plus declared volume-profile proxy, or real profile/tick data",
        "baseline_null": "matched_random_level + adjacent_window_poc + shuffled_volume_profile",
        "falsifier": "selected_window_artifact or volume_proxy_confusion",
        "status": "watch",
        "current_blocker": "window, binning and tolerance are not declared",
    },
    {
        "method_id": "poc_below_warning",
        "title": "POC sotto",
        "human_phrase": "pericoloso perche' il POC e' sotto",
        "candidate_observable": "POC relation to current price/range",
        "required_definitions": [
            "which_poc_window",
            "closed_candle_policy",
            "below_threshold",
            "risk_meaning_without_signal",
        ],
        "data_requirement": "computed POC plus closed OHLCV candle",
        "baseline_null": "random_level_below_price with same distance distribution",
        "falsifier": "directional_signal_leakage or selected_window_artifact",
        "status": "watch",
        "current_blocker": "risk language must become watch/reject/test, not direction",
    },
    {
        "method_id": "inefficiency_closure",
        "title": "Chiusura inefficienza",
        "human_phrase": "chiudere l'inefficienza / FVG / area con pochi volumi",
        "candidate_observable": "daily FVG/LVN/gap-fill event with declared fill rule",
        "required_definitions": [
            "zone_definition",
            "fill_threshold",
            "wick_or_close_rule",
            "forward_window",
            "invalidation_rule",
        ],
        "data_requirement": "daily OHLCV is enough for first FVG-style proxy; LVN needs volume-profile rule",
        "baseline_null": "equal_width_zone_fill_rate + block_preserving_return_null",
        "falsifier": "fill_rate_without_denominator or lookahead_bias",
        "status": "test_candidate",
        "current_blocker": "fill rule and zone definition must be declared",
    },
    {
        "method_id": "trendline_poc_retest",
        "title": "Retest trendline + POC",
        "human_phrase": "retest del POC e della trend line ascendente",
        "candidate_observable": "confluence event between declared trendline and POC zone",
        "required_definitions": [
            "pivot_selection_rule",
            "line_timeframe",
            "retest_tolerance",
            "POC_window",
            "forward_outcome",
        ],
        "data_requirement": "OHLCV plus deterministic trendline construction and POC artifact",
        "baseline_null": "POC_only vs trendline_only vs random_slope_line ablation",
        "falsifier": "confluence_overfit or manual_annotation_drift",
        "status": "watch",
        "current_blocker": "trendline construction is still manual",
    },
    {
        "method_id": "mm52_retest",
        "title": "Retest MM52",
        "human_phrase": "test / retest MM52",
        "candidate_observable": "moving-average touch/rejection event",
        "required_definitions": [
            "MA_type",
            "MA_length",
            "source_price",
            "timeframe",
            "touch_or_close_rule",
        ],
        "data_requirement": "OHLCV on declared timeframe",
        "baseline_null": "shifted_MA + random_moving_level + MA_only_baseline",
        "falsifier": "threshold_sweep_overfit",
        "status": "watch",
        "current_blocker": "MA definition and pass/fail rule are not declared",
    },
    {
        "method_id": "timeframe_matrix",
        "title": "Timeframe ottimale",
        "human_phrase": "mensile, settimanale, day, 4h, 1h, 45m, 30m, 15m, 10m, 5m, 1m",
        "candidate_observable": "timeframe admissibility matrix",
        "required_definitions": [
            "event_family",
            "native_data_per_timeframe",
            "denominator",
            "open_candle_policy",
        ],
        "data_requirement": "native OHLCV per timeframe plus feed robustness",
        "baseline_null": "timeframe_denominator_control",
        "falsifier": "opinionated_timeframe_choice",
        "status": "implemented",
        "current_blocker": "intraday native OHLCV is missing; daily only is currently testable",
    },
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json_optional(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _timeframe_state() -> dict[str, Any]:
    payload = _read_json_optional(TIMEFRAME_LATEST)
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    rows = payload.get("timeframe_rows") if isinstance(payload.get("timeframe_rows"), list) else []
    return {
        "schema": payload.get("schema"),
        "generated_at": payload.get("generated_at"),
        "recommended_next_test_timeframe": metrics.get("recommended_next_test_timeframe"),
        "testable": [r.get("timeframe") for r in rows if r.get("status") == "testable"],
        "watch": [r.get("timeframe") for r in rows if r.get("status") == "watch"],
        "blocked": [r.get("timeframe") for r in rows if r.get("status") == "blocked"],
    }


def _field_state() -> dict[str, Any]:
    payload = _read_json_optional(FIRST_HYPOTHESIS_LATEST)
    card = (payload.get("cards") or [{}])[0] if isinstance(payload.get("cards"), list) else {}
    return {
        "schema": payload.get("schema"),
        "generated_at": payload.get("generated_at"),
        "verdict": card.get("verdict"),
        "decision": card.get("decision"),
    }


def build_method_intake(*, focus: str = "inefficiency_closure") -> dict[str, Any]:
    generated_at = _utc_now()
    field = _field_state()
    timeframe = _timeframe_state()
    focus_method = next((m for m in METHODS if m["method_id"] == focus), METHODS[2])
    cards = []
    for method in METHODS:
        status = method["status"]
        decision = "test" if status == "test_candidate" else ("observe" if status == "implemented" else "watch")
        cards.append({
            "claim_id": f"btc_method_{method['method_id']}",
            "method_id": method["method_id"],
            "title": method["title"],
            "claim": f"Translate '{method['human_phrase']}' into {method['candidate_observable']}.",
            "decision": decision,
            "status": status,
            "human_phrase": method["human_phrase"],
            "candidate_observable": method["candidate_observable"],
            "required_definitions": method["required_definitions"],
            "data_requirement": method["data_requirement"],
            "baseline": method["baseline_null"],
            "null": method["baseline_null"],
            "falsifier": method["falsifier"],
            "evidence": method["current_blocker"],
            "boundary": "No trading signal: method intake creates test contracts, not targets or advice.",
            "next_test": (
                "Use this method only after missing definitions are answered "
                "and a matched null is declared."
            ),
        })

    unresolved = sorted({
        item
        for method in METHODS
        if method["status"] != "implemented"
        for item in method["required_definitions"]
    })
    thia_questions = [
        "Quale exchange/sorgente e' il riferimento: Bitstamp soltanto o evento robusto su Binance/Coinbase?",
        "Per ogni POC: qual e' la finestra Volume Profile esatta e quale binning/tolleranza usi?",
        "Quando una inefficienza e' chiusa: wick, close, attraversamento completo, percentuale o volume?",
        "MM52 significa SMA/EMA, su quale timeframe, e quale regola invalida il test?",
        "Come costruisci le trendline: quali pivot, tolleranza e timeframe?",
        "Che output ti serve se non possiamo dare un segnale: watchlist, invalidazione, reject reason o prossimo test?",
    ]

    return {
        "schema": "dndlab.bitcoin.method_intake.v1",
        "generated_at": generated_at,
        "domain": "bitcoin-regime-lab",
        "source_note": "Derived from Alipio visual notes and Massimo Rea method substrate; no raw images or transcripts included.",
        "input_artifacts": {
            "field": str(FIRST_HYPOTHESIS_LATEST),
            "timeframe": str(TIMEFRAME_LATEST),
            "intake_doc": str(REPO_ROOT / "docs" / "BITCOIN_ALIPIO_METHOD_INTAKE_20260518.md"),
        },
        "summary": {
            "observe": 1,
            "watch": sum(1 for m in METHODS if m["status"] == "watch"),
            "test": sum(1 for m in METHODS if m["status"] == "test_candidate"),
            "reject": 0,
            "trading_signal": False,
        },
        "cards": cards,
        "metrics": {
            "methods_total": len(METHODS),
            "methods_implemented": sum(1 for m in METHODS if m["status"] == "implemented"),
            "methods_watch": sum(1 for m in METHODS if m["status"] == "watch"),
            "methods_test_candidate": sum(1 for m in METHODS if m["status"] == "test_candidate"),
            "unresolved_definitions": len(unresolved),
            "recommended_next_method": focus_method["method_id"],
        },
        "field_state": field,
        "timeframe_state": timeframe,
        "unresolved_definitions": unresolved,
        "thia_questions_for_alipio": thia_questions,
        "recommended_next": {
            "method_id": focus_method["method_id"],
            "title": focus_method["title"],
            "why": (
                "It can become a daily-computable test before precise Volume "
                "Profile POC data exists, while preserving the no-signal boundary."
            ),
            "tool_candidate": "btc_daily_inefficiency_candidate.py",
            "precondition": "define zone/fill/invalidation rule and matched null",
        },
        "boundary": {
            "public_claim": False,
            "trading_signal": False,
            "operational": False,
            "advice": False,
            "price_target": False,
            "entry_exit": False,
        },
    }


def write_artifact(payload: dict[str, Any]) -> dict[str, str]:
    VALUE_DIR.mkdir(parents=True, exist_ok=True)
    latest = VALUE_DIR / "btc_method_intake_latest.json"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stamped = VALUE_DIR / f"btc_method_intake_{stamp}.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    latest.write_text(text + "\n", encoding="utf-8")
    stamped.write_text(text + "\n", encoding="utf-8")
    return {"latest": str(latest), "stamped": str(stamped)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build BTC method-intake cards.")
    parser.add_argument("--focus", default="inefficiency_closure", help="Recommended next method_id.")
    parser.add_argument("--write", action="store_true", help="Write under data/bitcoin-regime-lab/value/")
    parser.add_argument("--json", action="store_true", help="Print JSON payload.")
    args = parser.parse_args()

    payload = build_method_intake(focus=args.focus)
    if args.write:
        payload["files"] = write_artifact(payload)
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"status": "OK", "files": payload.get("files"), "summary": payload["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
