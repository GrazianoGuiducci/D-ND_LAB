# Tests

Phase 0 placeholder. Test scaffolding lands in Phase 1 alongside core/
implementation.

## Planned coverage

- **Unit**: each movement function (dispatcher, autopsy parser, seed
  integrator filter logic, semantic bridge mapping).
- **Integration**: full cycle on a fixture domain (synthetic seed +
  recorded LLM responses) — verifies orchestration end-to-end without
  hitting a real provider.
- **Contract**: domains/<name>/config.json validates against
  config.schema.json. Missing fields fail loudly.
- **Regression**: Phase 1 milestone — physics domain run via the new
  template produces output equivalent (modulo timestamps + LLM
  variability) to the original /opt/MM_D-ND/tools/lab_agent.sh.
