# Phase 6 v3 — UI/Layout refactor + restante scaletta

> **Crystallized.** Risposta a screenshot operatore 28/04 mattina:
> "la UI/layout va rivista, il design non è fatto bene; conviene
> trasferire quello che abbiamo nel LAB del sito in modo intelligente."

## Delta osservato (dalle 3 schermate)

| Aspetto | LabGraph del sito (`d-nd.com/ai-lab`) | Dashboard nostra v2 |
|---|---|---|
| Layout | 3-col: sidebar CAMPO sx + grafo center + sidebar DETTAGLIO dx | Single column verticale, grafo + seed/reports stack |
| Tabs in alto | GRAFO / BICONO / AGENTE / INCROCIO TEORIE | Niente tabs |
| Stats sidebar | teorie/ponti/vuoti/scoperte/cicli + freschezza + legenda | Niente |
| Chat | Floating bottom-right (THIA) con quick-action buttons | Bottom sheet full-width |
| Labels nodi grafo | Sempre visibili (toggle), ben distanziati | Sovrapposti, illeggibili nel cluster |
| Nodi teoria | Cerchi grandi colorati con lettera (Q T G E R) | Mini-circle con type-color |
| Detail panel dx | Card report con verdict + chips + actions (Apri/Esplora) | Markdown raw inline |
| Sezione descrittiva | "Ghost Index", "Pairs senza ponte", legend espansiva | Niente |

L'operatore: "servirà una buona parte descrittiva di quello che accade
perché altrimenti nessuno comprende bene".

## Findings recon — pattern riusabili dal sito

- `/opt/d-nd_com/components/Shell3Col.tsx` — layout 3-col v3 con
  closed/open states per le sidebar, HoverPopover system. Pattern
  replicabile in vanilla CSS grid.
- `/opt/d-nd_com/components/LabGraph.tsx:216` — `activeTab` state con
  4 valori (grafo/agente/incrocio/bicono). Cross-tab handoff con
  jumpToFeedFile (click report → vai ad Agente con quel report
  aperto).
- Pattern delle teorie come **nodi grandi colorati con lettera centrale**
  (Q/T/G/E/R) — non default Cytoscape, va custom-styled.

## Piano v3 (refactor dashboard)

### v3.1 — Layout 3-col + tabs

- Frontend: nuovo HTML structure con Tailwind grid:
  - Top: header + tab bar (GRAFO / BICONO / AGENTE / INCROCIO)
  - Body: `grid-cols-[260px_1fr_320px]` (campo | content | dettaglio)
  - Sidebar collapsible (chevron toggle)
- Tabs sono single-page, switchando lo stato Alpine `activeTab`.

### v3.2 — Sidebar CAMPO sx (stats + freschezza + legenda)

- Calcolato dal `lab_graph.json` + dal `seed.json`:
  - **Stats**: teorie / ponti / vuoti / scoperte / cicli (counts da graph stats)
  - **Freschezza**: oggi (reports < 24h), fresche (< 7d), ghost urgenti (graph stats.ghost_high_urgency)
  - **Legenda**: A Accumulazione · F Falsifica · C Candidata · ponte vuoto · oggi (con cerchi colore)
- Toggle "Mostra tutti i nomi (Label sempre visibili senza hover)"

### v3.3 — Sidebar DETTAGLIO dx

- Quando un nodo è cliccato: mostra card con
  - chip type (`report` / `tensione` / `teoria`) + chip data + chip maturity (A/F/C)
  - title (truncated 2 line)
  - verdict (se report)
  - "→ Apri report" → switcha tab AGENTE con il report aperto
  - "→ Esplora nel grafo" (zoom su quel nodo)
- Vuoto state: testo "Click su un nodo per dettaglio"

### v3.4 — Tab GRAFO (refinement)

- Cytoscape style update:
  - Nodi `teoria` → cerchio grande (40px) con lettera Q/T/G/E/R bianca al centro
  - Nodi `report` → cerchio piccolo (12px) con colore pair
  - Labels truncate 30 chars + ellipsis
  - "Mostra tutti i nomi" toggle: when off, solo hover; when on, sempre visibili
  - Zoom auto-fit on graph load

### v3.5 — Tab BICONO

