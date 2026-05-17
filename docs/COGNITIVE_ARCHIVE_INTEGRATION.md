# Cognitive Archive Integration

> Mappa persistente degli archivi cognitivi storici e installabili da
> considerare quando il meta-lab progetta Lab o sistemi AI con capacita'
> operative autonome.
>
> Stato: prima cristallizzazione, 2026-05-17.

## Scopo

Il sistema possiede piu' archivi di skill, kernel e meta-prompt nati in fasi
diverse del modello D-ND/MMSp. Questi archivi non vanno trattati come una
libreria piatta di prompt da copiare. Vanno letti come strati di lineage:

```text
archivio storico -> seme installabile -> skill operative -> Lab generato
```

La regola e':

```text
si eredita il movimento cognitivo, non il linguaggio storico;
si trasferisce la procedura verificabile, non la persona narrativa;
si dichiara provenance e profondita' di lettura prima di usarla nel MML.
```

## Archivi oggi rilevanti

### `/opt/skill`

Snapshot skill THIA, formato flat `agent_skills_*.md`.

Uso corretto:

- sorgente compatta per vedere la tassonomia THIA a tre piani;
- distribuzione rapida verso ambienti Coder/Chat AI;
- confronto con le skill gia' censite in `docs/SKILL_CATALOG.md`;
- fonte per recuperare skill cognitive portabili quando un nuovo Lab non
  richiede tutto KPhi1.

Caratteristiche lette:

- Plane 0: Kernel MM, non una skill;
- Plane 1: skill cognitive portabili;
- Plane 2: skill operative legate a infrastruttura THIA;
- Plane 3: bridge e connettori;
- thinker-pack per sistemi chat non collegati al runtime THIA.

Rischio:

- essendo snapshot flat, puo' contenere skill ritirate o versioni non
  aggiornate rispetto al runtime corrente;
- non basta il nome della skill: serve leggere il corpo e dichiarare
  `read_depth`.

### `/opt/KPhi1`

Seme strutturato e installabile di sistema cognitivo autopoietico.

Uso corretto:

- riferimento principale quando il meta-lab deve progettare un sistema AI
  capace di auto-orientarsi, installare facolta' e propagare contesto locale;
- fonte per pattern di kernel, non solo per singole skill;
- modello per bootstrap di sistemi autonomi con DNA globale, contesto locale,
  router di capacita', veto e memoria processuale.

Elementi letti e utili:

- `_AI_CONTEXT.md`: Omega Kernel v4.0, campo di potenziale, P0-P6, VRA;
- `DNA.md`: identita' KPhi1, VRA, Stream-Guard, autopoiesi Genesis;
- `kernel/guard_rules.md`: soglie P0-P6, KLI obbligatorio, checklist DONE;
- `kernel/context_protocol.md`: Fractal Context Protocol, `_AI_CONTEXT.md`
  locale per ogni directory significativa;
- `kernel/genesis_bootstrap.md`: blueprint per generare runtime minimo;
- `kernel/chimera_protocol.md`: ricombinazione genetica di skill, da usare
  come pattern, non come concatenazione di prompt;
- `skills/kernel-conductor/SKILL.md`: router delle 27 facolta';
- `skills/aeternitas-sys/SKILL.md`: veto su auto-modifiche che tradiscono il
  seme;
- `skills/mnemos-sys/SKILL.md`: memoria come processo e cristallizzazione
  autopoietica.

Pattern da trasferire al meta-lab:

- **FCP / genoma locale**: ogni Lab figlio deve avere contesto globale +
  contesto locale, e il locale puo' restringere ma non contraddire il seme.
- **Conductor**: il meta-lab sceglie combo di facolta' in base al movimento,
  non lista tutte le skill disponibili.
- **Aeternitas**: ogni auto-modifica di seed, MML, skill o UI contract deve
  avere un check di invarianza e un possibile veto.
- **Mnemos**: la memoria utile non e' archivio; diventa modifica del processo.
  Ogni ciclo significativo deve produrre un KLI o un motivo di decadimento.
- **Genesis**: un sistema nuovo deve poter rigenerare il runtime minimo da
  blueprint, altrimenti non e' reinstallabile.
- **Chimera**: creare nuove skill e' ammissibile solo come sintesi con
  parentage dichiarato, goal esplicito e scope permanente/effimero.

Rischio:

- KPhi1 usa un linguaggio ontologico forte. Nel Lab operativo va transdotto in
  contratti verificabili: trigger, output, stop condition, assertion, runtime
  trace;
