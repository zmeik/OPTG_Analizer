# Dental Formula Extractor (planned)

**Status:** Planned. Not yet implemented.

This module is the natural continuation of the AIPR 2026 paper's framing (see paper §7.3). The MMOral-OPG-Bench multiple-choice benchmark is, in clinical practice, a *projection* of the real deployment target: a fully populated **per-tooth dental formula** capturing for each FDI position the presence/absence of the tooth, restoration history (filling, crown, RCT, post), pathology (caries, periapical lesion, granuloma, abscess), implant status, and marginal bone loss around any implant.

This module will:

- Extract structured per-tooth records from a panoramic radiograph
- Use the v19/v20 honest aggregation protocol (parent repository) on per-tooth sub-questions
- Cross-validate against expert-annotated dental formulas (parallel Darwin Arena ground-truth annotation work)
- Output a normalised JSON dental formula consumable by clinical practice-management systems

## Relation to parent repository

- The **honest aggregation protocol** (v19 / v20) is reused from the parent `src/`
- The **voter pool** philosophy (80 prompts, 7 technique families) is reused
- The **evaluation target** changes from closed-ended MCQ accuracy to structured-output F1 / Cohen's κ per FDI position

## Citation

When this module ships, please cite both the parent paper (AIPR 2026) and the module's own paper (forthcoming).
