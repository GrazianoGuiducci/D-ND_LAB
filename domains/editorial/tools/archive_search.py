"""archive_search — full-text search over the editorial corpus.

Phase 4 minimal: simple keyword + multi-keyword scoring across markdown
files in the corpus directory. No embeddings, no FTS5 — works without
extra services. Phase 4.5 can swap in chromadb / BM25 if quality drops.

Corpus layout (all gitignored):
  domains/editorial/corpus/
    *.md                        — operator's archive entries
    operator_telegram_*.md      — exported chat
    operator_repo_notes_*.md    — repo-level notes
    operator_session_*.md       — Claude session transcripts

Privacy: the corpus is not committed to the repo. Only placeholder
README + .gitkeep are tracked. Each user populates locally.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def build(domain: str) -> dict[str, Any]:
    """Return a ToolEntry for the agent."""
    from core import paths

    corpus_dir = paths.domain_dir(domain) / "corpus"

    def archive_search(query: str, max_results: int = 10) -> str:
        """Search the corpus for entries matching the query.

        Returns markdown-formatted results: filename + match-rich snippet
        for each hit, capped at max_results. Returns an explicit "no
        corpus" message if the corpus is empty/missing — the agent
        should switch to TENSION_REMAINS in that case.
        """
        if not corpus_dir.exists():
            return (
                f"corpus directory does not exist: {corpus_dir}\n"
                "The lab cannot do source/echo discrimination without a corpus. "
                "Mark TENSION_REMAINS for this cycle and surface the corpus gap."
            )

        files = sorted(corpus_dir.rglob("*.md"))
        files = [f for f in files if f.name != "README.md" and not f.name.startswith(".")]
        if not files:
            return (
                f"corpus directory is empty: {corpus_dir}\n"
                "Mark TENSION_REMAINS and report that the corpus needs populating."
            )

        # Tokenize query (lowercase, alphanumerics)
        terms = [t for t in re.findall(r"\w{3,}", query.lower())]
        if not terms:
            return "query has no usable terms (need words ≥3 chars). Try keywords from active tensions."

        scored: list[tuple[int, Path, str]] = []
        for fp in files:
            try:
                text = fp.read_text(errors="replace")
            except Exception:
                continue
            text_l = text.lower()
            score = sum(text_l.count(t) for t in terms)
            if score == 0:
                continue
            snippet = _best_snippet(text, terms)
            scored.append((score, fp, snippet))

        scored.sort(key=lambda x: -x[0])
        if not scored:
            return f"no entries matched query: {query!r}. Tried terms: {terms}."

        out_lines = [f"# Archive search: {query!r}"]
        out_lines.append(f"Hits: {len(scored)} / {len(files)} entries")
        out_lines.append("")
        for score, fp, snippet in scored[:max_results]:
            rel = fp.relative_to(corpus_dir)
            out_lines.append(f"## {rel} (score={score})")
            out_lines.append(snippet)
            out_lines.append("")
        return "\n".join(out_lines)

    return {
        "fn": archive_search,
        "schema": {
            "type": "function",
            "function": {
                "name": "archive_search",
                "description": (
                    "Search the operator's archive for entries matching a query. "
                    "Use to find convergence points (multiple entries about the same concept), "
                    "to verify whether an insight is source or echo, and to gather context "
                    "before drafting. Returns top matches with snippets."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Keywords or phrase to search for in the corpus.",
                        },
                        "max_results": {
                            "type": "integer",
                            "default": 10,
                            "description": "Cap on number of hits returned.",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
    }


def _best_snippet(text: str, terms: list[str], window: int = 250) -> str:
    """Return the snippet of length `window` chars containing the most term hits."""
    text_l = text.lower()
    best_idx = 0
    best_score = -1
    for i in range(0, len(text), 50):
        chunk = text_l[i:i + window]
        score = sum(chunk.count(t) for t in terms)
        if score > best_score:
            best_score = score
            best_idx = i
    snippet = text[best_idx:best_idx + window].strip()
    return f"> ...{snippet}..."
