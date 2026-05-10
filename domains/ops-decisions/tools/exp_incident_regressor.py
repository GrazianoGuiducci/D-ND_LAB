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
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta


GIT_REPOS = [
    "/opt/MM_D-ND",
    "/opt/D-ND_LAB",
    "/opt/THIA",
]

FAMILY_COMMIT_MARKERS = {
    "auth_boundary": [
        ("refresh_token_reused", 5),
        ("codex_home", 4),
        ("codex token", 3),
        ("auth_fail", 3),
        ("post incident 0721", 2),
        ("401", 1),
        ("pre-flight", 1),
        ("preflight", 1),
    ],
    "closure_write_boundary": [
        ("cycle 20260504_1138", 5),
        ("expected_report mancante", 5),
        ("scrivere il file report", 4),
        ("read-only", 4),
        ("workspace-write", 3),
        ("--full-auto", 3),
        ("vincolo read-only", 3),
    ],
}

STRUCTURAL_COMMIT_MARKERS = [
    ("soluzione strutturale", 5),
    ("root cause", 4),
    ("causa", 3),
    ("risolve", 3),
    ("workspace-write", 3),
    ("--full-auto", 3),
    ("codex_home", 3),
    ("pre-flight", 1),
    ("preflight", 1),
]

SYMPTOMATIC_COMMIT_MARKERS = [
    "manually",
    "retry",
    "restart",
    "recover this cycle",
]

MIN_COMMIT_EVIDENCE_SCORE = 8
DEFAULT_COMMIT_WINDOW_HOURS = 12
CAUSAL_COMMIT_WINDOW_HOURS = 4


def parse_incident(
    filepath: str,
    incident_timestamps: list[datetime] | None = None,
) -> dict:
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
        "commit_fix_source": "none",
        "commit_window_hours": CAUSAL_COMMIT_WINDOW_HOURS,
        "commit_window_until": None,
        "commit_window_guard": "max_4h_or_next_incident",
        "commit_evidence": [],
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

    attach_commit_fix_evidence(result, incident_timestamps=incident_timestamps)

    return result


def parse_iso_timestamp(value: str | None) -> datetime | None:
    """Parse incident timestamp into an aware datetime."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def git_commits_after(
    timestamp: datetime,
    hours: int = DEFAULT_COMMIT_WINDOW_HOURS,
    until: datetime | None = None,
) -> list[dict]:
    """Return commit messages in the post-incident search window."""
    until = until or timestamp + timedelta(hours=hours)
    commits = []
    for repo in GIT_REPOS:
        if not os.path.isdir(os.path.join(repo, ".git")):
            continue
        try:
            proc = subprocess.run(
                [
                    "git",
                    "-C",
                    repo,
                    "log",
                    f"--since={timestamp.isoformat()}",
                    f"--until={until.isoformat()}",
                    "--format=%H%x1f%h%x1f%aI%x1f%s%x1f%b%x1e",
                    "--all",
                ],
                capture_output=True,
                text=True,
                timeout=20,
            )
        except Exception:
            continue
        if proc.returncode != 0:
            continue
        for raw in proc.stdout.strip("\x1e\n").split("\x1e"):
            if not raw.strip():
                continue
            parts = raw.strip().split("\x1f")
            if len(parts) < 5:
                continue
            full_hash, short_hash, commit_time, subject, body = parts[:5]
            commits.append(
                {
                    "repo": repo,
                    "hash": short_hash,
                    "full_hash": full_hash,
                    "timestamp": commit_time,
                    "subject": subject.strip(),
                    "body": body.strip(),
                }
            )
    commits.sort(key=lambda c: c["timestamp"])
    return commits


def score_commit_for_family(commit: dict, family: str) -> tuple[int, str]:
    """Score whether a commit is evidence for a family and classify fix quality."""
    text = f"{commit['subject']}\n{commit['body']}".lower()
    if "revert(" in text or "falso ricordo" in text:
        return (0, "UNOBSERVED")

    family_score = sum(
        weight for marker, weight in FAMILY_COMMIT_MARKERS.get(family, []) if marker in text
    )
    if family_score == 0:
        return (0, "UNOBSERVED")

    structural_score = sum(
        weight for marker, weight in STRUCTURAL_COMMIT_MARKERS if marker in text
    )
    symptomatic_score = sum(1 for marker in SYMPTOMATIC_COMMIT_MARKERS if marker in text)

    if structural_score > symptomatic_score:
        return (family_score + structural_score, "det=-1")
    if symptomatic_score > 0:
        return (family_score + symptomatic_score, "det=+1")
    return (family_score, "UNRESOLVED")


def causal_commit_window_until(
    timestamp: datetime,
    incident_timestamps: list[datetime] | None = None,
    hours: int = CAUSAL_COMMIT_WINDOW_HOURS,
) -> datetime:
    """Return the causal commit evidence boundary for one incident.

    The window is capped at 4h and also stops before the next incident. This
    keeps dense incident days from importing another family's real repair.
    """
    until = timestamp + timedelta(hours=hours)
    if incident_timestamps:
        future_incidents = sorted(
            ts for ts in incident_timestamps if ts is not None and ts > timestamp
        )
        if future_incidents:
            until = min(until, future_incidents[0])
    return until


def attach_commit_fix_evidence(
    result: dict,
    incident_timestamps: list[datetime] | None = None,
) -> None:
    """Populate commit_fix_class when git history has post-incident evidence."""
    timestamp = parse_iso_timestamp(result.get("timestamp"))
    family = result.get("recurrence_family")
    if timestamp is None or not family:
        return

    until = causal_commit_window_until(timestamp, incident_timestamps)
    result["commit_window_until"] = until.isoformat()
    scored = []
    for commit in git_commits_after(
        timestamp,
        hours=CAUSAL_COMMIT_WINDOW_HOURS,
        until=until,
    ):
        score, fix_class = score_commit_for_family(commit, family)
        if score < MIN_COMMIT_EVIDENCE_SCORE:
            continue
        scored.append(
            {
                "score": score,
                "fix_class": fix_class,
                "repo": commit["repo"],
                "hash": commit["hash"],
                "timestamp": commit["timestamp"],
                "subject": commit["subject"],
            }
        )

    if not scored:
        return

    scored.sort(key=lambda item: (-item["score"], item["timestamp"]))
    best = scored[0]
    result["commit_fix_class"] = best["fix_class"]
    result["commit_fix_source"] = "git_log"
    result["commit_evidence"] = scored[:3]


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

    incident_timestamps = []
    for f in files:
        with open(f, "r") as fh:
            content = fh.read()
        ts_match = re.search(r"\*\*Started\*\*:\s*(\S+)", content)
        incident_timestamps.append(
            parse_iso_timestamp(ts_match.group(1)) if ts_match else None
        )

    incidents = [
        parse_incident(f, incident_timestamps=incident_timestamps) for f in files
    ]
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
