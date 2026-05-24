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

## Follow-up Material From Alipio - 2026-05-19

The operator provided two additional TradingView BTCUSD Bitstamp weekly
screenshots plus a text explanation of "chiudere l'inefficienza". This material
is still method-intake substrate only. It must not be copied as price target,
direction, signal or evidence.

Derived meaning of "inefficiency" from the text:

- **FVG / imbalance**: a fast directional candle move leaves a price zone with
  sparse exchange. Closure means price later trades back into or through that
  zone.
- **LVN / Volume Profile void**: a low-volume node or volume valley. Closure
  means price revisits a low-volume area and may traverse toward HVN/POC.
- **CME gap**: a futures close/open weekend gap. Closure means price revisits
  the gap range.

Important implication: Alipio's phrase is polysemic. The Lab must ask which
type is meant before testing. A single daily three-candle FVG proxy is only one
subtype and cannot represent the whole method.

Derived visual cues from the screenshots:

- source surface appears to be BTCUSD weekly on Bitstamp in TradingView;
- Volume Profile / POC levels are visually central;
- red horizontal levels are used as POC or important volume/structure levels;
- "POC sotto" is treated as warning/risk language, not directly as a trade;
- "ripartenza quando il POC discendente si allinea al POC ascendente" suggests
  a POC-drift/alignment hypothesis across profile windows;
- "retest del POC e della trend line ascendente" suggests confluence, not POC
  alone;
- "chiusura inefficienza 88.000" and "area di inefficienza cioe' con pochi
  volumi" suggest the current useful next object may be LVN/Volume Profile
  inefficiency, not only candle FVG;
- "1 obiettivo cambio momentum" and "2 obiettivo chiusura inefficienza" are
  human scenario labels. The Lab must translate them into watch/test/reject
  contracts, not targets;
- "re test MM52" appears as a gate/confluence condition requiring exact MA
  definition;
- "aspettare test della trend line dei max" suggests a trendline construction
  and retest rule still missing.

Effect on the current Lab:

- the daily FVG proxy has now failed a stricter dual-adjacent null, so it should
  remain `watch`;
- this does not invalidate Alipio's broader "inefficiency closure" language;
  it shows that the current proxy is too weak/general;
- the next useful intake is to split "inefficiency" into typed contracts:
  FVG, LVN/Volume Profile void, or CME gap.

## Method Cards To Build

| Human phrase | Candidate observable | Data needed | Null/falsifier | Current status |
| --- | --- | --- | --- | --- |
| POC del volume profile | POC level in a declared profile window | exchange, OHLCV or tick/volume source, profile window, binning rule, timezone | matched random levels; adjacent-window POC; shuffled-volume profile | future tool |
| POC sotto | POC relation to current price and recent range | computed POC, current/closed candle, tolerance | random level below price; selected-window artifact | method card first |
| Ripartenza quando POC discendente si allinea al POC ascendente | POC drift/alignment event across successive windows | repeated profile windows, drift rule, alignment tolerance | shuffled windows; adjacent-window control; no-lookahead split | future tool |
| Retest trendline + POC | confluence event with declared trendline rule | trendline endpoints, POC, retest tolerance, forward window | POC-only vs trendline-only ablation; random slope line | future tool |
| Chiusura inefficienza | typed FVG/LVN/CME-gap closure event | inefficiency type, candle series, volume profile window/binning or CME gap source, fill threshold | strict dual-adjacent control; arbitrary equal-width zones; block-preserving returns; shuffled-volume profile for LVN | watch after strict-null FVG proxy failed |
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
7. When you say "inefficiency", which subtype do you mean here: FVG/imbalance,
   LVN/Volume Profile void, or CME gap?
8. What exactly makes that inefficiency "closed": wick touch, close inside,
   full traversal, percentage fill, volume fill or touch of HVN/POC?
9. If the marked zone is an LVN/Volume Profile void, what is the profile
   window, binning/resolution and volume threshold that defines "low volume"?
10. Which MM52 is intended: simple/exponential, close-based, weekly/daily, and
   must the candle close above/below it?
11. How are trendlines drawn: which pivots, which timeframe, what tolerance?
12. Which timeframe is used to define the object, and which timeframe is used
    to confirm it?
13. What would make the method fail?
14. What output would be useful if the Lab cannot produce a signal: watchlist,
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

