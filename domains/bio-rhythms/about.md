# AI-Lab D-ND Bio-Rhythms

**Il regime esiste solo se sopravvive allo shuffle.**

Il battito cardiaco accelera o un'aritmia sta emergendo? Il sonno sta
transitando alla fase successiva o è solo rumore EEG? Lo stesso
problema strutturale del lab finance, applicato ai biosegnali.

## Cosa fa

Il lab D-ND Bio-Rhythms misura se le transizioni nei biosegnali —
heart-rate variability, fasi del sonno, espressione genica circadiana —
sono **dipoli orientati** che M preserva, oppure illusioni statistiche
che collassano quando l'ordine temporale viene distrutto.

Il punto non è "predire un'aritmia" — è distinguere strutturalmente un
regime reale da una variazione che sembra struttura ma non lo è.

## Come

Per ogni finestra di biosegnale:

1. Misura ordinato — score di orientamento sotto operatore M
2. Misura su shuffle — stessa distribuzione, ordine distrutto
3. Confronta naive baseline — RMSSD + SDNN (HRV classici time-domain)
4. Riporta delta D-ND vs naive vs null shuffle
5. Promuovi solo se delta sopravvive a almeno 2 finestre + 2 soggetti
   indipendenti

## Cosa produce

- Constraint operativi falsificabili (es. "il dipolo HRV richiede
  finestre ≥ 5 minuti per separare da rumore RMSSD")
- Kernel pacchettizzabile `dnd_kernel_bio_rhythm_regime` quando un
  finding sopravvive multi-window + multi-subject
- Onestà del processo: il lab dichiara NO_DELTA quando il segnale non
  c'è, invece di vendere risultati inesistenti

## Per chi

- Wearable health team: validazione strutturale dei loro algoritmi HRV
- Sleep tracking: discriminazione tra fase reale e oscillazione
- Clinical decision support: rigore strutturale come layer pre-diagnostico
- Ricercatori che vogliono falsificare le proprie ipotesi prima del paper

Il lab non sostituisce un cardiologo o un sonnologo. Misura se il
segnale dice quello che si pensa dica.

*Status: alpha · dominio in collaudo · pipeline sintetica validata ·
promozione vincolata a origine reale verificata e controlli multi-soggetto.*
