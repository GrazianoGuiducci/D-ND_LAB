#!/usr/bin/env python3
"""lab_lifecycle_manager.py — safe inventory and cleanup planning for Labs.

This tool is intentionally non-destructive in its first version. It maps every
filesystem surface that belongs to a Lab slug and can emit a cleanup manifest
for generated MetaLab candidates. Hard delete/archive can be added only after
the manifest contract is proven in E2E.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _meta_generated_root() -> Path:
    return _repo_root() / "data" / "meta-lab" / "generated_domains"


def _safe_slug(slug: str) -> str:
    cleaned = slug.strip().lower()
    if not cleaned or not cleaned.replace("-", "").replace("_", "").isalnum():
        raise ValueError("slug must use letters, numbers, '-' or '_'")
    return cleaned


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _rel(path: Path) -> str:
    root = _repo_root()
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _path_stats(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "files": 0, "dirs": 0, "bytes": 0}
    if path.is_file():
        return {"exists": True, "files": 1, "dirs": 0, "bytes": path.stat().st_size}
    files = 0
    dirs = 0
    total = 0
    for child in path.rglob("*"):
        try:
            if child.is_dir():
                dirs += 1
            elif child.is_file():
                files += 1
                total += child.stat().st_size
        except OSError:
            continue
    return {"exists": True, "files": files, "dirs": dirs, "bytes": total}


@dataclass(frozen=True)
class Surface:
    surface: str
    path: Path
    role: str
    delete_policy: str

    def to_json(self) -> dict[str, Any]:
        return {
            "surface": self.surface,
            "path": _rel(self.path),
            "role": self.role,
            "delete_policy": self.delete_policy,
            **_path_stats(self.path),
        }


def candidate_surfaces(slug: str) -> list[Surface]:
    generated_root = _meta_generated_root()
    specs = generated_root / "_specs"
    reports = generated_root / "_reports"
    return [
        Surface(
            "candidate_dir",
            generated_root / slug,
            "isolated generated candidate filesystem",
            "archive_or_delete_candidate_only",
        ),
        *[
            Surface("candidate_spec", path, "generator spec snapshot", "archive_or_delete_candidate_only")
            for path in sorted(specs.glob(f"{slug}_*.json"))
        ],
        *[
            Surface("candidate_report", path, "candidate run report", "archive_or_delete_candidate_only")
            for path in sorted(reports.glob(f"{slug}_*.json"))
        ],
        *[
            Surface("candidate_report_md", path, "human candidate run report", "archive_or_delete_candidate_only")
            for path in sorted(reports.glob(f"{slug}_*.md"))
        ],
    ]


def installed_surfaces(slug: str) -> list[Surface]:
    repo = _repo_root()
    data = repo / "data" / slug
    return [
        Surface("domain_template", repo / "domains" / slug, "installed Lab template/source", "archive_before_delete"),
        Surface("domain_runtime_data", data, "runtime data root", "archive_before_delete"),
        Surface("runtime_reports", data / "reports", "cycle reports", "archive_before_delete"),
        Surface("runtime_artifacts", data / "artifacts", "cycle artifacts", "archive_before_delete"),
        Surface("runtime_falsifier", data / "falsifier", "falsifier outputs", "archive_before_delete"),
        Surface("runtime_veritas", data / "veritas", "veritas/score outputs", "archive_before_delete"),
        Surface("runtime_narratives", data / "narratives", "narrative outputs", "archive_before_delete"),
        Surface("runtime_published", data / "published", "published mirrors", "manual_review_required"),
        Surface("runtime_scoperte", data / "scoperte", "discoveries", "manual_review_required"),
        Surface("runtime_soluzioni", data / "soluzioni", "solution/product outputs", "manual_review_required"),
        Surface("runtime_contributions", data / "contributions", "public/admin contributions", "manual_review_required"),
        Surface("runtime_locks", data / "locks", "locks", "delete_after_process_check"),
        Surface("runtime_cache", data / "market_cache", "domain cache", "delete_after_archive"),
    ]


def inventory(slug: str) -> dict[str, Any]:
    slug = _safe_slug(slug)
    surfaces = candidate_surfaces(slug) + installed_surfaces(slug)
    existing = [s.to_json() for s in surfaces if s.path.exists()]
    missing = [s.to_json() for s in surfaces if not s.path.exists()]
    return {
        "schema": "dndlab.lab_lifecycle_inventory.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "slug": slug,
        "repo_root": str(_repo_root()),
        "summary": {
            "existing_surfaces": len(existing),
            "missing_surfaces": len(missing),
            "files": sum(item["files"] for item in existing),
            "dirs": sum(item["dirs"] for item in existing),
            "bytes": sum(item["bytes"] for item in existing),
        },
        "existing": existing,
        "missing": missing,
        "safety": {
            "hard_delete_supported": False,
            "default_action": "inventory_only",
            "notes": "This version does not delete or archive files.",
        },
    }


def candidate_cleanup_manifest(slug: str) -> dict[str, Any]:
    inv = inventory(slug)
    candidate_items = [
        item for item in inv["existing"]
        if str(item["surface"]).startswith("candidate_")
    ]
    return {
        "schema": "dndlab.lab_lifecycle_cleanup_manifest.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "slug": inv["slug"],
        "mode": "dry_run_only",
        "scope": "meta_lab_generated_candidate",
        "would_touch": candidate_items,
        "summary": {
            "surfaces": len(candidate_items),
            "files": sum(item["files"] for item in candidate_items),
            "dirs": sum(item["dirs"] for item in candidate_items),
            "bytes": sum(item["bytes"] for item in candidate_items),
        },
        "blocked_operations": [
            "hard_delete",
            "archive_move",
            "installed_lab_delete",
        ],
        "next_required_step": "Review manifest, then implement archive/delete with tombstone in a separate change.",
    }


def write_manifest(payload: dict[str, Any], output_dir: Path | None = None) -> Path:
    out_dir = output_dir or (_repo_root() / "data" / "meta-lab" / "lifecycle_reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{payload['slug']}_{payload['schema'].split('.')[-2]}_{_utc_stamp()}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    inv = sub.add_parser("inventory", help="Map all known filesystem surfaces for a Lab slug.")
    inv.add_argument("slug")
    inv.add_argument("--json", action="store_true", help="Print full JSON payload.")
    inv.add_argument("--write-manifest", action="store_true", help="Write JSON report under data/meta-lab/lifecycle_reports.")

    cleanup = sub.add_parser("cleanup-generated-tests", help="Dry-run cleanup manifest for generated MetaLab candidates.")
    cleanup.add_argument("slug")
    cleanup.add_argument("--json", action="store_true", help="Print full JSON payload.")
    cleanup.add_argument("--write-manifest", action="store_true", help="Write JSON report under data/meta-lab/lifecycle_reports.")

    args = parser.parse_args()
    if args.command == "inventory":
        payload = inventory(args.slug)
    elif args.command == "cleanup-generated-tests":
        payload = candidate_cleanup_manifest(args.slug)
    else:
        parser.error("unknown command")

    if args.write_manifest:
        path = write_manifest(payload)
        payload["manifest_path"] = _rel(path)

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        summary = payload["summary"]
        print(f"{args.command}: {payload['slug']}")
        print(f"- surfaces: {summary.get('existing_surfaces', summary.get('surfaces', 0))}")
        print(f"- files: {summary['files']}")
        print(f"- dirs: {summary['dirs']}")
        print(f"- bytes: {summary['bytes']}")
        if payload.get("manifest_path"):
            print(f"- manifest: {payload['manifest_path']}")
        print("- hard delete: disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
