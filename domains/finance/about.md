# AI-Lab D-ND Finance

Questo lab studia i regime shift nei mercati come oggetti strutturali, non come etichette narrative. Il suo primo confine e' semplice: distinguere un dipolo bull/bear generativo da una sequenza che sembra avere regime solo perche' la guardiamo dopo il fatto.

Il lab confronta sempre due poli:

- mercato ordinato: rendimenti con memoria locale, cambio di stato e orientamento misurabile;
- controllo ingenuo: VaR statico, realized volatility e surrogati shuffle con stessa distribuzione ma ordine distrutto.

Se il segnale sparisce nello shuffle, il regime non e' una parola: e' una struttura. Se non sparisce, il lab non promuove il finding.

Il primo uso e' operativo: costruire kernel verificabili per regime shift su FX, crypto ed equity, con fallback sintetico quando i dati esterni non sono disponibili. Le API pubbliche servono a portare dati reali nel cycle; non sostituiscono il null test.
