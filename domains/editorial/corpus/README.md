# Editorial Corpus

This directory holds the operator's archive: the source material the
Editorial Lab reads when running cycles. **Contents here are private
by default** — `.gitignore` excludes everything except this README and
`.gitkeep`.

## What goes here

Whatever the operator considers their archive of insights:
- Notes (markdown, plain text)
- Exported chats (Telegram, Discord, Slack — text export)
- Session transcripts (Claude / GPT / other LLMs)
- Repo-level notes (PR descriptions, commit message bodies)
- Public posts the operator authored (so the lab can detect re-publication)

Keep entries dated where possible. Filename convention suggested:
```
YYYY-MM-DD_topic-or-source.md
```

## What does NOT go here

- The lab's own outputs (those go to `<data>/<editorial>/reports/`)
- Other people's content (citation-only is fine; full reproduction is not)
- Secrets / credentials / personal data of third parties

## Privacy

The corpus is read-only to the lab. The lab never publishes the corpus.
The lab's drafts may *reference* corpus entries but should not reproduce
them verbatim without operator review.

This README and `.gitkeep` are committed; everything else in this
directory is gitignored.
