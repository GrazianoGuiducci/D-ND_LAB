# Lab D-ND — meta-lab

## About

Il meta-lab è il primo lab D-ND che opera al livello del sistema, non al
livello di un dominio specifico. Il suo compito è **produrre semi cognitivi**
per laboratori nuovi: data una richiesta su un dominio target ("voglio un
lab su X"), il meta-lab applica il modus D-ND al dominio stesso ed estrae
la prima tensione strutturata + le invarianti che il dominio possiede + la
verifica empirica fattibile col compute disponibile.

L'output non è "un lab funzionante" pronto all'uso. È un **seme**: la
formulazione precisa della domanda iniziale del lab nuovo, le sue tensioni
dipolari naturali, gli assiomi del modello che si proiettano nel dominio,
le asserzioni numericamente verificabili. Da questo seme, lo scaffolding
fisso del D-ND_LAB (struttura cartelle, importer di base) crea il file
system completo, e il primo cycle del lab nuovo segue.

Il meta-lab applica al template generato lo stesso filtro che i lab di
dominio applicano ai propri findings: un counter-pole asimmetrico con
sette lenti. M1 verifica che le tensioni proposte abbiano dipoli
aritmetici (det≠0, non descrizione). M2 che le asserzioni siano davvero
eseguibili (PASS/FAIL/SKIP, non print). M3 che i tools iniziali girino
out-of-box. M4 che esista un naive baseline contro cui misurare il modus.
M5 che il primo cycle possa produrre informazione nuova, non solo restate.
M6 che il MML sia coerente con seed e tools. M7 che la transduzione di
dominio sia dichiarata senza copiare contenuto dal lab sorgente.

Se uno qualsiasi dei sette non passa, il template non viene installato:
il meta-lab dichiara il dominio "non di leva" e il rifiuto entra nel
cimitero del meta-lab come cristallizzazione utile, non come fallimento.
È A2 — il confine necessario.

Il meta-lab è in collaudo. Il suo primo test è la rigenerazione del lab
fisica esistente: dato il corpus interno del sistema, il meta-lab deve
produrre un seme di physics strutturalmente equivalente all'originale.
Diff zero su seme cognitivo + cycle equivalente = meta-lab valido.
