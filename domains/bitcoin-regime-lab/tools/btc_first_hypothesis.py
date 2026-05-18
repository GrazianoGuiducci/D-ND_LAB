#!/usr/bin/env python3
"""btc_first_hypothesis.py - first falsifiable BTC Lab hypothesis.

Consumes the exchange OHLCV value artifact and tests whether the daily BTC
field is robust enough to allow a later POC/FVG/timeframe hypothesis. This is a
precondition test, not a market signal.
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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing required artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_hypothesis_card(
    *,
    input_path: Path = EXCHANGE_LATEST,
    min_providers: int = 3,
    min_common_days: int = 30,
    max_latest_dispersion_pct: float = 0.5,
    max_window_dispersion_pct: float = 0.75,
) -> dict[str, Any]:
    source = _read_json(input_path)
    metrics = source.get("metrics") or {}
    boundary = source.get("boundary") or {}
    providers_ok = int(metrics.get("providers_ok") or 0)
    providers_error = int(metrics.get("providers_error") or 0)
    common_days = int(metrics.get("common_days_compared") or 0)
    latest_dispersion = float(metrics.get("latest_close_dispersion_pct") or 0)
    max_dispersion = float(metrics.get("max_close_dispersion_pct") or 0)
    latest_common_date = metrics.get("latest_common_date")

    checks = [
        {
            "id": "FEED_PROVIDER_COUNT",
            "pass": providers_ok >= min_providers,
            "observed": providers_ok,
            "threshold": min_providers,
        },
        {
            "id": "FEED_PROVIDER_ERRORS",
            "pass": providers_error == 0,
            "observed": providers_error,
            "threshold": 0,
        },
        {
            "id": "COMMON_WINDOW",
            "pass": common_days >= min_common_days,
            "observed": common_days,
            "threshold": min_common_days,
        },
        {
            "id": "LATEST_CLOSE_DISPERSION",
            "pass": latest_dispersion <= max_latest_dispersion_pct,
            "observed": latest_dispersion,
            "threshold": max_latest_dispersion_pct,
        },
        {
            "id": "WINDOW_CLOSE_DISPERSION",
            "pass": max_dispersion <= max_window_dispersion_pct,
            "observed": max_dispersion,
            "threshold": max_window_dispersion_pct,
        },
        {
            "id": "NO_SIGNAL_BOUNDARY",
            "pass": boundary.get("trading_signal") is False and boundary.get("advice") is False,
            "observed": boundary,
            "threshold": "trading_signal=false and advice=false",
        },
    ]
    passed = sum(1 for c in checks if c["pass"])
    failed = [c for c in checks if not c["pass"]]

    if failed:
        decision = "reject"
        verdict = "FIELD_NOT_ADMISSIBLE"
        next_test = "Do not test POC/FVG/timeframe claims until feed robustness is repaired."
    else:
        decision = "test"
        verdict = "FIELD_ADMISSIBLE_FOR_NEXT_HYPOTHESIS"
        next_test = (
            "Define one mechanical POC/FVG/timeframe observable with matched "
            "null; do not promote any price direction."
        )

    generated_at = _utc_now()
    claim_id = f"btc_feed_robustness_gate_{latest_common_date or generated_at[:10]}"
    return {
        "schema": "dndlab.bitcoin.first_hypothesis.v1",
        "generated_at": generated_at,
        "domain": "bitcoin-regime-lab",
        "input_artifact": str(input_path),
        "summary": {
            "observe": 0,
            "watch": 0,
            "test": 1 if decision == "test" else 0,
            "reject": 1 if decision == "reject" else 0,
            "trading_signal": False,
        },
        "cards": [
            {
                "claim_id": claim_id,
                "title": "First BTC hypothesis — daily feed robustness gate",
                "claim": (
                    "The daily BTC field is admissible for the next falsifiable "
                    "POC/FVG/timeframe test only if exchange feeds agree within "
                    "predeclared dispersion thresholds."
                ),
                "decision": decision,
                "verdict": verdict,
                "evidence": (
                    f"{providers_ok} providers ok, {providers_error} provider errors, "
                    f"{common_days} common days, latest close dispersion "
                    f"{latest_dispersion}%, max window dispersion {max_dispersion}%."
                ),
                "baseline": "single-feed interpretation is the naive baseline and is not admissible for promotion.",
                "null": "feed_robustness_null: if event labels or closes materially diverge across feeds, downgrade the field before testing price-level methods.",
                "checks": checks,
                "boundary": (
                    "No trading signal: this only decides whether the data field "
                    "is admissible for the next hypothesis test."
                ),
                "next_test": next_test,
            }
        ],
        "metrics": {
            "checks_passed": passed,
            "checks_total": len(checks),
            "providers_ok": providers_ok,
            "providers_error": providers_error,
            "common_days_compared": common_days,
            "latest_close_dispersion_pct": latest_dispersion,
            "max_close_dispersion_pct": max_dispersion,
            "latest_common_date": latest_common_date,
        },
        "boundary": {
            "public_claim": False,
            "trading_signal": False,
            "operational": False,
            "advice": False,
        },
    }


def write_artifact(payload: dict[str, Any]) -> dict[str, str]:
    VALUE_DIR.mkdir(parents=True, exist_ok=True)
    latest = VALUE_DIR / "btc_first_hypothesis_latest.json"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stamped = VALUE_DIR / f"btc_first_hypothesis_{stamp}.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    latest.write_text(text + "\n", encoding="utf-8")
    stamped.write_text(text + "\n", encoding="utf-8")
    return {"latest": str(latest), "stamped": str(stamped)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build first BTC falsifiable hypothesis card.")
    parser.add_argument("--input", default=str(EXCHANGE_LATEST), help="Path to btc_exchange_ohlcv_latest.json")
    parser.add_argument("--min-providers", type=int, default=3)
    parser.add_argument("--min-common-days", type=int, default=30)
    parser.add_argument("--max-latest-dispersion-pct", type=float, default=0.5)
    parser.add_argument("--max-window-dispersion-pct", type=float, default=0.75)
    parser.add_argument("--write", action="store_true", help="Write under data/bitcoin-regime-lab/value/")
    parser.add_argument("--json", action="store_true", help="Print JSON payload.")
    args = parser.parse_args()

    payload = build_hypothesis_card(
        input_path=Path(args.input),
        min_providers=args.min_providers,
        min_common_days=args.min_common_days,
        max_latest_dispersion_pct=args.max_latest_dispersion_pct,
        max_window_dispersion_pct=args.max_window_dispersion_pct,
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
