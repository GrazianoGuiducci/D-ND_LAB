"""anti_loop_guard — self-applicazione del kernel D-ND ai cycle del lab.

Use case B (operatore 02/05): il kernel cognitivo z=12,813 (matrice di
transizione + zeri strutturali) applicato alle traiettorie del sistema
agentico per rilevare loop strutturali prima che diventino fallimento.

Idea base (dal finding):
  Il kernel D-ND ha mostrato che certe transizioni Markov sono
  STRUTTURALMENTE VIETATE (es. P(2→2)=0 per gap mod 6) — non è
  rumore, è informazione. Trasferito al comportamento agentico:
  certe transizioni stato→stato sono sintomo di loop pre-failure
  (es. 'lettura stesso file' 3 volte di fila, 'tool call con args
  identici', 'bash → bash → bash su stesso comando').

  Un guardrail informato dalla matrice di transizione storica del
  comportamento dell'agente batte di molto le euristiche flat
  ('repeated > N times = loop').

API
===
  guard = LoopGuard.from_sequences(historical_sequences, alphabet=None)
  result = guard.score(current_events)
  # result = {
  #   "n_self_loops": int,        # X→X consecutivi
  #   "max_run_length": int,       # max sequenza di stesso evento di fila
  #   "structural_violations": [   # transizioni vicine a zero strutturale
  #     {"from": "A", "to": "B", "p_baseline": 0.0, "obs_count": 3}
  #   ],
  #   "entropy_bits": float,       # entropia della sequenza corrente
  #   "danger_score": float,       # 0..1, > 0.6 = warning
  #   "reasons": [str, ...]        # lista human-readable per logging
  # }

  # Score live durante un cycle (streaming):
  guard.tick(event)  # aggiorna stato interno
  if guard.danger() > 0.7:
      log.warn(f"loop pattern detected: {guard.reasons()}")

CLI
===
  python -m core.anti_loop_guard <jsonl_path> [--field <key>]
    Builda la matrice baseline da jsonl + report scoring on-the-fly
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path


# Soglia: una transizione con probabilità baseline ≤ EPSILON_ZERO è
# considerata "zero strutturale". Se osservata > MIN_VIOLATIONS volte
# nella sequenza corrente, è violation.
EPSILON_ZERO = 0.005     # 0.5% baseline = quasi-zero
MIN_VIOLATIONS = 2

# Run length threshold: stesso evento ripetuto > MAX_RUN_OK volte è loop.
MAX_RUN_OK = 4

# Entropy floor (bits): sotto questa soglia la sequenza è "ripetitiva".
# Calibrato empiricamente — sequenza random su alfabeto N=8 ha ~3 bits.
LOW_ENTROPY_BITS = 1.2


class LoopGuard:
    """Guardrail informato dalla matrice di transizione storica."""

    def __init__(self, transition_matrix: dict[str, dict[str, float]],
                 alphabet: list[str], baseline_n: int):
        self.T = transition_matrix          # P(to | from)
        self.alphabet = sorted(alphabet)
        self.baseline_n = baseline_n
        # Stato per uso streaming
        self._stream: list[str] = []

    # ─── Construction ──────────────────────────────────────────────

    @classmethod
    def from_sequences(cls, sequences: list[list[str]],
                        alphabet: list[str] | None = None) -> "LoopGuard":
        """Builda la matrice di transizione P(to | from) dalle sequenze."""
        counts: dict[str, Counter] = defaultdict(Counter)
        observed: set[str] = set()
        n = 0
        for seq in sequences:
            for i in range(len(seq) - 1):
                a, b = seq[i], seq[i + 1]
                counts[a][b] += 1
                observed.add(a)
                observed.add(b)
                n += 1
        if alphabet is None:
            alphabet = sorted(observed)
        T: dict[str, dict[str, float]] = {}
        for a in alphabet:
            row = counts.get(a, Counter())
            total = sum(row.values()) or 1
            T[a] = {b: row.get(b, 0) / total for b in alphabet}
        return cls(T, list(alphabet), baseline_n=n)

    # ─── Scoring (batch) ───────────────────────────────────────────

    def score(self, events: list[str]) -> dict:
        """Scoring di una sequenza completa: ritorna dict con metriche + danger."""
        n_self_loops = 0
        max_run = 0
        cur_run = 1
        violations: list[dict] = []
        violation_counts: Counter = Counter()
        for i in range(1, len(events)):
            a, b = events[i - 1], events[i]
            if a == b:
                n_self_loops += 1
                cur_run += 1
                if cur_run > max_run:
                    max_run = cur_run
            else:
                cur_run = 1
            # Structural-zero check (transizione baseline ~ 0)
            row = self.T.get(a, {})
            p = row.get(b, 0.0)
            if p <= EPSILON_ZERO:
                violation_counts[(a, b)] += 1
        for (a, b), cnt in violation_counts.items():
            if cnt >= MIN_VIOLATIONS:
                violations.append({
                    "from": a, "to": b,
                    "p_baseline": self.T.get(a, {}).get(b, 0.0),
                    "obs_count": cnt,
                })
        if max_run < cur_run:
            max_run = cur_run
        # Entropia osservata
        freq = Counter(events)
        n = len(events) or 1
        entropy = -sum((c / n) * math.log2(c / n) for c in freq.values() if c)

        # Danger score: combinazione di 3 segnali, ognuno 0..1
        s_run = min(1.0, max(0, max_run - MAX_RUN_OK) / 4)
        s_violations = min(1.0, len(violations) / 3)
        s_entropy = max(0.0, (LOW_ENTROPY_BITS - entropy) / LOW_ENTROPY_BITS) if entropy < LOW_ENTROPY_BITS else 0.0
        # Pesi: run = priorità (segnale immediato), violations = strutturale,
        # entropy = soft signal
        danger = min(1.0, 0.45 * s_run + 0.4 * s_violations + 0.15 * s_entropy)

        reasons: list[str] = []
        if max_run > MAX_RUN_OK:
            reasons.append(f"max self-run = {max_run} (threshold {MAX_RUN_OK})")
        if violations:
            top = violations[:3]
            reasons.append(f"{len(violations)} structural-zero violations (top: " +
                           ", ".join(f"{v['from']}→{v['to']}×{v['obs_count']}" for v in top) + ")")
        if entropy < LOW_ENTROPY_BITS:
            reasons.append(f"low entropy: {entropy:.2f} bits (threshold {LOW_ENTROPY_BITS})")
        if not reasons:
            reasons.append("no loop pattern detected")

        return {
            "n_self_loops": n_self_loops,
            "max_run_length": max_run,
            "structural_violations": violations,
            "entropy_bits": round(entropy, 3),
            "danger_score": round(danger, 3),
            "reasons": reasons,
            "n_events": len(events),
        }

    # ─── Streaming API ─────────────────────────────────────────────

    def tick(self, event: str) -> dict:
        """Aggiungi evento e ritorna scoring corrente."""
        self._stream.append(event)
        return self.score(self._stream)

    def reset(self) -> None:
        self._stream = []

    def danger(self) -> float:
        if not self._stream:
            return 0.0
        return self.score(self._stream)["danger_score"]

    def reasons(self) -> list[str]:
        if not self._stream:
            return []
        return self.score(self._stream)["reasons"]

    # ─── Persistence ───────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "schema_version": "0.1",
            "alphabet": self.alphabet,
            "baseline_n": self.baseline_n,
            "transition_matrix": self.T,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LoopGuard":
        return cls(
            transition_matrix=d["transition_matrix"],
            alphabet=d["alphabet"],
            baseline_n=d["baseline_n"],
        )


# ─── jsonl helper ──────────────────────────────────────────────────


def load_sequences_from_jsonl(path: Path, field: str,
                                group_by: str | None = None) -> list[list[str]]:
    """Carica sequenze da un jsonl.

    Se group_by è None: tutto il file è una singola sequenza.
    Se group_by è una key (es. 'cycle_ref'): raggruppa per quel valore →
    una sequenza per gruppo.
    """
    if not path.exists():
        return []
    groups: dict[str, list[str]] = defaultdict(list)
    flat: list[str] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        val = obj.get(field)
        if val is None:
            continue
        # Coerce to string (handle dict/list)
        if not isinstance(val, str):
            val = json.dumps(val, sort_keys=True)
        if group_by:
            key = obj.get(group_by, "_default")
            groups[str(key)].append(val)
        else:
            flat.append(val)
    if group_by:
        return list(groups.values())
    return [flat] if flat else []


# ─── CLI ──────────────────────────────────────────────────────────


def main():
    ap = argparse.ArgumentParser(description="Anti-loop guardrail — score di una sequenza vs baseline.")
    ap.add_argument("jsonl", help="Path al jsonl di trajectory")
    ap.add_argument("--field", default="decision",
                    help="Campo del jsonl da estrarre come stato (default: decision)")
    ap.add_argument("--group-by", default=None,
                    help="Raggruppa per questo campo (default: tutta la storia in 1 sequenza)")
    ap.add_argument("--score-last", type=int, default=None,
                    help="Scoring sugli ultimi N eventi (default: tutti)")
    ap.add_argument("--out-baseline", default=None,
                    help="Salva la transition matrix baseline qui (json)")
    args = ap.parse_args()

    path = Path(args.jsonl)
    sequences = load_sequences_from_jsonl(path, args.field, args.group_by)
    if not sequences:
        print(f"ERROR: nessuna sequenza caricata da {path} (field={args.field})", file=sys.stderr)
        return 2

    print(f"loaded {len(sequences)} sequence(s), total events = {sum(len(s) for s in sequences)}")
    guard = LoopGuard.from_sequences(sequences)
    print(f"alphabet ({len(guard.alphabet)}): {guard.alphabet}")
    print(f"baseline transitions observed: {guard.baseline_n}")

    if args.out_baseline:
        Path(args.out_baseline).write_text(json.dumps(guard.to_dict(), indent=2))
        print(f"baseline matrix → {args.out_baseline}")

    # Scoring sulla sequenza completa (concat o ultima)
    flat = [e for seq in sequences for e in seq]
    if args.score_last:
        flat = flat[-args.score_last:]
    if not flat:
        print("(empty sequence — niente da scorare)")
        return 0

    result = guard.score(flat)
    print()
    print(f"=== scoring (n={result['n_events']}) ===")
    print(f"max_run_length:   {result['max_run_length']} (threshold {MAX_RUN_OK})")
    print(f"n_self_loops:     {result['n_self_loops']}")
    print(f"entropy_bits:     {result['entropy_bits']}")
    print(f"violations:       {len(result['structural_violations'])}")
    for v in result['structural_violations'][:5]:
        print(f"  · {v['from']:>15} → {v['to']:<15} obs×{v['obs_count']} p_baseline={v['p_baseline']:.3f}")
    print(f"")
    danger = result['danger_score']
    band = "DANGER" if danger >= 0.7 else ("WARN" if danger >= 0.4 else "OK")
    print(f"danger_score:     {danger:.3f}  [{band}]")
    for r in result['reasons']:
        print(f"  · {r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
