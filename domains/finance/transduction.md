# Finance Lab — Transduction

> M7 — integrita' di transduzione.
> M8 — recupero skill/enzimi + skill_intent_map retrospettivo.
>
> Questa nota dichiara come il movimento D-ND e' stato tradotto dal caso
> sorgente physics al dominio finance senza copiare contenuto fisico.

## Movimento Conservato

Il Finance Lab conserva il contratto del movimento:

```text
domain_request -> transduction -> combo -> cycle -> report -> falsifier
-> runtime_awareness -> seed update -> UI surface
```

La combo finance non cerca "previsioni di mercato". Contiene il movimento
che discrimina se un cambio di regime conserva orientamento sotto
l'operatore M o se collassa come illusione statistica sotto shuffle.

Il ciclo deve quindi produrre:

- esperimento ordinato-vs-null;
- report con vincolo o finding;
- falsifier su claim e baseline;
- runtime awareness su dati, finestre, strumenti e sospensioni;
- aggiornamento del seed solo se il risultato regge.

## Invarianti Portati

Invarianti D-ND trasferiti:

- **A1/A2**: un regime reale deve lasciare orientamento non nullo, non
  solo variazione descrittiva di volatilita'.
- **A3/F1**: il residuo Cassini e' diagnostica di scala, non prova
  numerologica.
- **A4/F4**: il test e' locale e deve separare modulazione macro,
  autocorrelazione, volatilita' e regime.
- **A5/A8/A14**: il valore sopravvive quando diventa vincolo nel seed,
  non quando resta frase nel report.

Invarianti operativi:

- claim sempre falsificabile;
- null/baseline prima dell'interpretazione;
- nessuna promozione senza controprova;
- output maturo come kernel verificabile, non come opinione di mercato;
- cimitero come memoria dei falsi positivi e delle assunzioni cadute.

## Contenuto Sorgente Escluso

Dal Lab fisico non sono stati copiati:

- primi, zeta, GUE, RP, Anderson o soglie numeriche del dominio fisico;
- operatori fisici come contenuto semantico;
- report fisici come forma da imitare;
- claim su costanti speciali come phi, sqrt(5), 1/137 senza meccanismo;
- categorie UI fisiche come "ponti", "vuoti", "incrocio teorie".

Il Lab fisico resta sorgente di metodo. Finance usa materiale proprio:
serie temporali, rendimenti, finestre, costi, volatilita', drawdown,
correlazioni e regime persistence.

## Osservabili Domain-Native

Osservabili finance:

- log-return ordinati;
- realized volatility;
- VaR statico;
- drawdown e change in drawdown;
- orientamento lagged return sotto operatore M;
- determinante/covarianza antisimmmetrica locale;
- effect_z ordered-vs-shuffle;
- residuo Cassini su lag log-spaced;
- data_card con provider, source_url, retrieval_ts, era_hint e n_obs;
- stabilita' su finestre e asset indipendenti.

Gli osservabili devono essere misurati sul dominio, non tradotti da
termini fisici.

## Null, Baseline e Controlli

Baseline naive:

- VaR statico su finestra mobile;
- realized volatility annualizzata;
- random walk gaussiano calibrato su media e varianza locali.

Null e controlli:

- shuffle dei rendimenti con stessa distribuzione e ordine distrutto;
- replica su almeno due finestre indipendenti;
- replica su almeno due asset con profili diversi;
- confronto con synthetic fallback quando i dati reali non sono disponibili;
- data-card audit per impedire claim senza provenienza.

Un singolo `DND_DELTA` non e' finding maturo. Un singolo `NO_DELTA` non
falsifica il pipeline. Il Lab deve leggere la distribuzione dei risultati
prima di nominare un regime.

## M8 — skill_retrieval / enzyme_retrieval / skill_intent_map

Questo retrofit M8 non cambia i risultati finance gia' prodotti. Rende
esplicito cio' che il meta-lab dovra' fare prima di generare altri Lab:
collegare intento, dinamica d'uso, skill/meta-prompt, strumenti, null,
baseline e UI.

### skill_retrieval

Skill gia' dichiarate in `mml.json` e pertinenti al movimento finance:

