#!/usr/bin/env python3
"""btc_timeframe_matrix.py - BTC timeframe admissibility matrix.

Consumes the daily exchange feed artifact and classifies requested timeframes
as testable, watch-only or blocked. This answers the timeframe question as a
data-readiness/null-design matrix, not as a market signal.
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
EXCHANGE_LATEST = VALUE_DIR / "btc_exchange_ohlcv_latest.json"
FIRST_HYPOTHESIS_LATEST = VALUE_DIR / "btc_first_hypothesis_latest.json"

TIMEFRAMES = [
    {"id": "1M", "label": "mensile", "minutes": 43200, "role": "regime macro", "required_days": 365},
    {"id": "1W", "label": "settimanale", "minutes": 10080, "role": "regime primario", "required_days": 126},
    {"id": "1D", "label": "daily", "minutes": 1440, "role": "primo campo testabile", "required_days": 30},
    {"id": "4H", "label": "4 ore", "minutes": 240, "role": "setup strutturale", "required_days": 14},
    {"id": "1H", "label": "1 ora", "minutes": 60, "role": "setup locale", "required_days": 7},
    {"id": "45m", "label": "45 minuti", "minutes": 45, "role": "micro struttura", "required_days": 7},
    {"id": "30m", "label": "30 minuti", "minutes": 30, "role": "micro struttura", "required_days": 5},
    {"id": "15m", "label": "15 minuti", "minutes": 15, "role": "timing candidate", "required_days": 3},
    {"id": "10m", "label": "10 minuti", "minutes": 10, "role": "rumore/trigger", "required_days": 3},
    {"id": "5m", "label": "5 minuti", "minutes": 5, "role": "rumore/trigger", "required_days": 2},
    {"id": "1m", "label": "1 minuto", "minutes": 1, "role": "micro rumore", "required_days": 1},
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing required artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _series_window_days(exchange: dict[str, Any]) -> int:
    counts = []
    for feed in exchange.get("series") or []:
        candles = feed.get("candles") if isinstance(feed, dict) else None
        if isinstance(candles, list):
            counts.append(len(candles))
    return min(counts) if counts else 0


def build_timeframe_matrix(
    *,
    exchange_path: Path = EXCHANGE_LATEST,
    first_hypothesis_path: Path = FIRST_HYPOTHESIS_LATEST,
) -> dict[str, Any]:
    exchange = _read_json(exchange_path)
    first = _read_json(first_hypothesis_path)
    exchange_metrics = exchange.get("metrics") or {}
    first_metrics = first.get("metrics") or {}
    first_card = (first.get("cards") or [{}])[0] if isinstance(first.get("cards"), list) else {}
    daily_field_ok = first_card.get("verdict") == "FIELD_ADMISSIBLE_FOR_NEXT_HYPOTHESIS"
    common_days = int(exchange_metrics.get("common_days_compared") or first_metrics.get("common_days_compared") or 0)
    provider_ok = int(exchange_metrics.get("providers_ok") or first_metrics.get("providers_ok") or 0)
    provider_errors = int(exchange_metrics.get("providers_error") or first_metrics.get("providers_error") or 0)
    daily_window_days = min(common_days, _series_window_days(exchange) or common_days)

    rows = []
    for tf in TIMEFRAMES:
        daily_or_above = tf["minutes"] >= 1440
        if not daily_field_ok:
            status = "blocked"
            decision = "reject"
            available_days = 0
            native_feed = "blocked"
            reason = "Daily field is not admissible; repair feed robustness before timeframe selection."
        elif tf["id"] == "1D" and daily_window_days >= tf["required_days"]:
            status = "testable"
            decision = "test"
            available_days = daily_window_days
            native_feed = "daily"
            reason = "Daily feed has enough common candles and provider agreement for one mechanical null-matched test."
        elif daily_or_above:
            status = "watch"
            decision = "watch"
            available_days = daily_window_days
            native_feed = "daily"
            reason = "Can be summarized from daily candles, but the current window is too short for a stable regime denominator."
        else:
            status = "blocked"
            decision = "reject"
            available_days = 0
            native_feed = "missing_intraday"
            reason = "Intraday timeframe needs native intraday OHLCV before POC/FVG/timeframe evidence is admissible."

        rows.append({
            "timeframe": tf["id"],
            "label": tf["label"],
            "role": tf["role"],
            "status": status,
            "decision": decision,
            "required_days": tf["required_days"],
            "available_days": available_days,
            "native_feed": native_feed,
            "reason": reason,
        })

    testable = [r for r in rows if r["status"] == "testable"]
    watch = [r for r in rows if r["status"] == "watch"]
    blocked = [r for r in rows if r["status"] == "blocked"]
    recommended_next = testable[0]["timeframe"] if testable else None
    generated_at = _utc_now()
    return {
        "schema": "dndlab.bitcoin.timeframe_matrix.v1",
        "generated_at": generated_at,
        "domain": "bitcoin-regime-lab",
        "input_artifacts": {
            "exchange": str(exchange_path),
            "first_hypothesis": str(first_hypothesis_path),
        },
        "summary": {
            "observe": 0,
            "watch": len(watch),
            "test": len(testable),
            "reject": len(blocked),
            "trading_signal": False,
        },
        "cards": [
            {
                "claim_id": "btc_timeframe_matrix_daily_first",
                "title": "BTC timeframe matrix - daily first testable",
                "claim": "The current BTC data field can support a first daily mechanical hypothesis, not an optimal-timeframe answer.",
                "decision": "test" if recommended_next else "watch",
                "verdict": "TIMEFRAME_MATRIX_READY" if recommended_next else "TIMEFRAME_MATRIX_BLOCKED",
                "evidence": (
                    f"{provider_ok} providers ok, {provider_errors} errors, "
                    f"{daily_window_days} daily common candles; testable="
                    f"{','.join(r['timeframe'] for r in testable) or 'none'}."
                ),
                "baseline": "opinionated timeframe choice is the naive baseline and is not admissible.",
                "null": "timeframe_denominator_control: a timeframe is useful only if event labels beat matched adjacent-window/random-level controls.",
                "boundary": "No trading signal: this matrix selects the next test surface, not an entry/exit timeframe.",
                "next_test": "Define a daily POC/FVG/timeframe observable with matched null before considering intraday frames.",
            }
        ],
        "metrics": {
            "providers_ok": provider_ok,
            "providers_error": provider_errors,
            "common_days_compared": common_days,
            "daily_window_days": daily_window_days,
            "timeframes_total": len(rows),
            "timeframes_testable": len(testable),
            "timeframes_watch": len(watch),
            "timeframes_blocked": len(blocked),
            "recommended_next_test_timeframe": recommended_next,
        },
        "timeframe_rows": rows,
        "boundary": {
            "public_claim": False,
            "trading_signal": False,
            "operational": False,
            "advice": False,
        },
    }


def write_artifact(payload: dict[str, Any]) -> dict[str, str]:
    VALUE_DIR.mkdir(parents=True, exist_ok=True)
    latest = VALUE_DIR / "btc_timeframe_matrix_latest.json"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stamped = VALUE_DIR / f"btc_timeframe_matrix_{stamp}.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    latest.write_text(text + "\n", encoding="utf-8")
    stamped.write_text(text + "\n", encoding="utf-8")
    return {"latest": str(latest), "stamped": str(stamped)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build BTC timeframe admissibility matrix.")
    parser.add_argument("--exchange-input", default=str(EXCHANGE_LATEST))
    parser.add_argument("--first-hypothesis-input", default=str(FIRST_HYPOTHESIS_LATEST))
    parser.add_argument("--write", action="store_true", help="Write under data/bitcoin-regime-lab/value/")
    parser.add_argument("--json", action="store_true", help="Print JSON payload.")
    args = parser.parse_args()

    payload = build_timeframe_matrix(
        exchange_path=Path(args.exchange_input),
        first_hypothesis_path=Path(args.first_hypothesis_input),
    )
    if args.write:
        payload["files"] = write_artifact(payload)
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"status": "OK", "files": payload.get("files"), "summary": payload["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
