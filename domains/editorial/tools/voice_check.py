"""voice_check — non-dual-copy filter for editorial drafts.

Detects four classes of apologetic hedging that inflate copy without
adding signal, plus first-person-THIA violations and other operator-defined
voice issues.

This is a structural filter, not a stylistic one — it surfaces patterns
where the writer is hedging *the structural commitment* of the sentence.
A draft can be wrong and still pass voice_check (its structural
commitment is just wrong); it can be right and fail voice_check (the
commitment is right but hedged into invisibility).
"""

from __future__ import annotations

import re
from typing import Any


# Patterns are word-boundary aware to reduce false positives.
PATTERNS = {
    "modal_hedge": [
        # "might", "may", "could", "perhaps", "possibly", "potentially"
        r"\b(might|may|could|perhaps|possibly|potentially)\b",
    ],
    "temporal_hedge": [
        # "currently", "at this time", "in the present moment",
        # "at the moment", "for now", "today" used as hedge
        r"\b(currently|at this (?:time|moment)|for now|in the present moment)\b",
    ],
    "epistemic_hedge": [
        # "I believe", "it seems", "in my opinion", "I think",
        # "it appears", "from what I understand"
        r"\b(I (?:believe|think|feel)|it (?:seems|appears)|in my opinion|from what I understand)\b",
    ],
    "comparative_hedge": [
        # "one of many", "different from", "various", "kind of",
        # "sort of", "to some extent", "in some sense"
        r"\b(one of many|kind of|sort of|to some extent|in some sense)\b",
    ],
    "first_person_thia": [
        # First-person THIA references — "I am THIA", "my system",
        # "I have memory" (when speaking AS a system)
        r"\bI am (?:THIA|the system)\b",
        r"\bI (?:have|maintain|keep|remember)\s+(?:my own|persistent)\b",
    ],
    "tautology_dominant_frame": [
        # Sentences that restate dominant 2026 frames as discovery
        r"\bAI is changing\b",
        r"\battention is the (?:new|real)\b",
        r"\bin (?:a |an |the )?world (?:where|that)\s+AI\b",
    ],
}


def build(domain: str) -> dict[str, Any]:
    """Return a ToolEntry for the agent."""

    def voice_check(text: str) -> str:
        """Run the non-dual-copy filter over a piece of text. Returns
        a markdown-formatted report listing each violation found, with
        line context and category. PASS if no violations."""
        if not text or not text.strip():
            return "voice_check: empty text — nothing to check."

        violations: list[dict[str, Any]] = []
        lines = text.splitlines()
        for lineno, line in enumerate(lines, 1):
            for category, patterns in PATTERNS.items():
                for pat in patterns:
                    for m in re.finditer(pat, line, re.IGNORECASE):
                        violations.append({
                            "line": lineno,
                            "category": category,
                            "match": m.group(0),
                            "context": line.strip()[:140],
                        })

        if not violations:
            return "voice_check: PASS — no apologetic hedges, no first-person THIA, no dominant-frame tautologies detected."

        # Group by category
        by_cat: dict[str, list[dict[str, Any]]] = {}
        for v in violations:
            by_cat.setdefault(v["category"], []).append(v)

        out = [f"voice_check: {len(violations)} violations across {len(by_cat)} categories"]
        out.append("")
        for category, items in by_cat.items():
            out.append(f"## {category} ({len(items)})")
            for v in items[:5]:  # cap per category to keep output bounded
                out.append(f"- line {v['line']}: `{v['match']}`")
                out.append(f"  context: \"{v['context']}\"")
            if len(items) > 5:
                out.append(f"  ... and {len(items) - 5} more")
            out.append("")

        out.append("## Recommendation")
        out.append(
            "Each match opens a duality the model transcends. Either rewrite "
            "the sentence to declare directly (drop the hedge) or remove the "
            "sentence (it was hedge-shaped because it had no commitment to make)."
        )
        return "\n".join(out)

    return {
        "fn": voice_check,
        "schema": {
            "type": "function",
            "function": {
                "name": "voice_check",
                "description": (
                    "Run the non-dual-copy filter on a draft. Detects modal/temporal/"
                    "epistemic/comparative hedges, first-person-THIA violations, and "
                    "tautological restatement of dominant frames. Use BEFORE recording "
                    "the draft as final — voice_check is the last gate."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The draft text to check.",
                        },
                    },
                    "required": ["text"],
                },
            },
        },
    }
