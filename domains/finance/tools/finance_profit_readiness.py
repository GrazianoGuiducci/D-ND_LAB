#!/usr/bin/env python3
"""Profit-readiness readback for Finance Lab.

This tool aggregates the latest Finance value artifacts into one user-facing
state: whether the lab can start an internal paper/profit cycle, what blocks
it, and which autonomous investigation should run next. It never fetches
market data and never places orders.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA = "dndlab.finance.profit_readiness.value.v1"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


ROOT = repo_root()
VALUE_DIR = ROOT / "data" / "finance" / "value"


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


def list_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return []


def build_payload() -> dict[str, Any]:
    recurrence = summary("finance_recurrence_validation_cycle_latest.json")
    autonomy = summary("finance_autonomous_trading_contract_latest.json")
    scout = summary("finance_window_universe_scout_latest.json")
    candidate = summary("finance_candidate_discovery_cycle_latest.json")
    data = summary("finance_data_intake_audit_latest.json")
    health = summary("finance_operational_health_latest.json")

    selected_rows = scout.get("selected_for_crosscheck")
    selected_symbols = [
        str(row.get("symbol")).upper()
        for row in selected_rows
        if isinstance(row, dict) and row.get("symbol")
    ] if isinstance(selected_rows, list) else []
    robust_symbols = list_value(candidate.get("robust_all_null_symbols"))
    recurrence_candidates = list_value(recurrence.get("candidates"))
    recurring = list_value(recurrence.get("recurring_symbols"))
    single = list_value(recurrence.get("single_window_symbols"))
    candidates = recurrence_candidates or robust_symbols or selected_symbols

    paper_allowed = bool(
        recurrence.get("paper_live_sim_allowed") is True
        or autonomy.get("paper_live_sim_allowed") is True
    )
    sandbox_allowed = bool(autonomy.get("broker_sandbox_allowed") is True)
    real_allowed = bool(autonomy.get("real_execution_allowed") is True)
    recurrence_label = str(recurrence.get("label") or "missing")
    health_status = str(health.get("status") or autonomy.get("operational_health") or "missing")
    data_status = str(data.get("status") or "missing")
    provider_status = str(candidate.get("provider_crosscheck_status") or "missing")

    blocks: list[dict[str, str]] = []
    if data_status not in {"pass", "warn"}:
        blocks.append({
            "id": "data_not_ready",
            "label_it": "Dati non pronti",
            "label_en": "Data not ready",
            "detail_it": f"Stato data intake: {data_status}.",
            "detail_en": f"Data intake status: {data_status}.",
        })
    if provider_status != "pass":
        blocks.append({
            "id": "provider_crosscheck_not_pass",
            "label_it": "Provider non confermati",
            "label_en": "Providers not confirmed",
            "detail_it": f"Cross-check provider: {provider_status}.",
            "detail_en": f"Provider cross-check: {provider_status}.",
        })
    candidate_label = "/".join(candidates) if candidates else "i candidati"
    local_phrase_it = (
        f"{candidate_label} e' locale"
        if len(candidates) == 1
        else f"{candidate_label} sono locali"
    )
    local_phrase_en = (
        f"{candidate_label} is local"
        if len(candidates) == 1
        else f"{candidate_label} are local"
    )
    rolling_fail_it = (
        "non ha superato finestre rolling indipendenti"
        if len(candidates) == 1
        else "non hanno superato finestre rolling indipendenti"
    )
    rolling_fail_en = (
        "it did not survive independent rolling windows"
        if len(candidates) == 1
        else "they did not survive independent rolling windows"
    )

    if not recurring:
        blocks.append({
            "id": "recurrence_failed",
            "label_it": "Ricorrenza non dimostrata",
            "label_en": "Recurrence not proven",
            "detail_it": f"{local_phrase_it}: {rolling_fail_it}.",
            "detail_en": f"{local_phrase_en}: {rolling_fail_en}.",
        })
    if not paper_allowed:
        blocks.extend([
            {
                "id": "no_cost_slippage_model",
                "label_it": "Costi e slippage assenti",
                "label_en": "Missing cost/slippage model",
                "detail_it": "Manca un modello di costi prima del conto paper.",
                "detail_en": "A cost model is missing before any paper ledger.",
            },
            {
                "id": "no_paper_ledger",
                "label_it": "Ledger paper assente",
                "label_en": "Missing paper ledger",
                "detail_it": "Nessun registro paper ha ancora misurato profitto/perdita.",
                "detail_en": "No paper ledger has measured profit/loss yet.",
            },
            {
                "id": "no_risk_contract",
                "label_it": "Contratto rischio assente",
                "label_en": "Missing risk contract",
                "detail_it": "Mancano drawdown, size, stop e kill-switch del ciclo.",
                "detail_en": "Drawdown, size, stop and kill-switch are missing.",
            },
        ])
    if data_status == "warn":
        blocks.append({
            "id": "daily_only_data",
            "label_it": "Dati solo daily",
            "label_en": "Daily-only data",
            "detail_it": "Sufficiente per diagnostica, non per esecuzione fine.",
            "detail_en": "Enough for diagnostics, not fine execution.",
        })

    if real_allowed:
        status = "real_execution_ready"
        stage = "real_capital_execution"
    elif sandbox_allowed:
        status = "sandbox_ready"
        stage = "broker_sandbox"
    elif paper_allowed:
        status = "paper_ready"
        stage = "paper_live_sim"
    else:
        status = "not_ready"
        stage = "diagnostic_only"

    if status == "not_ready" and recurrence_label == "local_candidate_not_recurring":
        plain_it = f"Non pronto per profitto: {local_phrase_it}, i provider concordano, ma la ricorrenza non regge; niente paper."
        plain_en = f"Not ready for profit: {local_phrase_en}, providers agree, but recurrence fails; no paper."
        next_action = "auto_redesign_window_universe"
        next_it = "Ridisegnare automaticamente finestra/universo e rilanciare scout."
        next_en = "Automatically redesign window/universe and rerun the scout."
    elif status == "paper_ready":
        plain_it = "Pronto solo per design paper inattivo: nessuna esecuzione reale."
        plain_en = "Ready only for inactive paper design: no real execution."
        next_action = "prepare_inactive_paper_ledger"
        next_it = "Preparare ledger paper con costi, slippage e limiti rischio."
        next_en = "Prepare a paper ledger with costs, slippage and risk limits."
    else:
        plain_it = "Finance resta diagnostico: servono candidati ricorrenti prima del profit test."
        plain_en = "Finance remains diagnostic: recurring candidates are needed before a profit test."
        next_action = "run_scout_and_recurrence"
        next_it = "Rilanciare scout e validazione ricorrenza."
        next_en = "Rerun scout and recurrence validation."

    requirements = [
        {"id": "data_intake", "label_it": "Dati leggibili", "label_en": "Readable data", "passed": data_status in {"pass", "warn"}},
        {"id": "scout_candidate", "label_it": "Scout con candidato", "label_en": "Scout has candidate", "passed": bool(candidates)},
        {"id": "provider_crosscheck", "label_it": "Provider concordi", "label_en": "Provider agreement", "passed": provider_status == "pass"},
        {"id": "recurrence", "label_it": "Ricorrenza rolling", "label_en": "Rolling recurrence", "passed": bool(recurring)},
        {"id": "cost_slippage", "label_it": "Costi/slippage", "label_en": "Costs/slippage", "passed": paper_allowed},
        {"id": "risk_contract", "label_it": "Contratto rischio", "label_en": "Risk contract", "passed": sandbox_allowed or real_allowed},
        {"id": "paper_profit_ledger", "label_it": "Ledger profit paper", "label_en": "Paper profit ledger", "passed": sandbox_allowed or real_allowed},
        {"id": "reviewed_execution", "label_it": "Esecuzione revisionata", "label_en": "Reviewed execution", "passed": real_allowed},
    ]

    summary_payload = {
        "status": status,
        "stage": stage,
        "profit_state": "no_paper_profit_test" if not paper_allowed else "paper_design_allowed",
        "plain_status_it": plain_it,
        "plain_status_en": plain_en,
        "can_start_paper": paper_allowed,
        "can_start_sandbox": sandbox_allowed,
        "can_trade_real": real_allowed,
        "candidates": candidates,
        "recurring_symbols": recurring,
        "single_window_symbols": single,
        "primary_block": blocks[0]["id"] if blocks else None,
        "next_action": next_action,
        "next_action_plain_it": next_it,
        "next_action_plain_en": next_en,
        "data_status": data_status,
        "provider_status": provider_status,
        "recurrence_label": recurrence_label,
        "operational_health": health_status,
    }
    payload = {
        "schema": SCHEMA,
        "generated_at": datetime.now(UTC).isoformat(),
        "domain": "finance",
        "intent": "Make Finance profit/autonomy readiness explicit before paper, sandbox or execution stages.",
        "summary": summary_payload,
        "blocks": blocks,
        "profit_requirements": requirements,
        "sources": {
            "recurrence_validation": rel(VALUE_DIR / "finance_recurrence_validation_cycle_latest.json"),
            "autonomous_trading_contract": rel(VALUE_DIR / "finance_autonomous_trading_contract_latest.json"),
            "window_universe_scout": rel(VALUE_DIR / "finance_window_universe_scout_latest.json"),
            "candidate_discovery": rel(VALUE_DIR / "finance_candidate_discovery_cycle_latest.json"),
            "data_intake": rel(VALUE_DIR / "finance_data_intake_audit_latest.json"),
            "operational_health": rel(VALUE_DIR / "finance_operational_health_latest.json"),
        },
        "boundary": {
            "public_advice": False,
            "unreviewed_real_orders": False,
            "paper_live_sim_allowed": paper_allowed,
            "broker_sandbox_allowed": sandbox_allowed,
            "real_execution_allowed": real_allowed,
        },
        "cards": [
            {
                "claim_id": "finance_profit_readiness",
                "title": "Finance profit readiness",
                "decision": "advance" if paper_allowed else "redesign",
                "evidence": f"status={status}; candidates={','.join(candidates) or 'none'}; recurrence={recurrence_label}",
                "boundary": "Internal profit readiness only; no public advice or unreviewed real orders.",
            }
        ],
    }
    return payload


def write_payload(payload: dict[str, Any]) -> dict[str, str]:
    VALUE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    stamped = VALUE_DIR / f"finance_profit_readiness_{stamp}.json"
    latest = VALUE_DIR / "finance_profit_readiness_latest.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    stamped.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    return {"stamped": rel(stamped) or str(stamped), "latest": rel(latest) or str(latest)}


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
