# Roadmap

This repository started as the reproducibility artefact for **MMOral-OPG-Bench v19/v20 honest aggregation** (the 370/491 = 75.36% headline result; AIPR 2026 submission). It is the *first* deliverable of a longer line of work on honestly deployable AI for dental panoramic radiograph interpretation.

The current top-level structure (`src/`, `voter_predictions/`, `predictions/`, `stats/`, `figures/`, `data/`, `docs/`) is **frozen** as the artefact referenced from the paper [18]. Future work — the dental-formula deployment target, the broader Darwin-Lab Arena evolutionary framework, and other modules — lives under `modules/` and grows additively without disturbing the paper-cited artefact.

## Current state (v1.0, April 2026)

| Component | Path | Status | Reference |
|---|---|---|---|
| v19 / v20 honest aggregation protocols | `src/mmoral_gate_v19_cv_sz.py`, `src/mmoral_gate_v20_per_question_pool.py` | **Released** | Paper §3.3 |
| 80-voter prediction bundle | `voter_predictions/` (80 JSON files) | **Released** | Paper §3.1 |
| Aggregated predictions (v9/v18/v19/v20/baseline) | `predictions/` | **Released** | Paper §4.2 |
| Statistical bundle (Wilson, bootstrap, McNemar) | `stats/` | **Released** | Paper §5 |
| Figures (4) | `figures/` | **Released** | Paper §4.2–4.4, §3.3 |
| Methodology evolution chronology (DR-001..DR-022) | `docs/DECISION_LOG.md` | **Released** | Paper §3.2.1 |
| Codex audit response | `docs/DEFENSE.md` | **Released** | Paper §6 |
| Reproduction script | `RUN_REPRODUCTION.sh` | **Released** | One command, byte-identical 370/491 |

## Planned modules (`modules/` directory)

These are the next deliverables of the same research line. Each module gets its own subdirectory with its own README, code, and (when available) its own paper companion. Cross-references between modules are made via relative paths within this repository.

| Module | Path | Status | Brief |
|---|---|---|---|
| **Dental formula extractor** | `modules/dental-formula/` | Planned | Per-tooth structured output (presence, restoration history, caries, periapical, marginal bone loss around implants) — moves the deployment target from MCQ closed-ended to the actual clinical structured object that drives treatment planning. Cited in the AIPR 2026 paper (§7.3) as the natural continuation of MMOral-OPG-Bench-style benchmarks. |
| **Darwin-Lab Arena (full framework)** | `modules/darwin-arena/` | Planned | Full evolutionary loop, voter-pool generation pipeline, expert-in-the-loop κ scoring, chart-image triangulation. Currently summarised in DR-001..DR-022 of `docs/DECISION_LOG.md`; full implementation planned for camera-ready / next paper. |
| **Cross-benchmark transfer evaluation** | `modules/cross-benchmark/` | Planned | Apply the v19 honest aggregation protocol on other public medical-imaging VQA benchmarks (chest radiography, dermatoscopy, fundus). Tests whether the seven prompt-technique families (Paper Table 4) transfer with adaptation, or whether each modality discovers its own taxonomy. |
| **Leak-resistant evaluation server (specification)** | `modules/leak-resistant-eval/` | Planned (specification only) | Reference design for the perpetual sealed-evaluation server proposed in Paper §7.3 — five properties (cryptographic mapping resistance, code-as-submission, perpetual operation, model-update survival, rolling leaderboards). Not an implementation in this repository; rather a design document and discussion seed for the community. |

## Versioning policy

- **`main` branch**: always reflects the latest stable artefact. Paper [18] points here.
- **Tagged releases**: `v1.0.0` = AIPR 2026 submission state; subsequent tags as modules ship.
- **Module additions**: live in `modules/<name>/` and do not modify top-level paper-cited artefacts. Each module ships with its own version tag (e.g. `dental-formula-v0.1`) when it stabilises.
- **Top-level frozen paths**: `src/`, `voter_predictions/`, `predictions/`, `stats/`, `figures/`, `data/`, `docs/DECISION_LOG.md`, `docs/DEFENSE.md` are the AIPR 2026 paper artefact. Modifications to these would require a paper erratum and are avoided in normal development.

## Contact

Sergo G. Manukov — `smanukov@newvision.ge` · ORCID 0000-0002-7659-2677
- RUDN University, Department of Maxillofacial Surgery and Surgical Dentistry, Medical Institute (Moscow, Russia)
- New Vision University, School of Dentistry, Visiting Researcher (Tbilisi, Georgia)
