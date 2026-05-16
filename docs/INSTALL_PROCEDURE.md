# Lab installation procedure — canvas vivo

> **Scopo**: questo documento è la procedura che il futuro `lab_generator`
> seguirà per creare un nuovo lab autonomo. Oggi è scritto come guida
> manuale per l'operatore + TM3. Domani diventa la spec del generatore
> + flusso UI assistito da LLM su `dev.d-nd.com/labs/new`.
>
> **Versione**: bozza vivente — aggiornata mentre il demo physics matura.
> Origine: 29/04/2026, dopo che l'operatore ha cristallizzato il telos
> "il demo è il master, il seme è la base, il generatore è l'automazione
> della procedura, l'archivio in locale è `/opt/labs/`".

---

## 0. Modello mentale

```
[procedura manuale] ── crystallize ──> [generatore + UI]
        │                                      │
        │                                      ▼
        └──── usata per i primi lab ──> [lab1, lab2, ...] ──> /opt/labs/registry.json
```

Quello che facciamo a mano oggi per il dominio physics del demo D-ND_LAB
è la stessa cosa che il generatore farà domani per qualsiasi dominio
(finance, biology, ricerca aziendale). La procedura è universale; i
contenuti specifici vengono dall'intervista all'utente.

La procedura non deve pero' appiattire i domini. Prima di generare un lab
nuovo, il generatore deve applicare
`docs/DOMAIN_TRANSCENDENCE_AWARENESS.md`: si eredita il contratto del
movimento, non il contenuto del Lab sorgente.

---

## 1. Intervista (raccolta info)

L'assistente lab pone in ordine le domande. Ogni risposta finisce prima in una
richiesta strutturata (`domain_request.v1`), poi in `config.draft.json` quando
il meta-lab ha verificato che il dominio ha leva sufficiente.

Nel pacchetto pubblico la fase minima e' esposta via CLI:

```bash
dndlab plan-domain
```

Il comando raccoglie slug, titolo, tipo dominio e movimento/intento. Non genera
ancora un Lab: crea input per meta-lab/template generator e validator.

Il passaggio successivo alla richiesta e' la transduzione: il meta-lab deve
produrre `domains/<slug>/transduction.md` e
`domains/<slug>/ui_contract.json` insieme a `context.md`, `seed.json`,
`assertions.py`, tools iniziali e `mml.json`. Questi artefatti dichiarano
osservabili domain-native, null/baseline, regole adattive, contaminazioni
specifiche, contratto UI e test E2E attesi.

Le sezioni sono ordinate per dipendenza causale.

### 1.1 Identità del lab

- **Nome breve** (slug, used in path/URL): `physics`, `finance`,
  `editorial`, ...
- **Titolo full**: "Lab fisica D-ND", "Lab finanza dipolare", ...
- **Lingua principale**: it / en / multi
- **Scope di una riga**: cosa indaga questo lab?
- **Owner / responsabile**: email/nome operatore

### 1.2 Modello del dominio

- **Quali sono gli assiomi del modello?** (es. per physics: A1-A5 + F1-F2.
  Per finance: "no arbitrage", "mean reversion", "momentum decay", ...)
- **Quali sono i claim falsificabili?** Almeno 1-3 testabili numericamente.
- **Quali pattern di bias hai osservato in questo dominio?** (Per il
  bias_corrector: oltre alle 5 lenti universali, esempi specifici.)
- **Quali distribuzioni / oggetti / dataset di base usa il dominio?**
  (Per i test riproducibili.)

### 1.3 Fonti di conoscenza

- **Documenti di riferimento** (paper, libri, manuali): path/URL.
- **Cimitero pre-esistente**? Hai claim già falsificati nel dominio?
  (Importati, non hardcoded.)
- **Dati storici**? CSV, JSON, API endpoint.

### 1.4 Intento e direzione iniziale

- **Tensione iniziale**: cosa vuoi che il lab esplori per primo?
- **Direzione**: orizzonte di ricerca per il primo piano del seme.
- **Cosa NON vuoi che il lab faccia** (anti-pattern, scope esclusi).
- **Movimento da conservare**: quale dinamica deve poter compiere il
  sistema anche quando nessun operatore osserva il ciclo?

### 1.5 Capability attive

