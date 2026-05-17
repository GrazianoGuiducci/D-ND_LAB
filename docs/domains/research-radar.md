# Research Radar

`research-radar` is a generated D-ND domain for emerging research and
technology claims.

Its purpose is not to predict which paper or technology will matter. It turns
claims into falsifiable claim cards:

- source provenance;
- observable;
- naive baseline;
- null/control family;
- falsifier status;
- decision bound: `reject`, `watch`, `test` or `promote`.

## First Tool

The initial offline tool is:

```bash
python3 domains/research-radar/tools/exp_claim_radar.py --json
```

It uses synthetic claim cards and no network. The first useful boundary is:
a claim with hype and weak provenance is rejected; a claim with source,
independent evidence and reproducibility artifact can enter `TEST`, not
`PROMOTE`.

## Validation

Before promotion, validate the template with:

```bash
python3 domains/meta-lab/tools/lab_template_validator.py --strict-m7 domains/research-radar
python3 -m core.cli inspect --domain research-radar
python3 -m core.cli dry-run --domain research-radar
```

The domain was generated through the meta-lab capability stack, not by copying
the GPT/MMSp package directly.
