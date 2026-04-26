# Leak-Resistant Deployment-Evaluation Server (specification only)

**Status:** Design document only. Not an implementation.

This module is the **specification seed** for the perpetual sealed-evaluation server proposed in §7.3 of the parent AIPR 2026 paper. It contains a design document only — implementation is a research contribution in its own right and is plausibly best addressed by a community consortium rather than a single team.

The five minimum properties (per parent paper §7.3):

1. **Cryptographic resistance to mapping recovery** — submissions cannot be combined to reconstruct the held-out question–answer mapping
2. **Code-as-submission, online accessibility** — researchers submit a deterministic protocol, receive an aggregate score in bounded time, with no per-question disclosure
3. **Perpetual operation with an evolving test set** — controlled item rotation; rules out one-shot release of the sealed split
4. **Survival across model-update cycles** — the same submitted protocol remains comparable as new VLMs become available
5. **Rolling, comparable leaderboards** — each stored protocol is automatically re-evaluated against subsequent test-set versions, producing a time-indexed score history

## Discussion seed

This module is intentionally a discussion document, not a prototype. We invite contributions:
- Cryptographic protocols for property (1)
- Custodianship / governance models for property (3)
- Versioning standards for properties (4) and (5)

## Citation

When discussing this proposal, please cite the parent paper (AIPR 2026, §7.3).