- `assertion-verifier`: blocca promozioni senza PASS/FAIL/SKIP numerici;
- `autoresearch`: genera varianti di test senza fissarsi su asset/finestra;
- `capture-insight`: cristallizza nel seed il vincolo emerso;
- `audit-system`: controlla drift di dati, API, fallback e tool;
- `publish-safe` / `vulcan`: impediscono linguaggio predittivo non supportato;
- `research-lab` / `dnd-method`: mantengono il dominio come ricerca
  quantitativa falsificabile, non advisory;
- `cascata`, `cec`, `consapevolezza-condensato`,
  `autologica-operativa`, `eval`: runtime invariant del Lab.

Skill da non usare come autorita' del dominio:

- `paper-deployer`: resta output-layer potenziale; non autorizza claim
  finanziari pubblici finche' non esiste prodotto maturo e revisione;
- skill persona (`observer`, `vulcan`) non sostituiscono strumenti,
  baseline o falsifier.

### skill_reading_matrix

Questa matrice applica il protocollo
`docs/META_LAB_SKILL_READING_PROTOCOL.md` al finance reference. Non e'
esaustiva di tutto l'archivio: copre le skill che influenzano il ciclo
finance corrente, il MML o la UI.

| Skill | Source reale | Profondita' | Stato | Ruolo finance | Trigger | Rischio / correzione |
|---|---|---:|---|---|---|---|
| `assertion-verifier` | `/opt/.claude/skills/assertion-verifier.md` | L1 | VIVA-NO_EVAL | assertion/verifica | prima di promuovere claim | utile solo se le assertion possono fallire; evitare tautologie |
| `veritas-sys` | `/opt/THIA/.agent/skills/agent_skills_veritas.md` | L1 | VIVA | validation/firewall | prima di cristallizzare report o dato esterno | `rho` non e' previsione; serve attrito, non certezza |
| `helix-sys` | `/opt/THIA/.agent/skills/agent_skills_helix.md` | L1 | VIVA | redesign algoritmico | quando nasce un detector nuovo | usare per spec/test loop, non per task semplici |
| `kairos-sys` | `/opt/THIA/.agent/skills/agent_skills_kairos.md` | L1 | VIVA | rottura presupposti | dopo fallimenti ripetuti dello stesso score family | distruzione solo se produce substrato misurabile |
| `autologica-operativa` | `/opt/.claude/skills/autologica-operativa.md` | L1 | VIVA | context/procedura | su design esperimento | tradurre in domanda eseguibile, non in semantica |
| `cec` | `/opt/.claude/skills/cec.md` | L1 | VIVA | filtro decisionale | prima di cambio direzione/cristallizzazione | non sostituisce dati; se servono dati, si esegue tool |
| `consapevolezza-condensato` | `/opt/.claude/skills/consapevolezza-condensato.md` | L1 | VIVA-NO_EVAL | filtro modello | su atto sistemico | anti-pattern: lettura rituale senza assioma specifico |
| `cascata` | `/opt/.claude/skills/cascata.md` | L1 | VIVA | propagazione | dopo finding verificato | emergenti si segnano, non si implementano nella stessa cascata |
| `eval` | `/opt/.claude/skills/eval.md` | L1 | VIVA | skill health | quando si valuta una skill | non valida detector finance; valida trigger/fidelity skill |
| `audit-system` | `/opt/.claude/skills/audit-system.md` | L1 | VIVA-NO_EVAL | runtime audit | dopo cambio tool/dati | restringere scope a finance quando non serve cross-repo |
| `publish-safe` | `/opt/.claude/skills/publish-safe.md` | L1 | VIVA | output gate | prima di output pubblico | sicurezza publishing non equivale a verita' del finding |
| `research-lab` | `/opt/THIA/.agent/skills/agent_skills_research_lab.md` | L1 | VIVA | rigore ricerca | init/cambio claim | non importare contenuto Paper Zero come evidenza finance |
| `dnd-method` | `/opt/MM_D-ND/.claude/skills/dnd-method.md` | L1 | VIVA | metodo operativo | traduzione invarianti -> metriche | metodo di coding, non prova di mercato |
| `forgia` | `/opt/MM_D-ND/kernel/reference/skills/agent_skills_forgia.md` | L1 | VIVA | generation/deferred | solo quando finding diventa kernel | non forgiare entita' prima della maturita' |
| `autoresearch` | `/opt/.claude/skills/autoresearch.md` | L1 | VIVA-NO_EVAL | support_only | solo per ottimizzare skill/eval | il corpo non genera esperimenti finance: declassato |
| `capture-insight` | `/opt/.claude/skills/capture-insight.md` | L1 | VIVA-NO_EVAL | support_only | appunti operatore | quick capture, non seed integrator |
| `paper-deployer` | `/opt/.claude/skills/paper-deployer.md` | L1 | VIVA-NO_EVAL | deferred/support_only | solo dopo artefatto paper/site-ready | deploy pipeline, non maturita' finance |
| `observer` | `/opt/MM_D-ND/kernel/reference/skills/agent_skills_observer.md` | L1 | PERSONA-KERNEL | support_only | forma/domande | non sostituisce null/baseline |
| `vulcan` | `/opt/MM_D-ND/kernel/reference/skills/agent_skills_vulcan.md` | L1 | PERSONA-KERNEL | support_only | taglio linguistico | non e' procedura statistica |

