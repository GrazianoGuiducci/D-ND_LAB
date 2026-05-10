# Bio-Rhythms Lab

Lab D-ND di dominio per regime detection in biosegnali cardiaci e
circadiani. Conversione 2026-05-05 della directory `physics` (dormiente,
duplicava il lab fisico master MM_D-ND).

## Quickstart

Pipeline cycle (synthetic, no network):

```bash
cd /opt/D-ND_LAB
.venv/bin/python3 -m core.cli inspect --domain bio-rhythms
.venv/bin/python3 -m core.cli run --domain bio-rhythms
```

Gate dati reali (cycle 2+, PhysioNet):

```bash
# HRV da MIT-BIH normal sinus rhythm
.venv/bin/python3 domains/bio-rhythms/tools/biosignal_data.py \
    --provider physionet --record nsr2db/sel100 --signal RR

# Esperimento ordered-vs-shuffle su HRV da sorgente verificata
.venv/bin/python3 domains/bio-rhythms/tools/exp_hrv_regime.py \
    --from-physionet nsr2db/sel100 --json
```

## Struttura

- `mml.json` — multi-layer skill manifest, 16 skill su 8 layer
- `config.json` — 17 movements abilitati (autopsy → notify, incluso
  `trajectory_apply` per loop A8+A15)
- `seed_tensions.json` — 5 tensioni iniziali (RR_INTERVAL_DIPOLE,
  RMSSD_VS_DND_SPLIT, CASSINI_RESIDUE_BIOSIGNAL, NO_NETWORK_FIRST_CYCLE,
  KERNEL_BIO_PACKAGING)
- `tension_to_category.json` — mappatura per indicizzazione cross-lab
- `context.md` — prompt di sistema per l'agent del lab
- `assertions.py` — 5 asserzioni numeriche M1-M6 sandboxed
- `tools/exp_hrv_regime.py` — esperimento sintetico HRV con regime
  shift e null shuffle
- `tools/biosignal_data.py` — acquisizione da PhysioNet con cache +
  data card

## Roadmap (post-cycle 1)

1. Cycle 1 synthetic: verdict baseline pipeline
2. Cycle 2 PhysioNet MIT-BIH NSR (normal) + AFDB (atrial fibrillation):
   verificare provenienza reale prima di leggere il risultato come biologico
3. Cycle 3+ multi-soggetto + multi-window per validare se DND_DELTA
   sopravvive (constraint promotability)
4. Stage 5 packaging quando finding survive 2 finestre + 2 soggetti
5. Estensione a sleep stage transitions (Sleep-EDF) come secondo asse
6. Estensione a circadian gene expression (NCBI GEO) come terzo asse
