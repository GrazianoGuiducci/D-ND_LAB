# D-ND Bio-Rhythms Lab

**The regime exists only if it survives the shuffle.**

Is the heart rate accelerating, or is an arrhythmia emerging? Is sleep
transitioning to the next stage, or just EEG noise? Same structural
problem as the finance lab, applied to biosignals.

## What it does

The D-ND Bio-Rhythms lab measures whether transitions in biosignals —
heart-rate variability, sleep stages, circadian gene expression — are
**oriented dipoles** preserved by M, or statistical illusions that
collapse once temporal order is destroyed.

The point is not "predict an arrhythmia" — it is to structurally
distinguish a real regime from a variation that looks like structure
but isn't.

## How

For each biosignal window:

1. Measure ordered — orientation score under operator M
2. Measure on shuffle — same distribution, order destroyed
3. Compare naive baseline — RMSSD + SDNN (classical HRV time-domain)
4. Report D-ND delta vs naive vs null shuffle
5. Promote only if delta survives at least 2 windows + 2 independent
   subjects

## What it produces

- Falsifiable operational constraints (e.g. "the HRV dipole requires
  windows ≥ 5 minutes to separate from RMSSD noise")
- Packageable kernel `dnd_kernel_bio_rhythm_regime` when a finding
  survives multi-window + multi-subject
- Process honesty: the lab declares NO_DELTA when there is no signal,
  instead of selling results that don't exist

## For whom

- Wearable health teams: structural validation of their HRV algorithms
- Sleep tracking: discrimination between real stages and oscillation
- Clinical decision support: structural rigor as pre-diagnostic layer
- Researchers who want to falsify their own hypotheses before the paper

The lab does not replace a cardiologist or sleep specialist. It
measures whether the signal actually says what one thinks it does.

*Status: alpha · domain under validation · synthetic pipeline validated ·
promotion requires verified real origin and multi-subject controls.*
