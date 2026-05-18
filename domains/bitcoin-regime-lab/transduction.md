# Transduction — bitcoin-regime-lab

## Invariants

Movement, baseline/null, falsifier, runtime awareness and seed integration are
the invariant contract. The source request is planning context, not direct
truth.

## Excluded source contamination

Do not copy results from reference labs. Do not treat the request, operator
preference or capsule-only archive as evidence. Exclusions:

- buy/sell/entry/exit/price-target/profit/alpha/trading-signal language
- manual chart annotations treated as evidence without mechanical definitions
- Massimo Rea or Alipio methods treated as authority before observable/null/falsifier translation
- current/open candle backtests unless explicitly declared as live-only observation
- single-exchange wick or volume-profile result promoted without feed robustness

## Domain-native observables

The first real cycle must define observables that match `bitcoin-regime` and the
declared use dynamics. Until then this candidate remains reference-only.

## Null baseline

Every experiment needs baseline, null/control, and stop condition before
promotion. The smoke tool only verifies executable structure.


## Adaptive rules

Rules can be retired or narrowed when cycle traces show drift. A failed detector
must become a clearer precondition or be archived; it must not be rescued by
silent tuning.

## UI contract

The UI must expose field status, active tensions, falsifier, runtime dynamics,
data/source cards and what is not admissible.

## E2E install/runtime

The generated candidate must pass generator dry-run, isolated write, strict
M1-M8 validator, and then a later cycle-to-UI check before public use.

## skill_retrieval

Archive retrieval starts capsule-first. Skill archive, skill catalog and
enzimi are planning substrate until the required read depth is satisfied.

## possibility_inventory

Before choosing skills or tools, expose the available possibility field:
current docs, cognitive capsules, MMSp lineage, source Labs, presets and public
surfaces that can orient the first cycle without becoming automatic authority.

## skill_intent_map

The machine-readable map is stored in `skill_intent_map_json` and appended by
the generator when needed.

## question_field

The first cycle must expose the question that moves the Lab, the possible paths
still open, the missing nodes that prevent observation, and what would falsify
each path before promotion.

## capability_cascade

Any reusable capability must be written as a propagation candidate, not as an
automatic rule. Transfer to another Lab requires domain-native observables,
baseline/null and UI lens.


## possibility_inventory_json

Auto-generated availability map. These sources are possibilities, not automatic authority.

