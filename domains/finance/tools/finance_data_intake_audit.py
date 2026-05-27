#!/usr/bin/env python3
"""Audit Finance Lab market-data intake for autonomy readiness.

Read-only: no fetch, no detector, no trading decision. It inspects cached
market data, latest diagnostics and value artifacts to decide whether the data
surface is enough for the current autonomy stage.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA = "dndlab.finance.data_intake_audit.value.v1"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


ROOT = repo_root()
CACHE_DIR = ROOT / "data" / "finance" / "market_cache"
DIAGNOSTIC_DIR = ROOT / "data" / "finance" / "diagnostics"
VALUE_DIR = ROOT / "data" / "finance" / "value"


def rel(path: Path | None) -> str | None:
    if not path:
        return None
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def latest(pattern: str, directory: Path) -> Path | None:
    files = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def load_json(path: Path | None) -> dict[str, Any] | None:
    if not path or not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def parse_cache_file(path: Path) -> dict[str, Any]:
    data = load_json(path) or {}
    card = data.get("data_card") if isinstance(data.get("data_card"), dict) else {}
    return {
        "path": rel(path),
        "provider": data.get("provider") or card.get("provider") or "unknown",
        "symbol": data.get("symbol") or card.get("symbol_resolved") or "unknown",
        "interval": data.get("interval") or "unknown",
        "first_date": card.get("first_date"),
        "last_date": card.get("last_date"),
        "n_obs": data.get("n_obs") or card.get("n_obs") or len(data.get("close") or []),
        "retrieval_ts": card.get("retrieval_ts"),
        "source_url": card.get("source_url"),
        "frequency": card.get("frequency"),
        "note": card.get("note"),
        "has_volume": bool(data.get("volume")),
        "ohl_proxy": bool(card.get("note") and "OHL impostati = close" in str(card.get("note"))),
    }


def cache_inventory() -> dict[str, Any]:
    rows = [parse_cache_file(path) for path in sorted(CACHE_DIR.glob("*.json"))] if CACHE_DIR.exists() else []
    providers = Counter(str(row["provider"]) for row in rows)
    intervals = Counter(str(row["interval"]) for row in rows)
    symbols = sorted({str(row["symbol"]).upper() for row in rows if row.get("symbol")})
    latest_dates = sorted({str(row["last_date"]) for row in rows if row.get("last_date")})
    return {
        "cache_file_count": len(rows),
        "providers": dict(sorted(providers.items())),
        "intervals": dict(sorted(intervals.items())),
        "symbols": symbols,
        "latest_market_dates": latest_dates[-10:],
        "rows": rows,
    }


def diagnostic_surface() -> dict[str, Any]:
    transfer_path = latest("finance_transfer_diagnostic_*.json", DIAGNOSTIC_DIR)
    recurrence_path = latest("finance_recurrence_diagnostic_*.json", DIAGNOSTIC_DIR)
    transfer = load_json(transfer_path) or {}
    recurrence = load_json(recurrence_path) or {}
    transfer_rows = transfer.get("rows") if isinstance(transfer.get("rows"), list) else []
    recurrence_rows = recurrence.get("rows") if isinstance(recurrence.get("rows"), list) else []
    transfer_cards = [row.get("data_card") for row in transfer_rows if isinstance(row.get("data_card"), dict)]
    recurrence_cards = [row.get("data_card") for row in recurrence_rows if isinstance(row.get("data_card"), dict)]
    return {
        "latest_transfer": rel(transfer_path),
        "latest_transfer_label": (transfer.get("classification") or {}).get("label"),
        "latest_transfer_window": {
            "start": transfer.get("start"),
            "end": transfer.get("end"),
        },
        "latest_transfer_rows": len(transfer_rows),
        "latest_transfer_data_cards": len(transfer_cards),
        "latest_transfer_review_required": [
            row.get("symbol")
            for row in transfer_rows
            if row.get("status") != "OK"
        ],
        "latest_recurrence": rel(recurrence_path),
        "latest_recurrence_label": (recurrence.get("classification") or {}).get("label"),
        "latest_recurrence_rows": len(recurrence_rows),
        "latest_recurrence_data_cards": len(recurrence_cards),
    }


def stale_or_lagging_dates(latest_dates: list[str]) -> bool:
    if not latest_dates:
        return True
    last = latest_dates[-1]
    today = datetime.now(UTC).date()
    try:
        d = datetime.fromisoformat(last).date()
    except ValueError:
        return True
    return (today - d).days > 7


def build_payload() -> dict[str, Any]:
    inventory = cache_inventory()
    diagnostics = diagnostic_surface()
    autonomy = load_json(VALUE_DIR / "finance_autonomous_trading_contract_latest.json") or {}
    scout = load_json(VALUE_DIR / "finance_autonomy_opportunity_scout_latest.json") or {}
    autonomy_summary = autonomy.get("summary") if isinstance(autonomy.get("summary"), dict) else {}
    scout_summary = scout.get("summary") if isinstance(scout.get("summary"), dict) else {}

    providers = set(inventory["providers"].keys())
    intervals = set(inventory["intervals"].keys())
    symbols = set(inventory["symbols"])
    latest_dates = inventory["latest_market_dates"]

    checks: list[dict[str, Any]] = []

    def check(id_: str, status: str, detail: str, metric: Any = None) -> None:
        checks.append({"id": id_, "status": status, "detail": detail, "metric": metric})

    check("DATA_01_CACHE_PRESENT", "PASS" if inventory["cache_file_count"] > 0 else "FAIL",
          f"{inventory['cache_file_count']} cache files", inventory["cache_file_count"])
    check("DATA_02_DATA_CARDS_PRESENT", "PASS" if diagnostics["latest_transfer_data_cards"] else "FAIL",
          f"{diagnostics['latest_transfer_data_cards']}/{diagnostics['latest_transfer_rows']} latest transfer rows with cards",
          diagnostics["latest_transfer_data_cards"])
    check("DATA_03_PROVIDER_DIVERSITY", "WARN" if providers == {"yfinance"} else "PASS",
          f"providers={sorted(providers)}", sorted(providers))
    check("DATA_04_DAILY_ONLY", "WARN" if intervals <= {"1d"} else "PASS",
          f"intervals={sorted(intervals)}", sorted(intervals))
    check("DATA_05_SYMBOL_BREADTH", "PASS" if len(symbols) >= 6 else "WARN",
          f"{len(symbols)} cached symbols", len(symbols))
    check("DATA_06_FRESHNESS", "WARN" if stale_or_lagging_dates(latest_dates) else "PASS",
          f"latest market dates={latest_dates[-3:]}", latest_dates[-3:])
    check("DATA_07_NO_REVIEW_ROWS", "PASS" if not diagnostics["latest_transfer_review_required"] else "FAIL",
          f"review_required={diagnostics['latest_transfer_review_required']}",
          diagnostics["latest_transfer_review_required"])
    crypto_proxy = any(row.get("ohl_proxy") for row in inventory["rows"])
    real_crypto_ohlc = any(
        row.get("provider") == "coinbase"
        and str(row.get("symbol", "")).upper() in {"BTC-USD", "ETH-USD"}
        and row.get("n_obs", 0) >= 30
        for row in inventory["rows"]
    )
    crypto_status = "PASS" if real_crypto_ohlc else "WARN" if crypto_proxy else "PASS"
    crypto_detail = (
        "Coinbase crypto OHLCV present"
        if real_crypto_ohlc
        else "CoinGecko cache uses close-as-OHL proxy"
        if crypto_proxy
        else "no close-as-OHL proxy detected"
    )
    check("DATA_08_CRYPTO_OHLC", crypto_status, crypto_detail,
          {"close_as_ohl_proxy": crypto_proxy, "real_crypto_ohlc": real_crypto_ohlc})
    check("DATA_09_AUTONOMY_STAGE_MATCH", "PASS" if autonomy_summary.get("current_stage") == "diagnostic_only" else "WARN",
          f"stage={autonomy_summary.get('current_stage')}", autonomy_summary.get("current_stage"))
    check("DATA_10_SCOUT_HAS_NEXT_INQUIRY", "PASS" if scout_summary.get("selected_opportunity") else "WARN",
          f"selected={scout_summary.get('selected_opportunity')}", scout_summary.get("selected_opportunity"))

    failures = [row for row in checks if row["status"] == "FAIL"]
    warnings = [row for row in checks if row["status"] == "WARN"]
    status = "fail" if failures else "warn" if warnings else "pass"

    improvements = [
        {
            "id": "multi_provider_crosscheck",
            "priority": "high",
            "why": "yfinance is sufficient for diagnostic prototypes but weak as sole authority for autonomous trading.",
            "proposal": "Add a second OHLCV provider adapter and require same-window close/date agreement before paper/live-sim.",
        },
        {
            "id": "freshness_manifest",
            "priority": "high",
            "why": "The Lab has cached data, but no first-class freshness manifest per symbol/window.",
            "proposal": "Write a daily data intake manifest with provider, last market date, n_obs, gaps and cache age.",
        },
        {
            "id": "intraday_and_execution_context",
            "priority": "medium",
            "why": "Daily bars can discover candidates, but paper/live-sim needs entry/exit basis, costs and slippage.",
            "proposal": "Add optional intraday/sandbox feed only after a robust daily candidate exists.",
        },
        {
            "id": "crypto_real_ohlc",
            "priority": "medium" if not real_crypto_ohlc else "low",
            "why": "CoinGecko market_chart close-only data is not enough for OHLC-sensitive trading rules.",
            "proposal": (
                "Use Coinbase Exchange OHLCV for crypto candidates and keep CoinGecko as broad reference."
                if real_crypto_ohlc
                else "Use exchange OHLCV via a reviewed adapter for crypto candidates; keep CoinGecko as broad reference."
            ),
        },
        {
            "id": "corporate_action_and_calendar_guard",
            "priority": "medium",
            "why": "Adjusted yfinance bars help, but autonomous testing needs explicit exchange calendar and adjustment readback.",
            "proposal": "Add calendar/gap/adjustment checks to the intake manifest.",
        },
    ]

    stage_fit = (
        "sufficient_for_diagnostic_candidate_discovery"
        if status in {"pass", "warn"} and diagnostics["latest_transfer_data_cards"]
        else "not_sufficient_for_current_diagnostic"
    )
    if autonomy_summary.get("paper_live_sim_allowed"):
        stage_fit = "insufficient_for_paper_live_sim_without_execution_context"

    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(UTC).isoformat(),
        "domain": "finance",
        "summary": {
            "status": status,
            "stage_fit": stage_fit,
            "current_autonomy_stage": autonomy_summary.get("current_stage"),
            "selected_opportunity": scout_summary.get("selected_opportunity"),
            "cache_file_count": inventory["cache_file_count"],
            "providers": sorted(providers),
            "intervals": sorted(intervals),
            "symbol_count": len(symbols),
            "latest_transfer_label": diagnostics["latest_transfer_label"],
            "warnings": len(warnings),
            "failures": len(failures),
        },
        "checks": checks,
        "failures": failures,
        "warnings": warnings,
        "inventory": {
            key: value for key, value in inventory.items() if key != "rows"
        },
        "diagnostics": diagnostics,
        "improvements": improvements,
        "cards": [
            {
                "claim_id": "finance_data_intake_stage_fit",
                "title": "Finance data intake stage fit",
                "decision": "watch" if status == "warn" else "observe" if status == "pass" else "repair",
                "evidence": f"providers={len(providers)}; symbols={len(symbols)}; interval={','.join(sorted(intervals))}; status={status}",
                "boundary": "Data is enough for diagnostic discovery, not enough for autonomous paper/live-sim or broker execution.",
            },
            {
                "claim_id": "finance_data_intake_improvements",
                "title": "Data intake improvements",
                "decision": "test",
                "evidence": "multi-provider crosscheck and freshness manifest are the first high-priority upgrades.",
                "boundary": "Improving data intake does not create a trading candidate by itself.",
            },
        ],
    }


def write_payload(payload: dict[str, Any]) -> dict[str, str]:
    VALUE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    stamped = VALUE_DIR / f"finance_data_intake_audit_{stamp}.json"
    latest_path = VALUE_DIR / "finance_data_intake_audit_latest.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    stamped.write_text(text, encoding="utf-8")
    latest_path.write_text(text, encoding="utf-8")
    return {"stamped": rel(stamped) or str(stamped), "latest": rel(latest_path) or str(latest_path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = build_payload()
    if args.write:
        payload["written"] = write_payload(payload)
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"status": "ok", "written": payload.get("written")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
