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
        result["has_structural_fix"] = True
    elif symptomatic_score > 0:
        result["fix_classification"] = "det=+1"
    # else remains UNRESOLVED

    return result


def classify_incident_family(incidents: list[dict]) -> dict:
    """Group incidents by error family and check recurrence."""
    families = defaultdict(list)

    for inc in incidents:
        # Simple family classification by error keywords
        error_text = " ".join(inc["errors"]).lower()
        if "auth" in error_text or "login" in error_text:
            family = "auth_failure"
        elif "exit=124" in error_text or "timeout" in error_text:
            family = "timeout"
        elif "port" in error_text or "pid" in error_text or "orphan" in error_text:
            family = "process_orphan"
        else:
            family = "other"
        families[family].append(inc)

    analysis = {}
    for family, members in families.items():
        classifications = [m["fix_classification"] for m in members]
        analysis[family] = {
            "count": len(members),
            "classifications": classifications,
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

    summary = {
        "total_incidents": total,
        "det_minus_1_fixes": det_minus,
        "det_plus_1_fixes": det_plus,
        "unresolved": unresolved,
        "ratio_structural": det_minus / total if total > 0 else 0,
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
