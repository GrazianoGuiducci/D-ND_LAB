# Web Dashboard — Mockup / Visione

> **Phase 6 mockup.** Alignment document — review before build starts.
> Defines the dashboard's purpose, screens, data flow, and demo
> capabilities. The build follows from what's agreed here.

## Doppia funzione

La dashboard ha due audiences nello stesso prodotto:

1. **Operatore non-terminale** — gestisce il proprio lab installato
   localmente o sul VPS senza dover toccare la CLI. Configura
   domains, lancia cycles, legge report, vede costi.

2. **Visitatore pubblico** — su `lab.d-nd.com/dashboard` vede una
   demo viva del lab fisica D-ND in funzione + le sue varianti
   editoriale/financial/operational. La dashboard è lei stessa
   prova del modello: **"il sistema che si guarda mentre lavora"**.

## Architettura

```
┌─ Browser ──────────────────────────────┐
│  React + Tailwind + shadcn/ui          │
│  (single-page app, no SSR needed)      │
└──────────────┬─────────────────────────┘
               │ REST + WebSocket
               ▼
┌─ FastAPI service (new) ────────────────┐
│  /api/domains                          │
│  /api/domains/{d}/seed                 │
│  /api/domains/{d}/reports[/last]       │
│  /api/domains/{d}/trajectory           │
│  /api/domains/{d}/run         (POST)   │
│  /api/cycles/{id}/log         (WS)     │
│  /api/cycles/{id}/cost                 │
└──────────────┬─────────────────────────┘
               │ shells out + reads filesystem
               ▼
┌─ Existing core (unchanged) ────────────┐
│  python -m core.cli run --domain X     │
│  data/<domain>/{seed,reports,...}      │
└────────────────────────────────────────┘
```

Niente database. Lo stato è già nel filesystem (`data/<domain>/...`)
— l'API legge da lì. L'unica novità è uno strato HTTP/WS sopra il core.

## Screens

### 1. Home / Domain Picker

```
┌─────────────────────────────────────────────────────────┐
│ D-ND_LAB                                  [theme] [docs] │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Pick a domain or fork the same input across many       │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │  PHYSICS    │  │  EDITORIAL  │  │  + new      │    │
│  │             │  │             │  │             │    │
│  │  piano: 12  │  │  piano: 3   │  │  create from│    │
│  │  18 reports │  │  4 reports  │  │  template   │    │
│  │  $2.34 used │  │  $0.18 used │  │             │    │
│  │             │  │             │  │             │    │
│  │  [enter]    │  │  [enter]    │  │  [start]    │    │
│  └─────────────┘  └─────────────┘  └─────────────┘    │
│                                                         │
│  [ + Fork mode: same input → N domains parallel ]      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 2. Domain dashboard — Seed view

```
┌─ Domain: physics ──────────────────────────────────────┐
│                                                         │
│  ┌─ Current seed ────────────────────────────────────┐ │
│  │  Piano: 12                                        │ │
│  │  Direction: "8 GUE / 5 Poisson — il confine è... │ │
│  │                                                   │ │
│  │  Active tensions  (8)                             │ │
│  │  ▰▰▰▰▰▰▰▰▰   TRASCENDENZA_LIMITE      0.9         │ │
│  │  ▰▰▰▰▰▰▰▰▰   DUALITA_DIPOLARE_VS_ILLU 0.9         │ │
│  │  ▰▰▰▰▰▰▰▰▱   METRIC_TENSOR             0.85       │ │
│  │  ▰▰▰▰▰▰▰▱▱   BOUNDARY                  0.8        │ │
│  │  ▰▰▰▰▱▱▱▱▱   META                      0.5        │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  ┌─ Last reports ────────────────┐ ┌─ Trajectory ────┐│
│  │  agent_2026...md  (NEW + ...) │ │ 2026-04-26 NEXT ││
│  │  agent_2026...md  (FALSIFIED) │ │ 2026-04-25 NEXT ││
│  │  agent_2026...md  (CONSTRAINT)│ │ 2026-04-24 STOP ││
│  └───────────────────────────────┘ └─────────────────┘│
│                                                         │
│  [▶ Run new cycle]  [ inspect ]  [ history ]           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 3. Cycle runner — live log

