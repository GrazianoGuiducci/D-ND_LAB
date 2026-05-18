# Bitcoin Regime Lab - Alipio Method Intake

Date: 2026-05-18
Status: method-intake substrate, not trading rule.

This document preserves the operational reading of Alipio's BTC chart notes
and the first Massimo Rea-derived method references. It does not store private
screenshots, raw transcripts or trading advice.

The purpose is to help THIA and the Bitcoin Regime Lab ask better questions,
translate trader language into observable contracts, and decide which tools
must be built before a method can enter a cycle.

## Boundary

Alipio's notes are useful because they expose how a human domain observer reads
BTC structure:

- where the observer sees a relevant level;
- which confluences matter to them;
- which phrase signals an intended next check;
- which visual object should become measurable.

They are not evidence by themselves. They must pass:

- source and data-card definition;
- mechanical observable definition;
- matched baseline or null;
- falsifier review;
- no-signal boundary.

Forbidden promotion path:

```text
image note -> rule -> target -> signal
```

Allowed promotion path:

```text
image note -> method card -> observable spec -> data-card -> baseline/null
-> falsifier -> watch/test/reject status
```

## What The Images Contribute

The screenshots are weekly BTCUSD TradingView views on Bitstamp. They include
manual annotations around Volume Profile, POC, trendlines, moving averages and
inefficiency language.

Observed method-language, expressed as candidate objects:

- red horizontal POC lines from Volume Profile;
- POC below current structure as a risk/warning condition;
- POC descending alignment with ascending POC as a possible restart condition;
- retest of POC and ascending trendline;
- break/retest of descending trendline;
- MM52 retest as a possible gate;
- "chiusura inefficienza" around price zones with low volume or fast movement;
- high-volume area around the observer's marked region;
- momentum-change objective;
- weekly and semiannual timing language;
- Volume Profile right-side distribution as context, not as automatic target.

The current Lab has already translated the timeframe question into a matrix:
daily is the only current testable surface with available daily OHLCV; weekly
and monthly are watch-only until the denominator becomes strong enough;
intraday frames are blocked until native intraday data and feed robustness
exist.

## Method Cards To Build

| Human phrase | Candidate observable | Data needed | Null/falsifier | Current status |
| --- | --- | --- | --- | --- |
| POC del volume profile | POC level in a declared profile window | exchange, OHLCV or tick/volume source, profile window, binning rule, timezone | matched random levels; adjacent-window POC; shuffled-volume profile | future tool |
| POC sotto | POC relation to current price and recent range | computed POC, current/closed candle, tolerance | random level below price; selected-window artifact | method card first |
| Ripartenza quando POC discendente si allinea al POC ascendente | POC drift/alignment event across successive windows | repeated profile windows, drift rule, alignment tolerance | shuffled windows; adjacent-window control; no-lookahead split | future tool |
| Retest trendline + POC | confluence event with declared trendline rule | trendline endpoints, POC, retest tolerance, forward window | POC-only vs trendline-only ablation; random slope line | future tool |
| Chiusura inefficienza | FVG/LVN/gap-fill event | candle series, volume profile or FVG definition, fill threshold | arbitrary equal-width zones; block-preserving returns | candidate next spec |
| MM52 retest | moving-average touch/rejection event | exact MA length/type/source, close/high/low rule, tolerance | MA-only baseline; shifted MA; random moving level | future tool |
| Cambio momentum | momentum state change before/after declared event | chosen metric, window, threshold, forward horizon | naive drift/random walk; threshold sweep correction | future tool |
| Timeframe ottimale | timeframe admissibility matrix | data per timeframe, event counts, open-candle policy | denominator control; overfit and feed-sensitivity checks | implemented first pass |

## Questions THIA Should Ask Alipio

THIA should not ask "where will BTC go?". It should ask questions that turn the
method into a contract:

1. Which exchange/source is the reference for this method: Bitstamp only, or
   must the event survive Binance/Coinbase too?
