# Lab D-ND — ops-decisions

## About

Questo lab studia il sistema D-ND dall'interno. Legge gli incidenti
(cycle falliti, errori di deploy, processi orfani) e le decisioni
dell'operatore (memorie, feedback, commit) per estrarre regole
strutturali che il sistema non ha ancora formalizzato.

Due facce dello stesso lavoro. La prima risale dagli incidenti al nodo
dove mancava la condizione — propone fix regressivi, non toppe. La
seconda scava nel deposito decisionale — trova pattern ricorrenti e
li cristallizza come regole candidate.

Il lab non impone niente. Propone. L'operatore decide cosa diventa
regola e cosa va nel cimitero. Ogni proposta porta la sua metrica:
"quante volte questo pattern appare nel corpus" e "il fix proposto
avrebbe prevenuto la ricorrenza?"

Naive baseline: fix al sintomo + cristallizzazione manuale episodica.
Questo lab verifica se il modus D-ND (inversione al nodo regressivo +
pattern matching automatico) produce delta misurabile.

Il lab e in collaudo. Il primo cycle gira sul corpus reale del sistema:
2 incident report, 97 memorie operatore, 1 canale COWORK.