- **Verify assertions**: sì/no (richiede `assertions.py`)
- **Bias corrector**: sì/no (universale, sempre on)
- **Report falsifier**: sì/no (universale, sempre on)
- **Bicono extractor**: sì/no (richiede sezione bicono nei report)
- **Cimitero auto-write**: sì/no (richiede falsifier + evaluator)
- **Semantic bridge** (incrocio teorie multiple): sì/no
- **Refresh detector** (rigenerazione conoscenza): sì/no

### 1.6 Modelli LLM e budget

- **Provider primario** per l'agent producer: openrouter/anthropic
  subscription/openai subscription
- **Modello agent**: deepseek/sonnet/opus/...
- **Modelli bare** (corrector, falsifier, refiner, evaluator): bridge
  chain (codex→claude→openrouter) sì/no
- **Cost cap**: max per cycle in USD (None = no cap)
- **Timeout per movement**: default 1200s

### 1.7 Schedule

- **Cron**: quando gira automaticamente?
  (Default: 03:30 ogni notte, configurabile)
- **Modalità**: continuous / on-demand only / triggered by event
- **Notify**: chi riceve i report? Telegram / email / Sinapsi / nessuno

### 1.8 Esposizione

- **URL pubblico**: `<slug>.d-nd.com` o `lab.d-nd.com/<slug>`
- **Auth**: pubblico / login / IP whitelist / disabilitato
- **Card sul sito principale**: sì/no — testo card, immagine
- **Run cycle dalla UI pubblica**: sì/no (raccomandato no = early access)

---

## 2. Riassunto + validazione

L'assistente mostra all'operatore il `config.draft.json` complete e
chiede conferma. Validazioni automatiche:

- [ ] Slug univoco (non collide con `/opt/labs/<altro>` esistente)
- [ ] `assertions.py` (se richiesto) ha funzioni test_fn callable
- [ ] Tensioni iniziali ben formate (id, claim, intensità)
- [ ] LLM_API_KEY o subscription disponibile per il provider scelto
- [ ] Cron schedule sintatticamente valido
- [ ] URL non collide con nginx esistente

Se tutto OK, salva `config.final.json` e procede.

---

## 3. Generazione

Lo script `lab_generator` esegue, in ordine:

### 3.1 Filesystem scaffolding

```bash
mkdir -p /opt/labs/<slug>/{domains/<slug>,data/<slug>,dashboard,docs}
ln -s /opt/D-ND_LAB/core /opt/labs/<slug>/core      # codice condiviso
ln -s /opt/D-ND_LAB/dashboard /opt/labs/<slug>/dashboard  # UI condivisa
cp /opt/D-ND_LAB/.venv /opt/labs/<slug>/.venv       # Python env (o symlink)
```

(Symlink vs copia: trade-off tra propagazione update e isolamento.
Default = symlink di `core/`, copia di `dashboard/` per personalizzazione UI.)

### 3.2 Domain content

Da config:

- `domains/<slug>/context.md` — modello del dominio (testo dell'intervista)
- `domains/<slug>/assertions.py` — test riproducibili (template + content)
- `domains/<slug>/seed_tensions.json` — tensioni iniziali
- `domains/<slug>/transduction.md` — come il contratto del movimento
  e' stato tradotto nel dominio senza copiare contenuto sorgente improprio
- `domains/<slug>/ui_contract.json` — come il template dashboard a tre
  colonne viene popolato con moduli comuni e domain-native
- `domains/<slug>/tension_to_category.json` — mapping (può iniziare vuoto)
- `domains/<slug>/cimitero.md` — opzionale, importato se forniti claim

### 3.3 Config

- `config.json` — schedule, modelli, capability flags
- `.env` — credentials (LLM_API_KEY, THIA_LLM_TOKEN, ...)

### 3.4 Registry

```bash
# Append a /opt/labs/registry.json
{
  "slug": "<slug>",
  "title": "<title>",
  "url": "<url>",
  "status": "initialized",
  "created_at": "<ISO>",
  "owner": "<email>",
  "model": "<provider>/<model>",
  "schedule": "<cron>"
}
```

### 3.5 Nginx (se URL pubblico)

```
server {
    server_name <slug>.d-nd.com;
    location / { proxy_pass http://127.0.0.1:<port>/; }
    location /api/ { proxy_pass http://127.0.0.1:<port>/api/; }
}
```

`certbot --nginx -d <slug>.d-nd.com` per SSL.

### 3.6 Servizio (systemd)

```ini
[Unit]
Description=D-ND Lab — <slug>
[Service]
WorkingDirectory=/opt/labs/<slug>
EnvironmentFile=/opt/labs/<slug>/.env
ExecStart=/opt/labs/<slug>/.venv/bin/python -m core.api
Restart=on-failure
[Install]
WantedBy=multi-user.target
```

`systemctl enable --now lab-<slug>.service`

---

## 4. Primo cycle (validazione del lab)

Il generatore lancia un cycle controllato (no auth, log verbose):

```bash
cd /opt/labs/<slug>
.venv/bin/python -m core.cli run --domain <slug>
```

Verifiche:

- [ ] Tutti i movement enabled hanno `status=ok` o skipped intenzionale
- [ ] `assertions/` popolato (se verify_assertions on)
- [ ] `reports/agent_*.md` esiste
- [ ] `falsifier/falsifier_*.json` esiste
- [ ] `seed.json` aggiornato dal seed_integrator (NON svuotato)
- [ ] `lab_session_log.jsonl` ha entry per questo cycle

Se fail: log all'operatore, stato=`init_failed`, NO attivazione cron.

---

## 5. Pubblicazione

Se primo cycle OK:

- Aggiorna `registry.json` `status=active`
- Push card al sito principale (componente `LabsList.tsx` legge il registry)
- Notify operatore: "lab `<slug>` attivo su `<url>`"

---

## 6. Attivazione cron

Se schedule abilitato:

```bash
echo "30 3 * * * cd /opt/labs/<slug> && .venv/bin/python -m core.cli run --domain <slug> >> data/<slug>/cron.log 2>&1" | crontab -
```

Notify operatore quando il primo cron run completa.

---

## 7. Persistenza + osservabilità

Dopo attivazione, il lab gira da solo. Registry aggiornato dopo ogni cron
con `last_cycle_at`, `last_cycle_status`, `n_cycles_total`.

Pattern di osservabilità per l'operatore:
- Dashboard del lab specifico (`<url>/`)
- Aggregato cross-lab su `dev.d-nd.com/labs/dashboard`
- Notifica Telegram per HIGH flag persistenti / failure ricorrenti

---

## 8. Roll-back / decommissioning

Se un lab non serve più o ha problemi strutturali:

- `systemctl disable --now lab-<slug>.service`
- crontab rimossa
- `registry.json` → `status=archived`
- Filesystem `/opt/labs/<slug>` mantenuto per audit (non eliminato auto)
- Card rimossa dal sito principale
- Nginx config disabilitata + SSL revocata

---

## Note di implementazione

### Cosa ESISTE già (29/04)

- ✓ Master codebase D-ND_LAB con 21 movements (incl. Aeternitas + Veritas gate, trajectory_apply A8+A15 loop, narrative_writer)
- ✓ Domain physics demo con assertions + seed_tensions + context
- ✓ Bridge chain LLM (codex→claude→openrouter)
- ✓ A5 closure (verify_assertions + bicono_extractor + cimitero auto-write)
- ✓ UI dashboard con sidebar campo + counter-pole + bias corrector
- ✓ Early access modal (cycle pubblico disabilitato)

### Cosa MANCA per il generatore (in ordine)

1. **Test reale di A5 chiusura** sul demo physics (cycle in corso 29/04)
2. **`/opt/labs/` archive structure + registry.json** (vuoto al momento)
3. **`lab_generator.py` script** che esegue 3.1-3.6 da config.final.json
4. **UI questionario** su `dev.d-nd.com/labs/new` (LLM-guided intervista)
5. **Endpoint admin protetto** che chiama `lab_generator` (auth + audit log)
6. **Card auto-publish** al sito principale (componente + endpoint)

### Vincoli / principi

- **Domain-agnostic**: il codice in `core/` mai hardcoda dominio specifico.
  Tutto specifico vive in `domains/<slug>/`.
- **Riuso > reinvenzione**: bridge chain, prompt structure, lenti A8/A2/A4
  vengono riutilizzati per ogni lab.
- **Fail-soft**: ogni movement degrada graceful. Cycle non si rompe se
  un movement è disabilitato.
- **Audit trail**: ogni generazione/cycle/decisione lascia traccia
  persistente.
- **Operatore-first**: i primi N lab generati passano dall'operatore via
  password. Niente self-service per utenti esterni finché il sistema
  non è dimostrato stabile.

---

*Questo file evolve. Ogni step manuale che facciamo sul demo physics
diventa una sezione qui. Quando il generatore esiste, questo doc diventa
la sua spec.*