- alcune tabelle citano skill ritirate o rinominate. Prima di usare una skill
  serve confrontarla con `skills/REGISTRY.md` e con la diagnostica del Lab.

### `/opt/d-nd_cockpit/docs/system/kernel`

Archivio storico MMSp / cockpit originario.

Uso corretto:

- lineage e archeologia concettuale dei meta-prompt;
- fonte per recuperare logiche antiche ancora valide quando il sistema attuale
  mostra un buco;
- materiale da leggere in modo mirato, non da importare in blocco.

File osservati nella mappa iniziale:

- `MMS_Master.txt`;
- `D-ND_PrimaryRules.txt`;
- `00_Assioma_di_Invarianza_Ontologica.txt`;
- `System_Prompt_Architettura_Assiomatica_Halo_Genoma_v3_0.txt`;
- `System_Prompt_Yi_Synaptic_Navigator_YSN_v4_0.txt`;
- `System_Prompt_ALAN_v14_2_1.txt`;
- `System_Prompt_SACS_PS_v13_0.txt` e `v14_0`;
- `System_Prompt_Morpheus_v1_0.txt`;
- `Meta_System_Prompt_v2_5_Orchestratore_Flussi_Lavoro_Adattivi_AWO.txt`;
- `Meta_System_Prompt_v5_0_COAC.txt`;
- `Pragma_Semantic_Wave_4_4.txt`;
- `Prompt_dei_13_Livelli.txt`;
- `Orchestratore_Cercatore_Costruttore_OCC_v1_0.txt`;
- `metaprompt_in_sviluppo/*` per AETO, Cornelius, DAEDALUS, COAC, MMS,
  Observer, PCS e MetaMaster.

Rischio:

- archivio storico significa alta probabilita' di contaminazione linguistica,
  pattern obsoleti o conflitti con procedure attuali;
- nessun file storico diventa autorita' finche' non viene letto, ridotto a
  procedura e confrontato con il territorio vivo.

## Procedura di consultazione per il meta-lab

Quando un dominio o sistema AI richiede nuove capacita' cognitive:

1. Definisci il movimento richiesto, non la skill desiderata.
2. Consulta gli archivi in ordine di prossimita':
   - docs correnti del Lab (`SKILL_CATALOG`, `SKILL_FIELD_MAP`,
     `SKILL_DIAGNOSTIC`, `META_LAB_SKILL_*`);
   - `/opt/KPhi1` se serve un seme installabile o una struttura autonoma;
   - `/opt/skill` se serve una skill THIA flat/portabile;
   - `/opt/d-nd_cockpit/docs/system/kernel` se serve lineage storico o una
     logica originaria non piu' presente in runtime.
3. Per ogni fonte candidata registra:
   - path esatto;
   - `read_depth`;
   - pattern estratto;
   - artefatto che modifica;
   - contaminazione esclusa;
   - test o evidenza E2E prevista.
4. Trasduci il pattern in uno di questi output:
   - layer MML;
   - sezione `context.md`;
   - `_AI_CONTEXT.md` locale o equivalente;
   - tool/assertion/null/baseline;
   - UI lens;
   - veto/check pre-modifica;
   - nuova skill con parentage dichiarato.
5. Se non puoi indicare l'output modificato, la fonte resta `support_only`.

## Contratto per nuovi sistemi AI

Un nuovo sistema AI derivato dal meta-lab dovrebbe nascere con:

- seme globale: invarianti D-ND e intent-in-movement;
- genoma locale: contesto specifico del dominio/sistema;
- router di facolta': combo minima, non catalogo totale;
- veto di invarianza: protezione del seme prima delle auto-modifiche;
- memoria processuale: KLI/triplette/decadimento, non solo log;
- runtime awareness: cosa ha fatto, cosa ha scartato, cosa ha modificato;
- reinstallabilita': snapshot o bootstrap che rigenera il sistema da zero;
- UI contract: tre colonne comuni + moduli domain-native.

## Relazione con finance e physics

Physics resta il caso sorgente verificato per il movimento del Lab.

Finance e' il primo figlio utile per testare se le regole reggono quando il
materiale cambia. Il prossimo lavoro su finance deve usare questi archivi solo
per migliorare:

- precondizioni misurabili;
- veto su promozioni non ammissibili;
- memoria di cio' che il ciclo ha imparato;
- UI domain-native che mostra regime, baseline/null, data-card e decision
  bounds.

Non bisogna trasformare finance in una copia di KPhi1 o del cockpit storico.
Questi archivi servono il movimento del Lab, non lo sostituiscono.