```json
[
  {
    "source_id": "skill_docs",
    "source_path": "docs/SKILL_CATALOG.md + docs/SKILL_FIELD_MAP.md + docs/SKILL_DIAGNOSTIC.md",
    "source_kind": "catalog",
    "available_possibility": "Route the request through validation, processing, observation, interface and runtime layers.",
    "movement_link": "choose minimal coordinated skills for the requested movement",
    "read_depth_required": "L0 for routing; L1-L2 before active MML authority",
    "candidate_artifact": "skill_reading_matrix|mml|context",
    "activation_trigger": "before generated Lab context or MML is finalized",
    "test_or_evidence": "M8 skill_intent_map and validator coherence",
    "contamination_risk": "declaring skills by name without reading their body",
    "status": "available"
  },
  {
    "source_id": "cognitive_archives",
    "source_path": "docs/cognitive_archives/*.json",
    "source_kind": "capsule",
    "available_possibility": "Use KPhi1, THIA skill snapshot and cockpit/MMSp lineage as planning context without loading full archives.",
    "movement_link": "recover existing cognitive patterns before inventing new ones",
    "read_depth_required": "CAPSULE; BODY when changing context, MML, tool, assertion or UI",
    "candidate_artifact": "archive_retrieval|transduction|skill_intent_map",
    "activation_trigger": "when the request needs autonomous cognition, lineage or missing capability recovery",
    "test_or_evidence": "archive_retrieval_json with body_required when capsule is insufficient",
    "contamination_risk": "treating capsule or historical language as active authority",
    "status": "available"
  },
  {
    "source_id": "physics_lab_source",
    "source_path": "domains/physics + docs/templates/domain_presets/physics_bridge.v1.json",
    "source_kind": "lab_source",
    "available_possibility": "Reuse bridge audits, null discipline, observable contracts and tool-surface patterns as movement templates.",
    "movement_link": "transfer scientific cycle discipline without copying physics content",
    "read_depth_required": "L1 for docs/preset; E2E before shared generator rule",
    "candidate_artifact": "null|baseline|tool|ui|preset",
    "activation_trigger": "when a new domain needs bridge, scale, null or observable-contract logic",
    "test_or_evidence": "domain-native observables and nulls in the receiving Lab",
    "contamination_risk": "copying TQGE/physics labels or numerical results into another domain",
    "status": "available"
  },
  {
    "source_id": "domain_presets",
    "source_path": "docs/templates/domain_presets",
    "source_kind": "preset",
    "available_possibility": "Accelerate known domain families while preserving intent-specific adaptation.",
    "movement_link": "seed observables, baseline, falsifiers and UI modules for matching families",
    "read_depth_required": "L1 plus adaptation questions",
    "candidate_artifact": "ui_contract|seed_tensions|baseline|null",
    "activation_trigger": "when domain kind matches an existing preset family",
    "test_or_evidence": "strict validator plus first cycle smoke",
    "contamination_risk": "preset copied without adapting to the actual intent",
    "status": "available"
  },
  {
    "source_id": "public_physics_surface",
    "source_path": "d-nd.com/ai-lab + docs/LAB_SURFACE_TOPOLOGY.md",
    "source_kind": "public_surface",
    "available_possibility": "Learn which UI/THIA surfaces help humans read the physics Lab and transfer only the interaction pattern.",
    "movement_link": "improve dashboard explanation and assistant context without treating public UI as runtime evidence",
    "read_depth_required": "support_only unless paired with repo/runtime evidence",
    "candidate_artifact": "ui|copy|assistant_context",
    "activation_trigger": "when generated Lab needs public-facing comprehension or THIA framing",
    "test_or_evidence": "cycle-to-UI check and explicit surface boundary",
    "contamination_risk": "confusing main-site physics Lab with installable D-ND_LAB runtime",
    "status": "support_only"
  },
  {
    "source_id": "domain_preset:bitcoin_regime.v1",
    "source_path": "docs/templates/domain_presets/bitcoin_regime.v1.json",
    "source_kind": "preset",
    "available_possibility": "Domain-native starter observables, baselines, falsifiers, UI modules and adaptation questions.",
    "movement_link": "adapt known domain-family patterns to this request before inventing new tools",
    "read_depth_required": "L1 plus adaptation questions; E2E before promotion",
    "candidate_artifact": "seed_tensions|context|tool|null|baseline|ui_contract",
    "activation_trigger": "when the request kind matches the preset domain_family",
    "test_or_evidence": "strict validator, smoke tool and first cycle with domain-native data-card",
    "contamination_risk": "using the preset as final domain truth or skipping intent-specific adaptation",
    "status": "available",
    "preset_id": "bitcoin_regime.v1",
    "starter_observables": [
      "btc_log_return",
      "realized_volatility",
      "drawdown_recovery_path",
      "range_trend_persistence",
      "volume_or_liquidity_proxy",
      "volume_profile_poc",
      "low_volume_node_lvn",
      "fvg_or_imbalance_zone",
      "cme_gap_status",
      "trendline_retest_event",
      "naked_poc_lifecycle_state",
      "timeframe_matrix_status",
      "kumo_regime_state",
      "exchange_event_agreement"
    ],
    "starter_baselines": [
      "random_walk_or_naive_drift",
      "shuffled_returns",
      "circular_block_shuffle",
      "adjacent_window_control",
      "friction_baseline",
      "matched_random_level",
      "shuffled_volume_profile",
      "equal_width_zone_fill_rate",
      "predeclared_forward_window",
      "timeframe_denominator_control",
      "poc_confluence_ablation",
      "feed_robustness_null",
      "open_candle_exclusion"
    ],
    "starter_falsifiers": [
      "lookahead_bias",
      "selected_window_artifact",
      "baseline_collapse",
      "method_without_observable",
      "manual_annotation_drift",
      "fill_rate_without_denominator",
      "volume_proxy_confusion",
      "signal_language_before_promotion"
    ],
    "domain_native_ui_modules": [
      "RegimeState",
      "EvidenceVsBaseline",
      "WatchRejectTest",
      "DataCard",
      "NonAdmissibleInference",
      "VolumeProfileMap",
      "InefficiencyMap",
      "HypothesisCard",
      "InvalidationRules",
      "TimeframeMatrix",
      "NakedPOCQueue",
      "KumoRegimeMap",
      "FeedRobustness",
      "SourceMethodCards"
    ],
    "adaptation_questions": [
      "Which BTC data source is acceptable for the first public cycle?",
      "Which timeframe and granularity should be monitored first?",
      "Which human question should the Lab constrain rather than predict?",
      "Which expert method, if any, is documented enough to be translated into observable, null and falsifier?",
      "What should a human observer see in the dashboard after one useful cycle?",
      "Which volume-profile source and binning rule are acceptable for a first POC/LVN cycle?",
      "How is an inefficiency considered filled, partially filled or invalidated?",
      "Which Alipio/Massimo Rea method should be translated first into observable, null and falsifier?"
    ]
  }
]
```



