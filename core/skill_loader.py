"""skill_loader.py — Carica le skill di un lab in base al suo MML.

Il MML (Metamasterlab, file mml.json del lab) dichiara skills_attive
come subset delle 56 skill totali (27 kernel + 29 runtime). Lo skill
loader risolve i path effettivi e adatta il format per il runtime
agent target (Claude Code / codex / Hermes / standalone).

Pattern speculare al lab_template_generator.py del meta-lab — qui non
si pensa, si fa I/O strutturato. L'intelligenza è nel MML, il loader
esegue.

API:
    load_skills_for_lab(lab_slug, runtime="auto") -> list[Skill]
    resolve_skill_source(name, hint=None) -> Path | None
    install_for_runtime(skills, runtime, target_dir) -> dict (report)

Refactor 2026-05-04 P2.A.6.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


# Path costanti del sistema
KERNEL_SKILLS_DIR = Path("/opt/MM_D-ND/kernel/reference/skills")
RUNTIME_CLAUDE_SKILLS_DIR = Path("/opt/.claude/skills")
DOMAINS_DIR = Path("/opt/D-ND_LAB/domains")

RuntimeTarget = Literal["claude-code", "codex", "hermes", "standalone", "auto"]


@dataclass
class Skill:
    """Skill risolta — ha un nome, un path concreto, un body, e metadata."""
    name: str
    source_path: Path
    source_kind: Literal["kernel", "runtime", "external"]
    body: str = ""
    rationale: str = ""
    trigger: str = ""
    category: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source_path": str(self.source_path),
            "source_kind": self.source_kind,
            "rationale": self.rationale,
            "trigger": self.trigger,
            "category": self.category,
            "body_length": len(self.body),
            "metadata": self.metadata,
        }


# ─── Path resolution ─────────────────────────────────────────────

def resolve_skill_source(name: str, hint: str | None = None) -> tuple[Path, str] | None:
    """Trova il path della skill data il nome.
    Preferenza: hint esplicito > kernel sorgente > runtime Claude Code.
    Ritorna (path, kind) dove kind ∈ {"kernel", "runtime"}.
    """
    if hint:
        # hint può essere absolute path o relativo al repo MM_D-ND/D-ND_LAB
        p = Path(hint)
        if p.is_absolute() and p.exists():
            kind = "kernel" if "kernel/reference/skills" in str(p) else "runtime"
            return (p, kind)
        # relativo
        for base in (Path("/opt/MM_D-ND"), Path("/opt/D-ND_LAB")):
            candidate = base / hint
            if candidate.exists():
                kind = "kernel" if "kernel" in str(candidate) else "runtime"
                return (candidate, kind)

    # Lookup kernel-side
    kernel_path = KERNEL_SKILLS_DIR / f"agent_skills_{name}.md"
    if kernel_path.exists():
        return (kernel_path, "kernel")

    # Lookup runtime-side
    runtime_md = RUNTIME_CLAUDE_SKILLS_DIR / f"{name}.md"
    if runtime_md.exists():
        return (runtime_md, "runtime")
    runtime_dir = RUNTIME_CLAUDE_SKILLS_DIR / name
    if runtime_dir.is_dir():
        # multi-file skill
        skill_md = runtime_dir / "SKILL.md"
        if skill_md.exists():
            return (skill_md, "runtime")
        return (runtime_dir, "runtime")

    return None


# ─── MML reading ─────────────────────────────────────────────────

def _read_mml(lab_slug: str) -> dict[str, Any] | None:
    """Legge mml.json del lab. Ritorna None se non esiste."""
    mml_path = DOMAINS_DIR / lab_slug / "mml.json"
    if not mml_path.exists():
        return None
    try:
        return json.loads(mml_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


# Layer ordering canonico (vedi SKILL_FIELD_MAP.md). Determina l'ordine di
# attivazione: validation → processing → output → osservazione → interface →
# generation → emergency → domain → identity → runtime patterns.
LAYER_ORDER = [
    "validation_layer",
    "processing_layer",
    "output_layer",
    "observation_layer",
    "interface_layer",
    "generation_layer",
    "emergency_layer",
    "domain_layer",
    "identity_layer",
    "runtime_patterns",
]


def _normalize_skills_attive(
    skills_attive: Any,
) -> list[tuple[dict[str, Any], str | None]]:
    """Normalizza skills_attive nei due formati supportati dal mml.schema.json:

    - Formato (a) flat array: ritorna [(entry, None), ...] con layer=None
    - Formato (b) layered object: ritorna [(entry, layer_name), ...] in
      ordine LAYER_ORDER, preservando il layer come metadata

    Layer sconosciuti (non in LAYER_ORDER) vengono inclusi in coda con
    layer name as-is. Input malformato → []. Idempotente.
    """
    if isinstance(skills_attive, list):
        return [(e, None) for e in skills_attive if isinstance(e, dict)]
    if not isinstance(skills_attive, dict):
        return []
    out: list[tuple[dict[str, Any], str | None]] = []
    seen_layers: set[str] = set()
    # Ordered layers first
    for layer in LAYER_ORDER:
        entries = skills_attive.get(layer)
        if not isinstance(entries, list):
            continue
        for e in entries:
            if isinstance(e, dict):
                out.append((e, layer))
        seen_layers.add(layer)
    # Trailing custom layers (non-canonical names — extension future-proof)
    for layer, entries in skills_attive.items():
        if layer in seen_layers or not isinstance(entries, list):
            continue
        for e in entries:
            if isinstance(e, dict):
                out.append((e, layer))
    return out


def load_skills_for_lab(
    lab_slug: str,
    runtime: RuntimeTarget = "auto",
    include_body: bool = False,
) -> list[Skill]:
    """Carica le skill del lab in base al suo MML.
    Se mml.json mancante o malformato, ritorna lista vuota (nessun
    lazy-loaded subset disponibile).

    Supporta entrambi i formati di skills_attive:
    - flat array (legacy)
    - layered object per i 9 layer del sistema cognitivo (canonico,
      vedi mml.schema.json definitions.skill_layered_object)
    """
    mml = _read_mml(lab_slug)
    if not mml:
        return []
    normalized = _normalize_skills_attive(mml.get("skills_attive"))
    out: list[Skill] = []
    for entry, layer in normalized:
        name = entry.get("name")
        if not name:
            continue
        hint = entry.get("source")
        resolved = resolve_skill_source(name, hint)
        if not resolved:
            continue
        path, kind = resolved
        body = ""
        if include_body and path.is_file():
            try:
                body = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                body = ""
        metadata: dict[str, Any] = {
            "mml_lab": lab_slug,
            "runtime_target": runtime,
        }
        if layer:
            metadata["layer"] = layer
        out.append(Skill(
            name=name,
            source_path=path,
            source_kind=kind,
            body=body,
            rationale=entry.get("rationale", ""),
            trigger=entry.get("trigger", ""),
            category=entry.get("category", ""),
            metadata=metadata,
        ))
    return out


# ─── Runtime adapter ─────────────────────────────────────────────

def install_for_runtime(
    skills: list[Skill],
    runtime: RuntimeTarget,
    target_dir: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Materializza le skill nel format/path richiesto dal runtime target.
    - claude-code: copia/symlink in target_dir/.claude/skills/<name>.md
    - codex: scrive in target_dir/.codex/skills/<name>.md (path da
      definire stabilmente — placeholder agentskills.io standard)
    - hermes: format agentskills.io compatibile, target_dir/skills/
    - standalone: registra in registry interno (placeholder).
    Ritorna report {installed: [...], errors: [...], dry_run: bool}.
    """
    if runtime == "auto":
        runtime = "claude-code"  # default conservativo

    if target_dir is None:
        if runtime == "claude-code":
            target_dir = Path("/opt/.claude/skills")
        else:
            target_dir = Path(f"/tmp/skills-{runtime}")

    installed: list[str] = []
    errors: list[str] = []

    for skill in skills:
        if not skill.source_path.exists():
            errors.append(f"{skill.name}: source_path missing {skill.source_path}")
            continue
        # Decidi destination filename per runtime
        if runtime in ("claude-code", "codex"):
            dest = target_dir / f"{skill.name}.md"
        elif runtime == "hermes":
            # Hermes/agentskills.io: ogni skill in dir propria con SKILL.md
            dest = target_dir / skill.name / "SKILL.md"
        elif runtime == "standalone":
            dest = target_dir / "registry" / f"{skill.name}.md"
        else:
            errors.append(f"{skill.name}: runtime sconosciuto {runtime}")
            continue

        if dry_run:
            installed.append(f"[dry-run] {skill.source_path} → {dest}")
            continue

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            if skill.source_path.is_file():
                # Copy content (no symlink — più portabile cross-runtime)
                content = skill.source_path.read_text(encoding="utf-8", errors="replace")
                dest.write_text(content, encoding="utf-8")
                installed.append(str(dest))
            else:
                # multi-file skill (cartella) — copia ricorsiva minimale
                import shutil
                shutil.copytree(skill.source_path, dest.parent / skill.name, dirs_exist_ok=True)
                installed.append(str(dest.parent / skill.name))
        except OSError as e:
            errors.append(f"{skill.name}: {e}")

    return {
        "runtime": runtime,
        "target_dir": str(target_dir),
        "installed": installed,
        "errors": errors,
        "dry_run": dry_run,
    }


# ─── CLI entry point ─────────────────────────────────────────────

def _main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("lab_slug", help="slug del lab (es. physics, finance, meta-lab)")
    ap.add_argument("--runtime", default="auto",
                    choices=["claude-code", "codex", "hermes", "standalone", "auto"])
    ap.add_argument("--install", action="store_true",
                    help="installa skill nel runtime target (default: solo lookup)")
    ap.add_argument("--dry-run", action="store_true",
                    help="con --install, mostra cosa farebbe senza scrivere")
    ap.add_argument("--target-dir", default=None, help="override target dir")
    args = ap.parse_args()

    skills = load_skills_for_lab(args.lab_slug, runtime=args.runtime, include_body=False)
    if not skills:
        print(json.dumps({"error": f"nessuna skill trovata per lab '{args.lab_slug}' "
                                    "(mml.json mancante o vuoto)"},
                         indent=2))
        return 1

    if args.install:
        target = Path(args.target_dir) if args.target_dir else None
        report = install_for_runtime(skills, args.runtime, target, dry_run=args.dry_run)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if not report["errors"] else 1

    # Solo lookup
    print(json.dumps([s.to_dict() for s in skills], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
