# Editorial Domain

The publishing-aware lab. Reads the operator's archive, identifies
where the unsaid resultant lives, drafts copy through the **bicono
filter** and the **non-dual-copy gate**.

## Why this domain exists

Most published content is echo of received insight, not source. The
editorial lab discriminates:

|                  | Source                  | Echo                      |
|------------------|-------------------------|---------------------------|
| Transferable     | **Publishable**         | Re-published noise        |
| Idiosyncratic    | Memoir / case study     | Status update             |

The lab targets the **Source × Transferable** quadrant. The other
three are visible (and labeled) so the operator can decide their fate
without confusion.

## How it works

1. **Read the corpus** — markdown files in `domains/editorial/corpus/`
   (gitignored — your archive stays private)
2. **Find convergences** — when 3+ entries point at the same concept
   from different angles, the unsaid synthesis between them is the
   resultant
3. **Cut to one piece** — not "ten things builders should know" but
   one question whose answer changes how the reader thinks
4. **Draft + bicono filter** — radii (the dipole the piece lives in),
   singular (the pre-dipole state), invariant of passage (what survives
   the cut), field of possibility (what becomes possible / not-possible
   for the reader)
5. **Voice check** — non-dual-copy gate strips apologetic hedging
   (modal/temporal/epistemic/comparative), first-person-THIA violations,
   tautological restatement of dominant frames

## What goes in the corpus

`domains/editorial/corpus/` is your archive. Everything inside is
gitignored except the README + .gitkeep, so private content stays local.

Useful entries:

- Notes (markdown / plain text)
- Exported chats (Telegram, Discord, Slack — text export)
- Session transcripts (Claude / GPT / other LLMs you collaborate with)
- Repo-level notes (PR descriptions, commit message bodies)
- Posts you've authored (so the lab can detect re-publication)

Filename convention:

```
YYYY-MM-DD_topic-or-source.md
```

Date helps the lab order observations chronologically when looking
for trajectories.

## Configuration

`domains/editorial/config.json` enables the same 16 movements as
physics, with these differences:

- `movements.agent.params.min_report_bytes: 800` — editorial reports
  are typically shorter than physics; lower threshold for early-stop
- `movements.verify_assertions.enabled: false` — no condensate-style
  assertions in editorial
- `movements.structural_check.params.patterns_module:
  "domains.editorial.structural_patterns"` — domain-specific
  anti-pattern detection (not yet implemented; falls back to universal)

Tools registered:

- `archive_search` — full-text search over corpus with multi-keyword
  scoring + snippet extraction
- `embedding_index` — semantic search (skeleton; chromadb integration
  Phase 4.5)
- `voice_check` — non-dual-copy filter on a draft

## Seed tensions

Eight starting editorial tensions in `seed_tensions.json`. Top three:

- **TENSION_SOURCE_VS_ECHO** (0.95) — most published content is echo,
  not source; the lab's first task is to discriminate
- **TENSION_CONVERGENCE_UNREAD** (0.9) — three-or-more entries about
  the same concept signal an unread synthesis
- **TENSION_DIRECTIVE_AS_COPY** (0.85) — internal system directives
  leak into public copy as if they were the message itself

## First cycle

```bash
# 1. Add some notes to the corpus
cp ~/notes/*.md ~/.d-nd-lab/domains/editorial/corpus/

# 2. Switch domain
echo 'LAB_DOMAIN=editorial' >> ~/.d-nd-lab/.env

# 3. Run a cycle
docker compose run --rm lab
```

The agent will pick a tension, search the corpus for convergences,
draft a piece if it finds source × transferable material, or mark
TENSION_REMAINS if the corpus didn't yield a clean cut.

## Privacy

- Corpus content stays in `domains/editorial/corpus/` and is
  gitignored. Only README + .gitkeep are tracked.
- Drafts go to `data/editorial/reports/agent_<ts>.md`
- The lab never publishes — drafts are for operator review.
- The lab does not modify your corpus.

## What an editorial cycle produced (validation run)

A test cycle on a 3-entry mini-corpus identified the structural dipole
**Accumulation (det=+1) vs Compounding (det=0)** across three different
domains in the corpus (AI infrastructure, Seed installation, defensive
coding) — and produced a 7779-byte essay titled "The Addition Bias"
with the dipole explicitly named. The same modus that runs on numerical
physics tensions ran on semantic content and found a structural
invariant. That's the test of the abstract template.
