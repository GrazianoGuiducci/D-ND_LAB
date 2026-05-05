# AI-Lab D-ND Finance

This lab studies market regime shifts as structural objects, not as after-the-fact labels. Its first boundary is direct: separate a generative bull/bear dipole from a sequence that only looks regime-like after interpretation.

Every cycle compares two poles:

- ordered market data: returns with local memory, state transitions, and measurable orientation;
- naive control: static VaR, realized volatility, and shuffled surrogates with the same distribution but destroyed order.

If the signal disappears under shuffle, the regime is not just a word: it is structure. If it does not, the lab does not promote the finding.

The intended output is practical: verified regime-shift kernels for FX, crypto, and equity workflows, runnable first on synthetic data and then on public market feeds when available.
