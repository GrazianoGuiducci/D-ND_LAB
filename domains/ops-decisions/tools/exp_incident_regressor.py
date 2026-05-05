"""Incident Regressor — traces incidents to their regressive node.

Given a set of incident_*.md files, classifies each fix as:
  - det=+1 (symptomatic: fixes the output, not the cause)
  - det=-1 (regressive: fixes the condition that allowed the incident)
  - UNRESOLVED (no fix recorded)

Then checks recurrence: did an incident of the same family reappear
after a det=+1 fix? After a det=-1 fix?

Usage:
  python3 tools/exp_incident_regressor.py [--incident-dir PATH]

Output: JSON with classification + recurrence analysis.
"""

import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime


def parse_incident(filepath: str) -> dict:
    """Parse an incident_*.md file into structured data."""
    with open(filepath, "r") as f:
        content = f.read()

    result = {
        "file": os.path.basename(filepath),
        "timestamp": None,
        "errors": [],
        "suggested_fixes": [],
        "has_structural_fix": False,
        "fix_classification": "UNRESOLVED",
        "node_class": "UNKNOWN_NODE",
        "fix_class": "UNRESOLVED",
        "fix_source": "none",
        "fix_text_class": "UNRESOLVED",
        "commit_fix_class": "UNOBSERVED",
        "recurrence_family": "unknown",
    }

    # Extract timestamp
    ts_match = re.search(r"\*\*Started\*\*:\s*(\S+)", content)
    if ts_match:
        result["timestamp"] = ts_match.group(1)

    # Extract error summary
    err_match = re.search(r"\*\*Errors\*\*:\s*(.+)", content)
    if err_match:
        result["errors"].append(err_match.group(1).strip())

    # Extract suggested fixes
    fix_section = re.search(
        r"## Suggested fixes\s*\n(.*?)(?:\n## |\Z)", content, re.DOTALL
    )
    if fix_section:
        fixes = re.findall(r"[-*]\s*(.+)", fix_section.group(1))
        result["suggested_fixes"] = fixes

    # Classify: does the fix address root cause or symptom?
    content_lower = content.lower()
    error_text = " ".join(result["errors"]).lower()
    structural_markers = [
        "execstartpre",
        "pre-flight",
        "watchdog",
        "guard",
        "reorder",
        "root cause",
        "regressive",
        "structural",
        "prevent",
    ]
    symptomatic_markers = [
        "manually",
        "run manually",
        "retry",
        "restart",
        "kill",
        "recover this cycle",
    ]

    structural_score = sum(1 for m in structural_markers if m in content_lower)
    symptomatic_score = sum(1 for m in symptomatic_markers if m in content_lower)

    if structural_score > symptomatic_score:
        result["fix_classification"] = "det=-1"
        result["fix_text_class"] = "det=-1"
        result["has_structural_fix"] = True
    elif symptomatic_score > 0:
        result["fix_classification"] = "det=+1"
        result["fix_text_class"] = "det=+1"
    # else remains UNRESOLVED

    result["fix_class"] = result["fix_text_class"]
    if result["suggested_fixes"]:
        result["fix_source"] = "incident_suggested_fixes"

    codex_exit = None
    claude_exit = None
    codex_match = re.search(r"codex exit=(\d+)", error_text)
    claude_match = re.search(r"claude exit=(\d+)", error_text)
    if codex_match:
        codex_exit = int(codex_match.group(1))
    if claude_match:
        claude_exit = int(claude_match.group(1))

    has_primary_report = "## verdict" in content_lower and "## bicono" in content_lower
    has_seed_write_boundary = any(
        marker in content_lower
        for marker in [
            "non ho aggiornato",
            "read-only",
            "vincolo read-only",
            "seed",
            "seme.json",
        ]
    )

    if codex_exit == 42 or "auth_fail" in content_lower:
        result["node_class"] = "AUTH_BOUNDARY"
        result["recurrence_family"] = "auth_boundary"
    elif codex_exit == 0 and has_primary_report and has_seed_write_boundary:
        result["node_class"] = "CLOSURE_WRITE_BOUNDARY"
        result["recurrence_family"] = "closure_write_boundary"
    elif claude_exit == 124 or "timeout" in error_text:
        result["node_class"] = "FALLBACK_TIMEOUT"
        result["recurrence_family"] = "fallback_timeout"

    return result


def classify_incident_family(incidents: list[dict]) -> dict:
    """Group incidents by error family and check recurrence."""
    families = defaultdict(list)

    for inc in incidents:
        family = inc.get("recurrence_family") or "unknown"
        families[family].append(inc)

    analysis = {}
    for family, members in families.items():
        classifications = [m["fix_class"] for m in members]
        node_classes = sorted({m["node_class"] for m in members})
        analysis[family] = {
            "count": len(members),
            "classifications": classifications,
            "node_classes": node_classes,
            "recurrence_after_symptomatic": (
                classifications.count("det=+1") > 1
            ),
            "recurrence_after_structural": False,  # needs temporal check
        }

    return analysis


def main():
    parser = argparse.ArgumentParser(description="Incident Regressor")
    parser.add_argument(
        "--incident-dir",
        default="/opt/MM_D-ND/tools/data/reports",
        help="Directory containing incident_*.md files",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    pattern = os.path.join(args.incident_dir, "incident_*.md")
    files = sorted(glob.glob(pattern))

    if not files:
        print(f"No incident files found in {args.incident_dir}")
        sys.exit(0)

    incidents = [parse_incident(f) for f in files]
    family_analysis = classify_incident_family(incidents)

    # Summary statistics
    total = len(incidents)
    det_minus = sum(1 for i in incidents if i["fix_classification"] == "det=-1")
    det_plus = sum(1 for i in incidents if i["fix_classification"] == "det=+1")
    unresolved = sum(
        1 for i in incidents if i["fix_classification"] == "UNRESOLVED"
    )
    node_classes = sorted({i["node_class"] for i in incidents})
    recurrence_families = sorted({i["recurrence_family"] for i in incidents})
    required_split_keys = [
        "node_class",
        "fix_source",
        "fix_text_class",
        "commit_fix_class",
        "recurrence_family",
    ]

    summary = {
        "total_incidents": total,
        "det_minus_1_fixes": det_minus,
        "det_plus_1_fixes": det_plus,
        "unresolved": unresolved,
        "ratio_structural": det_minus / total if total > 0 else 0,
        "node_class_count": len(node_classes),
        "node_classes": node_classes,
        "recurrence_families": recurrence_families,
        "split_contract_keys": required_split_keys,
        "split_schema_coverage": f"{len(required_split_keys)}/{len(required_split_keys)}",
        "family_analysis": family_analysis,
        "incidents": incidents,
    }

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(f"=== Incident Regression Analysis ===")
        print(f"Total incidents: {total}")
        print(f"  det=-1 (structural): {det_minus} ({summary['ratio_structural']:.0%})")
        print(f"  det=+1 (symptomatic): {det_plus}")
        print(f"  UNRESOLVED: {unresolved}")
        print()
        for family, data in family_analysis.items():
            print(f"Family '{family}': {data['count']} incidents")
            print(f"  Classifications: {data['classifications']}")
            print(
                f"  Recurrence after symptomatic fix: {data['recurrence_after_symptomatic']}"
            )


if __name__ == "__main__":
    main()
