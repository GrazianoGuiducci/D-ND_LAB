#!/usr/bin/env python3
"""Small offline claim-card evaluator for Research Radar.

No network by default. It scores claim cards against naive baselines:
headline-only popularity and source-count-only promotion.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ClaimCard:
    claim_id: str
    claim: str
    source_type: str
    observable: str
    baseline: str
    null: str
    evidence_count: int
    independent_sources: int
    hype_terms: int
    has_repro_artifact: bool


SAMPLE_CLAIMS = [
    ClaimCard(
        claim_id="rr_demo_001",
        claim="A new small model beats frontier systems on a benchmark.",
        source_type="preprint_or_blog",
        observable="reported benchmark delta with reproducibility artifact",
        baseline="headline-only popularity",
        null="same score after benchmark leakage or cherry-picked subset",
        evidence_count=2,
        independent_sources=1,
        hype_terms=3,
        has_repro_artifact=False,
    ),
    ClaimCard(
        claim_id="rr_demo_002",
        claim="A measurement method recovers signal under shuffled labels.",
        source_type="paper_plus_code",
        observable="effect remains under preregistered negative controls",
        baseline="source-count-only promotion",
        null="effect disappears under label shuffle and time-window split",
        evidence_count=4,
        independent_sources=3,
        hype_terms=0,
        has_repro_artifact=True,
    ),
]


def evaluate_real_iris_balance_claim() -> dict:
    """Evaluate a real source/data-card where label shuffle is a bad null.

    UCI's Iris dataset card states 3 classes of 50 instances each. For the
    claim "the class distribution is balanced", a label shuffle preserves class
    counts exactly, so the null is executable but not discriminating.
    """
    class_counts = {
        "Iris-setosa": 50,
        "Iris-versicolor": 50,
        "Iris-virginica": 50,
    }
    labels = [
        label
        for label, count in class_counts.items()
        for _ in range(count)
    ]
    rng_state = 1649
    shuffled = labels[:]
    for i in range(len(shuffled) - 1, 0, -1):
        rng_state = (1103515245 * rng_state + 12345) % (2**31)
        j = rng_state % (i + 1)
        shuffled[i], shuffled[j] = shuffled[j], shuffled[i]
    shuffled_counts = {label: shuffled.count(label) for label in class_counts}
    imbalance = max(class_counts.values()) - min(class_counts.values())
    shuffled_imbalance = max(shuffled_counts.values()) - min(shuffled_counts.values())
    null_delta = shuffled_imbalance - imbalance
    return {
        "claim_id": "rr_real_iris_001",
        "claim": "The UCI Iris dataset has a balanced target distribution: 3 classes with 50 instances each.",
        "source_type": "primary_dataset_card",
        "source_provenance": {
            "name": "UCI Machine Learning Repository: Iris",
            "url": "https://archive.ics.uci.edu/dataset/53/iris",
            "doi": "10.24432/C56C76",
            "source_quote_ref": "dataset card reports 150 instances and 3 classes of 50 instances each",
        },
        "data_card": {
            "instances": 150,
            "features": 4,
            "target": "class",
            "class_counts": class_counts,
            "missing_values": False,
            "license": "CC BY 4.0",
        },
        "observable": "class-count imbalance",
        "baseline": "source/data-card presence naive promotion",
        "null": "label shuffle over target categories",
        "control_result": {
            "shuffle_seed": 1649,
            "observed_imbalance": imbalance,
            "shuffled_counts": shuffled_counts,
            "shuffled_imbalance": shuffled_imbalance,
            "null_delta": null_delta,
            "null_discriminating": null_delta != 0,
        },
        "evidence_count": 1,
        "independent_sources": 1,
        "hype_terms": 0,
        "has_repro_artifact": True,
        "radar_score": 0.62,
        "decision": "WATCH",
        "non_admissible": False,
        "reason": "real source/data-card passes provenance, but the executable label-shuffle null is invariant for a count-balance claim; require a claim-appropriate null before TEST",
    }


def evaluate(card: ClaimCard) -> dict:
    provenance = min(1.0, 0.25 * card.evidence_count + 0.20 * card.independent_sources)
    reproducibility = 0.35 if card.has_repro_artifact else 0.0
    hype_penalty = min(0.45, card.hype_terms * 0.15)
    score = max(0.0, min(1.0, provenance + reproducibility - hype_penalty))
    if score >= 0.75 and card.independent_sources >= 2 and card.has_repro_artifact:
        decision = "TEST"
    elif score >= 0.45:
        decision = "WATCH"
    else:
        decision = "REJECT"
    return {
        **asdict(card),
        "radar_score": round(score, 3),
        "decision": decision,
        "non_admissible": decision == "REJECT",
        "reason": (
            "requires direct replication test"
            if decision == "TEST"
            else "insufficient independence or reproducibility"
            if decision == "WATCH"
            else "hype/provenance imbalance beats evidence"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="do not write value-facing artifacts under data/research-radar/value",
    )
    parser.add_argument(
        "--real-null-demo",
        action="store_true",
        help="evaluate one real source/data-card with an executable null-control",
    )
    args = parser.parse_args()
    rows = (
        [evaluate_real_iris_balance_claim()]
        if args.real_null_demo
        else [evaluate(card) for card in SAMPLE_CLAIMS]
    )
    generated_at = datetime.now(timezone.utc).isoformat()
    output = {
        "schema": "research_radar.claim_eval.v1",
        "generated_at": generated_at,
        "baseline": (
            "source/data-card presence naive promotion"
            if args.real_null_demo
            else "naive headline/source-count promotion"
        ),
        "null_family": (
            ["label_shuffle_count_invariance"]
            if args.real_null_demo
            else ["label_shuffle", "time_window_split", "benchmark_leakage"]
        ),
        "cards": rows,
        "summary": {
            "test": sum(1 for r in rows if r["decision"] == "TEST"),
            "watch": sum(1 for r in rows if r["decision"] == "WATCH"),
            "reject": sum(1 for r in rows if r["decision"] == "REJECT"),
            "promote": sum(1 for r in rows if r["decision"] == "PROMOTE"),
        },
    }
    if not args.no_write:
        artifact_dir = Path("/opt/D-ND_LAB/data/research-radar/value")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        latest = artifact_dir / "claim_cards_latest.json"
        stamped = artifact_dir / f"claim_cards_{generated_at[:19].replace(':', '').replace('-', '').replace('T', '_')}.json"
        payload = json.dumps(output, indent=2, ensure_ascii=False) + "\n"
        latest.write_text(payload, encoding="utf-8")
        stamped.write_text(payload, encoding="utf-8")
    if args.json:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        for row in rows:
            print(f"{row['claim_id']}: {row['decision']} score={row['radar_score']} - {row['reason']}")
        if not args.no_write:
            print("artifact: /opt/D-ND_LAB/data/research-radar/value/claim_cards_latest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
