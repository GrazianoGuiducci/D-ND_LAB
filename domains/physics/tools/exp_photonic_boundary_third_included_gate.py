#!/usr/bin/env python3
"""
Photonic boundary third-included gate.

This tool projects the GUE/Poisson boundary direction into a physical return:
a 1D dielectric multilayer. It does not classify the optical spectrum as GUE or
Poisson. It asks whether the boundary survives as an intermediate transmission
state between ordered metallic Sturmian stacks and balanced random stacks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np


PHI = (1 + np.sqrt(5)) / 2
SILVER = 1 + np.sqrt(2)
BRONZE = 1 + np.sqrt(3)


def sturmian_sequence(theta: float, n: int, phase: float) -> np.ndarray:
    idx = np.arange(n + 1, dtype=float)
    vals = np.floor(idx * theta + phase)
    return np.diff(vals).astype(int)


def periodic_sequence(n: int) -> np.ndarray:
    return (np.arange(n) % 2).astype(int)


def optical_transfer(seq: np.ndarray, wavelength: float, n_a: float, n_b: float) -> float:
    """Return a simple normal-incidence transmission proxy for fixed layers."""
    matrix = np.eye(2, dtype=complex)
    for symbol in seq:
        index = n_b if int(symbol) else n_a
        thickness = 1.0 / (4.0 * index)  # quarter-wave at lambda0=1
        phase = 2.0 * np.pi * index * thickness / wavelength
        layer = np.array(
            [
                [np.cos(phase), 1j * np.sin(phase) / index],
                [1j * index * np.sin(phase), np.cos(phase)],
            ],
            dtype=complex,
        )
        matrix = layer @ matrix
        norm = np.linalg.norm(matrix)
        if norm > 1e80:
            matrix = matrix / norm
    denom = abs(matrix[0, 0]) ** 2
    if denom <= 1e-300:
        return 1e6
    return float(min(1e6, 1.0 / denom))


def transmission_spectrum(seq: np.ndarray, wavelengths: np.ndarray, n_a: float, n_b: float) -> np.ndarray:
    return np.array([optical_transfer(seq, wl, n_a, n_b) for wl in wavelengths], dtype=float)


def peak_positions(values: np.ndarray, wavelengths: np.ndarray, quantile: float) -> np.ndarray:
    threshold = float(np.quantile(values, quantile))
    peaks = []
    for index in range(1, len(values) - 1):
        if values[index] >= threshold and values[index] >= values[index - 1] and values[index] >= values[index + 1]:
            peaks.append(float(wavelengths[index]))
    return np.array(peaks, dtype=float)


def r_statistic_from_positions(positions: np.ndarray) -> float | None:
    if len(positions) < 4:
        return None
    gaps = np.diff(np.sort(positions))
    gaps = gaps[gaps > 1e-12]
    if len(gaps) < 2:
        return None
    left = gaps[:-1]
    right = gaps[1:]
    return float(np.mean(np.minimum(left, right) / np.maximum(left, right)))


def spectral_entropy(values: np.ndarray) -> float:
    clipped = np.clip(values.astype(float), 0.0, None)
    total = float(np.sum(clipped))
    if total <= 0:
        return 0.0
    probs = clipped / total
    probs = probs[probs > 0]
    return float(-np.sum(probs * np.log(probs)) / np.log(len(values)))


def summarize_spectrum(values: np.ndarray, wavelengths: np.ndarray, peak_quantile: float) -> dict[str, Any]:
    peaks = peak_positions(values, wavelengths, peak_quantile)
    log_values = np.log10(np.clip(values, 1e-12, 1e6))
    return {
        "T_mean": float(np.mean(values)),
        "T_median": float(np.median(values)),
        "logT_mean": float(np.mean(log_values)),
        "logT_std": float(np.std(log_values)),
        "stopband_fraction": float(np.mean(values < 0.1)),
        "highband_fraction": float(np.mean(values > 1.0)),
        "spectral_entropy": spectral_entropy(values),
        "peak_count": int(len(peaks)),
        "peak_spacing_r": r_statistic_from_positions(peaks),
    }


def finite(values: list[float | None]) -> np.ndarray:
    return np.array([v for v in values if v is not None and np.isfinite(v)], dtype=float)


def aggregate(rows: list[dict[str, Any]], domain: str) -> dict[str, Any]:
    subset = [row for row in rows if row["domain"] == domain]
    out: dict[str, Any] = {"count": len(subset)}
    for key in [
        "T_mean",
        "T_median",
        "logT_mean",
        "logT_std",
        "stopband_fraction",
        "highband_fraction",
        "spectral_entropy",
        "peak_count",
        "peak_spacing_r",
    ]:
        arr = finite([row.get(key) for row in subset])
        if len(arr) == 0:
            out[key] = {"count": 0}
        else:
            out[key] = {
                "count": int(len(arr)),
                "median": float(np.median(arr)),
                "mean": float(np.mean(arr)),
                "min": float(np.min(arr)),
                "max": float(np.max(arr)),
            }
    return out


def median_metric(summary: dict[str, Any], domain: str, metric: str) -> float | None:
    value = summary.get(domain, {}).get(metric, {})
    median = value.get("median") if isinstance(value, dict) else None
    return float(median) if median is not None else None


def run(args: argparse.Namespace) -> dict[str, Any]:
    rng = np.random.default_rng(args.seed)
    ns = [int(part) for part in args.ns.split(",") if part.strip()]
    phases = [float(part) for part in args.phases.split(",") if part.strip()]
    wavelengths = np.linspace(args.wavelength_min, args.wavelength_max, args.wavelength_count)
    domains = {
        "phi": 1 / PHI,
        "silver": 1 / SILVER,
        "bronze": 1 / BRONZE,
    }

    rows: list[dict[str, Any]] = []
    for n in ns:
        for phase in phases:
            phi_seq = sturmian_sequence(1 / PHI, n, phase)
            ones = int(np.sum(phi_seq))
            for domain, theta in domains.items():
                seq = sturmian_sequence(theta, n, phase)
                values = transmission_spectrum(seq, wavelengths, args.n_a, args.n_b)
                rows.append({
                    "domain": domain,
                    "N": n,
                    "phase": phase,
                    "ones": int(np.sum(seq)),
                    **summarize_spectrum(values, wavelengths, args.peak_quantile),
                })

            seq = periodic_sequence(n)
            values = transmission_spectrum(seq, wavelengths, args.n_a, args.n_b)
            rows.append({
                "domain": "periodic_ab",
                "N": n,
                "phase": phase,
                "ones": int(np.sum(seq)),
                **summarize_spectrum(values, wavelengths, args.peak_quantile),
            })

            for trial in range(args.random_trials):
                seq = np.array([1] * ones + [0] * (n - ones), dtype=int)
                rng.shuffle(seq)
                values = transmission_spectrum(seq, wavelengths, args.n_a, args.n_b)
                rows.append({
                    "domain": "balanced_random_phi_density",
                    "trial": trial,
                    "N": n,
                    "phase": phase,
                    "ones": ones,
                    **summarize_spectrum(values, wavelengths, args.peak_quantile),
                })

    summary = {domain: aggregate(rows, domain) for domain in sorted({row["domain"] for row in rows})}
    phi_stop = median_metric(summary, "phi", "stopband_fraction")
    random_stop = median_metric(summary, "balanced_random_phi_density", "stopband_fraction")
    periodic_stop = median_metric(summary, "periodic_ab", "stopband_fraction")
    phi_entropy = median_metric(summary, "phi", "spectral_entropy")
    random_entropy = median_metric(summary, "balanced_random_phi_density", "spectral_entropy")
    periodic_entropy = median_metric(summary, "periodic_ab", "spectral_entropy")

    third_included = False
    if None not in (phi_stop, random_stop, periodic_stop, phi_entropy, random_entropy, periodic_entropy):
        between_stop = min(periodic_stop, random_stop) <= phi_stop <= max(periodic_stop, random_stop)
        between_entropy = min(periodic_entropy, random_entropy) <= phi_entropy <= max(periodic_entropy, random_entropy)
        separated_random = abs(phi_stop - random_stop) >= args.min_stopband_delta
        third_included = bool(between_stop and between_entropy and separated_random)

    return {
        "experiment": "photonic_boundary_third_included_gate",
        "parameters": {
            "ns": ns,
            "phases": phases,
            "wavelength_min": args.wavelength_min,
            "wavelength_max": args.wavelength_max,
            "wavelength_count": args.wavelength_count,
            "n_a": args.n_a,
            "n_b": args.n_b,
            "peak_quantile": args.peak_quantile,
            "random_trials": args.random_trials,
            "seed": args.seed,
            "min_stopband_delta": args.min_stopband_delta,
        },
        "observable_contract": {
            "claim": "photonic phi stack carries a boundary state between periodic order and balanced random disorder",
            "observable": "stopband_fraction, spectral_entropy, peak_spacing_r on wavelength transmission spectra",
            "operator": "fixed-quarter-wave transfer matrix scan",
            "denominator": "N x phase x generator rows with balanced random controls",
            "non_possible": "phi indistinguishable from balanced random or outside the periodic-random interval",
        },
        "classification": {
            "third_included_photonic_boundary": third_included,
            "phi_stopband_median": phi_stop,
            "random_stopband_median": random_stop,
            "periodic_stopband_median": periodic_stop,
            "phi_entropy_median": phi_entropy,
            "random_entropy_median": random_entropy,
            "periodic_entropy_median": periodic_entropy,
        },
        "summary": summary,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ns", default="55,89,144")
    parser.add_argument("--phases", default="0,0.25,0.5,0.75")
    parser.add_argument("--wavelength-min", type=float, default=0.65)
    parser.add_argument("--wavelength-max", type=float, default=1.85)
    parser.add_argument("--wavelength-count", type=int, default=241)
    parser.add_argument("--n-a", type=float, default=1.0)
    parser.add_argument("--n-b", type=float, default=1.7)
    parser.add_argument("--peak-quantile", type=float, default=0.70)
    parser.add_argument("--random-trials", type=int, default=12)
    parser.add_argument("--min-stopband-delta", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=202605151734)
    parser.add_argument("--out", default="tools/data/photonic_boundary_third_included_gate_20260515_1734.json")
    args = parser.parse_args()

    output = run(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(json.dumps({
        "classification": output["classification"],
        "summary_domains": {
            domain: {
                "count": row["count"],
                "stopband_fraction": row["stopband_fraction"],
                "spectral_entropy": row["spectral_entropy"],
                "peak_spacing_r": row["peak_spacing_r"],
            }
            for domain, row in output["summary"].items()
        },
        "out": str(out),
    }, indent=2))


if __name__ == "__main__":
    main()
