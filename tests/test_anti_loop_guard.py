"""tests for core.anti_loop_guard — kernel D-ND self-applicato ai cycle del lab."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.anti_loop_guard import LoopGuard, MAX_RUN_OK, LOW_ENTROPY_BITS


class TestLoopGuardBaseline(unittest.TestCase):
    def setUp(self):
        self.healthy_history = [
            ["read", "edit", "bash", "edit", "bash", "read", "edit", "bash", "test"],
            ["read", "bash", "edit", "test", "edit", "bash", "test", "edit"],
        ]
        self.guard = LoopGuard.from_sequences(self.healthy_history)

    def test_alphabet_inferred(self):
        self.assertEqual(set(self.guard.alphabet), {"read", "edit", "bash", "test"})

    def test_transition_matrix_rows_sum_to_1(self):
        for a in self.guard.alphabet:
            row = self.guard.T[a]
            total = sum(row.values())
            self.assertAlmostEqual(total, 1.0, places=5,
                                    msg=f"row {a} sum = {total}")

    def test_persistence_roundtrip(self):
        d = self.guard.to_dict()
        g2 = LoopGuard.from_dict(d)
        self.assertEqual(g2.alphabet, self.guard.alphabet)
        self.assertEqual(g2.T, self.guard.T)


class TestLoopGuardScoring(unittest.TestCase):
    def setUp(self):
        self.guard = LoopGuard.from_sequences([
            ["a", "b", "c", "a", "b", "c", "a", "b"],
            ["a", "c", "b", "a", "b", "c"],
        ])

    def test_healthy_sequence_low_danger(self):
        r = self.guard.score(["a", "b", "c", "a", "b"])
        self.assertLess(r["danger_score"], 0.4, f"healthy got {r}")

    def test_long_self_run_raises_danger(self):
        # 6 'a' di fila → max_run 6 > threshold 4
        r = self.guard.score(["a", "a", "a", "a", "a", "a"])
        self.assertGreater(r["max_run_length"], MAX_RUN_OK)
        self.assertGreater(r["danger_score"], 0.4,
                           f"long run should warn, got {r}")

    def test_low_entropy_signal_active(self):
        # Tutto uguale → entropy = 0
        r = self.guard.score(["a"] * 10)
        self.assertLess(r["entropy_bits"], LOW_ENTROPY_BITS)
        self.assertGreater(r["danger_score"], 0.5,
                           f"flat sequence should danger, got {r}")

    def test_streaming_tick(self):
        self.guard.reset()
        for ev in ["a", "b", "c", "a", "b"]:
            self.guard.tick(ev)
        self.assertEqual(len(self.guard._stream), 5)
        # Reset funziona
        self.guard.reset()
        self.assertEqual(len(self.guard._stream), 0)


if __name__ == "__main__":
    unittest.main()
