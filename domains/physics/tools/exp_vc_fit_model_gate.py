#!/usr/bin/env python3
"""
Fit simple V_c scale models only after the fit-ready denominator gate.

The input is the fit-ready scale table. This tool does not recompute spectra.
It compares small two-parameter model families on rows whose denominator is
complete or contaminated, and reports broken rows as excluded mass.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


ADMISSIBLE_STATES = {"complete", "contaminated"}


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def variance(values: list[float]) -> float:
    mu = mean(values)
    return sum((value - mu) ** 2 for value in values)


def fit_line(xs: list[float], ys: list[float]) -> tuple[float, float, list[float]]:
    x_mean = mean(xs)
    y_mean = mean(ys)
    denom = sum((x - x_mean) ** 2 for x in xs)
    if denom == 0:
        intercept = y_mean
        slope = 0.0
    else:
        slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denom
        intercept = y_mean - slope * x_mean
    predictions = [intercept + slope * x for x in xs]
    return intercept, slope, predictions


def leave_one_out(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    errors: list[float] = []
    for index in range(len(xs)):
        train_xs = [x for i, x in enumerate(xs) if i != index]
        train_ys = [y for i, y in enumerate(ys) if i != index]
        intercept, slope, _ = fit_line(train_xs, train_ys)
        predicted = intercept + slope * xs[index]
        errors.append((ys[index] - predicted) ** 2)
    return sum(errors) / len(errors)


def transform_x(name: str, n_value: float) -> float:
    if name == "linear_N":
        return n_value
    if name == "log_N":
        return math.log(n_value)
    if name == "inv_sqrt_N":
        return 1.0 / math.sqrt(n_value)
    if name == "inv_N":
        return 1.0 / n_value
    if name == "power_to_zero":
        return math.log(n_value)
    raise ValueError(f"unknown model {name}")


def fit_model(name: str, points: list[list[float]]) -> dict:
    ns = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    if name == "power_to_zero":
        if any(y <= 0 for y in ys):
            return {"model": name, "fit_status": "invalid_nonpositive_y"}
        fit_ys = [math.log(y) for y in ys]
    else:
        fit_ys = ys

    xs = [transform_x(name, n_value) for n_value in ns]
    intercept, slope, transformed_predictions = fit_line(xs, fit_ys)
    if name == "power_to_zero":
        predictions = [math.exp(value) for value in transformed_predictions]
    else:
        predictions = transformed_predictions

    residuals = [y - pred for y, pred in zip(ys, predictions)]
    rss = sum(value * value for value in residuals)
    tss = variance(ys)
    n = len(points)
    k = 2
    aic = n * math.log(max(rss / n, 1e-15)) + 2 * k
    aicc = aic + (2 * k * (k + 1)) / max(n - k - 1, 1)
    return {
        "model": name,
        "fit_status": "ok",
        "intercept": intercept,
        "slope": slope,
        "rss": rss,
        "aicc": aicc,
        "r2": None if tss == 0 else 1.0 - (rss / tss),
        "loocv_mse": leave_one_out(xs, ys if name != "power_to_zero" else fit_ys),
        "predictions": [[int(n_value), pred] for n_value, pred in zip(ns, predictions)],
    }


def unit_limit_check(points: list[list[float]]) -> dict:
    below = [point for point in points if float(point[1]) < 1.0]
    return {
        "last_value": float(points[-1][1]) if points else None,
        "below_unit_count": len(below),
        "below_unit_N": [int(point[0]) for point in below],
        "unit_limit_status": "violated_in_observed_window" if below else "not_violated",
    }


def summarize_row(row: dict) -> dict:
    points = row.get("fit_points", [])
    model_names = ["linear_N", "log_N", "inv_sqrt_N", "inv_N", "power_to_zero"]
    fits = [fit_model(name, points) for name in model_names]
    ok_fits = [fit for fit in fits if fit.get("fit_status") == "ok"]
    best = min(ok_fits, key=lambda fit: fit["aicc"]) if ok_fits else None
    second = sorted(ok_fits, key=lambda fit: fit["aicc"])[1] if len(ok_fits) > 1 else None
    delta_aicc = None if not best or not second else second["aicc"] - best["aicc"]
    return {
        "level": row["level"],
        "class_threshold": row["class_threshold"],
        "denominator_state": row["denominator_state"],
        "fit_ready_rows": row["fit_ready_rows"],
        "total_rows": row["total_rows"],
        "excluded_rows": row["excluded_rows"],
        "fit_points": points,
        "unit_limit_check": unit_limit_check(points),
        "best_model": None if not best else best["model"],
        "delta_aicc_to_second": delta_aicc,
        "model_fits": fits,
    }


def run(args: argparse.Namespace) -> dict:
    source = Path(args.input)
    data = json.loads(source.read_text(encoding="utf-8"))
    rows = data.get("rows", [])
    admissible = [
        row for row in rows if row.get("denominator_state") in ADMISSIBLE_STATES
    ]
    excluded = [
        row for row in rows if row.get("denominator_state") not in ADMISSIBLE_STATES
    ]
    summaries = [summarize_row(row) for row in admissible if len(row.get("fit_points", [])) >= 3]

    best_index: dict[str, int] = {}
    for summary in summaries:
        best_index[summary["best_model"]] = best_index.get(summary["best_model"], 0) + 1

    ambiguous = [
        f"{summary['level']}:{summary['class_threshold']}"
        for summary in summaries
        if summary["delta_aicc_to_second"] is not None
        and summary["delta_aicc_to_second"] < args.min_delta_aicc
    ]

    unit_violations = [
        f"{summary['level']}:{summary['class_threshold']}"
        for summary in summaries
        if summary["unit_limit_check"]["unit_limit_status"] == "violated_in_observed_window"
    ]

    return {
        "experiment": "vc_fit_model_gate",
        "input": str(source),
        "contract": {
            "admissible_states": sorted(ADMISSIBLE_STATES),
            "excluded_states": sorted(
                set(row.get("denominator_state", "unknown") for row in excluded)
            ),
            "model_families": [
                "a+b*N",
                "a+b*log(N)",
                "a+b/sqrt(N)",
                "a+b/N",
                "c*N^b with zero asymptote",
            ],
            "min_delta_aicc_for_unique_family": args.min_delta_aicc,
        },
        "counts": {
            "input_rows": len(rows),
            "admissible_rows": len(admissible),
            "excluded_rows": len(excluded),
            "fit_summaries": len(summaries),
        },
        "excluded_by_state": [
            {
                "level": row["level"],
                "class_threshold": row["class_threshold"],
                "denominator_state": row["denominator_state"],
                "fit_ready_rows": row["fit_ready_rows"],
                "total_rows": row["total_rows"],
                "excluded_rows": row["excluded_rows"],
            }
            for row in excluded
        ],
        "best_model_index": dict(sorted(best_index.items())),
        "ambiguous_model_rows": sorted(ambiguous),
        "unit_limit_violations": sorted(unit_violations),
        "summaries": summaries,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--min-delta-aicc", type=float, default=2.0)
    args = parser.parse_args()

    output = run(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "experiment": output["experiment"],
                "counts": output["counts"],
                "best_model_index": output["best_model_index"],
                "ambiguous_model_rows": output["ambiguous_model_rows"],
                "unit_limit_violations": output["unit_limit_violations"],
                "out": str(out),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
