"""Movement — bicono_extractor (universal).

Parses the bicono section of the agent report and persists structured JSON.
Without this, the dashboard tab "Bicono" stays empty even when reports
contain the section.

Operatore (29/04): "il demo deve possedere tutti gli elementi che lo rendono
significativo — biconi, scoperte, cimitero che cresce".

Pattern: il report markdown contiene una sezione "## Bicono della scoperta"
con sub-sections (radici, singolare, invariante, campo). Il movement parsa
queste sub-sections e produce biconi/<ts>.json strutturato che la dashboard
consuma via /api/domains/<domain>/biconi.

Universale: il parsing e' agnostico al contenuto. Il dominio decide se i
suoi report includono la sezione e in che lingua. Lab D-ND usa "Bicono
della scoperta / radici / singolare / invariante / campo". Lab finance
custom potrebbe usare termini diversi (configurabili in domain config).

Critical=False: report senza bicono section → skip silenzioso, nessun file
scritto. Pattern non-distruttivo.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from core import config as cfg
from core import paths
from core.lab_agent import CycleContext, register_movement

logger = logging.getLogger(__name__)


# Default markers (D-ND lab demo). Override in domain config:
#   movements.bicono_extractor.params:
#     section_marker: "## Bicono della scoperta"
#     subsection_keys: { radici: "Due radici", singolare: "Singolare", ... }
DEFAULT_SECTION_RE = re.compile(
    r"^##\s+Bicono\s+della\s+scoperta\s*\n+([\s\S]*?)(?=\n##\s|\Z)",
    re.MULTILINE | re.IGNORECASE,
)

DEFAULT_SUBSECTION_KEYS = {
    "radici":     r"Due\s+radici|Radici|Roots",
    "singolare":  r"Singolare|Singolarit[aà]|Singular",
    "invariante": r"Invariante\s+di\s+passaggio|Invariante|Invariant",
    "campo":      r"Campo\s+di\s+possibilita|Campo|Field\s+of\s+possibility",
}


def bicono_extractor(ctx: CycleContext) -> None:
    """Extract bicono section from the latest agent report and persist as JSON."""
    params = cfg.movement_params(ctx.config, "bicono_extractor")

    # Skip if agent did not produce a report
    if ctx.movement_status.get("agent", "") != "ok":
        ctx.record_skipped("bicono_extractor", "agent did not complete")
        return

    ts = ctx.timestamp
    report_path = paths.reports_dir(ctx.domain) / f"agent_{ts}.md"
    if not report_path.exists():
        ctx.record_skipped("bicono_extractor", "no report at expected path")
        return

    try:
        text = report_path.read_text(errors="replace")
    except Exception as e:
        ctx.movement_status["bicono_extractor"] = f"pending: read failed: {e}"
        return

    # Custom section pattern from config (optional)
    section_marker = params.get("section_marker")
    if section_marker:
        section_re = re.compile(
            rf"^##\s+{re.escape(section_marker.lstrip('# ').strip())}\s*\n+([\s\S]*?)(?=\n##\s|\Z)",
            re.MULTILINE | re.IGNORECASE,
        )
    else:
        section_re = DEFAULT_SECTION_RE

    m = section_re.search(text)
    if not m:
        ctx.record_skipped("bicono_extractor", "no bicono section in report")
        return

    body = m.group(1).strip()

    # Custom sub-section keys from config (optional)
    sub_keys = params.get("subsection_keys") or DEFAULT_SUBSECTION_KEYS

    parsed: dict[str, str] = {}
    for key, pattern in sub_keys.items():
        # Each sub-section starts with bold marker like "**Due radici**" or
        # "- **Radici**" or just a heading line "### Radici"
        sub_re = re.compile(
            rf"(?:^|\n)\s*(?:[-*]\s+)?(?:###?\s+|\*\*)\s*(?:{pattern})\s*[:*]*\s*([\s\S]*?)"
            rf"(?=\n\s*(?:[-*]\s+)?(?:###?\s+|\*\*)|\Z)",
            re.IGNORECASE,
        )
        sm = sub_re.search(body)
        if sm:
            parsed[key] = _clean(sm.group(1))[:1500]

    if not any(parsed.values()):
        ctx.record_skipped("bicono_extractor", "section found but no sub-sections matched")
        return

    # Title from report H1
    title_m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    report_title = title_m.group(1).strip() if title_m else ""

    record = {
        "domain": ctx.domain,
        "timestamp": ts,
        "report_file": report_path.name,
        "report_title": report_title[:200],
        "bicono": parsed,
        "marked_at": datetime.now(timezone.utc).isoformat(),
    }

    out_dir = paths.domain_data_dir(ctx.domain) / "biconi"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"bicono_{ts}.json"
    out_path.write_text(json.dumps(record, indent=2, ensure_ascii=False))

    ctx.record_success(
        "bicono_extractor",
        sub_sections_extracted=sum(1 for v in parsed.values() if v),
        output_path=str(out_path),
    )
    logger.info(
        "bicono_extractor: %d sub-sections extracted → %s",
        sum(1 for v in parsed.values() if v), out_path,
    )


def _clean(s: str) -> str:
    """Trim, collapse whitespace, strip leading list markers."""
    s = s.strip()
    s = re.sub(r"^[-*]\s+", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


register_movement("bicono_extractor", bicono_extractor)
