#!/usr/bin/env python3
"""
exp_boundary_denominator_prescan.py

Boundary-oriented prescan for transferring the `denominator_state` gate beyond
V_c. The unit under test is not the GUE/Poisson label. The unit is the
domain/window row before a structural claim is allowed to use its observable.

Input deposits:
- tools/data/autoricerca_journal.json: base 13-domain GUE/Poisson perimeter.
- tools/data/boundary_shuffle_audit.json: available shuffle/null support.

Output:
- one row per base domain/window with source type, denominator_state,
  excluded_mass, observable, null/surrogate, and transfer verdict.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


DEFAULT_DOMAIN_KEY = {
    "numeri_primi": "primes",
    "random_matrix": "gue",
    "logistica_biforcazione": "logistic",
    "ising_2d": "ising_2d",
    "cellular_automata": "cell_auto",
    "brownian_motion": "brownian",
    "percolation": "percolation",
    "coupled_oscillators": "coupled_osc",
    "zeta_zeros": "zeta_zeros",
    "pendolo_doppio": "pendolo_doppio",
}


def is_base_cycle(value: Any) -> bool:
    if isinstance(value, int):
        return 1 <= value <= 13
    if isinstance(value, float):
        return value.is_integer() and 1 <= int(value) <= 13
    return False


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def load_json(path: Path) -> Any:
    with path.open() as f:
        return json.load(f)


def source_type(spacing: str | None) -> str:
    if spacing == "GUE-like":
        return "GUE"
    if spacing == "Poisson-like":
        return "Poisson"
    if spacing:
        return spacing
    return "absent"


def null_label(null_row: dict[str, Any] | None) -> str:
    if not null_row:
        return "absent"
    z = null_row.get("z_score")
    if finite_number(z):
        return f"shuffle z={float(z):.2f}; class_change={bool(null_row.get('class_changes'))}"
    return "shuffle present; z absent"


def classify_denominator(row: dict[str, Any], null_row: dict[str, Any] | None) -> tuple[str, float, str]:
    observable_defined = finite_number(row.get("spacing_r")) and row.get("spacing") in {
        "GUE-like",
        "Poisson-like",
    }
    if not observable_defined:
        return "absent", 1.0, "falls"

    if null_row is None:
        return "absent", 1.0, "blank"

    n_gaps = null_row.get("n_gaps")
    z = null_row.get("z_score")
    has_null = finite_number(n_gaps) and finite_number(z)
    if not has_null:
        return "broken", 1.0, "falls"

    excluded_mass = 0.0
    state = "complete"
    if int(n_gaps) < 500:
        state = "contaminated"
        excluded_mass = 1.0 - (float(n_gaps) / 500.0)

    return state, max(0.0, excluded_mass), "transfers"


def build_rows(autoricerca: list[dict[str, Any]], shuffle_audit: dict[str, Any]) -> list[dict[str, Any]]:
    base_rows = [row for row in autoricerca if is_base_cycle(row.get("ciclo"))]
    base_rows.sort(key=lambda row: int(row["ciclo"]))
    null_domains = shuffle_audit.get("domains", {})

    rows = []
    for row in base_rows:
        domain = row.get("dominio", "")
        null_key = DEFAULT_DOMAIN_KEY.get(domain, domain)
        null_row = null_domains.get(null_key)
        denominator_state, excluded_mass, transfer = classify_denominator(row, null_row)
        rows.append(
            {
                "domain_window": f"{domain}:cycle_{int(row['ciclo'])}",
                "domain": domain,
                "cycle": int(row["ciclo"]),
                "source_domain_type": source_type(row.get("spacing")),
                "denominator_state": denominator_state,
                "excluded_mass": round(excluded_mass, 6),
                "observable": {
                    "name": "spacing_r",
                    "defined": finite_number(row.get("spacing_r")),
                    "value": row.get("spacing_r"),
                    "label": row.get("spacing"),
                    "n_points": row.get("n_punti"),
                },
                "null_surrogate": {
                    "name": "shuffle_r_statistic",
                    "status": null_label(null_row),
                    "domain_key": null_key if null_row else None,
                    "n_gaps": null_row.get("n_gaps") if null_row else None,
                    "r_shuffled_mean": null_row.get("r_shuffled_mean") if null_row else None,
                    "z_score": null_row.get("z_score") if null_row else None,
                    "class_changes": null_row.get("class_changes") if null_row else None,
                },
                "transfer": transfer,
            }
        )
    return rows


def merge_extra_null_audit(shuffle_audit: dict[str, Any], extra_paths: list[str]) -> dict[str, Any]:
    merged = {
        **shuffle_audit,
        "domains": dict(shuffle_audit.get("domains", {})),
    }
    extras = []
    for raw_path in extra_paths:
        path = Path(raw_path)
        if not path.exists():
            continue
        data = load_json(path)
        domains = data.get("domains", {}) if isinstance(data, dict) else {}
        for domain, row in domains.items():
            if not isinstance(row, dict) or "error" in row:
                continue
            merged["domains"][domain] = row
        extras.append(str(path))
    if extras:
        merged["extra_null_audits"] = extras
    return merged


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_transfer: dict[str, int] = {}
    by_state: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for row in rows:
        by_transfer[row["transfer"]] = by_transfer.get(row["transfer"], 0) + 1
        by_state[row["denominator_state"]] = by_state.get(row["denominator_state"], 0) + 1
        by_type[row["source_domain_type"]] = by_type.get(row["source_domain_type"], 0) + 1
    return {
        "n_rows": len(rows),
        "by_transfer": by_transfer,
        "by_denominator_state": by_state,
        "by_source_domain_type": by_type,
        "transfer_scope": [
            row["domain_window"] for row in rows if row["transfer"] == "transfers"
        ],
        "blank_scope": [row["domain_window"] for row in rows if row["transfer"] == "blank"],
        "falls_scope": [row["domain_window"] for row in rows if row["transfer"] == "falls"],
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    autoricerca = load_json(Path(args.autoricerca))
    shuffle_audit = load_json(Path(args.shuffle_audit))
    if args.extra_null_audit:
        shuffle_audit = merge_extra_null_audit(shuffle_audit, args.extra_null_audit)
    rows = build_rows(autoricerca, shuffle_audit)
    output = {
        "experiment": "boundary_denominator_prescan",
        "question": "Does denominator_state transfer beyond V_c on the 8 GUE / 5 Poisson boundary perimeter?",
        "perimeter": "base autoricerca cycles 1..13: 8 GUE-like, 5 Poisson-like",
        "observable_contract": {
            "claim": "denominator_state gate transfer beyond V_c",
            "observable": "spacing_r label row with shuffle/null availability",
            "operator": "row-aligned domain/window prescan",
            "null": "boundary_shuffle_audit shuffle r-statistic when present",
            "non_possible": "claiming transfer where null/surrogate is absent",
            "extra_null_audits": shuffle_audit.get("extra_null_audits", []),
        },
        "summary": summarize(rows),
        "rows": rows,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(output, f, indent=2)

    print(f"wrote={out_path}")
    print(f"rows={output['summary']['n_rows']}")
    print(f"by_transfer={output['summary']['by_transfer']}")
    print(f"by_denominator_state={output['summary']['by_denominator_state']}")
    for row in rows:
        print(
            f"{row['domain_window']}\t{row['source_domain_type']}\t"
            f"{row['denominator_state']}\t{row['excluded_mass']:.3f}\t"
            f"{row['transfer']}\t{row['null_surrogate']['status']}"
        )
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--autoricerca", default="tools/data/autoricerca_journal.json")
    parser.add_argument("--shuffle-audit", default="tools/data/boundary_shuffle_audit.json")
    parser.add_argument("--extra-null-audit", action="append", default=[])
    parser.add_argument("--out", default="tools/data/boundary_denominator_prescan_20260509_1409.json")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
