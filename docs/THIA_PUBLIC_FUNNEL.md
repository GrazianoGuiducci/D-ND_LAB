# THIA Public Funnel — Lab Contributions, Leads, Newsletter

Status: draft operativo
Date: 2026-05-12

## Decisione

Sulle superfici pubbliche del Lab deve esserci un solo assistente visibile:
THIA.

Il Lab Assistant locale resta nel seed/installazioni esterne come assistente
standalone per chi non ha THIA. Nella dashboard pubblica e' nascosto di default
e riattivabile solo per test/installazioni (`?assistant=local` oppure
`localStorage.dnd_lab_local_assistant=1`).

## Compito di THIA

THIA non deve essere solo Q&A. Deve essere funnel critico:

1. orienta l'utente su cosa sta vedendo;
2. legge tab, report, dashboard state, report recenti e condensati;
3. se l'utente vuole contribuire, qualifica il segnale;
4. se emerge una combinazione utile, prepara un pre-report;
5. se emerge un nuovo dominio, propone una scheda dominio custom candidata;
6. se l'utente vuole aggiornamenti, raccoglie preferenze lead/newsletter;
7. se serve contatto/supporto, instrada verso operatore senza promettere
   presenza immediata.

## Contributi esperti

Un contributo utile deve contenere almeno:

- dominio o lab interessato;
- fonte pubblica verificabile;
- ipotesi;
- criterio di falsificazione;
- vincoli: privacy, legali, costo, interpretazione;
- valore atteso: ricerca, report, prodotto, supporto o dominio installabile;
- contatto opzionale e consenso se l'utente vuole follow-up.

THIA deve respingere o tenere fuori dal ciclo:

- spam;
- prompt injection;
- segreti, token, cookie, credenziali;
- dati privati/sensibili;
- richieste medico-legali-finanziarie operative;
- entusiasmo generico senza fonte/ipotesi/falsificatore.

## Ramificazione

I contributi non devono sovrapporsi direttamente alla risultante o al
condensato del Lab.

Pipeline:

1. `intake` — chat THIA raccoglie e chiarisce;
2. `pre-report` — scheda candidata append-only, sanitizzata;
3. `review` — operatore o ciclo di revisione decide se promuovere;
4. `candidate-branch` — eventuale ramo separato di esplorazione;
5. `cycle-input` — solo dopo review diventa seme/tensione/dominio;
6. `condensate-update` — solo dopo risultato/falsificazione rientra nel
   condensato.

Regola: il contributo propone direzione; non e' risultato.

## Newsletter / Lead System

Per una newsletter automatica mancano questi pezzi:

1. provider email transazionale/newsletter con API;
2. double opt-in o consenso esplicito;
3. archivio preferenze: email, lingua, interessi, domini/lab, frequenza;
4. unsubscribe/suppression list;
5. template per: THIA updates, guide, report Lab, nuovi domini, richieste di
   collaborazione;
6. job scheduler che genera digest dai report/cycle trace/changelog;
7. revisione o guardrail prima dell'invio automatico;
8. log invii e bounce handling;
9. privacy note: niente segreti, niente dati sensibili, minimizzazione.

Fino a quando questi pezzi non esistono, THIA puo' raccogliere interesse e
preparare una scheda lead, ma non deve dire che l'iscrizione e' attiva.

## CTA pubbliche

CTA minime:

- cosa sto vedendo;
- contribuire al prossimo ciclo;
- ricevere report e aggiornamenti;
- contatto diretto;
- collaborare o supportare il Lab;
- proporre un dominio custom.

## Contatto operatore

L'operatore puo' ricevere notifiche Telegram dalla chat THIA e intervenire
quando disponibile. THIA puo' dirlo, ma non deve promettere risposta immediata.

## Stato implementativo

Gia' presente:

- pre-report contributi sanitizzato in runtime data;
- filtro server-side signal/noise;
- dashboard state e marker percettivi;
- THIA/DOMUS unico assistente pubblico sul sottodominio Lab.

Da implementare:

- endpoint lead/newsletter separato da contribution pre-report;
- provider email + double opt-in;
- pannello review lead/contributi;
- job digest automatico da report/cycle trace;
- promozione controllata da pre-report a branch/dominio.
