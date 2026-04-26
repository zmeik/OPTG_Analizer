# Darwin-Lab Arena (full framework, planned)

**Status:** Planned. Not yet implemented in this repository.

This module will hold the full implementation of the **Darwin-Lab Arena** evolutionary prompt-population framework — currently summarised in `docs/DECISION_LOG.md` (DR-001..DR-022) and §3.2 of the AIPR 2026 paper.

Components planned for release:

- **Genotype six-tuple** (prompt template, image-preprocessing pipeline, FDI-grounding overlay, evidence-checklist generator, persona, post-processor)
- **Evolution loop** (selection, mutation, branching, generation tracking)
- **Per-task selection pressure** scoring against the public benchmark
- **Expert-in-the-loop κ scoring** infrastructure
- **Chart-image triangulation** (cross-checking voter outputs against canonical OPG anatomy)
- **Voter-pool serialisation** (JSON manifests, lineage tracking, version pinning)

## Relation to parent repository

The **AIPR 2026 paper claim** in this repository is *the existence and recoverability of prompt-output diversity* on MMOral-OPG-Bench (see Paper §3.2 "Reproducibility scope of the voter pool"). The Darwin-Lab Arena module ships the **specific procedure** that produced the 80-voter pool — useful for replication on other benchmarks but not strictly required to reproduce the v19 = 370/491 = 75.36% headline (which depends only on the released voter-prediction bundle in the parent `voter_predictions/`).

## Citation

When this module ships, please cite both the parent paper (AIPR 2026) and the module's own paper (forthcoming).
