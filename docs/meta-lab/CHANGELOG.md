# Meta-lab Changelog

## 2026-05-21

### Added

- Added `docs/templates/assistant_contract.v0.json` as draft contract for
  reusable THIA context assistants across public site, Lab dashboards,
  generated Labs, installer surfaces and admin review.
- Extended `docs/templates/ui_contract.v1.json` with an optional `assistant`
  block.
- Extended `docs/templates/onboarding_contract.v1.json` with
  `assistant_intake` quarantine/review rules.

### Updated

- Expanded `THIA_contextual_assistant` in
  `docs/meta-lab/CAPABILITY_REGISTRY.json` from prompt-context capability into
  a domain-adapted assistant/intake contract capability.
- Marked Finance and Meta-lab registry entries as assistant-adapter candidates.
- Added Finance and BTC assistant examples to their `ui_contract.json` files:
  starter profiles, intake profiles, forbidden imports/outputs and promotion
  boundaries.
- Updated `domains/meta-lab/context.md` so generated Labs treat THIA assistant
  profile as part of the Lab birth contract.
- Updated `domains/meta-lab/tools/domain_request_runner.py` so generated
  candidates include an `assistant` block in `ui_contract.json` and
  `assistant_intake` in `onboarding_contract.json`.

### Boundary

- Documentation and contract changes only.
- No widget, dashboard runtime, API, installer, seed or deploy behavior
  changed.
- Generator behavior changed only for future isolated/generated candidates:
  it now emits assistant contract metadata; it does not install or activate
  any Lab by itself.

## 2026-05-20

### Added

- Created `docs/META_LAB_ORGANIC_GROWTH_SYSTEM.md` as governance layer for
  organic Lab growth.
- Created draft registries:
  - `docs/meta-lab/CAPABILITY_REGISTRY.json`;
  - `docs/meta-lab/LAB_REGISTRY.json`;
  - `docs/meta-lab/MIGRATION_REGISTRY.json`.

### Captured

- BTC -> Meta-lab transferable patterns:
  - `lab_review_card`;
  - `human_method_intake_card`;
  - `value_artifact_before_cycle`;
  - `host_side_pre_cycle_refresh`;
  - `source_robustness_gate`;
  - `scale_or_timeframe_matrix`;
  - `confluence_ablation`;
  - `THIA_contextual_assistant`;
  - `markdown_admin_review`.
- Finance as mature reference for:
  - `no_signal_boundary`;
  - baseline/null;
  - precondition boundary;
  - data-card;
  - decision bounds.
- Safety candidates:
  - `source_provenance_guard`;
  - `role_boundary_guard`;
  - `secret_redaction_guard`.

### Proposed

- Migrate `lab_review_card` to Finance through a domain adapter
  `finance_regime_review_card`.
- Adapt BTC source robustness into Finance provider/dataset robustness.
- Review whether BTC timeframe matrix and Physics scale sweep should become a
  generic scale admissibility capability.
- Apply role-boundary and secret-redaction guards to public intake surfaces
  only after inventory and tests.

### Boundary

- These files are documentation/registry drafts only.
- No runner, generator, installer, seed, tool, API or UI behavior changed.
