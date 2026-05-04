"""Decision Archaeologist — extracts recurring patterns from operator memory corpus.

Reads feedback_*.md files from operator memory directory. For each file,
extracts the operational pattern crystallized. Then clusters patterns by
structural similarity and proposes candidate rules.

Usage:
  python3 tools/exp_decision_archaeologist.py [--memory-dir PATH] [--min-frequency 3]

Output: JSON with extracted patterns, clusters, candidate rules.
"""

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict


# Structural markers that indicate dipolar thinking in operator decisions
DIPOLE_MARKERS = {
    "det_minus_1": [
        "inversione", "regressiv", "nodo regressivo", "risali",
        "det=-1", "osserva prima", "territorio", "non-sapere",
        "strutturale", "confine", "condizione relazionale",
    ],
    "det_plus_1": [
        "toppa", "sintomo", "det=+1", "mappa", "assunzione",
        "superficiale", "aggiungi", "supponi", "presupponi",
    ],
    "axiom_refs": {
        "A2": ["confine", "det=-1", "inversione", "boundary"],
        "A4": ["modus", "qualita della domanda", "osservare prima"],
        "A5": ["ciclo", "autopoie", "cimitero"],
        "A8": ["autologic", "f(f(x))", "sistema applica"],
        "A9": ["terzo incluso", "terza via"],
        "A12": ["deposito", "traccia la curva", "sovrapposizione"],
        "A14": ["cascata", "propaga", "seme"],
        "A15": ["automazione", "veicolo senza guidatore", "auto-corr"],
    },
}


def extract_pattern(filepath: str) -> dict:
    """Extract operational pattern from a feedback_*.md file."""
    with open(filepath, "r") as f:
        content = f.read()

    filename = os.path.basename(filepath)
    content_lower = content.lower()

    # Score dipolar structure
    det_minus_score = sum(
        1 for m in DIPOLE_MARKERS["det_minus_1"] if m in content_lower
    )
    det_plus_score = sum(
        1 for m in DIPOLE_MARKERS["det_plus_1"] if m in content_lower
    )

    # Detect axiom references
    axioms_found = []
    for axiom, markers in DIPOLE_MARKERS["axiom_refs"].items():
        if any(m in content_lower for m in markers):
            axioms_found.append(axiom)

    # Classify pattern type
    if det_minus_score > 0 and det_plus_score > 0:
        pattern_type = "dipolar_explicit"  # Both poles mentioned
    elif det_minus_score > det_plus_score:
        pattern_type = "structural_fix"
    elif det_plus_score > det_minus_score:
        pattern_type = "anti_pattern_identified"
    else:
        pattern_type = "neutral"

    # Extract title/theme from filename
    theme = filename.replace("feedback_", "").replace(".md", "").replace("_", " ")

    # Extract first substantive paragraph as summary
    lines = [l.strip() for l in content.split("\n") if l.strip() and not l.startswith("#")]
    summary = lines[0] if lines else ""

    return {
        "file": filename,
        "theme": theme,
        "pattern_type": pattern_type,
        "dipole_score": {
            "det_minus_1": det_minus_score,
            "det_plus_1": det_plus_score,
        },
        "axioms_referenced": axioms_found,
        "summary_first_line": summary[:200],
        "word_count": len(content.split()),
    }


def cluster_patterns(patterns: list[dict]) -> dict:
    """Cluster patterns by axiom co-occurrence and type."""
    # Axiom frequency
    axiom_counter = Counter()
    for p in patterns:
        for a in p["axioms_referenced"]:
            axiom_counter[a] += 1

    # Type distribution
    type_counter = Counter(p["pattern_type"] for p in patterns)

    # Axiom co-occurrence (patterns sharing 2+ axioms)
    cooccurrence = defaultdict(int)
    for p in patterns:
        refs = sorted(p["axioms_referenced"])
        for i in range(len(refs)):
            for j in range(i + 1, len(refs)):
                cooccurrence[f"{refs[i]}+{refs[j]}"] += 1

    return {
        "axiom_frequency": dict(axiom_counter.most_common()),
        "pattern_type_distribution": dict(type_counter),
        "axiom_cooccurrence": dict(
            sorted(cooccurrence.items(), key=lambda x: -x[1])[:10]
        ),
        "total_dipolar_explicit": type_counter.get("dipolar_explicit", 0),
        "total_with_axiom_ref": sum(
            1 for p in patterns if p["axioms_referenced"]
        ),
    }


def propose_candidate_rules(patterns: list[dict], min_freq: int = 3) -> list[dict]:
    """Propose candidate crystallizations from frequent patterns."""
    # Group by axiom clusters
    axiom_groups = defaultdict(list)
    for p in patterns:
        key = tuple(sorted(p["axioms_referenced"]))
        if key:
            axiom_groups[key].append(p)

    candidates = []
    for axioms, members in axiom_groups.items():
        if len(members) >= min_freq:
            candidates.append({
                "axiom_cluster": list(axioms),
                "frequency": len(members),
                "member_themes": [m["theme"] for m in members],
                "dominant_type": Counter(
                    m["pattern_type"] for m in members
                ).most_common(1)[0][0],
                "candidate_rule": (
                    f"Pattern recurring {len(members)}x around axioms "
                    f"{', '.join(axioms)}. "
                    f"Themes: {', '.join(m['theme'][:30] for m in members[:3])}..."
                ),
            })

    return sorted(candidates, key=lambda x: -x["frequency"])


def main():
    parser = argparse.ArgumentParser(description="Decision Archaeologist")
    parser.add_argument(
        "--memory-dir",
        default="/root/.claude/projects/-opt/memory",
        help="Directory containing feedback_*.md files",
    )
    parser.add_argument(
        "--min-frequency",
        type=int,
        default=3,
        help="Minimum pattern frequency to propose as candidate rule",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    pattern = os.path.join(args.memory_dir, "feedback_*.md")
    files = sorted(glob.glob(pattern))

    if not files:
        print(f"No feedback files found in {args.memory_dir}")
        sys.exit(0)

    patterns = [extract_pattern(f) for f in files]
    clusters = cluster_patterns(patterns)
    candidates = propose_candidate_rules(patterns, args.min_frequency)

    result = {
        "corpus_size": len(files),
        "patterns_extracted": len(patterns),
        "clusters": clusters,
        "candidate_rules": candidates,
        "patterns": patterns,
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"=== Decision Archaeology ===")
        print(f"Corpus: {len(files)} feedback files")
        print(f"Patterns with axiom refs: {clusters['total_with_axiom_ref']}")
        print(f"Dipolar explicit: {clusters['total_dipolar_explicit']}")
        print()
        print("Axiom frequency:")
        for ax, count in clusters["axiom_frequency"].items():
            print(f"  {ax}: {count} occurrences")
        print()
        print(f"Candidate rules (freq >= {args.min_frequency}):")
        for c in candidates:
            print(f"  [{c['frequency']}x] {c['axiom_cluster']}: {c['candidate_rule'][:100]}")


if __name__ == "__main__":
    main()
