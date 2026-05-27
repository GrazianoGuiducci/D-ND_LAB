#!/usr/bin/env python3
"""External macro provider probe for the Finance Lab.

This cycle is used only after price-derived objects have failed. It fetches
public FRED graph CSV series, converts levels into daily changes, and runs the
same ordered-vs-shuffle plus block-preserving null families used by the real
market transfer diagnostics.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from exp_regime_shift import run_experiment  # noqa: E402
from finance_transfer_diagnostic import finite, null_stats  # noqa: E402


SCHEMA = "dndlab.finance.external_macro_probe.v1"
FRED_GRAPH_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"
DEFAULT_SERIES = ["DGS10", "DGS2", "T10Y2Y", "DFF", "VIXCLS"]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


ROOT = repo_root()
VALUE_DIR = ROOT / "data" / "finance" / "value"
PROBE_DIR = ROOT / "data" / "finance" / "external_macro_probe"


def rel(path: Path | None) -> str | None:
    if not path:
        return None
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def fetch_fred_series(series_id: str, *, start: str, end: str, timeout: float) -> dict[str, Any]:
    url = f"{FRED_GRAPH_CSV}?id={series_id}"
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(url, headers={"User-Agent": "D-ND-Lab/1.0 finance macro probe"})
        response.raise_for_status()
    reader = csv.DictReader(io.StringIO(response.text))
    dates: list[str] = []
    values: list[float] = []
    for row in reader:
        date = row.get("observation_date") or row.get("DATE") or row.get("date")
        raw = row.get(series_id)
        if not date or raw in {None, "", "."}:
            continue
        if date < start or date > end:
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        if not math.isfinite(value):
            continue
        dates.append(date)
        values.append(value)
    if len(values) < 64:
        raise RuntimeError(f"insufficient FRED observations for {series_id}: {len(values)}")
    arr = np.asarray(values, dtype=float)
    changes = np.diff(arr)
    return {
        "series": series_id,
        "dates": dates,
        "levels": arr,
        "changes": changes,
        "data_card": {
            "provider": "fred_graph_csv",
            "symbol_resolved": series_id,
            "source_url": url,
            "license": "FRED public graph CSV; verify redistribution rights for publication",
            "frequency": "daily_or_business_daily",
            "first_date": dates[0],
            "last_date": dates[-1],
            "n_obs": len(dates),
            "retrieval_ts": datetime.now(UTC).isoformat(),
            "object_kind": "external_macro_daily_level_change",
        },
    }


def run_series(series_id: str, *, start: str, end: str, seed: int, shuffles: int, timeout: float) -> dict[str, Any]:
    try:
        fetched = fetch_fred_series(series_id, start=start, end=end, timeout=timeout)
        changes = np.asarray(fetched["changes"], dtype=float)
        meta = fetched["data_card"]
        iid = run_experiment(shuffles=shuffles, seed=seed, real_returns=changes, real_meta=meta)
        block5 = null_stats(changes, seed=seed + 7005, shuffles=shuffles, block=5)
        block21 = null_stats(changes, seed=seed + 7021, shuffles=shuffles, block=21)
        robust = all(item["verdict"] == "DND_DELTA" for item in ({"verdict": iid["verdict"]}, block5, block21))
        return {
            "series": series_id,
            "status": "OK",
            "requested_start": start,
            "requested_end": end,
            "actual_start": meta.get("first_date"),
            "actual_end": meta.get("last_date"),
            "n": int(iid["n"]),
            "iid": {
                "verdict": iid["verdict"],
                "effect_z": finite(float(iid["effect_z"])),
                "ordered": finite(float(iid["ordered"])),
                "shuffle_mean": finite(float(iid["shuffle_mean"])),
                "shuffle_std": finite(float(iid["shuffle_std"])),
            },
            "block5": block5,
            "block21": block21,
            "robust_all_nulls": robust,
            "partial_confirmations": sum(
                item["verdict"] == "DND_DELTA"
                for item in ({"verdict": iid["verdict"]}, block5, block21)
            ),
            "var_95": finite(float(iid["var_95"])),
            "realized_vol": finite(float(iid["realized_vol"])),
            "data_card": meta,
        }
    except Exception as exc:
        return {
            "series": series_id,
            "status": "REVIEW_REQUIRED",
            "requested_start": start,
            "requested_end": end,
            "error": str(exc),
        }


def classify(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok_rows = [row for row in rows if row.get("status") == "OK"]
    review_rows = [row for row in rows if row.get("status") != "OK"]
    robust = [row["series"] for row in ok_rows if row.get("robust_all_nulls")]
    partial = [row["series"] for row in ok_rows if row.get("partial_confirmations", 0) > 0 and not row.get("robust_all_nulls")]
    if robust:
        label = "external_macro_probe_candidate"
        decision = "requires_recurrence_and_provider_review"
    elif ok_rows:
        label = "no_external_macro_delta"
        decision = "declare_no_current_edge_or_add_new_provider"
    else:
        label = "external_macro_provider_review_required"
        decision = "repair_or_replace_external_macro_provider"
    return {
        "label": label,
        "decision": decision,
        "ok_series": [row["series"] for row in ok_rows],
        "review_required_series": [row["series"] for row in review_rows],
        "robust_all_null_series": robust,
        "partial_series": partial,
        "operational": False,
        "public_claim": False,
        "trading_signal": False,
    }


def build_payload(series: list[str], *, start: str, end: str, seed: int, shuffles: int, timeout: float) -> dict[str, Any]:
    rows = [
        run_series(series_id, start=start, end=end, seed=seed + idx * 100, shuffles=shuffles, timeout=timeout)
        for idx, series_id in enumerate(series)
    ]
    classification = classify(rows)
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(UTC).isoformat(),
        "domain": "finance",
        "intent": "Probe whether a genuinely external macro provider offers a candidate after price-derived objects fail.",
        "start": start,
        "end": end,
        "seed": seed,
        "shuffles": shuffles,
        "series": series,
        "rows": rows,
        "classification": classification,
        "boundary": {
            "public_advice": False,
            "paper_live_sim_allowed": False,
            "broker_sandbox_allowed": False,
            "real_execution_allowed": False,
        },
        "cards": [
            {
                "claim_id": "finance_external_macro_probe",
                "title": "External macro provider probe",
                "decision": classification["decision"],
                "evidence": (
                    f"label={classification['label']}; "
                    f"robust={len(classification['robust_all_null_series'])}; "
                    f"partial={len(classification['partial_series'])}; "
                    f"review={len(classification['review_required_series'])}"
                ),
                "boundary": "Provider/object probe only; not public advice, paper simulation or trading signal.",
            }
        ],
    }


def write_outputs(payload: dict[str, Any]) -> dict[str, str]:
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    PROBE_DIR.mkdir(parents=True, exist_ok=True)
    VALUE_DIR.mkdir(parents=True, exist_ok=True)
    probe_path = PROBE_DIR / f"finance_external_macro_probe_{stamp}.json"
    value_path = VALUE_DIR / f"finance_external_macro_probe_{stamp}.json"
    latest_path = VALUE_DIR / "finance_external_macro_probe_latest.json"
    files = {"probe": rel(probe_path) or str(probe_path), "value": rel(value_path) or str(value_path), "latest": rel(latest_path) or str(latest_path)}
    payload["files"] = files
    text = json.dumps(payload, indent=2)
    probe_path.write_text(text + "\n")
    value_path.write_text(text + "\n")
    latest_path.write_text(text + "\n")
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--series", default=",".join(DEFAULT_SERIES))
    parser.add_argument("--start", default="2025-05-27")
    parser.add_argument("--end", default="2026-05-27")
    parser.add_argument("--seed", type=int, default=5271320)
    parser.add_argument("--shuffles", type=int, default=1024)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    series = [item.strip().upper() for item in args.series.split(",") if item.strip()]
    payload = build_payload(series, start=args.start, end=args.end, seed=args.seed, shuffles=args.shuffles, timeout=args.timeout)
    if args.write:
        payload["files"] = write_outputs(payload)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        summary = payload["classification"]
        print(f"{summary['label']} robust={summary['robust_all_null_series']} partial={summary['partial_series']} review={summary['review_required_series']}")


if __name__ == "__main__":
    main()
