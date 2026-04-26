# Cross-Benchmark Transfer Evaluation (planned)

**Status:** Planned. Not yet implemented.

This module will test the **transferability of the seven prompt-technique families** (parent paper Table 4) across medical-imaging benchmarks beyond MMOral-OPG-Bench. The hypothesis tested:

> *Each medical-imaging modality discovers its own family taxonomy under the same Darwin-Lab Arena evolutionary loop, but the meta-level structure (spatial grounding, image preprocessing, self-verification, reasoning patterns, persona conditioning, domain specialists, atlas grounding) is preserved with modality-appropriate substitutions.*

Planned target benchmarks:

| Modality | Benchmark candidate |
|---|---|
| Chest radiography | MIMIC-CXR-VQA, CheXbench |
| Dermatoscopy | DermVL-Bench (if released) |
| Fundus / retinal | RFMiD-VQA, FundusBench |
| Histopathology | PathVQA, PathChat |

For each, the experimental contract is the same as the parent paper:

1. Run an evolutionary loop to produce a voter pool under per-task selection pressure
2. Apply v19/v20 honest aggregation protocol from the parent repository
3. Quantify the prompt-sensitivity slack (single-prompt SOTA vs voter-union upper bound) on the public release
4. Compare the discovered family taxonomy against the dental taxonomy in parent paper Table 4

## Relation to parent repository

This module reuses the parent's `src/` aggregation code unchanged; only the voter pool and benchmark differ.

## Citation

When this module ships, please cite both the parent paper (AIPR 2026) and the module's own paper (forthcoming).
