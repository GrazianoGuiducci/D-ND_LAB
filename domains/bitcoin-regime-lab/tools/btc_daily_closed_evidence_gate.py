#!/usr/bin/env python3
"""btc_daily_closed_evidence_gate.py - closed daily evidence gate for BTC Lab.

The gate distinguishes closed daily evidence from the current open daily candle.
It is a small policy-mutation guard: the Lab may refresh live context, but it
must not reinterpret LVN/FVG/timeframe policy from a partial daily candle.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


VERSION = "0.1.0"
DOMAIN = "bitcoin-regime-lab"
DOMAIN_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = DOMAIN_DIR.parents[1]
DATA_ROOT = Path(os.environ.get("LAB_DATA_DIR", REPO_ROOT / "data")).resolve()
DATA_DIR = DATA_ROOT / DOMAIN
VALUE_DIR = DATA_DIR / "value"

EXCHANGE_LATEST = VALUE_DIR / "btc_exchange_ohlcv_latest.json"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _series_common_dates(exchange: dict[str, Any]) -> list[date]:
    provider_sets: list[set[date]] = []
    for series in exchange.get("series") or []:
        if not isinstance(series, dict):
            continue
        candles = series.get("candles")
        if not isinstance(candles, list):
            continue
        dates = {_parse_date(c.get("date")) for c in candles if isinstance(c, dict)}
        clean = {d for d in dates if d is not None}
        if clean:
            provider_sets.append(clean)
    if not provider_sets:
        return []
    common = set.intersection(*provider_sets)
    return sorted(common)


def build_daily_closed_evidence_gate(now: datetime | None = None) -> dict[str, Any]:
    now = now or _utc_now()
    exchange = _read_json(EXCHANGE_LATEST)

    metrics = exchange.get("metrics") if isinstance(exchange.get("metrics"), dict) else {}
    common_dates = _series_common_dates(exchange)
    latest_common = _parse_date(metrics.get("latest_common_date")) or (common_dates[-1] if common_dates else None)
    today = now.date()
    open_daily_date = latest_common if latest_common and latest_common >= today else None
    closed_dates = [d for d in common_dates if d < today]
    latest_closed = closed_dates[-1] if closed_dates else None

    providers_ok = int(metrics.get("providers_ok") or 0)
    common_days = int(metrics.get("common_days_compared") or len(common_dates) or 0)
    dispersion = metrics.get("latest_close_dispersion_pct")

    enough_closed_denominator = providers_ok >= 3 and len(closed_dates) >= 30
    open_candle_excluded = bool(open_daily_date)
    closed_evidence_ready = bool(latest_closed and enough_closed_denominator)
    mutation_allowed = closed_evidence_ready and (latest_common is not None) and latest_common < today

    if mutation_allowed:
        decision = "ADMIT_CLOSED_DAILY_EVIDENCE"
        status = "test"
        next_action = "Closed daily evidence is fresh enough; downstream LVN/FVG/timeframe reinterpretation may read the latest closed common date."
    elif closed_evidence_ready:
        decision = "HOLD_OPEN_DAILY_CANDLE"
        status = "watch"
        next_action = "Refresh context may continue, but policy mutation must use the latest closed common date, not the current open daily candle."
    else:
        decision = "BLOCK_DAILY_REINTERPRETATION"
        status = "reject"
        next_action = "Repair daily feed denominator before policy mutation or reinterpretation."

    card = {
        "claim_id": "btc_daily_closed_evidence_gate",
        "title": "BTC daily closed evidence gate",
        "decision": status,
        "verdict": decision,
        "claim": "BTC Lab policy mutation must use closed daily evidence and exclude the current open daily candle.",
        "evidence": (
            f"latest_common_date={latest_common.isoformat() if latest_common else 'n/a'}; "
            f"latest_closed_common_date={latest_closed.isoformat() if latest_closed else 'n/a'}; "
            f"today_utc={today.isoformat()}; providers_ok={providers_ok}; "
            f"closed_common_days={len(closed_dates)}."
        ),
        "boundary": "Gate for Lab self-adjustment only: it does not create market orders, targets, entries, exits or advice.",
        "next_test": next_action,
    }

    return {
        "schema": "dndlab.bitcoin.daily_closed_evidence_gate.v1",
        "generated_at": now.isoformat(),
        "domain": DOMAIN,
        "version": VERSION,
        "intent": "Prevent BTC Lab policy mutation from using current open daily-candle noise as closed evidence.",
        "input_artifacts": {
            "exchange_ohlcv": str(EXCHANGE_LATEST),
        },
        "gate": {
            "decision": decision,
            "mutation_allowed": mutation_allowed,
            "closed_evidence_ready": closed_evidence_ready,
            "open_candle_excluded": open_candle_excluded,
            "today_utc": today.isoformat(),
            "latest_common_date": latest_common.isoformat() if latest_common else None,
            "open_daily_date": open_daily_date.isoformat() if open_daily_date else None,
            "latest_closed_common_date": latest_closed.isoformat() if latest_closed else None,
            "next_allowed_daily_date": (today + timedelta(days=1)).isoformat() if open_daily_date else today.isoformat(),
            "rule": "A daily artifact may update live context on the current UTC date, but policy mutation/reinterpretation must use the latest common provider date strictly before today UTC.",
        },
        "metrics": {
            "providers_ok": providers_ok,
            "common_days_compared": common_days,
            "closed_common_days": len(closed_dates),
            "latest_close_dispersion_pct": dispersion,
        },
        "summary": {
            "observe": 1 if exchange else 0,
            "watch": 1 if decision == "HOLD_OPEN_DAILY_CANDLE" else 0,
            "test": 1 if decision == "ADMIT_CLOSED_DAILY_EVIDENCE" else 0,
            "reject": 1 if decision == "BLOCK_DAILY_REINTERPRETATION" else 0,
            "trading_signal": False,
        },
        "cards": [card],
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
    latest = VALUE_DIR / "btc_daily_closed_evidence_gate_latest.json"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stamped = VALUE_DIR / f"btc_daily_closed_evidence_gate_{stamp}.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    latest.write_text(text + "\n", encoding="utf-8")
    stamped.write_text(text + "\n", encoding="utf-8")
    return {"latest": str(latest), "stamped": str(stamped)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build BTC daily closed-evidence gate artifact.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = build_daily_closed_evidence_gate()
    if args.write:
        payload["written"] = write_artifact(payload)
    print(json.dumps(payload, indent=2 if args.json else None, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