- Galleria di mini-bicono per ogni report con bicono parsed
- Filtro: solo report con bicono completo / tutti
- Click su mini-bicono → switcha tab AGENTE con quel report

### v3.6 — Tab AGENTE

- Lista report (sx) + viewer report (dx) — come la v2 ma in 2-col
  invece che impilato
- Bicono dinamico in alto del viewer (già fatto in v2.3)
- Pulsante "▶ Run cycle" qui, non nella sidebar seed

### v3.7 — Tab INCROCIO TEORIE

- Phase 6 v4 — tabella delle 10 pair TQGE+R con costante / dipolo
  / ponte / insights_dal_lab. Per ora placeholder "in arrivo".

### v3.8 — Chat panel floating bottom-right

- Stile coerente con `THIA` panel del sito (purple accent, quick-action buttons)
- Quick actions iniziali (per dominio physics): "Spiega l'ultimo report",
  "Cosa c'è nel cimitero?", "Quale tensione è prioritaria?"
- Resta floating, non bottom sheet
- Context node badge ancora dentro

### v3.9 — Sezione "cosa accade qui" (descrittivo, top)

- Sopra le tabs: paragrafo breve che spiega il dominio attivo
  (cosa fa il lab, cosa rappresenta il grafo, come leggerlo)
- Letto da `domains/<d>/context.md` (prima sezione "Identity"
  estratta), così evolve col dominio

## Ordine di commit

1. v3.1 + v3.2 + v3.3 layout 3-col + tabs vuoti + sidebar
2. v3.4 grafo con teoria-as-letter + label toggle
3. v3.5 tab BICONO
4. v3.6 tab AGENTE
5. v3.8 chat floating + quick actions
6. v3.9 descrittivo top
7. v3.7 INCROCIO placeholder

## Vincoli

- Sempre vanilla HTML + Alpine + Tailwind CDN (zero build)
- Sempre coerente col palette d-nd.com
- Niente fallback statici nei contenuti — sempre da config/data
- Backend invariato — i dati ci sono già, è solo presentazione

---

# Scaletta globale dopo v3

| Phase | Cosa | Stato |
|---|---|---|
| 6 v1 | Dashboard base + chat | ✓ shipped |
| 6 v2 | Graph viz + node→chat + dynamic bicono | ✓ shipped |
| **6 v3** | **UI refactor 3-col + tabs + chat floating** | **next** |
| 6 v4 | Tab INCROCIO TEORIE (placeholder → reale) | dopo v3 |
| 6 v5 | Chat con tools (read_report, run_cycle, inject_tension via UI confirm) | post v3 |
| 6 v6 | Magic-link auth (gestione operatore remota da browser) | post v5 |
| 6 v7 | Fork mode (stesso input → N domini paralleli + convergence map) | la specialità |
| 6 v8 | LabGraph fullscreen modal (pattern dal sito) | UX polish |
| 6 v9 | Cost trend charts (Recharts via CDN) | observability |
| 7 | Repo D-ND_LAB privato → pubblico | decisione operatore |
| 8 | Lancio: README finale + announcement social + HN | post Phase 7 |
| 9 | Lab Operativo (terzo dominio: dogfooding su THIA) | post-lancio |
| 10 | Lab Finanziario (combo m_spectro + two-channel su returns) | post-lancio |

## Ordine raccomandato

**Subito (priority alta — UX bloccante per l'operatore):**
v3 (layout) → v5 (chat tools, perché il chat è il principale punto di
contatto utente non-CLI) → v8 (LabGraph fullscreen, perché il grafo
è hero della UI).

**Dopo aver testato (priority media):**
v4 (Incrocio teorie tab) → v6 (auth) → v9 (cost charts).

**Quando il prodotto è stabile:**
v7 (fork mode — la specialità unica del prodotto, vale la pena solo
quando il resto è solido) → Phase 7 flip pubblico.

**Dopo lancio:**
Lab Operativo + Lab Finanziario come terzo/quarto dominio.

---

# Recovery

Se la sessione si interrompe durante v3, riprendi da:
- Questo file
- Ultimo commit: `git log --oneline -3` su /opt/D-ND_LAB
- Stato dashboard: `systemctl is-active d-nd-lab-dashboard`
- Live: `https://lab.d-nd.com/dashboard/`
