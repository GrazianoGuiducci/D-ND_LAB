"""
exp_z12813_sequential_info.py
=============================
A/B test: does sequential order in prime gaps carry exploitable information?

Finding: z=12,813 — the sequential order of prime gap residues (mod 6) carries
massive information. The Markov transition matrix of real gaps has det=0.023 and
structural zeros (P(2->2)=P(4->4)=0), while shuffled gaps have det~0.

Test design:
  - Naive method: predict next gap residue using marginal frequencies only
    (ignores sequential order — equivalent to shuffled model)
  - Informed method: predict next gap residue using 1st-order Markov transition
    probabilities (exploits sequential structure the finding identified)
  - Metric: mean log-likelihood per prediction on held-out test set
  - Secondary: prediction accuracy (most-probable class)

If the finding is real, the informed method should significantly outperform naive.
"""

import json
import math
import time
from collections import Counter, defaultdict

SEED = 42
MAX_PRIME = 200_000  # enough primes, fast enough


def sieve_primes(n):
    """Simple sieve of Eratosthenes."""
    is_prime = [False, False] + [True] * (n - 1)
    for i in range(2, int(n**0.5) + 1):
        if is_prime[i]:
            for j in range(i * i, n + 1, i):
                is_prime[j] = False
    return [i for i in range(2, n + 1) if is_prime[i]]


def prime_gap_residues_mod6(primes):
    """Compute gap residues mod 6 for consecutive primes > 5."""
    filtered = [p for p in primes if p > 5]
    gaps = []
    for i in range(len(filtered) - 1):
        g = (filtered[i + 1] - filtered[i]) % 6
        gaps.append(g)
    return gaps


def method_naive(train_gaps, test_gaps):
    """
    Predict each test gap using marginal frequencies only (order-blind).
    Returns (mean_log_likelihood, accuracy, predictions).
    """
    counts = Counter(train_gaps)
    total = sum(counts.values())
    states = sorted(counts.keys())
    marginal = {s: counts[s] / total for s in states}

    # Smoothing for unseen states
    all_states = {0, 2, 4}
    for s in all_states:
        if s not in marginal:
            marginal[s] = 1e-10

    log_liks = []
    correct = 0
    best_state = max(marginal, key=marginal.get)

    for gap in test_gaps:
        p = marginal.get(gap, 1e-10)
        log_liks.append(math.log(p))
        if best_state == gap:
            correct += 1

    mean_ll = sum(log_liks) / len(log_liks) if log_liks else 0.0
    acc = correct / len(test_gaps) if test_gaps else 0.0
    return mean_ll, acc


def method_informed(train_gaps, test_gaps):
    """
    Predict each test gap using 1st-order Markov transition probabilities.
    Exploits sequential structure (the finding: z=12,813).
    Returns (mean_log_likelihood, accuracy).
    """
    # Build transition counts
    trans_counts = defaultdict(Counter)
    for i in range(len(train_gaps) - 1):
        trans_counts[train_gaps[i]][train_gaps[i + 1]] += 1

    # Normalize to probabilities with Laplace smoothing (alpha=0.001)
    all_states = {0, 2, 4}
    alpha = 0.001
    trans_prob = {}
    for s in all_states:
        row_total = sum(trans_counts[s].values()) + alpha * len(all_states)
        trans_prob[s] = {}
        for t in all_states:
            trans_prob[s][t] = (trans_counts[s][t] + alpha) / row_total

    # Also need marginal for the very first prediction (no context)
    counts = Counter(train_gaps)
    total = sum(counts.values())
    marginal = {s: counts.get(s, alpha) / (total + alpha * len(all_states)) for s in all_states}

    log_liks = []
    correct = 0

    for i, gap in enumerate(test_gaps):
        if i == 0:
            # No previous context, use marginal
            probs = marginal
        else:
            prev = test_gaps[i - 1]
            probs = trans_prob.get(prev, marginal)

        p = probs.get(gap, 1e-10)
        log_liks.append(math.log(max(p, 1e-10)))

        best = max(probs, key=probs.get)
        if best == gap:
            correct += 1

    mean_ll = sum(log_liks) / len(log_liks) if log_liks else 0.0
    acc = correct / len(test_gaps) if test_gaps else 0.0
    return mean_ll, acc


def shuffle_deterministic(lst, seed):
    """Fisher-Yates shuffle with LCG PRNG for reproducibility (no numpy)."""
    out = list(lst)
    n = len(out)
    # Simple LCG
    s = seed
    for i in range(n - 1, 0, -1):
        s = (s * 6364136223846793005 + 1442695040888963407) % (2**64)
        j = s % (i + 1)
        out[i], out[j] = out[j], out[i]
    return out


def compute_det_3x3(matrix):
    """Determinant of a 3x3 matrix (list of lists)."""
    a = matrix
    return (a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
            - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
            + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]))


