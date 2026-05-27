#!/usr/bin/env python3
"""Lag-memory review for Finance scout partials.

The standard orientation/null family keeps finding local windows that fail
recurrence. This tool tests the latest partial scout rows with a different,
pre-existing Finance idea: lag-memory profile contrast. It runs rolling
windows and reports whether any candidate survives as a recurring lag-memory
object. It does not authorize paper, sandbox or orders.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lag_memory_precondition import area_gap_at, rolling_scale, shuffled  # noqa: E402
from market_data import fetch  # noqa: E402


SCHEMA = "dndlab.finance.lag_memory_candidate_review.value.v1"
NULL_FAMILIES = ("iid_shuffle", "circular_block_5", "circular_block_21")
FRACTIONS = np.arange(0.20, 0.81, 0.05)
Z_PROMOTE = 3.0
P_PROMOTE = 0.05


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


ROOT = repo_root()
VALUE_DIR = ROOT / "data" / "finance" / "value"
REVIEW_DIR = ROOT / "data" / "finance" / "lag_memory_review"


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


def finite(value: float) -> float | None:
    return value if math.isfinite(value) else None


def autocorr(values: np.ndarray, lag: int) -> float:
    if len(values) <= lag + 3:
        return 0.0
    x = values[:-lag]
    y = values[lag:]
    sx = float(np.std(x, ddof=1))
    sy = float(np.std(y, ddof=1))
    if sx <= 0 or sy <= 0 or not math.isfinite(sx) or not math.isfinite(sy):
        return 0.0
    return float(np.mean((x - np.mean(x)) * (y - np.mean(y))) / (sx * sy))


def dynamic_window(n: int) -> int:
    return max(20, min(100, n // 5))


def matched_filter_score_at_dynamic(returns: np.ndarray, split_fraction: float) -> float:
    z = returns / rolling_scale(returns)
    width = dynamic_window(len(z))
    split = int(round(len(returns) * split_fraction))
    split = max(width, min(len(z) - width, split))
    left = z[split - width:split]
    right = z[split:split + width]
    lag1_delta = autocorr(right, 1) - autocorr(left, 1)
    lag2_delta = autocorr(right, 2) - autocorr(left, 2)
    return max(lag1_delta, 0.0) + max(-lag2_delta, 0.0)


def split_profile_dynamic(returns: np.ndarray) -> np.ndarray:
    return np.asarray([matched_filter_score_at_dynamic(returns, float(frac)) for frac in FRACTIONS], dtype=float)


def make_cluster(start: int, end: int, values: list[float]) -> dict[str, Any]:
    return {
        "start_index": start,
        "end_index": end,
        "start_fraction": float(FRACTIONS[start]),
        "end_fraction": float(FRACTIONS[end]),
        "length": end - start + 1,
        "mass": float(sum(v - Z_PROMOTE for v in values)),
        "peak_z": float(max(values)),
        "endpoint_touch": start == 0 or end == len(FRACTIONS) - 1,
        "endpoint_adjacent": start <= 1 or end >= len(FRACTIONS) - 2,
    }


def clusterize(z_profile: np.ndarray) -> list[dict[str, Any]]:
    clusters: list[dict[str, Any]] = []
    start: int | None = None
    values: list[float] = []
    for idx, value in enumerate(z_profile):
        if value >= Z_PROMOTE:
            if start is None:
                start = idx
                values = []
            values.append(float(value))
        elif start is not None:
            clusters.append(make_cluster(start, idx - 1, values))
            start = None
            values = []
    if start is not None:
        clusters.append(make_cluster(start, len(z_profile) - 1, values))
    return clusters


def best_cluster(clusters: list[dict[str, Any]]) -> dict[str, Any] | None:
    filtered = [row for row in clusters if not row.get("endpoint_touch") and not row.get("endpoint_adjacent")]
    return max(filtered, key=lambda row: (float(row["mass"]), float(row["peak_z"]))) if filtered else None


def profile_stats(ordered_profile: np.ndarray, null_profiles: np.ndarray) -> dict[str, Any]:
    split_mean = np.mean(null_profiles, axis=0)
    split_std = np.std(null_profiles, axis=0, ddof=1)
    split_std = np.where(split_std > 0, split_std, np.inf)
    ordered_z = (ordered_profile - split_mean) / split_std
    ordered_cluster = best_cluster(clusterize(ordered_z))
    ordered_mass = float(ordered_cluster["mass"]) if ordered_cluster else 0.0
    null_masses = []
    for row in null_profiles:
        row_z = (row - split_mean) / split_std
        cluster = best_cluster(clusterize(row_z))
        null_masses.append(float(cluster["mass"]) if cluster else 0.0)
    null_arr = np.asarray(null_masses, dtype=float)
    null_mean = float(np.mean(null_arr))
    null_std = float(np.std(null_arr, ddof=1))
    effect_z = (ordered_mass - null_mean) / null_std if null_std > 0 else 0.0
    p_value = float((1 + np.sum(null_arr >= ordered_mass)) / (len(null_arr) + 1))
    return {
        "cluster_effect_z": finite(float(effect_z)),
        "cluster_p_value": finite(p_value),
        "best_cluster_non_endpoint": ordered_cluster,
        "verdict": "DND_DELTA" if ordered_cluster and effect_z >= Z_PROMOTE and p_value <= P_PROMOTE else "NO_DELTA",
    }


def seed_for(seed: int, symbol: str, window_label: str, null_name: str) -> int:
    return abs(hash((seed, symbol, window_label, null_name))) % (2 ** 32)


def review_window(symbol: str, provider: str, start: str, end: str, *, label: str, seed: int, shuffles: int) -> dict[str, Any]:
    try:
        data = fetch(provider, symbol, start=start, end=end, interval="1d")
        returns = np.asarray(data["returns"], dtype=float)
        if len(returns) < 60:
            raise RuntimeError(f"not enough returns for lag review: {len(returns)}")
        ordered_profile = split_profile_dynamic(returns)
        null_results = {}
        for null_name in NULL_FAMILIES:
            rng = np.random.default_rng(seed_for(seed, symbol, label, null_name))
            null_profiles = np.asarray(
                [split_profile_dynamic(shuffled(returns, rng, null_name)) for _ in range(shuffles)],
                dtype=float,
            )
            null_results[null_name] = profile_stats(ordered_profile, null_profiles)
        robust = all(result["verdict"] == "DND_DELTA" for result in null_results.values())
        card = data.get("data_card") or {}
        best = max(
            (r.get("best_cluster_non_endpoint") for r in null_results.values() if r.get("best_cluster_non_endpoint")),
            key=lambda r: (float(r["mass"]), float(r["peak_z"])),
            default=None,
        )
        return {
            "label": label,
            "symbol": symbol,
            "provider": provider,
            "status": "OK",
            "requested_start": start,
            "requested_end": end,
            "actual_start": card.get("first_date"),
            "actual_end": card.get("last_date"),
            "n": len(returns),
            "dynamic_match_window": dynamic_window(len(returns)),
            "score_midpoint": finite(float(matched_filter_score_at_dynamic(returns, 0.5))),
            "area_gap_midpoint": finite(float(area_gap_at(returns, 0.5))),
            "null_results": null_results,
            "robust_all_lag_nulls": robust,
            "best_cluster": best,
            "data_card": card,
        }
    except Exception as exc:
        return {
            "label": label,
            "symbol": symbol,
            "provider": provider,
            "status": "REVIEW_REQUIRED",
            "requested_start": start,
            "requested_end": end,
            "error": str(exc),
        }


def rolling_windows(start: str, end: str, *, step_days: int, count: int) -> list[dict[str, str]]:
    start_dt = datetime.fromisoformat(start).date()
    end_dt = datetime.fromisoformat(end).date()
    width = (end_dt - start_dt).days
    windows = []
    for idx in range(count):
        shifted_end = end_dt - timedelta(days=idx * step_days)
        shifted_start = shifted_end - timedelta(days=width)
        windows.append({
            "label": "anchor" if idx == 0 else f"prev_step_{idx}",
            "start": shifted_start.isoformat(),
            "end": shifted_end.isoformat(),
        })
    return windows


def latest_partial_candidates(limit: int) -> list[dict[str, Any]]:
    scout = load_json(VALUE_DIR / "finance_window_universe_scout_latest.json") or {}
    summary = scout.get("summary") if isinstance(scout.get("summary"), dict) else {}
    selected = summary.get("selected_for_crosscheck")
    if not isinstance(selected, list):
        return []
    out = [
        row for row in selected
        if isinstance(row, dict) and row.get("partial_confirmations", 0) > 0 and not row.get("robust_all_nulls")
    ]
    return out[:limit]


def review_candidate(candidate: dict[str, Any], *, seed: int, shuffles: int, step_days: int, count: int) -> dict[str, Any]:
    symbol = str(candidate["symbol"]).upper()
    provider = str(candidate.get("provider") or "yfinance")
    windows = rolling_windows(str(candidate["start"]), str(candidate["end"]), step_days=step_days, count=count)
    rows = [
        review_window(symbol, provider, window["start"], window["end"], label=window["label"], seed=seed + idx, shuffles=shuffles)
        for idx, window in enumerate(windows)
    ]
    robust_windows = [row["label"] for row in rows if row.get("robust_all_lag_nulls")]
    review_windows = [row["label"] for row in rows if row.get("status") != "OK"]
    if len(robust_windows) >= 2:
        label = "lag_recurring_candidate"
        decision = "prepare_lag_paper_design_inputs"
    elif robust_windows:
        label = "lag_local_candidate"
        decision = "redesign_lag_window_or_object"
    elif review_windows:
        label = "lag_review_required"
        decision = "repair_data_before_lag_review"
    else:
        label = "no_lag_memory_candidate"
        decision = "change_market_object_or_mechanism"
    return {
        "symbol": symbol,
        "source_candidate": candidate,
        "windows": windows,
        "rows": rows,
        "classification": {
            "label": label,
            "decision": decision,
            "robust_windows": robust_windows,
            "review_windows": review_windows,
            "paper_live_sim_allowed": False,
            "broker_sandbox_allowed": False,
            "real_execution_allowed": False,
        },
    }


def build_payload(candidates: list[dict[str, Any]], *, seed: int, shuffles: int, step_days: int, count: int) -> dict[str, Any]:
    results = [
        review_candidate(candidate, seed=seed, shuffles=shuffles, step_days=step_days, count=count)
        for candidate in candidates
    ]
    recurring = [r["symbol"] for r in results if r["classification"]["label"] == "lag_recurring_candidate"]
    local = [r["symbol"] for r in results if r["classification"]["label"] == "lag_local_candidate"]
    review = [r["symbol"] for r in results if r["classification"]["label"] == "lag_review_required"]
    if recurring:
        label = "lag_recurring_candidate_found"
        decision = "prepare_inactive_lag_paper_inputs"
        next_gate = "Design cost/slippage/risk and inactive ledger before any paper run."
    elif local:
        label = "lag_local_only"
        decision = "redesign_lag_window_or_object"
        next_gate = "Do not run paper; lag-memory also appears local."
    elif review:
        label = "lag_review_required"
        decision = "repair_data_before_lag_review"
        next_gate = "Resolve review rows before interpreting lag-memory candidates."
    else:
        label = "no_lag_memory_candidate"
        decision = "change_market_object_or_mechanism"
        next_gate = "Partial orientation rows did not survive alternate lag-memory null review."
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(UTC).isoformat(),
        "domain": "finance",
        "intent": "Review scout partial rows under a different lag-memory null family before spending more recurrence cycles.",
        "summary": {
            "label": label,
            "decision": decision,
            "candidates": [str(c.get("symbol")).upper() for c in candidates],
            "recurring_symbols": recurring,
            "local_symbols": local,
            "review_symbols": review,
            "paper_live_sim_allowed": False,
            "broker_sandbox_allowed": False,
            "real_execution_allowed": False,
            "next_gate": next_gate,
        },
        "parameters": {
            "seed": seed,
            "shuffles": shuffles,
            "step_days": step_days,
            "window_count": count,
            "null_families": list(NULL_FAMILIES),
        },
        "candidate_results": results,
        "boundary": {
            "operational": False,
            "public_claim": False,
            "trading_signal": False,
            "paper_live_sim": False,
        },
        "sources": {
            "window_universe_scout": rel(VALUE_DIR / "finance_window_universe_scout_latest.json"),
            "precondition_contract": rel(ROOT / "domains" / "finance" / "precondition_contract.json"),
        },
        "cards": [
            {
                "claim_id": "finance_lag_memory_candidate_review",
                "title": "Finance lag-memory candidate review",
                "decision": decision,
                "evidence": f"label={label}; recurring={len(recurring)}; local={len(local)}; review={len(review)}",
                "boundary": "Alternate null-family review; no paper/live-sim or execution is authorized.",
            }
        ],
    }


def write_payload(payload: dict[str, Any]) -> dict[str, str]:
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    VALUE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    artifact = REVIEW_DIR / f"finance_lag_memory_candidate_review_{stamp}.json"
    stamped = VALUE_DIR / f"finance_lag_memory_candidate_review_{stamp}.json"
    latest = VALUE_DIR / "finance_lag_memory_candidate_review_latest.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    artifact.write_text(text, encoding="utf-8")
    stamped.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    return {
        "artifact": rel(artifact) or str(artifact),
        "stamped": rel(stamped) or str(stamped),
        "latest": rel(latest) or str(latest),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", help="comma-separated symbols; default latest scout partial rows")
    parser.add_argument("--candidate-limit", type=int, default=6)
    parser.add_argument("--seed", type=int, default=242)
    parser.add_argument("--shuffles", type=int, default=128)
    parser.add_argument("--step-days", type=int, default=45)
    parser.add_argument("--window-count", type=int, default=5)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    candidates = latest_partial_candidates(args.candidate_limit)
    if args.symbols:
        wanted = {item.strip().upper() for item in args.symbols.split(",") if item.strip()}
        candidates = [row for row in candidates if str(row.get("symbol", "")).upper() in wanted]
    payload = build_payload(
        candidates,
        seed=args.seed,
        shuffles=args.shuffles,
        step_days=args.step_days,
        count=args.window_count,
    )
    if args.write:
        payload["written"] = write_payload(payload)
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"status": "ok", "written": payload.get("written")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
