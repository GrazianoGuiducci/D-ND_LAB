#!/usr/bin/env python3
"""Exact-window transfer diagnostic for the D-ND finance lab.

This tool turns a real-market transfer question into a checkable runtime
artifact. It is intentionally conservative: it writes data-card provenance,
keeps acquisition failures visible, and never promotes market or trading
claims from a single window.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from exp_regime_shift import cassini_residue, orientation_score, run_experiment  # noqa: E402
from market_data import fetch  # noqa: E402


DEFAULT_SYMBOLS = ["SPY", "QQQ", "IWM", "EFA", "TLT", "GLD", "BTC-USD"]
PRIMARY_EQUITY = {"SPY", "QQQ"}
CORRELATED_EQUITY = {"SPY", "QQQ", "IWM"}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_output_dir() -> Path:
    return repo_root() / "data" / "finance" / "diagnostics"


def finite(value: float) -> float | None:
    return value if math.isfinite(value) else None


def block_permute(returns: np.ndarray, block: int, rng: np.random.Generator) -> np.ndarray:
    if block <= 1:
        shuffled = returns.copy()
        rng.shuffle(shuffled)
        return shuffled
    chunks = [returns[i:i + block] for i in range(0, len(returns), block)]
    order = rng.permutation(len(chunks))
    return np.concatenate([chunks[i] for i in order])[: len(returns)]


def null_stats(
    returns: np.ndarray,
    *,
    seed: int,
    shuffles: int,
    block: int | None = None,
) -> dict[str, Any]:
    ordered = abs(orientation_score(returns))
    rng = np.random.default_rng(seed)
    scores = []
    cassini_scores = []
    for _ in range(shuffles):
        if block is None:
            sample = returns.copy()
            rng.shuffle(sample)
        else:
            sample = block_permute(returns, block, rng)
        scores.append(abs(orientation_score(sample)))
        cassini_scores.append(cassini_residue(sample))
    arr = np.asarray(scores, dtype=float)
    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1)) if shuffles > 1 else 0.0
    effect_z = (ordered - mean) / std if std > 0 else math.inf
    return {
        "ordered": finite(float(ordered)),
        "shuffle_mean": finite(mean),
        "shuffle_std": finite(std),
        "effect_z": finite(float(effect_z)),
        "verdict": "DND_DELTA" if effect_z > 3.0 and ordered > mean else "NO_DELTA",
        "cassini_residue": finite(float(cassini_residue(returns))),
        "shuffle_cassini_mean": finite(float(np.mean(cassini_scores))),
    }


def run_symbol(symbol: str, *, start: str, end: str, seed: int, shuffles: int) -> dict[str, Any]:
    try:
        data = fetch("yfinance", symbol, start=start, end=end)
        returns = np.asarray(data["returns"], dtype=float)
        iid = run_experiment(
            shuffles=shuffles,
            seed=seed,
            real_returns=returns,
            real_meta=data["data_card"],
        )
        block5 = null_stats(returns, seed=seed + 5005, shuffles=shuffles, block=5)
        block21 = null_stats(returns, seed=seed + 5021, shuffles=shuffles, block=21)
        card = iid.get("data_card") or {}
        return {
            "symbol": symbol,
            "provider": "yfinance",
            "status": "OK",
            "requested_start": start,
            "requested_end": end,
            "actual_start": card.get("first_date"),
            "actual_end": card.get("last_date"),
            "n": iid["n"],
            "seed": seed,
            "shuffles": shuffles,
            "iid": {
                "verdict": iid["verdict"],
                "effect_z": finite(float(iid["effect_z"])),
                "ordered": finite(float(iid["ordered"])),
                "shuffle_mean": finite(float(iid["shuffle_mean"])),
                "shuffle_std": finite(float(iid["shuffle_std"])),
            },
            "block5": block5,
            "block21": block21,
            "robust_all_nulls": all(
                item["verdict"] == "DND_DELTA"
                for item in ({"verdict": iid["verdict"]}, block5, block21)
            ),
            "var_95": finite(float(iid["var_95"])),
            "realized_vol": finite(float(iid["realized_vol"])),
            "cassini_residue": finite(float(iid["cassini_residue"])),
            "data_card": card,
        }
    except Exception as exc:  # keep acquisition failures visible in the artifact
        return {
            "symbol": symbol,
            "provider": "yfinance",
            "status": "REVIEW_REQUIRED",
            "requested_start": start,
            "requested_end": end,
            "error": str(exc),
        }


def classify(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok_rows = [r for r in rows if r.get("status") == "OK"]
    review_rows = [r for r in rows if r.get("status") != "OK"]
    robust = {r["symbol"] for r in ok_rows if r.get("robust_all_nulls")}
    iid_pass = {r["symbol"] for r in ok_rows if r.get("iid", {}).get("verdict") == "DND_DELTA"}

    if review_rows:
        review_reason = "Some symbols could not be acquired and remain REVIEW_REQUIRED."
    else:
        review_reason = None

    if PRIMARY_EQUITY.issubset(robust):
        if robust - CORRELATED_EQUITY:
            label = "cross_asset_candidate"
            reason = "Primary equity and at least one less-correlated control passed all nulls."
        else:
            label = "correlated_equity_local"
            reason = "SPY and QQQ passed all nulls, while less-correlated controls did not."
    elif PRIMARY_EQUITY.issubset(iid_pass):
        label = "iid_only_review"
        reason = "SPY and QQQ pass iid shuffle but do not both survive block-preserving nulls."
    elif iid_pass:
        label = "single_or_partial_window"
        reason = "At least one asset passes iid shuffle, but transfer is incomplete."
    else:
        label = "no_transfer_delta"
        reason = "No transfer class survives the current exact-window diagnostic."

    return {
        "label": label,
        "reason": reason,
        "review_reason": review_reason,
        "iid_dnd_symbols": sorted(iid_pass),
        "robust_all_null_symbols": sorted(robust),
        "review_required_symbols": sorted(r["symbol"] for r in review_rows),
        "operational": False,
        "public_claim": False,
        "trading_signal": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    classification = payload["classification"]
    lines = [
        "# Finance Transfer Diagnostic - Exact Window",
        "",
        f"Generated: {payload['generated_at']}",
        f"Window: `{payload['start']}..{payload['end']}`",
        f"Seed: `{payload['seed']}`",
        f"Shuffles per null: `{payload['shuffles']}`",
        "",
        "## Executive Read",
        "",
        f"Transfer class: `{classification['label']}`.",
        classification["reason"],
        "",
        "This is a diagnostic artifact, not a trading signal or public finance claim.",
        "",
        "## Boundary",
        "",
        "- Operational: `false`",
        "- Public claim: `false`",
        "- Trading signal: `false`",
        "- Promotion requires recurrence and materially independent assets.",
        "",
        "## Exact-Window Table",
        "",
        "| Symbol | Actual dates | n | iid | z_iid | block5 | z_b5 | block21 | z_b21 | robust | RV | VaR95 |",
        "|---|---|---:|---|---:|---|---:|---|---:|---|---:|---:|",
    ]
    for r in payload["rows"]:
        if r.get("status") != "OK":
            lines.append(
                f"| {r['symbol']} | REVIEW_REQUIRED | 0 | error | 0 | error | 0 | error | 0 | false | 0 | 0 |"
            )
            continue
        lines.append(
            "| {symbol} | {dates} | {n} | `{iid}` | {zi:.3f} | `{b5}` | {zb5:.3f} | "
            "`{b21}` | {zb21:.3f} | `{robust}` | {rv:.4f} | {var:.5f} |".format(
                symbol=r["symbol"],
                dates=f"{r.get('actual_start') or '?'}..{r.get('actual_end') or '?'}",
                n=r["n"],
                iid=r["iid"]["verdict"],
                zi=r["iid"]["effect_z"] or 0.0,
                b5=r["block5"]["verdict"],
                zb5=r["block5"]["effect_z"] or 0.0,
                b21=r["block21"]["verdict"],
                zb21=r["block21"]["effect_z"] or 0.0,
                robust=str(bool(r["robust_all_nulls"])).lower(),
                rv=r["realized_vol"] or 0.0,
                var=r["var_95"] or 0.0,
            )
        )
    lines.extend(["", "## Provenance", ""])
    for r in payload["rows"]:
        if r.get("status") != "OK":
            lines.append(f"- `{r['symbol']}`: REVIEW_REQUIRED - {r.get('error')}")
            continue
        card = r.get("data_card") or {}
        lines.append(
            f"- `{r['symbol']}`: {card.get('source_url') or 'source unavailable'}; "
            f"retrieved `{card.get('retrieval_ts') or 'unknown'}`; "
            f"era `{card.get('era_hint') or 'unknown'}`"
        )
    lines.extend(
        [
            "",
            "## Next Gate",
            "",
            (
                "If this artifact is used by a cycle, the report must cite this JSON "
                "instead of embedding unchecked transfer numbers only in prose. A "
                "single exact window remains non-operational even when multiple "
                "correlated assets pass."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(payload: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"finance_transfer_diagnostic_{payload['generated_at_compact']}"
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    payload["outputs"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2026-02-09")
    parser.add_argument("--end", default="2026-05-09")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--shuffles", type=int, default=1024)
    parser.add_argument("--output-dir", type=Path, default=default_output_dir())
    parser.add_argument("--json", action="store_true", help="print payload JSON to stdout")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    generated = datetime.now(UTC)
    rows = [
        run_symbol(symbol, start=args.start, end=args.end, seed=args.seed, shuffles=args.shuffles)
        for symbol in symbols
    ]
    payload = {
        "schema": "finance_transfer_diagnostic.v1",
        "generated_at": generated.isoformat(),
        "generated_at_compact": generated.strftime("%Y%m%d_%H%M%S"),
        "domain": "finance",
        "kind": "transfer_diagnostic",
        "start": args.start,
        "end": args.end,
        "symbols": symbols,
        "seed": args.seed,
        "shuffles": args.shuffles,
        "nulls": ["iid_shuffle", "block_permutation_5", "block_permutation_21"],
        "rows": rows,
        "classification": classify(rows),
        "boundary": {
            "operational": False,
            "public_claim": False,
            "trading_signal": False,
        },
    }
    json_path, md_path = write_outputs(payload, args.output_dir)

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Wrote JSON: {json_path}")
        print(f"Wrote Markdown: {md_path}")
        print(f"Transfer class: {payload['classification']['label']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