def compute_z_score(real_gaps, n_shuffles=200):
    """Compute z-score: how different is real det from shuffle distribution."""
    all_states = sorted({0, 2, 4})
    state_idx = {s: i for i, s in enumerate(all_states)}

    def build_trans_matrix(gaps):
        counts = [[0.0] * 3 for _ in range(3)]
        for i in range(len(gaps) - 1):
            a, b = gaps[i], gaps[i + 1]
            if a in state_idx and b in state_idx:
                counts[state_idx[a]][state_idx[b]] += 1
        # Normalize rows
        for r in range(3):
            row_sum = sum(counts[r])
            if row_sum > 0:
                for c in range(3):
                    counts[r][c] /= row_sum
        return counts

    real_mat = build_trans_matrix(real_gaps)
    real_det = compute_det_3x3(real_mat)

    shuffle_dets = []
    for trial in range(n_shuffles):
        sg = shuffle_deterministic(real_gaps, SEED + trial * 7919)
        sm = build_trans_matrix(sg)
        shuffle_dets.append(compute_det_3x3(sm))

    mean_s = sum(shuffle_dets) / len(shuffle_dets)
    var_s = sum((d - mean_s) ** 2 for d in shuffle_dets) / len(shuffle_dets)
    std_s = var_s ** 0.5 if var_s > 0 else 1e-10

    z = (real_det - mean_s) / std_s
    return z, real_det, mean_s, std_s, real_mat


def run_test():
    t0 = time.time()

    # Generate primes and gap residues
    primes = sieve_primes(MAX_PRIME)
    gaps = prime_gap_residues_mod6(primes)

    # Split: 70% train, 30% test (sequential split — order matters!)
    split = int(len(gaps) * 0.7)
    train_gaps = gaps[:split]
    test_gaps = gaps[split:]

    # A/B test
    naive_ll, naive_acc = method_naive(train_gaps, test_gaps)
    informed_ll, informed_acc = method_informed(train_gaps, test_gaps)

    # Also reproduce the z-score on this dataset
    z, real_det, shuffle_mean_det, shuffle_std_det, trans_matrix = compute_z_score(
        gaps, n_shuffles=200
    )

    # Check structural zeros
    structural_zeros = {
        "P(2->2)": trans_matrix[1][1],  # state 2 is index 1
        "P(4->4)": trans_matrix[2][2],  # state 4 is index 2
    }

    elapsed = time.time() - t0

    # Compute Wilcoxon-like sign test via bootstrap log-likelihood comparison
    # For each test point, informed has a different log-lik than naive.
    # We count how many times informed > naive per-sample.
    all_states = {0, 2, 4}
    counts = Counter(train_gaps)
    total_train = sum(counts.values())
    marginal = {s: counts.get(s, 0.001) / (total_train + 0.003) for s in all_states}

    alpha_smooth = 0.001
    trans_counts = defaultdict(Counter)
    for i in range(len(train_gaps) - 1):
        trans_counts[train_gaps[i]][train_gaps[i + 1]] += 1
    trans_prob = {}
    for s in all_states:
        row_total = sum(trans_counts[s].values()) + alpha_smooth * len(all_states)
        trans_prob[s] = {t: (trans_counts[s][t] + alpha_smooth) / row_total for t in all_states}

    informed_wins = 0
    n_compared = 0
    for i in range(1, len(test_gaps)):
        prev = test_gaps[i - 1]
        gap = test_gaps[i]
        p_naive = marginal.get(gap, 1e-10)
        p_informed = trans_prob.get(prev, marginal).get(gap, 1e-10)
        ll_naive = math.log(max(p_naive, 1e-10))
        ll_informed = math.log(max(p_informed, 1e-10))
        if ll_informed > ll_naive:
            informed_wins += 1
        n_compared += 1

    win_rate = informed_wins / n_compared if n_compared > 0 else 0.0

    # Use log-likelihood as the primary score (higher = better)
    metrics = {
        "naive_score": round(naive_ll, 6),
        "informed_score": round(informed_ll, 6),
        "delta": round(informed_ll - naive_ll, 6),
        "n_trials": len(test_gaps),
        "details": {
            "naive_accuracy": round(naive_acc, 4),
            "informed_accuracy": round(informed_acc, 4),
            "accuracy_delta": round(informed_acc - naive_acc, 4),
            "naive_mean_loglik": round(naive_ll, 6),
            "informed_mean_loglik": round(informed_ll, 6),
            "loglik_delta_bits": round((informed_ll - naive_ll) / math.log(2), 4),
            "z_score_det_real_vs_shuffle": round(z, 2),
            "det_real": round(real_det, 6),
            "det_shuffle_mean": round(shuffle_mean_det, 6),
            "structural_zeros": {k: round(v, 6) for k, v in structural_zeros.items()},
            "informed_wins_per_sample": round(win_rate, 4),
            "n_compared": n_compared,
            "n_primes": len(primes),
            "n_gaps": len(gaps),
            "train_size": len(train_gaps),
            "test_size": len(test_gaps),
            "elapsed_seconds": round(elapsed, 2),
            "interpretation": (
                "Positive delta = Markov (informed) outperforms marginal (naive). "
                "This confirms sequential order carries predictive information. "
                "z-score measures how far real transition det is from shuffle distribution."
            ),
        },
    }

    with open("metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"Naive  mean-LL: {naive_ll:.6f}  acc: {naive_acc:.4f}")
    print(f"Informed mean-LL: {informed_ll:.6f}  acc: {informed_acc:.4f}")
    print(f"Delta (LL): {informed_ll - naive_ll:.6f}  ({(informed_ll - naive_ll)/math.log(2):.4f} bits)")
    print(f"Informed wins per sample: {win_rate:.4f} ({informed_wins}/{n_compared})")
    print(f"z-score (det real vs shuffle): {z:.2f}")
    print(f"Structural zeros - P(2->2): {structural_zeros['P(2->2)']:.6f}, P(4->4): {structural_zeros['P(4->4)']:.6f}")
    print(f"Elapsed: {elapsed:.2f}s")
    print("metrics.json written.")


if __name__ == "__main__":
    run_test()
