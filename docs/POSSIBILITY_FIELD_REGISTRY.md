# Possibility Field Registry

> Contratto operativo per fornire al meta-lab le possibilita' disponibili
> prima che scelga skill, strumenti, preset o propagazioni.
>
> Stato: prima cristallizzazione, 2026-05-18.

## Scopo

La `capability_cascade` registra cosa puo' propagarsi dopo che una capacita'
emerge. Prima pero' serve una superficie diversa: il **campo delle
possibilita' disponibili**.

Il meta-lab non deve ricordare a mano che esistono skill MMSp, capsule,
KPhi1, `/opt/skill`, preset di dominio, Lab fisico, Lab finance o il Lab di
fisica pubblico sul sito. Deve ricevere una mappa ispezionabile:

```text
fonti disponibili -> possibilita' candidate -> lettura richiesta
-> artefatto possibile -> test -> esclusioni
```

Questo documento definisce il blocco `possibility_inventory`.

## Fonti Del Campo

Le fonti non hanno la stessa autorita'. Vanno presentate al meta-lab come
possibilita', non come istruzioni da copiare.

| Fonte | Uso corretto | Autorita' iniziale |
|---|---|---|
| `docs/SKILL_CATALOG.md` | vedere skill candidate e layer | catalogo |
| `docs/SKILL_FIELD_MAP.md` | capire collaborazioni e architettura MMSp | mappa |
| `docs/SKILL_DIAGNOSTIC.md` | distinguere viva, stub, persona, no-eval | diagnostica |
| `docs/cognitive_archives/*.json` | orientare senza leggere archivi lunghi | capsula |
| `/opt/MM_D-ND/tools/data/cognitive_enzymes_archive.md` | recuperare enzimi gia' estratti | capsula/lineage |
| `/opt/skill` | snapshot THIA flat e thinker-pack | corpo se letto |
| `/opt/KPhi1` | seme installabile, router facolta', veto, memoria | corpo se letto |
| `/opt/d-nd_cockpit/docs/system/kernel` | lineage MMSp storico | corpo se letto |
| `domains/physics` | Lab sorgente verificato, tool e pattern fisici | esempio sorgente |
| `domains/finance` e altri Lab figli | pattern pratici e UI/domain lens | esempio derivato |
| `docs/templates/domain_presets` | acceleratori di famiglia | preset |
| sito `d-nd.com/ai-lab` | superficie pubblica del Lab fisico e THIA | pubblico, non runtime repo |

## Possibility Inventory

Ogni generazione o affinamento sostanziale deve produrre un blocco:

```json
{
  "possibility_inventory": [
    {
      "source_id": "skill_catalog|physics_lab|kphi1|cockpit_mmsp|...",
      "source_path": "path o superficie",
      "source_kind": "catalog|capsule|body|lab_source|preset|public_surface",
      "available_possibility": "cosa rende possibile",
      "movement_link": "quale movimento del Lab potrebbe servire",
      "read_depth_required": "L0|L1|L2|L3|CAPSULE|BODY|BODY_PLUS_REFS|E2E",
      "candidate_artifact": "context|mml|tool|assertion|null|baseline|ui|preset|copy|skill",
      "activation_trigger": "quando il Lab dovrebbe usarla",
      "test_or_evidence": "come verificare che non sia decorativa",
      "contamination_risk": "cosa non trasferire",
      "status": "available|needs_body_read|support_only|deferred|blocked"
    }
  ]
}
```

Il blocco puo' stare in `skill_intent_map_json`, in `transduction.md` o in un
report meta-lab. Se una fonte modifica `context.md`, `mml.json`, tool,
assertions, UI o regole di ciclo, deve anche comparire in
`archive_retrieval` o `skill_reading_matrix` con profondita' coerente.

## Sequenza Corretta

```text
domain_request
  -> possibility_inventory
  -> question_field
  -> skill_reading_matrix
  -> skill_intent_map
  -> generated artifacts
  -> capability_cascade
```

La domanda usa le possibilita' disponibili, ma non ne e' schiava. Il
domandatore puo' aprire una via non ancora presente; in quel caso la via entra
in `missing_nodes` e non in `skills_attive`.

## Cross-lab Exchange

Il Lab fisico e i Lab figli devono potersi scambiare pattern senza copiarsi.

Esempi:

- Physics -> Bitcoin/Finance: null di label shuffle, finite-size/scale sweep,
  unfolding sensitivity diventano pattern di robustezza, non contenuto fisico.
- Finance -> Bitcoin: boundary no-signal, decision constraints e data-card
  diventano guardrail contro segnali prematuri.
- Bitcoin -> Meta-lab: timeframe matrix e feed robustness possono diventare
  preset multi-scala solo dopo almeno un altro dominio con controlli propri.
- Public physics Lab su `d-nd.com/ai-lab` -> repo: UI/THIA e narrazione
  possono mostrare cosa aiuta gli umani a capire il ciclo, ma non sono prova
  del runtime installabile.
- Repo -> sito pubblico: nuove capacita' del meta-lab possono aggiornare copy
  e dashboard solo dopo E2E e confine epistemico chiaro.

## Regole

1. Una possibilita' non letta e' `available` o `needs_body_read`, non
   `active`.
2. Una possibilita' senza artefatto candidato resta `support_only`.
3. Una possibilita' che richiede segreti, dati privati o runtime non
   disponibili resta `blocked` o `deferred`.
4. Un Lab sorgente fornisce pattern di movimento; il dominio ricevente deve
   sostituire osservabili, null e UI lens.
5. Il meta-lab deve preferire combo minime coordinate a cataloghi lunghi.
6. Se un ciclo scopre che mancava una fonte utile, aggiungerla al registry o
   alle capsule, non lasciarla solo in memoria di istanza.

## Rapporto Con Skill E Cascata

- `possibility_inventory`: cosa il sistema puo' provare a usare ora.
- `question_field`: quale domanda apre il ciclo usando o superando quelle
  possibilita'.
- `skill_reading_matrix`: quali fonti sono state lette abbastanza.
- `skill_intent_map`: come le fonti lette diventano movimento.
- `capability_cascade`: cosa emerge dopo e puo' propagarsi.

Questi blocchi sono coordinati. Nessuno sostituisce gli altri.
