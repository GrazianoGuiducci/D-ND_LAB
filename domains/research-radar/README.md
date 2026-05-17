# Research Radar Lab

Generated from a meta-lab domain request. Purpose: turn emerging research and
technology claims into claim cards with source provenance, baseline/null,
falsifier and decision bounds.

Smoke:

```bash
python3 domains/research-radar/tools/exp_claim_radar.py --json
python3 domains/meta-lab/tools/lab_template_validator.py --strict-m7 domains/research-radar
python3 -m core.cli inspect --domain research-radar
```
