# D-ND Lab Portfolio Status - 2026-05-24

Status: operational classification, not product promise.

This document records the current working classification of the visible Labs so
the system does not spend energy polishing inactive surfaces before value
cycles exist.

## Principle

The Lab portfolio is not judged by UI completeness. A Lab is useful when it has
one of these roles:

- produces value-facing artifacts from real inputs;
- protects the system from false promotion;
- generates or evaluates other Labs;
- preserves a method until a future cycle can make it observable.

Translation polish, extra buttons and UX refinements are suspended unless they
serve one of those roles.

## Current Classes

| Lab | Class | State | Next useful action |
| --- | --- | --- | --- |
| D-ND Meta-lab | core/genesis | Generates and validates Lab templates and installable candidates. | Keep as Genesis Lab. Use it to turn proven patterns into reusable contracts. |
| D-ND MetaMasterLab (`ops-decisions`) | core/system | Governs Lab evolution, intent drift, noise vs exponentiality and promotion/block decisions. | Keep slug for compatibility. Use it to decide which Lab evolves next. |
| Bitcoin Regime Lab | value-active | Has live value artifacts, feed gate, timeframe matrix, Alipio method intake and dashboard surface. Latest agent cycle exposed a runtime report contract failure, not a domain claim. | Initialize next cycle from Alipio material as method-spec, not price signal. Repair/report contract before trusting autonomous output. |
| AI-Lab D-ND Research Radar | value-candidate | Has claim-card artifact and a clear external use: classify emerging claims by source/data-card/null. | Give it one real claim task, preferably AI/research/tooling, and see if it produces a useful evidence roadmap. |
| AI-Lab D-ND Finance | method-reserve | Has rich history and baseline/null lessons, but no current value artifacts. Useful as regime-method laboratory, not public market product yet. | Run a small supervised refresh only to test self-improvement and artifact production, not to publish finance signal. |
| D-ND Physics Lab | origin/core-reserve | Original autonomous D-ND research Lab. Also visible on the site as the D-ND physics/research Lab. Deep and valuable, but should not be casually restarted. | Keep known. Reopen separately with supervised restart logic. |
| AI-Lab D-ND Bio-Rhythms | draft/provenance-test | Useful provenance lesson: strong synthetic delta cannot become biological finding. Needs PhysioNet/WFDB acquisition repair before value. | Keep as draft/testbed for provenance guards. Do not promote until real-data acquisition is repaired. |
| Editorial Lab | parked | Contains a useful constraint: directive is not source. Without a live corpus task it risks becoming noise. | Park. Reopen only if there is a concrete corpus/publishing task. |

## Operational Direction

Near-term priority:

1. BTC: use Alipio material to produce one useful method-spec or proxy artifact.
2. Research Radar: assign one real claim and test value.
3. Finance: run a small supervised artifact refresh to observe self-improvement.
4. MetaMasterLab: use results from 1-3 to decide evolution, block or quarantine.

Do not spend more time on translations/buttons until a Lab result makes the UX
worth polishing.

## Production Boundary

BTC and Finance are not production trading systems.

Allowed public posture:

- observable field;
- watch/test/reject status;
- missing definitions;
- falsifier result;
- next useful question.

Forbidden public posture:

- buy/sell;
- target;
- entry/exit;
- advice;
- alpha/performance promise.

## Next BTC Initialization From Alipio

Input available:

- `/opt/alipio file_BTC.md`;
- two TradingView BTCUSD Bitstamp screenshots;
- existing BTC method intake document.

Next BTC cycle should ask:

```text
Can the Alipio "inefficiency closure" language be turned into one typed,
observable method contract without becoming a signal?
```

Expected output:

- method subtype selected or blocked;
- missing parameters listed;
- proxy/non-proxy boundary explicit;
- nulls selected;
- no trading signal.

Implemented first backend step:

- tool: `domains/bitcoin-regime-lab/tools/btc_auto_ignite.py`;
- artifact: `data/bitcoin-regime-lab/value/btc_auto_ignite_latest.json`;
- role: gather current BTC artifacts, generate provisional LVN/Volume Profile
  proxy assumptions, expose nearest LVN proxy zones and define next nulls;
- future UI: `autoaccendi Lab` button can call this tool/API before any
  cognitive cycle.

## Next Finance Probe

Finance should not be restarted as prediction. A useful probe is:

```text
Can the Finance Lab produce a fresh value artifact that carries forward the
sliding-window/split-bias lesson and exposes what it refuses to infer?
```

If it cannot produce a current artifact, MetaMasterLab should classify it as
method-reserve until the data/value path is repaired.