Correzione emersa dalla lettura: il finance reference non deve piu'
trattare `autoresearch`, `capture-insight` o `paper-deployer` come autorita'
di ciclo. Restano supporti/deferred. La direzione operativa dopo i fallimenti
block21 passa invece da `helix-sys` + `kairos-sys`: specificare la
precondizione misurabile del detector e rompere il presupposto della stessa
famiglia di score prima di ciclare di nuovo.

### enzyme_retrieval

Enzimi cognitivi pertinenti al finance corrente:

- separare segnale da eco narrativa;
- trasformare detector debole in domanda sulla precondizione mancante;
- usare il cimitero come memoria dei falsi positivi, non come fallimento;
- leggere runtime e trace prima del report finale;
- dichiarare `NO_DELTA` come vincolo operativo quando la potenza non e'
  recuperabile.

Capacita' mancanti da trattare come strumenti/null/gate, non come copy:

- precondition detector per capire quando una famiglia di statistiche ha
  potenza recuperabile;
- block-preserving null espliciti per evitare shuffle troppo liberi;
- data-card piu' forte quando si passa da synthetic a market data;
- UI lens che renda visibile "non ammissibile" prima di ogni linguaggio
  value-facing.

### skill_intent_map

```json
{
  "intent": "costruire un Lab finance che rileva quando un'ipotesi di regime non regge prima che diventi decisione di esposizione",
  "movement_class": "calibration+recovery",
  "use_dynamics": [
    "confrontare detector di regime contro baseline e null",
    "identificare la precondizione mancante quando purezza non produce potenza recuperabile",
    "bloccare promozioni e linguaggio predittivo se il detector resta NO_DELTA",
    "cristallizzare vincoli decisionali e runtime awareness"
  ],
  "skill_layers": {
    "validation_layer": ["assertion-verifier", "cec"],
    "processing_layer": ["autoresearch", "capture-insight"],
    "observation_layer": ["audit-system"],
    "output_layer": ["publish-safe", "vulcan"],
    "domain_layer": ["research-lab", "dnd-method"],
    "runtime_patterns": ["cascata", "consapevolezza-condensato", "autologica-operativa", "eval"]
  },
  "meta_prompts": [
    "Non cercare un altro parametro del detector. Trova la precondizione che deve essere vera prima che un detector di regime abbia potenza recuperabile.",
    "Confronta target, baseline VaR/RV e null block-preserving senza introdurre lookahead.",
    "Se la precondizione non regge, produrre NO_DELTA e vincolo di ridisegno, non una nuova promessa."
  ],
  "generated_artifacts": [
    "transduction.md",
    "mml.json",
    "ui_contract.json",
    "tools/exp_regime_shift.py",
    "tools/finance_diagnostic_report.py",
    "assertions.py"
  ],
  "null_baseline_requirements": [
    "random walk",
    "shuffled returns",
    "block bootstrap o block-preserving null",
    "VaR/RV baseline",
    "data-card anti-lookahead"
  ],
  "ui_lens": [
    "Regime Gate",
    "Baseline / Null",
    "Data-card",
    "Non ammissibile",
    "Cycle trace"
  ],
  "exclusions": [
    "buy/sell/forecast/profit",
    "singola finestra come autorita'",
    "fisica copiata come semantica",
    "paper-deployer come autorizzazione pubblica"
  ]
}
```

