# Lab Thought And Capability Cascade

> Contratto operativo per trattare i cicli come pensiero del Lab e per
> propagare nuove capacita' senza trasformarle in regole cieche.
>
> Stato: prima cristallizzazione, 2026-05-18.

## Scopo

Un ciclo non e' solo un report e non e' solo falsificazione. Il ciclo e' il
pensiero osservabile del Lab: apre domande, genera possibilita', costruisce
strumenti, attacca le proprie ipotesi, conserva cio' che resta utile e
prepara il ciclo successivo.

Il falsifier resta autorita' di blocco, ma non e' l'intero Lab. Il Lab valido
ha almeno questi organi:

- **domandatore**: apre il campo delle possibilita' e identifica i nodi
  mancanti;
- **campo**: rende osservabili dati, tensioni, vincoli, runtime e residui;
- **agente**: propone ipotesi operative e strumenti;
- **falsifier**: attacca claim, bias, hard-zero, edge case e continuita';
- **deposito**: conserva report, cimitero, graph, bicono e prodotti;
- **cascata**: decide quali capacita' locali possono servire altri domini o
  superfici.

## Ciclo Come Pensiero

Ogni ciclo deve poter essere letto con questa sequenza:

```text
osserva -> domanda -> possibilita' -> esperimento/tool -> falsificazione
-> deposito -> cascade -> prossimo seme
```

Se manca la domanda, il ciclo rischia di diventare solo sweep. Se manca il
falsifier, diventa narrazione. Se manca la cascata, il sistema impara solo
localmente e il meta-lab non acquisisce nuove frecce.

## Domandatore Contract

Ogni nuovo Lab, nuovo ciclo importante o nuova capacita' trasferibile deve
produrre un blocco `question_field` nel report, in `transduction.md` o in un
artefatto equivalente.

Campi minimi:

```json
{
  "primary_question": "quale domanda muove il ciclo",
  "possibility_field": ["vie aperte prima del collapse operativo"],
  "missing_nodes": ["dati, tool, baseline, null, UI o skill mancanti"],
  "falsification_paths": ["cosa renderebbe falsa o non utile ogni via"],
  "observable_requirements": ["cosa serve per rendere misurabile la domanda"],
  "non_admissible": ["cosa non deve essere promosso o trasferito"],
  "next_question": "domanda minima che il ciclo consegna al successivo"
}
```

Regola: il domandatore non sostituisce il falsifier. Apre il possibile prima
del test; il falsifier decide cosa non puo' entrare come autorita'.

## Capability Cascade Card

Quando un ciclo produce una capacita' nuova, anche piccola, il Lab deve
scrivere una `capability_cascade` invece di affidarsi alla memoria della chat.

Schema logico:

```json
{
  "capability_id": "slug-stabile",
  "source_domain": "dominio o ciclo sorgente",
  "source_cycle": "id report/trace se disponibile",
  "new_affordance": "cosa ora il sistema puo' fare che prima non faceva",
  "immediate_domain": "dove nasce e dove e' gia' verificata",
  "transferable_domains": ["domini candidati, non promossi automaticamente"],
  "affected_surfaces": [
    "context",
    "mml",
    "tools",
    "assertions",
    "ui_contract",
    "dashboard",
    "thia",
    "installer",
    "public_copy",
    "onboarding",
    "docs",
    "tests"
  ],
  "required_checks": ["test prima della promozione"],
  "non_admissible_transfer": ["cosa sarebbe contaminazione"],
  "next_question": "quale domanda apre nel meta-lab"
}
```

La card non autorizza la propagazione automatica. Produce candidati di
propagazione. Ogni propagazione reale deve passare dal dominio ricevente con
osservabili, baseline/null e UI lens propri.

## Livelli Di Cascata

- **Locale**: migliora il Lab corrente senza cambiare altri domini.
- **Dominio fratello**: una capacita' puo' servire finance, bitcoin,
  research-radar, bio-rhythms o altri Lab, ma va tradotta.
- **Meta-lab/generatore**: una capacita' diventa preset, template, validator,
  tool o prompt del generatore.
- **Superficie pubblica/prodotto**: la capacita' cambia dashboard, copy,
  onboarding, installer, documentazione o THIA assistant.
- **Archivio/skill**: la capacita' e' ricorrente e merita capsula, skill o
  integrazione nel capability stack.

## Regole Di Promozione

1. Una capacita' nata in un dominio non diventa regola generale solo perche'
   ha funzionato una volta.
2. Prima della promozione serve dichiarare `valid_when` e `retire_when`.
3. Il trasferimento deve conservare il movimento, non il contenuto del dominio
   sorgente.
4. Se una capacita' modifica UI, installer, MML, context o copy pubblica,
   deve comparire nella cascade card.
5. Se una capacita' apre piu' direzioni possibili, usare il domandatore prima
   del collapse: non scegliere la prima forma plausibile solo perche' e'
   implementabile.

## Esempio: Bitcoin Timeframe Matrix

Possibile capacita' nata dal Bitcoin Regime Lab:

- `capability_id`: `timeframe_matrix_discovery`
- `new_affordance`: confrontare piu' timeframe come campo di osservazione,
  non come opinione dell'operatore.
- `immediate_domain`: bitcoin-regime-lab.
- `transferable_domains`: finance, bio-rhythms, research-radar, monitoring.
- `required_checks`: leakage guard, feed robustness, baseline naive,
  timeframe-specific null, decision boundary no-signal.
- `non_admissible_transfer`: copiare livelli BTC o POC come contenuto in
  altri domini; promuovere timeframe come segnale operativo.
- `next_question`: quali domini hanno fenomeni multi-scala dove la scala
  stessa e' osservabile falsificabile?

Il meta-lab deve registrarla come possibilita'. La promuove a preset comune
solo se almeno due domini la richiedono e superano controlli domain-native.

## Output Atteso Nel Meta-lab

Ogni generazione o affinamento sostanziale deve riportare:

- `question_field`: domanda, possibilita', nodi mancanti e falsificazioni;
- `capability_cascade`: nuove capacita' e superfici toccate;
- `missing_nodes`: cosa manca per far pensare meglio il Lab al ciclo
  successivo;
- `propagation_candidates`: dove la capacita' potrebbe essere utile, senza
  promuoverla automaticamente.

Questi blocchi sono parte della consapevolezza del sistema. Se restano solo in
chat, al compact successivo diventano perdita di movimento.
