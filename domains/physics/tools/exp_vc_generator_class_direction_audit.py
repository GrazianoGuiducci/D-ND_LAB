#!/usr/bin/env python3
"""
Class-conditional direction audit for the V_c generator gate.

This tool does not recompute spectra. It reads a JSON deposit produced by
exp_vc_nonsturmian_label_null_gate.py and asks whether V_c scale behavior is
legible only after source_mode is typed into generator classes.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

VC_DEFINED_EVENTS = {"internal_cross", "internal_multi"}


def generator_class(source_mode: str) -> str:
    if source_mode == "phi_sturmian":
        return "reference_order"
    if source_mode.startswith("block_shuffle_"):
        return "order_memory"
    if source_mode.startswith("periodic_approximant_"):
        return "periodic_closure"
    if source_mode in {"balanced_random", "markov_density"}:
        return "random_dispersion"
    return "untyped"


def safe_median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(median(values))


def event_rates(rows: list[dict]) -> dict:
    counts = Counter(row["event"] for row in rows)
    total = len(rows)
    vc_defined_rows = [row for row in rows if row.get("event") in VC_DEFINED_EVENTS]
    fit_ready_rows = [row for row in vc_defined_rows if row.get("vc_interp") is not None]
    out = {"rows": total, "events": dict(sorted(counts.items()))}
    for event, count in sorted(counts.items()):
        out[f"{event}_rate"] = count / total if total else None
    out["vc_defined_rows"] = len(vc_defined_rows)
    out["fit_ready_rows"] = len(fit_ready_rows)
    out["excluded_rows"] = total - len(vc_defined_rows)
    out["fit_ready_rate"] = len(fit_ready_rows) / total if total else None
    out["excluded_rate"] = (total - len(vc_defined_rows)) / total if total else None
    out["vc_missing_after_defined_rows"] = len(vc_defined_rows) - len(fit_ready_rows)
    return out


def slope_by_n(points: list[tuple[int, float]]) -> float | None:
    if len(points) < 2:
        return None
    points = sorted(points)
    x_mean = sum(n for n, _ in points) / len(points)
    y_mean = sum(value for _, value in points) / len(points)
    denom = sum((n - x_mean) ** 2 for n, _ in points)
    if denom == 0:
        return None
    return float(sum((n - x_mean) * (value - y_mean) for n, value in points) / denom)


def summarize_rows(rows: list[dict]) -> dict:
    grouped: dict[tuple[int, str, float], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(int(row["N"]), generator_class(row["source_mode"]), float(row["r_threshold"]))].append(row)

    by_n_class_threshold = {}
    trend_points: dict[tuple[str, float], list[tuple[int, float]]] = defaultdict(list)
    rate_points: dict[tuple[str, float, str], list[tuple[int, float]]] = defaultdict(list)

    for (n, klass, threshold), group in sorted(grouped.items()):
        vc_values = [row["vc_interp"] for row in group if row.get("vc_interp") is not None]
        summary = {
            **event_rates(group),
            "vc_median": safe_median(vc_values),
            "label_jaccard_median": safe_median([float(row["label_jaccard"]) for row in group]),
            "hamming_ratio_median": safe_median([float(row["hamming_ratio"]) for row in group]),
        }
        by_n_class_threshold[f"N{n}:{klass}:r{threshold:g}"] = summary
        if summary["vc_median"] is not None:
            trend_points[(klass, threshold)].append((n, summary["vc_median"]))
        for event in ("internal_cross", "internal_multi", "no_cross", "floor_hit"):
            rate = summary.get(f"{event}_rate")
            if rate is not None:
                rate_points[(klass, threshold, event)].append((n, float(rate)))

    trends = {}
    for key, points in sorted(trend_points.items()):
        klass, threshold = key
        values = [value for _, value in sorted(points)]
        trends[f"{klass}:r{threshold:g}:vc_median"] = {
            "points": [[n, value] for n, value in sorted(points)],
            "delta_first_last": float(values[-1] - values[0]) if len(values) >= 2 else None,
            "slope_per_N": slope_by_n(points),
        }

    rate_trends = {}
    for key, points in sorted(rate_points.items()):
        klass, threshold, event = key
        values = [value for _, value in sorted(points)]
        rate_trends[f"{klass}:r{threshold:g}:{event}_rate"] = {
            "points": [[n, value] for n, value in sorted(points)],
            "delta_first_last": float(values[-1] - values[0]) if len(values) >= 2 else None,
        }

    return {
        "by_n_class_threshold": by_n_class_threshold,
        "vc_trends": trends,
        "event_rate_trends": rate_trends,
        "fit_ready": summarize_fit_ready(rows),
    }


def summarize_fit_ready(rows: list[dict]) -> dict:
    """Build the explicit fit-ready contract.

    V_c is not a neutral missing value: it only exists for event rows whose
    event type preserves a crossing. The fit table therefore separates
    fit-ready mass from excluded mass before any scale curve is read.
    """
    grouped: dict[tuple[str, float], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(generator_class(row["source_mode"]), float(row["r_threshold"]))].append(row)

    by_class_threshold = {}
    for (klass, threshold), group in sorted(grouped.items()):
        by_n: dict[int, list[dict]] = defaultdict(list)
        for row in group:
            by_n[int(row["N"])].append(row)

        n_summary = {}
        fit_points = []
        excluded_events_total = Counter()
        event_counts_total = Counter(row["event"] for row in group)
        for n, n_rows in sorted(by_n.items()):
            fit_rows = [
                row for row in n_rows
                if row.get("event") in VC_DEFINED_EVENTS and row.get("vc_interp") is not None
            ]
            excluded_rows = [row for row in n_rows if row.get("event") not in VC_DEFINED_EVENTS]
            missing_rows = [
                row for row in n_rows
                if row.get("event") in VC_DEFINED_EVENTS and row.get("vc_interp") is None
            ]
            excluded_events = Counter(row["event"] for row in excluded_rows)
            excluded_events_total.update(excluded_events)
            vc_median = safe_median([row["vc_interp"] for row in fit_rows])
            if vc_median is not None:
                fit_points.append((n, vc_median))
            n_summary[f"N{n}"] = {
                "rows": len(n_rows),
                "fit_ready_rows": len(fit_rows),
                "excluded_rows": len(excluded_rows),
                "vc_missing_after_defined_rows": len(missing_rows),
                "fit_ready_rate": len(fit_rows) / len(n_rows) if n_rows else None,
                "excluded_events": dict(sorted(excluded_events.items())),
                "vc_median_fit_ready": vc_median,
            }

        values = [value for _, value in sorted(fit_points)]
        by_class_threshold[f"{klass}:r{threshold:g}"] = {
            "event_counts": dict(sorted(event_counts_total.items())),
            "excluded_events": dict(sorted(excluded_events_total.items())),
            "by_N": n_summary,
            "fit_points": [[n, value] for n, value in sorted(fit_points)],
            "fit_delta_first_last": float(values[-1] - values[0]) if len(values) >= 2 else None,
            "fit_slope_per_N": slope_by_n(fit_points),
        }

    return {
        "contract": {
            "vc_defined": "event in {internal_cross, internal_multi}",
            "fit_ready": "vc_defined and vc_interp is not null",
            "excluded_mass": "event outside {internal_cross, internal_multi}; report as excluded, not as neutral missing data",
        },
        "by_class_threshold": by_class_threshold,
    }


def run(args: argparse.Namespace) -> dict:
    source = Path(args.input)
    data = json.loads(source.read_text(encoding="utf-8"))
    event_rows = data.get("event_rows", [])
    accepted_event_rows = data.get("accepted_event_rows", [])

    return {
        "experiment": "vc_generator_class_direction_audit",
        "input": str(source),
        "parameters": vars(args),
        "vc_defined_contract": {
            "vc_defined_events": sorted(VC_DEFINED_EVENTS),
            "vc_defined": "event in {internal_cross, internal_multi}",
            "fit_ready": "vc_defined and vc_interp is not null",
            "excluded_mass_policy": "Keep no_cross/floor_hit outside fit denominators and report them as excluded mass.",
        },
        "per_mode_best": summarize_rows(event_rows),
        "accepted_candidates": summarize_rows(accepted_event_rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    output = run(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")

    compact = {
        "experiment": output["experiment"],
        "input": output["input"],
        "vc_defined_contract": output["vc_defined_contract"],
        "per_mode_best_vc_trends": output["per_mode_best"]["vc_trends"],
        "accepted_candidate_vc_trends": output["accepted_candidates"]["vc_trends"],
        "accepted_fit_ready": output["accepted_candidates"]["fit_ready"],
        "out": str(out),
    }
    print(json.dumps(compact, indent=2))


if __name__ == "__main__":
    main()
