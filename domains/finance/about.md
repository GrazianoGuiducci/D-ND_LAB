# AI-Lab D-ND Finance

> **Il regime esiste solo se sopravvive allo shuffle.**

Questo lab studia i regime shift nei mercati come **oggetti strutturali**, non come etichette narrative. Il suo primo confine è semplice: distinguere un dipolo bull/bear generativo da una sequenza che sembra avere regime solo perché la guardiamo dopo il fatto.

## Come opera

Il lab confronta sempre due poli:

- **mercato ordinato** — rendimenti con memoria locale, cambio di stato e orientamento misurabile sotto l'operatore M;
- **controllo ingenuo** — VaR statico, realized volatility e surrogati shuffle con stessa distribuzione ma ordine distrutto.

Se il segnale sopravvive allo shuffle, il regime non è una parola: è struttura. Se non sopravvive, il lab **non promuove** il finding.

## Cosa ottieni

- **Finding A/B** verificabili: D-ND vs naive baseline, con effect-size (z-score) misurabile contro shuffle
- **Verdict trasparente** ad ogni cycle: `DND_DELTA` (regime reale) o `NO_DELTA` (illusione)
- **Kernel pacchettizzato** (target maturazione): `dnd_kernel_finance_regime_shift`, protocollo replicabile per hedge fund, family office, advisory finanziaria

## Confine epistemico

Il lab non promette previsioni di prezzo. Misura **struttura del regime** — un livello sopra rispetto a "indovinare la direzione". Cinque condizioni necessarie per ogni finding promosso: metrica reale + null baseline shuffle + naive baseline (VaR + vol) + delta D-ND ≥ 3σ + fallimento dichiarato quando il delta è assente.

Il primo cycle è partito **sandboxed senza rete** su dataset sintetico. Le API pubbliche (yfinance, FRED, CoinGecko, World Bank) portano dati reali nei cycle successivi — non sostituiscono il null test.

---

*Status: alpha · dominio in collaudo · ultimo synthetic realistic in NO_DELTA · promozione vincolata a gate su dati reali con controlli robusti.*
