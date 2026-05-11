# Contribution Registry And Pre-report

Status: implemented first ring for public Lab improvement intake
Date: 2026-05-11

## Purpose

The public Lab Assistant can collect improvement suggestions, but public demo
chat must not write directly into seed, run cycles, or schedule email. External
requests should pass through a contribution registry and a pre-report
(`preport`) before any contamination enters the Lab.

## Flow

```text
visitor suggestion
  -> contribution registry
  -> preport analysis
  -> operator review
  -> accepted contamination
  -> seed tension / next-cycle direction / new domain draft
```

## Registry Record

Each suggestion should be normalized into:

- `id`: stable generated id
- `created_at`: UTC timestamp
- `domain`: existing or proposed domain
- `source_type`: visitor / expert / operator / imported public source
- `contact_preference`: none / email_requested / newsletter_requested
- `public_data_source`: URL or description of public data only
- `hypothesis`: what the visitor thinks the Lab should test
- `falsification_test`: what would make the proposal fail
- `constraints`: legal, privacy, cost, quality, interpretation limits
- `expected_value`: research / product / report / installation / support
- `noise_score`: 0..1
- `signal_score`: 0..1
- `status`: new / preported / accepted / rejected / needs_clarification
- `operator_note`: internal review note

Never store secrets, credentials, private datasets, personal health/financial
advice requests, or unreviewed private files in the registry.

## Pre-report

The pre-report is a read-only analysis over registry items. It should decide:

- whether the suggestion is concrete enough to become a candidate tension;
- whether the proposed source is public and suitable;
- what baseline or null would make the test meaningful;
- what risk or ambiguity must be resolved before the Lab sees it;
- whether it belongs to an existing domain or requires a new domain draft.

Suggested verdicts:

- `ACCEPT_CANDIDATE`: can become a reviewed Lab contamination
- `NEEDS_CLARIFICATION`: ask one precise missing question
- `REJECT_NOISE`: generic, unsupported, promotional, unsafe, or impossible
- `ARCHIVE_CONTEXT`: useful background but not a Lab action

## Assistant Behavior

If the visitor asks to contribute, explain the flow:

```text
I can turn your idea into a candidate improvement spec.
Useful specs include: domain, public source/data, hypothesis, falsification
test, constraints, and expected value. In this public demo I do not save Lab
changes, run cycles, or send email automatically; concrete specs go to operator
review.
```

The public demo can persist only a sanitized contribution/preport record under
ignored runtime data. This is not Lab contamination yet: it does not alter seed,
does not run a cycle, does not schedule mail, and does not promote a new domain.

If the visitor does not contribute, the assistant should help them understand
recent results and the way the Lab works:

```text
The Lab reads its recent reports, cemetery, products, diagnostics, and seed.
It learns by cycles, adjusts when findings fail, and can be redirected toward
new horizons when the operator chooses a new direction.
```

## Fast Operator Contact

THIA Assistant can notify the operator through Telegram when activity happens
in site chat, and the operator may join the conversation with the visitor from
the page context. This can be described as a fast human connection path, with
two boundaries:

- it is availability-based, not a guaranteed real-time support promise;
- visitors must not send secrets, credentials, private datasets, or sensitive
  personal material through this path.

## Implemented Endpoint

```text
POST /api/domains/{domain}/contributions
```

Payload fields:

- `message`
- `proposed_domain`
- `public_data_source`
- `hypothesis`
- `falsification_test`
- `constraints`
- `expected_value`
- `contact_preference`: none / email_requested / newsletter_requested /
  telegram_operator / follow_up_requested
- `contact`
- `context_tab`
- `context_view`

The endpoint rate-limits public submissions, redacts common secret patterns,
sanitizes text, writes an
append-only `registry.jsonl`, and emits Markdown + JSON preports under:

```text
data/<domain>/contributions/
```

## Next Implementation Ring

1. Connect the Lab Assistant UI to the endpoint behind an explicit visitor
   confirmation such as "Registra come proposta".
2. Add an operator-only review view for pending preports.
3. Add an operator-only promotion path from accepted preports to seed tension
   or new-domain draft.