## Regole Adattive

### Regola: No Trading Signal

- `origin`: dominio finance ad alto rischio di sovrainterpretazione.
- `protects`: evita che un vincolo strutturale diventi consiglio operativo.
- `valid_when`: ogni output pubblico o report value-facing.
- `retire_when`: mai senza revisione legale/prodotto; il Lab non nasce
  come advisory.
- `evidence`: README e context dichiarano output come test strutturale,
  non prediction accuracy.

### Regola: Double Replication

- `origin`: cicli 20260505 hanno mostrato sensibilita' bassa e pass-rate
  atteso da rumore su synthetic.
- `protects`: falsi positivi da singola finestra o singolo asset.
- `valid_when`: prima di promuovere `DND_DELTA` su dati reali.
- `retire_when`: solo se il kernel maturo dimostra potenza statistica
  diversa con protocollo piu' forte.
- `evidence`: finance README, sezione cycle 1, richiede due finestre e
  due asset prima della promozione.

### Regola: Data Card Required

- `origin`: rischio di leakage, fonte non tracciata e cambio endpoint.
- `protects`: impedisce finding su dati non auditabili.
- `valid_when`: ogni uso di `--from-market`.
- `retire_when`: se il dominio usa solo synthetic o dataset versionato
  localmente con manifest.
- `evidence`: `market_data.py` e `context.md` richiedono `data_card`.

## Contaminazioni Specifiche

Il Finance Lab deve bloccare:

- lookahead bias;
- survivorship bias;
- data snooping;
- split scelti dopo aver visto il risultato;
- overfit su asset singolo;
- endpoint drift o dati non versionati;
- linguaggio predittivo non supportato;
- UI che trasforma una sospensione in un segnale buy/sell.

## UI Contract

La UI finance deve mostrare il movimento, non vendere il risultato.

Contratto eseguibile:

```text
domains/finance/ui_contract.json
```

Il Finance Lab usa il template comune a tre colonne:

- sinistra: stato del campo, tensioni, cimitero, counter-pole;
- centro: regime map + baseline comparison;
- destra: data-card, decision bounds, runtime dynamics, THIA assistant.

Superfici minime:

- ipotesi attiva;
- asset e finestra sotto test;
- ordered-vs-shuffle evidence;
- baseline naive;
- data-card/provenienza;
- stato `DND_DELTA`, `NO_DELTA` o `SOSPENSIONE`;
- regole adattive attive;
- vincoli decisionali: cosa non e' ammissibile con l'evidenza corrente;
- runtime awareness: strumenti invocati, finestre scartate, sospensioni.

Label vietate senza prodotto maturo:

- "buy";
- "sell";
- "forecast";
- "profit";
- "alpha signal".

## E2E e Reinstall

Il Lab deve passare questi test prima di essere considerato demo forte:

```bash
python3 -m core.cli inspect --domain finance
python3 domains/meta-lab/tools/lab_template_validator.py --strict-m7 domains/finance
python3 domains/finance/tools/exp_regime_shift.py --json
python3 domains/finance/assertions.py
```

Per un E2E operativo completo:

```bash
bash tools/dnd-cycle.sh finance
```

Un ciclo reale resta valido solo se il report distingue risultato,
sospensione, vincolo e non-ammissibile.

## Stato di Transduzione

Status M7/M8: retrofitted.

Il Finance Lab e' un buon primo figlio applicato per il meta-lab perche'
ha:

- dominio ad alto valore;
- baseline naturale;
- null robusti;
- rischio reale di contaminazione;
- output utile come vincolo decisionale;
- strumenti gia' eseguibili;
- cicli storici con VETO/SOSPENSIONE che dimostrano che il sistema non
  promuove automaticamente cio' che non regge.