```
┌─ Running cycle: physics @ 2026-04-27 21:35 ────────────┐
│                                                         │
│  Movements                                              │
│  ✓ autopsy           (0.0s)                            │
│  ✓ build_field       (0.1s, 619 bytes)                 │
│  ⟳ agent             (running... turn 6/25)            │
│  ◯ validate_seed                                        │
│  ◯ verify_assertions                                    │
│  ◯ structural_check                                     │
│  ...                                                    │
│                                                         │
│  Live log                                               │
│  ┌───────────────────────────────────────────────────┐ │
│  │  [21:35:12] turn 1 — agent reading field          │ │
│  │  [21:35:18] turn 1 — tool: list_dir               │ │
│  │  [21:35:24] turn 2 — agent picked tension BOUNDARY│ │
│  │  [21:35:42] turn 3 — tool: run_python (320 lines) │ │
│  │  [21:36:11] turn 3 — result: GUE r=0.503, PoissN..│ │
│  │  [21:36:33] turn 4 — agent formulating null base..│ │
│  │  ...                                               │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  Cost so far: $0.04 (45K tokens) | Stop:  [✗ abort]    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 4. Report viewer — bicono visualizzato

```
┌─ Report: agent_20260427_2005.md ───────────────────────┐
│                                                         │
│  # Triadic Boundary: Ordering Fraction as Third Included│
│  Date: 2026-04-27 20:05  Verdict: NEW + CONSTRAINT     │
│                                                         │
│  ┌─ Bicono ────────────────────────────────────────┐  │
│  │                                                  │  │
│  │     i.i.d. structure ←───→ Ordered structure    │  │
│  │     (Brody curve)          (off Brody curve)    │  │
│  │           │                       │              │  │
│  │           └──────── ◯ ────────────┘              │  │
│  │              The gap sequence                    │  │
│  │              before separation                   │  │
│  │                                                  │  │
│  │  Invariant of passage: the r-statistic          │  │
│  │                                                  │  │
│  │  Field of possibility:                          │  │
│  │  ✓ POSSIBLE: discriminate via shuffle test      │  │
│  │  ✗ NOT POSSIBLE: infer from local stat alone    │  │
│  └─────────────────────────────────────────────────┘  │
│                                                         │
│  ┌─ Full report (markdown rendered) ─────────────────┐ │
│  │  ## Claim Under Test                              │ │
│  │  > The BOUNDARY claim asserts 8 GUE-like and 5..│ │
│  │  ...                                              │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  [ download .md ]  [ raw json ]  [ refiner output ]    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 5. Fork Mode — la specialità del lab

Questo è il pezzo unico della dashboard, allineato con la tua
intuizione "varianti di contesto che crescono nelle loro risultanti".

```
┌─ Fork: same input → N domains in parallel ─────────────┐
│                                                         │
│  Input tension: "what is the structural invariant       │
│                  that connects accumulation and noise?" │
│                                                         │
│  Run on:  ☑ physics     ☑ editorial    ☐ financial     │
│           ☑ operational ☐ semantic      [+ add new]    │
│                                                         │
│  [▶ Fork & run all 3]                                  │
│                                                         │
│  ┌─ physics ─────┐ ┌─ editorial ──┐ ┌─ operational ─┐  │
│  │ Resultant:    │ │ Resultant:   │ │ Resultant:    │  │
│  │ "rinforzo è   │ │ "addition    │ │ "drift senza  │  │
│  │  impossibile  │ │  bias is the │ │  cassetto =   │  │
│  │  — 1/φ²<1"    │ │  same shape" │ │  rumore"      │  │
│  │ Verdict: CONS │ │ Verdict: SRC │ │ Verdict: NEW  │  │
│  └───────────────┘ └──────────────┘ └───────────────┘  │
│                                                         │
│  ┌─ Convergence map ─────────────────────────────────┐ │
│  │ All three resultants share the dipole             │ │
│  │ "additive (det=+1) vs structural (det=0)" —       │ │
│  │ different vocabularies, same modus.               │ │
│  │                                                   │ │
│  │ This is what "varianti di contesto che crescono   │ │
│  │ nelle loro risultanti" means structurally.        │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 6. Cost trend (dashboard footer or section)

```
Cost over time                Tokens over time
$5 ┤              ╭──         200K ┤    ╭──╮
$4 ┤            ╭─╯           150K ┤  ╭─╯  ╰──
$3 ┤        ╭───╯             100K ┤╭─╯
$2 ┤    ╭───╯                  50K ┤╯
$1 ┤╭───╯                       0K └──────────
$0 └──────────                      Apr 20-27
   Apr 20-27