Candidate first spec, after the 2026-05-19 strict-null result:

- `btc_method_intake_card.py`: writes a structured method card for one Alipio
  object with required data, unresolved definitions and no-signal boundary.
- `btc_daily_inefficiency_candidate.py`: already tested a simple daily
  FVG/gap-fill proxy and downgraded it to `watch` because the strict
  dual-adjacent null filled more than the proxy.
- next, `btc_volume_profile_lvn_proxy.py` or `btc_volume_profile_poc_proxy.py`:
  computed LVN/POC proxy with a
  declared binning/window rule, labelled as proxy unless real volume-profile
  data is available.

## Alipio Source Intake - 2026-05-24

Source observed by TM7-vps:

- local extracted text: `/opt/alipio file_BTC.md`;
- two operator-provided TradingView BTCUSD Bitstamp screenshots;
- screenshots are not stored in the repo;
- the extracted text is not copied verbatim into the public repo.

External reference check, used only to tighten definitions:

- TradingView defines Volume Profile as traded activity over a specified period
  at price levels, with POC as the price level with the highest traded volume:
  `https://www.tradingview.com/support/solutions/43000502040-volume-profile/`
- CME states Bitcoin futures trade Sunday-Friday, creating a concrete source
  boundary for any CME-gap test:
  `https://www.cmegroup.com/education/courses/introduction-to-bitcoin/what-are-bitcoin-futures`
- TradingView public FVG scripts commonly model FVG as a three-candle
  imbalance/skip zone; treat this as community implementation evidence, not as
  authority:
  `https://www.tradingview.com/script/3FU8M8KK-QuantRX-Fair-Value-Gap/`

Updated reading of the material:

- Alipio's "chiusura inefficienza" must remain a typed object, not a generic
  bullish/bearish expectation.
- The three admissible subtypes are:
  - FVG/imbalance: candle-derived skipped zone;
  - LVN/Volume Profile void: low-volume area inside a declared profile window;
  - CME gap: futures session close/open gap with futures-specific source.
- The screenshots emphasize weekly BTCUSD Bitstamp context, Volume Profile,
  POC, MM52, trendline retests and momentum-change labels.
- The phrase "POC sotto" is a risk/watch language. The Lab must translate it
  into relation-to-price plus baseline, not into warning, target or entry.
- The right-side Volume Profile visible in the screenshot is not reproducible
  from daily OHLCV alone unless the Lab declares a proxy. A true replay needs
  the profile window, row/bin setting, source volume and session policy.

Immediate cycle implication:

1. Do not rerun the broad daily FVG proxy as if it represented the full Alipio
   method. It already became `watch` under stricter null.
2. The next BTC object should be an **Alipio method-spec cycle**, not a price
   prediction cycle.
3. Best first candidate: `LVN/Volume Profile inefficiency spec card`.
4. If the exact TradingView profile parameters are not available, build only a
   proxy artifact and label it `proxy`, not `poc_replay`.
5. Keep Bitstamp as screenshot replay source, then test Binance/Coinbase as
   feed robustness before promotion.

Recommended next method contract:

```text
Object: LVN / Volume Profile inefficiency closure
Source: BTCUSD Bitstamp first; Binance/Coinbase for robustness
Timeframe: weekly screenshot context, daily data only for proxy unless native
  weekly/profile data is declared
Required parameters: profile window, binning/rows, POC/HVN/LVN threshold,
  touch/fill rule, invalidation rule, forward window
Nulls: equal-width random zones, adjacent profile window, shuffled-volume
  profile proxy, no-lookahead declaration
Allowed output: watch/test/reject, missing definitions, next data request
Forbidden output: target, entry, exit, buy/sell, advice
```

Questions to send back to Alipio before a stronger cycle:

1. Nei due screenshot, quale finestra esatta del Volume Profile genera POC/LVN?
2. Il profilo e Fixed Range, Visible Range o sessione/periodo specifico?
3. Quante righe/bin usa TradingView nel profilo?
4. Una inefficienza LVN e chiusa con wick, close, attraversamento completo o
   arrivo a HVN/POC?
5. MM52 e SMA o EMA, su weekly o daily, e quale close/touch invalida il test?
6. Le trendline sono costruite su quali pivot e con quale tolleranza?
7. Quale output sarebbe utile se il Lab non puo dare segnali: zona watch,
   invalidazione, reject reason o prossima domanda?

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