## question_field_json

Auto-generated from the domain request so the candidate preserves the question that moves the first cycle.

```json
{
  "primary_question": "Can `bitcoin-regime-lab` turn the requested intent into an observable cycle without promoting an untested result?",
  "possibility_field": [
    "installable reference candidate",
    "blocked domain with useful missing nodes",
    "domain-specific tool or data requirement before first real cycle"
  ],
  "missing_nodes": [
    "domain-native observables from first real cycle",
    "claim-appropriate baseline/null",
    "cycle-to-UI evidence before public use"
  ],
  "falsification_paths": [
    "no observable can be defined without copying another domain",
    "baseline/null cannot be built out-of-box",
    "cycle output cannot update seed, report and UI surfaces"
  ],
  "observable_requirements": [
    "source/data card where external data is used",
    "runtime trace",
    "falsifier verdict",
    "seed or cimitero update"
  ],
  "non_admissible": [
    "buy/sell/entry/exit/price-target/profit/alpha/trading-signal language",
    "manual chart annotations treated as evidence without mechanical definitions",
    "Massimo Rea or Alipio methods treated as authority before observable/null/falsifier translation",
    "current/open candle backtests unless explicitly declared as live-only observation",
    "single-exchange wick or volume-profile result promoted without feed robustness"
  ],
  "next_question": "What is the smallest real cycle that can make the domain-specific movement observable?"
}
```

## capability_cascade_json

Auto-generated propagation card. It is a candidate, not an automatic promotion rule.

```json
[
  {
    "capability_id": "domain_request_to_installable_candidate",
    "source_domain": "meta-lab",
    "source_cycle": "domain_request_runner",
    "new_affordance": "Convert a domain request into an isolated install-or-block candidate with M1-M8 evidence.",
    "immediate_domain": "bitcoin-regime-lab",
    "transferable_domains": [
      "future generated labs"
    ],
    "affected_surfaces": [
      "context",
      "mml",
      "tools",
      "assertions",
      "ui_contract",
      "onboarding",
      "docs",
      "tests"
    ],
    "required_checks": [
      "strict M1-M8 validator",
      "smoke tool output",
      "cycle-to-UI check before public use"
    ],
    "non_admissible_transfer": [
      "copying domain content as evidence",
      "treating a reference candidate as a live Lab"
    ],
    "next_question": "Which candidate capability should become a reusable preset only after another domain needs it?"
  }
]
```