```

## Demo mode (public)

Quando la dashboard gira pubblicamente su `lab.d-nd.com/dashboard`:

- Modalità **read-only** per visitatori (no run cycle)
- Display dei dati live del lab fisica D-ND nightly
- Bicono visualizer + report viewer + trajectory log come "vetrina"
- "Fork mode" può girare con corpora di esempio cliccabili (privacy
  preserved, no operator data)
- CTA: "Install your own → curl install.sh | bash"

Il visitatore vede **il sistema che si guarda mentre lavora** —
la dashboard è la prova vivente del modello che descrive.

## Tech stack proposto

| Layer | Choice | Rationale |
|---|---|---|
| Frontend | React 19 + Vite + Tailwind + shadcn/ui | Stack che già usi su d-nd.com — coerenza |
| State | TanStack Query | server-state caching senza Redux complexity |
| Charts | Recharts | semplice, dati storici trend |
| Markdown | react-markdown + rehype | rendering report |
| Backend | FastAPI + uvicorn | Python (consistente col core), WebSocket nativo |
| WS streaming | FastAPI WebSocket | log live durante cycle |
| Build | Docker compose service `dashboard` | porta 3000 frontend, 5000 backend, nginx routing |
| Deploy | docker compose up | un comando, tutto |

## Login (auth opt-in)

Auth è opt-in via `DASHBOARD_AUTH=enabled` env var. Pattern:

- **Localhost / single user**: `DASHBOARD_AUTH=disabled` (default).
  Nessun login, accesso libero a chi può raggiungere la porta.
- **Esposto in rete / VPS**: `DASHBOARD_AUTH=enabled`. JWT
  magic-link via email — utente inserisce email, riceve link,
  sessione 30 giorni. Niente password DB.
- **Multi-tenant hosted (Phase 7+)**: stesso meccanismo + un
  account-id nel JWT che namespacing i `data/<account>/<domain>/`.
- **Demo pubblica `lab.d-nd.com/dashboard`**: nessuna auth — modalità
  read-only, niente azioni (run cycle, modify seed, chat injection).

Magic-link richiede SMTP config (env vars `SMTP_HOST`,
`SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`). Se assenti, il login è
disabilitato e la dashboard accetta solo localhost.

## Chat panel — l'agent del lab in modalità interattiva

La chat NON è un wrapper LLM generico. È **lo stesso agent** che gira
il cycle, in modalità conversazionale. Stesso prompt context (domain
context.md + seme + ultimi report), stesso modello, stessa adapter
config — solo che invece di un cycle batch, fa una risposta per
messaggio.

### Why it changes the product

| | Cycle agent | Chat agent |
|---|---|---|
| Trigger | Cron / `dndlab run` | User message |
| Goal | Scrivere un report autonomo | Rispondere a una domanda con consapevolezza |
| Output | `agent_<ts>.md` + bicono + seed update | Stream conversazionale + opzionale "inject as tension" |
| Context | `agent_field_live.md` (statico) | Stesso + history conversazione + ultimi report |
| Tools | filesystem + python_exec + bash | Read-only + side-effect tools gated da UI confirm |

### Use case concreti

1. **"Perché il lab ha esplorato BOUNDARY stanotte?"**
   Chat agent legge trajectory + projector output del cycle e spiega
   la logica della scelta — la consapevolezza retrospettiva del lab.

2. **"Cosa c'è nel cimitero che ho dimenticato?"**
   Estrae i 3 claim più recenti caduti + sostituzione strutturale.

3. **"Aggiungi tensione: '...'"**
   Valida la formulazione (struttura non opinione), chiede conferma,
   inietta nel seme con porta + tipo + intensity.

4. **"Lancia un cycle ora focalizzato su METRIC_TENSOR."**
   Imposta direzione override, lancia cycle async, ritorna cycle_id,
   il pannello cycle runner mostra il log streaming.

5. **"Mostrami i report dove abbiamo falsificato GUE."**
   Searches reports per verdict pattern, ritorna lista linkable.

### Tools che la chat espone al modello

Read-only (sempre attivi):
- `read_report(ts)` — legge un report passato
- `read_cimitero()` — claim falsificati
- `read_seed()` — stato corrente
- `read_trajectory_log(n=10)` — ultime decisioni evaluator
- `read_evolution_report(ts)` — refiner output
- `search_reports(query)` — full-text su tutti i report
- `search_archive(query)` — solo dominio editorial

Side-effect (gated da UI confirm):
- `inject_tension(claim, intensity, type, porta)` — manuale, dopo
  conferma operatore
- `run_cycle(direction_override?)` — lancia async, ritorna cycle_id
- `modify_seed_direction(new_direction)` — cambia direzione,
  confidence=high required

### Safety chat

- `LLM_MAX_COST_USD_PER_SESSION` cap (default $1.00 — chat può
  consumare molto se uno scrolla messaggi)
- Rate limit: max N messaggi al minuto per session
- History persistita in `data/<domain>/chat_sessions/<session_id>.jsonl`
- Conferma UI obbligatoria per side-effect tools — il modello propone,
  l'operatore approva con click

### UI panel

```
┌─ Chat with the lab ─────────────────────────────────────┐
│  Domain: physics              Session: 2026-04-27 21:12 │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  > Perché BOUNDARY questa notte?                        │
│                                                         │
│  Ha massimo discriminating power perché 8 GUE / 5       │
│  Poisson sono già misurati — il cut è disponibile.      │
│  TRASCENDENZA_LIMITE intensity 0.9 ma scope troppo      │
│  ampio per il budget; il refiner della notte prima      │
│  l'aveva segnalato come scelta alternativa per il       │
│  ciclo seguente.                                        │
│                                                         │
│  > Aggiungi tensione: "convergenza primi-zeta è stata   │
│    misurata solo in log scale — testare lineare"        │
│                                                         │
│  Sembra una tensione di tipo confine_inesplorato.       │
│  Proporrei intensity 0.75, porta 'novità'.              │
│                                                         │
│  [✓ inject as proposed] [✎ modify] [✗ skip]             │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  [type your message...]                  Cost: $0.012   │
│                                            Send: Ctrl+↵ │
└─────────────────────────────────────────────────────────┘
```

## Stima rivista (con login + chat)

| Sub-task | Giorni |
|---|---|
| 6A — mockup (questo doc) | done |
| 6B — backend FastAPI + REST + WS | 2 |
| 6C — frontend MVP (4 schermate base) | 3 |
| 6D — chat panel + tools wiring | 2-3 |
| 6E — auth opt-in (JWT magic-link) | 1-2 |
| 6F — bicono visualizer + cost charts | 1-2 |
| 6G — fork mode (parallel domains + convergence) | 2 |
| 6H — Docker compose + demo mode | 1 |

**Totale: 12-15 giorni** per la Phase 6 completa.

### Strategia in due milestones

**Phase 6 v1 — Core dashboard + chat (8-9 giorni)**
6B + 6C + 6D + 6E + 6H. Niente fork mode, niente charts.
Già rivoluzionario: dashboard usabile + chat conversazionale +
auth + deploy ready.

**Phase 6 v2 — Visualizers + Fork mode (4-6 giorni)**
6F + 6G. Differenziatori sopra v1.

### Pragmatic single-session shortcut

Per shippare un MVP **in una singola sessione di sviluppo**:

- Frontend: HTML single-page servito da FastAPI con Tailwind CDN
  + Alpine.js (no build step, no React setup)
- Backend: 1 file `core/api.py` con tutti gli endpoint REST + WS + chat
- Docker: aggiungo service `dashboard` con port mapping
- Auth: opt-in via env var, ma implementazione magic-link può venire
  in 6E v2

Stack semplificato sacrifica polish UI ma consegna **funzionalità reale
oggi**: dashboard usabile via browser, lab gestibile senza terminale,
chat funzionante, deploy via docker compose. Migrabile a React proper
in Phase 6 v2 senza buttare nulla — gli endpoint REST + WS sono già
stabili.

## Domande per te

1. **Stack frontend**: React + shadcn (proposto, allineato col tuo
   sito) o preferisci Vue (allineato MiroFish)?

2. **Demo mode pubblica**: la dashboard la deployamo su
   `lab.d-nd.com/dashboard` come parte della Phase 6 stessa, o prima
   stabilizziamo l'app locale e poi la portiamo live?

3. **Fork mode**: ti torna come la "specialità" che differenzia D-ND_LAB
   da tool agentici generici? È il pezzo che mostra "il modello che
   pensa in più dimensioni di contesto contemporaneamente".

4. **MVP-prima vs full-Phase-6**: vuoi che parta con MVP 3-4 giorni
   (schermate base) per testare il flow, e poi decidiamo fork mode +
   charts? Oppure vai con tutto in 6-10 giorni?

Dimmi e parto.