2. For each POC line, what is the exact Volume Profile window start/end?
3. Is the POC manually drawn or computed by a TradingView profile tool?
4. What bin size or profile resolution is used?
5. What tolerance counts as a POC touch or retest?
6. When is a Naked POC considered active, touched, retired or invalidated?
7. What exactly makes an inefficiency "closed": wick touch, close inside,
   full traversal, percentage fill or volume fill?
8. Which MM52 is intended: simple/exponential, close-based, weekly/daily, and
   must the candle close above/below it?
9. How are trendlines drawn: which pivots, which timeframe, what tolerance?
10. Which timeframe is used to define the object, and which timeframe is used
    to confirm it?
11. What would make the method fail?
12. What output would be useful if the Lab cannot produce a signal: watchlist,
    invalidation, rejected hypothesis, next test or source/data warning?

These answers should become method cards or contribution artifacts. They must
not directly alter the seed.

## Massimo Rea Intake Status

TM1/TM7-local recovered derived method material from two public transcript
sources and metadata-only entries for additional videos that were rate-limited.
The public repo stores only derived method substrate, not raw transcripts.

Current usable method families:

- Naked POC lifecycle: completed-period POC remains active until first future
  touch, then retires.
- Timeframe hierarchy: daily, weekly and monthly appear central in the
  recovered method material; 4h/12h are extensions, not default authority.
- POC confluence: POC should be tested alone and with VAH/VAL, trendline,
  Fibonacci, inefficiency and Kumo to avoid visual overfit.
- Kumo gate: possible confirmation/failure state, not signal authority.
- Feed disagreement: Bitstamp can reproduce Alipio's screenshots, but event
  labels should be checked against Binance/Coinbase before promotion.

Future TM1 work can retry unavailable videos if Alipio provides specific URLs,
titles or timestamps. Extraction output should remain method cards, glossary
and open questions.

## Practical Next Tool

The next high-value tool should not immediately calculate a public POC target.
Current exchange daily OHLCV is enough for field admissibility and timeframe
matrix, but not enough to reproduce TradingView Volume Profile precisely unless
we define an explicit proxy.

Recommended next movement:

```text
daily_method_spec_card -> one mechanical daily FVG or POC-proxy observable
-> matched null -> falsifier -> dashboard watch/test/reject
```

Candidate first spec:

- `btc_method_intake_card.py`: writes a structured method card for one Alipio
  object with required data, unresolved definitions and no-signal boundary.
- then `btc_daily_inefficiency_candidate.py`: tests a simple daily FVG/gap-fill
  definition because it can be computed from OHLCV without tick-level volume.
- only after that, `btc_volume_profile_poc_proxy.py`: computed POC proxy with a
  declared binning/window rule, labelled as proxy unless real volume-profile
  data is available.

## UI Implications

The dashboard should make value obvious to a BTC observer without pretending to
trade:

- current BTC field/data quality;
- timeframe matrix: what can be tested now, what is watch-only, what is blocked;
- method intake cards: POC, inefficiency, MM52, trendline, Kumo;
- watchlist: active but untested possibilities;
- rejected hypotheses and why;
- next test requested by the Lab;
- source/method panel: Alipio/Rea-derived material with extraction status.

THIA's role in the dashboard is to explain the current Lab state and collect
method clarifications. It should be able to say:

```text
Daily is currently the only admissible test surface. Weekly/monthly are watch
surfaces; intraday needs native data. The Lab can collect your POC/FVG/MM52
definition, but it will not treat it as a signal until it survives a matched
null and falsifier.
```

## Cross-Lab Transfer

Reusable capabilities for the meta-lab:

- timeframe admissibility matrix;
- method-intake cards from human experts;
- source/data-card before interpretation;
- confluence ablation;
- no-signal boundary for high-risk domains;
- THIA-guided human clarification loop.

Non-transferable content:

- BTC price levels from screenshots;
- Alipio manual annotations as rules;
- Massimo Rea language as authority;
- any target, entry, exit or performance promise.
