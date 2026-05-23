#!/usr/bin/env python3
"""lab_lifecycle_manager.py — safe inventory and cleanup planning for Labs.

This tool is intentionally non-destructive in its first version. It maps every
filesystem surface that belongs to a Lab slug and can emit a cleanup manifest
for generated MetaLab candidates. Hard delete/archive can be added only after
the manifest contract is proven in E2E.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _meta_generated_root() -> Path:
    return _repo_root() / "data" / "meta-lab" / "generated_domains"


def _archive_root() -> Path:
    return _repo_root() / "data" / "meta-lab" / "archive"


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


def _assert_inside_repo(path: Path) -> None:
    root = _repo_root().resolve()
    resolved = path.resolve()
    if root != resolved and root not in resolved.parents:
        raise ValueError(f"path escapes repo root: {path}")


def _assert_inside_archive(path: Path) -> None:
    archive = _archive_root().resolve()
    resolved = path.resolve()
    if archive != resolved and archive not in resolved.parents:
        raise ValueError(f"path escapes archive root: {path}")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _candidate_archive_plan(slug: str, stamp: str | None = None) -> dict[str, Any]:
    inv = inventory(slug)
    stamp = stamp or _utc_stamp()
    archive_base = _archive_root() / "generated_tests" / inv["slug"] / stamp
    moves = []
    for item in inv["existing"]:
        if not str(item["surface"]).startswith("candidate_"):
            continue
        src = _repo_root() / item["path"]
        _assert_inside_repo(src)
        dst = archive_base / item["path"]
        _assert_inside_archive(dst)
        move = {
            "surface": item["surface"],
            "role": item["role"],
            "from": item["path"],
            "to": _rel(dst),
            "files": item["files"],
            "dirs": item["dirs"],
            "bytes": item["bytes"],
        }
        if src.is_file():
            move["sha256"] = _sha256_file(src)
        moves.append(move)
    return {
        "schema": "dndlab.lab_lifecycle_archive_manifest.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "slug": inv["slug"],
        "archive_id": f"generated_tests/{inv['slug']}/{stamp}",
        "mode": "dry_run",
        "scope": "meta_lab_generated_candidate",
        "archive_base": _rel(archive_base),
        "moves": moves,
        "summary": {
            "surfaces": len(moves),
            "files": sum(item["files"] for item in moves),
            "dirs": sum(item["dirs"] for item in moves),
            "bytes": sum(item["bytes"] for item in moves),
        },
        "safety": {
            "installed_lab_surfaces_included": False,
            "requires_execute": True,
            "required_confirm": f"ARCHIVE:{inv['slug']}",
            "hard_delete_supported": False,
        },
    }


def archive_generated_tests(slug: str, *, execute: bool, confirm: str | None) -> dict[str, Any]:
    slug = _safe_slug(slug)
    plan = _candidate_archive_plan(slug)
    if not plan["moves"]:
        plan["safety"]["status"] = "nothing_to_archive"
        return plan
    required = plan["safety"]["required_confirm"]
    if not execute:
        return plan
    if confirm != required:
        raise ValueError(f"archive requires --confirm {required!r}")
    for move in plan["moves"]:
        src = _repo_root() / move["from"]
        dst = _repo_root() / move["to"]
        _assert_inside_repo(src)
        _assert_inside_archive(dst)
        if not src.exists():
            raise FileNotFoundError(move["from"])
        if dst.exists():
            raise FileExistsError(move["to"])
    archive_base = _repo_root() / plan["archive_base"]
    archive_base.mkdir(parents=True, exist_ok=True)
    pre_manifest = write_manifest({**plan, "mode": "execute_preflight"})
    for move in plan["moves"]:
        src = _repo_root() / move["from"]
        dst = _repo_root() / move["to"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
    tombstone = archive_base / "TOMBSTONE.json"
    tombstone.write_text(
        json.dumps(
            {
                "schema": "dndlab.lab_lifecycle_tombstone.v1",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "slug": slug,
                "archive_id": plan["archive_id"],
                "preflight_manifest": _rel(pre_manifest),
                "source_scope": plan["scope"],
                "delete_boundary": "archive_first_no_hard_delete",
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    plan["mode"] = "executed_archive_move"
    plan["manifest_path"] = _rel(pre_manifest)
    plan["tombstone_path"] = _rel(tombstone)
    return plan


def purge_archive_manifest(archive_id: str, *, execute: bool, confirm: str | None) -> dict[str, Any]:
    cleaned = archive_id.strip().strip("/")
    if not cleaned or ".." in Path(cleaned).parts:
        raise ValueError("archive_id must be a relative archive path")
    target = _archive_root() / cleaned
    _assert_inside_archive(target)
    stats = _path_stats(target)
    payload = {
        "schema": "dndlab.lab_lifecycle_purge_manifest.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "archive_id": cleaned,
        "target": _rel(target),
        "mode": "dry_run",
        "summary": stats,
        "safety": {
            "archive_only": True,
            "requires_execute": True,
            "required_confirm": f"PURGE:{cleaned}",
        },
    }
    if not execute:
        return payload
    required = payload["safety"]["required_confirm"]
    if confirm != required:
        raise ValueError(f"purge requires --confirm {required!r}")
    if not target.exists():
        raise FileNotFoundError(cleaned)
    pre_manifest = write_manifest({**payload, "mode": "execute_preflight"})
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    payload["mode"] = "executed_purge"
    payload["manifest_path"] = _rel(pre_manifest)
    return payload


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

    archive = sub.add_parser("archive-generated-tests", help="Archive generated MetaLab candidate surfaces; dry-run unless --execute is set.")
    archive.add_argument("slug")
    archive.add_argument("--json", action="store_true", help="Print full JSON payload.")
    archive.add_argument("--write-manifest", action="store_true", help="Write JSON report under data/meta-lab/lifecycle_reports.")
    archive.add_argument("--execute", action="store_true", help="Move candidate files into data/meta-lab/archive.")
    archive.add_argument("--confirm", help="Required confirmation token for --execute.")

    purge = sub.add_parser("purge-archive", help="Delete an archived lifecycle bundle; dry-run unless --execute is set.")
    purge.add_argument("archive_id")
    purge.add_argument("--json", action="store_true", help="Print full JSON payload.")
    purge.add_argument("--write-manifest", action="store_true", help="Write JSON report under data/meta-lab/lifecycle_reports.")
    purge.add_argument("--execute", action="store_true", help="Delete the archived bundle.")
    purge.add_argument("--confirm", help="Required confirmation token for --execute.")

    args = parser.parse_args()
    try:
        if args.command == "inventory":
            payload = inventory(args.slug)
        elif args.command == "cleanup-generated-tests":
            payload = candidate_cleanup_manifest(args.slug)
        elif args.command == "archive-generated-tests":
            payload = archive_generated_tests(args.slug, execute=args.execute, confirm=args.confirm)
        elif args.command == "purge-archive":
            payload = purge_archive_manifest(args.archive_id, execute=args.execute, confirm=args.confirm)
        else:
            parser.error("unknown command")
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}")
        return 2

    if args.write_manifest:
        path = write_manifest(payload)
        payload["manifest_path"] = _rel(path)

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        summary = payload["summary"]
        print(f"{args.command}: {payload.get('slug', payload.get('archive_id'))}")
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
