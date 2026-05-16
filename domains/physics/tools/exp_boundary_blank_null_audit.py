#!/usr/bin/env python3
"""
exp_boundary_blank_null_audit.py

Targeted null/surrogate audit for BOUNDARY prescan blank rows.

The global boundary shuffle audit is a historical deposit. This tool does not
rewrite it; it creates an extra row-aligned null audit for selected blank
domains so the denominator prescan can decide whether blank -> transfers,
blank -> falls, or blank remains blank.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from dnd_autoricerca import _genera_variante, genera_segnale


R_GUE = 0.5307
R_POISSON = 2 * math.log(2) - 1
DEFAULT_DOMAINS = ("zeta_zeros", "pendolo_doppio")


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def normalized_spacings(signal: np.ndarray, metadata: dict[str, Any]) -> np.ndarray:
    values = np.asarray(signal, dtype=float)
    values = values[np.isfinite(values)]
    if metadata.get("is_spacings"):
        spacings = values[values > 0]
    else:
        spacings = np.diff(np.sort(values))
        spacings = spacings[spacings > 0]
    if len(spacings) == 0:
        return spacings
    mu = float(np.mean(spacings))
    return spacings / mu if mu > 0 else np.array([])


def r_statistic(spacings: np.ndarray) -> float:
    if len(spacings) < 2:
        return float("nan")
    left = spacings[:-1]
    right = spacings[1:]
    denom = np.maximum(left, right)
    valid = denom > 0
    if not np.any(valid):
        return float("nan")
    ratios = np.minimum(left[valid], right[valid]) / denom[valid]
    return float(np.mean(ratios))


def classify_r(value: float) -> str:
    if not finite_number(value):
        return "absent"
    return "GUE" if abs(value - R_GUE) < abs(value - R_POISSON) else "Poisson"


def generate_domain_signal(domain: str) -> tuple[np.ndarray, dict[str, Any]]:
    if "_var_" not in domain:
        return genera_segnale(domain)

    base, raw_value = domain.rsplit("_var_", 1)
    try:
        value: Any = float(raw_value)
    except ValueError:
        value = raw_value

    if base == "logistica_biforcazione":
        signal, metadata = _genera_variante(base, {"r_override": value})
    elif base == "zeta_zeros":
        signal, metadata = _genera_variante(base, {"n_zeros": int(value)})
    elif base == "numeri_primi":
        signal, metadata = _genera_variante(base, {"max_n": int(value)})
    elif base == "cellular_automata":
        signal, metadata = _genera_variante(base, {"rule_number": int(value)})
    else:
        signal, metadata = _genera_variante(base, {"param": value})

    metadata = {**metadata, "dominio": domain, "variant_base": base, "variant_value": value}
    return signal, metadata


def audit_domain(domain: str, n_shuffle: int, rng: np.random.Generator) -> dict[str, Any]:
    signal, metadata = generate_domain_signal(domain)
    spacings = normalized_spacings(signal, metadata)
    r_original = r_statistic(spacings)

    shuffled = []
    for _ in range(n_shuffle):
        shuffled.append(r_statistic(rng.permutation(spacings)))
    shuffled_arr = np.asarray(shuffled, dtype=float)
    shuffled_arr = shuffled_arr[np.isfinite(shuffled_arr)]

    if len(shuffled_arr) == 0 or not finite_number(r_original):
        return {
            "domain": domain,
            "error": "insufficient finite spacing/null values",
            "n_gaps": int(len(spacings)),
        }

    mean = float(np.mean(shuffled_arr))
    std = float(np.std(shuffled_arr))
    z_score = 0.0 if std <= 1e-12 else float((r_original - mean) / std)
    class_original = classify_r(r_original)
    class_shuffled = classify_r(mean)

    return {
        "domain": domain,
        "r_original": round(float(r_original), 6),
        "r_shuffled_mean": round(mean, 6),
        "r_shuffled_std": round(std, 6),
        "z_score": round(z_score, 6),
        "n_shuffle": int(n_shuffle),
        "n_gaps": int(len(spacings)),
        "class_original": class_original,
        "class_shuffled": class_shuffled,
        "class_changes": class_original != class_shuffled,
        "ordering_dependent": abs(z_score) > 3.0,
        "source": {
            "generator": "dnd_autoricerca.genera_segnale",
            "metadata": metadata,
            "null": "marginal-preserving spacing permutation",
        },
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    rng = np.random.default_rng(args.seed)
    domains = args.domains or list(DEFAULT_DOMAINS)
    results = {
        domain: audit_domain(domain, args.n_shuffle, rng)
        for domain in domains
    }
    output = {
        "experiment": "boundary_blank_null_audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "n_shuffle": args.n_shuffle,
        "reference": {
            "R_GUE": R_GUE,
            "R_Poisson": R_POISSON,
        },
        "domains": results,
        "summary": {
            "domains": domains,
            "ready": [
                domain for domain, row in results.items()
                if "error" not in row and finite_number(row.get("z_score"))
            ],
            "errors": [
                domain for domain, row in results.items()
                if "error" in row
            ],
        },
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"wrote={out}")
    for domain, row in results.items():
        if "error" in row:
            print(f"{domain}\tERROR\t{row['error']}")
            continue
        print(
            f"{domain}\tn={row['n_gaps']}\tr={row['r_original']:.6f}\t"
            f"shuffle={row['r_shuffled_mean']:.6f}\tz={row['z_score']:.2f}\t"
            f"{row['class_original']}->{row['class_shuffled']}"
        )
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domains", nargs="*", default=list(DEFAULT_DOMAINS))
    parser.add_argument("--n-shuffle", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=202605091430)
    parser.add_argument("--out", default="tools/data/boundary_blank_null_audit_20260509.json")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
