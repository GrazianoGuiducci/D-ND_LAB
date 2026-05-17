#!/usr/bin/env python3
"""Small offline claim-card evaluator for Research Radar.

No network by default. It scores claim cards against naive baselines:
headline-only popularity and source-count-only promotion.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict


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
    args = parser.parse_args()
    rows = [evaluate(card) for card in SAMPLE_CLAIMS]
    output = {
        "schema": "research_radar.claim_eval.v1",
        "baseline": "naive headline/source-count promotion",
        "null_family": ["label_shuffle", "time_window_split", "benchmark_leakage"],
        "cards": rows,
        "summary": {
            "test": sum(1 for r in rows if r["decision"] == "TEST"),
            "watch": sum(1 for r in rows if r["decision"] == "WATCH"),
            "reject": sum(1 for r in rows if r["decision"] == "REJECT"),
        },
    }
    if args.json:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        for row in rows:
            print(f"{row['claim_id']}: {row['decision']} score={row['radar_score']} - {row['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
