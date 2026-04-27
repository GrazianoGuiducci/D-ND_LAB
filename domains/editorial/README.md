# Editorial Domain

Publishing-aware lab. Mines insight archives (operator notes, conversations,
git commits, research logs) to identify resultants worth publishing, then
drafts copy through the bicono filter and the non-dual-copy gate.

## Why this domain exists

Most published content is echo, not source. The editorial lab applies the
D-ND modus to published thinking: expand the archive of what has been said,
observe where the unobserved resultant lives, cut to one piece, write it
through the structural filter so it does not collapse into hedge or hype.

Output: drafts that hold weight (LinkedIn, Bluesky, long-form), morning
digests for the operator, response templates pre-aligned with voice.

## Status

**Phase 0 — placeholder.** Real content (context.md, tension_to_category.json,
seed_tensions.json, archive_search/embedding_index/voice_check tools) lands
in **Phase 4** as the test of the abstract template. If the editorial lab
runs end-to-end producing a publishable draft, the template is portable.

## What goes here (target structure)

```
editorial/
├── config.json
├── context.md                  # editorial model: source vs echo, transferable
│                                #   vs idiosyncratic, dipoles of register,
│                                #   non-dual-copy anti-patterns, bicono examples
├── tension_to_category.json    # categories: source / echo / transferable / etc
├── seed_tensions.json          # initial editorial tensions
├── tools/
│   ├── archive_search.py       # FTS5 + BM25 on operator archive
│   ├── embedding_index.py      # semantic similarity (chromadb)
│   └── voice_check.py          # gate: hedge / register drift / first-person THIA
├── structural_patterns.py      # editorial-specific anti-patterns
└── corpus/                     # operator archive (gitignored — private)
    └── README.md               # how to populate (Phase 4)
```

## Privacy note

Corpus content (operator notes, conversations, archives) is **gitignored**.
The repo ships only with placeholders / generic examples. Each user populates
their own corpus locally.
