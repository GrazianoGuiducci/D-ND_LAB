# Finance Lab — Transduction

> M7 — integrita' di transduzione.
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

Status M7: retrofitted.

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
