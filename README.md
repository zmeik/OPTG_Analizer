# MMOral-OPG-Bench: 75.36% Leakage-Guarded Accuracy via Pre-Specified CV-Selected Voter Committees

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Reproducibility: One Command](https://img.shields.io/badge/reproducibility-one%20command-success)]()

> **Leakage-guarded accuracy of 75.36% (370/491) on MMOral-OPG-Bench closed-ended questions, +5.50 pp over the prior LOO-safe baseline. McNemar exact p = 1.12 × 10⁻⁷. No GT leak at inference, no oracle, no model weight training or fine-tuning on benchmark labels (committee selection uses leave-one-out label access only within predefined task groups).** The submitted paper title uses 'honest aggregation' in the same restricted technical sense (GT(k) is never used to select the prediction for k).

## Headline Result

| Method | Correct | Accuracy | Wilson 95% CI | McNemar vs baseline |
|---|---:|---:|---|---|
| Prior honest baseline (ChatGPT LOO-safe gate) | 343 / 491 | 69.86% | [65.66, 73.75]% | — |
| v9 strict uniform nested LOO | 350 / 491 | 71.28% | [67.13, 75.11]% | p = 1.5×10⁻³ |
| v20 strict per-question pool | 363 / 491 | 73.93% | [69.87, 77.62]% | p = 3.2×10⁻⁴ |
| v18 single-config gate | 364 / 491 | 74.13% | [70.08, 77.81]% | p = 4.9×10⁻⁵ |
| **v19 PRIMARY** (CV-selected combo size) | **370 / 491** | **75.36%** | **[71.36, 78.96]%** | **p = 1.1×10⁻⁷** |
| Voter-union oracle (engineering ceiling, NOT a claim) | 483 / 491 | 98.37% | — | — |

**Critical:** McNemar v19 vs v20 = **0.21** — the +7-question advantage of v19 over the strictest variant v20 is **not statistically significant**. The headline gain over baseline is robust to any of the standard validity challenges on protocol design.

**Scope of the claim.** The reported 75.36% should be interpreted as a benchmark-specific leakage-guarded committee-aggregation result on the public 491-question snapshot of MMOral-OPG-Bench, *not* as external clinical validation or evidence of general diagnostic performance. The 98.37% voter-union value in the bottom row is a latent-support measurement of the underlying VLM fleet (the empirical ceiling that any per-question selector could reach if it had perfect oracle access), *not* a deployment number.

## Reproduce in one command

```bash
git clone https://github.com/zmeik/OPTG_Analizer.git
cd OPTG_Analizer
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
bash RUN_REPRODUCTION.sh
```

Expected output:

```
=== v19 RESULT: 370/491 = 75.36%  Δ=+27 ===
```

## What this is and is not

### Is

- A **gate ensemble** over closed-book vision-language model (VLM) prompt variants on the MMOral-OPG-Bench benchmark.
- **Pre-specified** (in form: see [note](#note-on-pre-registered)): small finite hyperparameter grid, fixed default values, regex subfamily rules pre-committed.
- **Statistically defensive**: every claim accompanied by Wilson CI, bootstrap CI, McNemar exact p-value.
- **Reviewer-defensible**: addresses the four standard leakage concerns (per-group voter ranking, per-group apply-if-gain, hyperparameter overfitting, post-hoc rule design) — see [`docs/DEFENSE.md`](docs/DEFENSE.md).
- **Code-complete**: `bash RUN_REPRODUCTION.sh` produces `370/491` byte-for-byte from the included voter predictions and dataset.

### Is NOT

- An oracle simulation. We do not use GPT-4-as-judge. The benchmark itself defines the answer key (multiple choice letters); evaluation is mechanical letter-matching.
- A new VLM. We aggregate predictions from existing closed-book voter prompts (no model training, no GT-fine-tuning).
- A 75% claim with 95% statistical confidence. The Wilson CI lower bound is 71.36%; we report 75.36% as the point estimate. See [`stats/PAPER_STATS.md`](stats/PAPER_STATS.md) for full disclosure.
- An open-vocabulary system. The 12 task categories and 14 subfamilies are inherent to the MMOral-OPG-Bench question structure.

> <a id="note-on-pre-registered"></a> **Note on "pre-registered" / "pre-specified" usage.** Throughout this work, "pre-registered" / "pre-specified" denotes that the small hyperparameter grid (combo size ∈ {2, 3, 4}; top-K = 8; min-coverage = 0.7) and the 14 subfamily regex rules were committed to Git **before** running the final v19 / v20 evaluation, not formally registered on OSF or any external preregistration platform. The full design-evolution history is auditable via the project's `docs/DECISION_LOG.md` (DR-001..DR-022). The submitted manuscript title uses the word "honest aggregation" in the same restricted technical sense as the README's "leakage-guarded accuracy" — namely that GT(k) never enters the per-question prediction for k.

## Repo structure

```
.
├── README.md                       (you are here)
├── LICENSE                         MIT
├── CITATION.cff                    Citation metadata
├── requirements.txt                Python deps
├── RUN_REPRODUCTION.sh             One-command reproduction
├── src/
│   ├── mmoral_gate_v19_cv_sz.py            v19 PRIMARY 370/491 = 75.36%
│   ├── mmoral_gate_v20_per_question_pool.py v20 STRICT 363/491 = 73.93%
│   ├── mmoral_oracle_lite.py               Dataset loader, GT, scorer
│   ├── mmoral_visual_contract_voter.py     Task classification (12 categories)
│   └── mmoral_specialist_gate_lab.py       Earlier 343-baseline gate (ChatGPT)
├── predictions/
│   ├── baseline_343.json                  Prior baseline
│   ├── v9_strict_350.json                 Strict ablation
│   ├── v18_fixed_364.json                 Single-config ablation
│   ├── v19_primary_370.json               PRIMARY result
│   └── v20_strict_363.json                Strict per-question pool ablation
├── voter_predictions/
│   └── (80+ JSON files: g1_* through g32_*, h1_* through h3_*)
├── data/
│   └── mmoral_compact_questions.json      Compact non-image MMOral metadata + answer key
├── stats/
│   ├── v19_paper_statistics.json          Full statistical bundle
│   ├── v20_paper_statistics.json          v20 stats including McNemar v19 vs v20
│   ├── ablation_table.tex                 LaTeX ablation table
│   └── per_task_table.tex                 LaTeX per-task table
├── figures/
│   ├── fig_tier_accuracy.{png,pdf}        5-tier accuracy bar chart
│   ├── fig_per_task.{png,pdf}             Per-task baseline vs v19 comparison
│   └── fig_mcnemar.{png,pdf}              v19 vs baseline 2×2 contingency
└── docs/
    ├── PAPER_DRAFT.md                     Camera-ready paper draft
    └── DEFENSE.md                         Response to Codex audit (4 attack points)
```

## How v19 works (in 5 lines)

```
For each task group G (or rule-based subfamily of generic_tooth_identification):
    For each combo size sz in {2, 3, 4}:
        Compute nested-LOO predictions on G with combo size sz, top-K=8 voters, min-coverage=0.7
    Pick sz* with highest LOO-CV accuracy (task-internal cross-validation)
    Apply iff nested_LOO_accuracy(sz*) > baseline_accuracy
```

**Honesty property:** for each question k in G, the combo identity is selected using only G\{k}. Question k's own GT never enters the decision for k. See [`src/mmoral_gate_v19_cv_sz.py`](src/mmoral_gate_v19_cv_sz.py) for the 185-line implementation.

## Per-task breakdown

| Task | N | Baseline | v19 | Δ | sz (CV-selected) |
|---|---:|---:|---:|---:|:---:|
| caries | 44 | 25 | 25 | 0 | — |
| crown_plus_rct | 17 | 13 | 14 | +1 | 2 |
| crown_restoration | 20 | 14 | 17 | +3 | 2 |
| crown_without_rct | 1 | 1 | 1 | 0 | — |
| filling_restoration | 21 | 14 | 14 | 0 | — |
| **generic_tooth_identification** (sub-family CV) | 259 | 189 | **197** | **+8** | mixed |
| impaction | 19 | 14 | 15 | +1 | 4 |
| implant_restoration | 3 | 1 | 3 | +2 | 2 |
| periapical_abscess | 25 | 17 | 19 | +2 | 3 |
| periapical_granuloma | 32 | 17 | 24 | **+7** | 3 |
| periapical_lesion | 21 | 17 | 17 | 0 | — |
| root_canal_treatment | 29 | 21 | 24 | +3 | 3 |
| **TOTAL** | **491** | **343** | **370** | **+27** | — |

## Data

The MMOral-OPG-Bench is a multiple-choice question set on 100 dental panoramic radiographs (491 questions in the public HuggingFace release; 500 in the original paper text) released by Hao *et al.* 2025 (arXiv:2509.09254, "Towards Better Dental AI: A Multimodal Benchmark and Instruction Dataset for Panoramic X-ray Analysis"). The benchmark is distributed at https://huggingface.co/datasets/OralGPT/MMOral-OPG-Bench. We do **not** redistribute the panoramic images. The `data/mmoral_compact_questions.json` file contains only the question text, options, task category, and answer key — sufficient for evaluating gate predictions.

To run the original VLM voters from scratch (rather than reusing our cached `voter_predictions/`), you would need access to the OPG images directly from the MMOral-OPG-Bench distribution, plus a VLM API key (the original voters were generated using a mix of Claude Opus, GPT-4V, and Gemini Pro on the OPG images).

## Citation

If you use this code or build on this protocol, please cite:

```bibtex
@unpublished{manukov2026mmoral,
  title  = {Prompt-sensitivity slack on {MMOral-OPG-Bench}: blind 56.80\%, honest aggregation 75.36\%, voter-union support 98.37\%},
  author = {Manukov, Sergo G.},
  year   = {2026},
  note   = {Manuscript submitted to AIPR 2026, the 9th International Conference on Artificial Intelligence and Pattern Recognition, Xiamen, China (under peer review). Code and data: \url{https://github.com/zmeik/OPTG_Analizer}}
}
```

ORCID: 0000-0002-7659-2677

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgments

This work is part of a PhD dissertation in dental medicine (RUDN University, scientific advisor: Prof. S. Yu. Ivanov, MD, PhD, Corresponding Member of the Russian Academy of Sciences). Methodological consultation provided by Anthropic Claude Opus 4.7 (1M context) and OpenAI ChatGPT (Codex) via independent reviewer-AI critique loops. The Codex audit (see `CHATGPT55_CHALLENGE/09_REPRODUCIBILITY_AUDIT_NOTES.md` in the working repository) directly informed the v20 strict ablation.

The MMOral-OPG-Bench dataset is the work of its respective authors; this repository does not redistribute the radiograph images.

## Contact

Sergo Manukov · smanukov@newvision.ge · ORCID 0000-0002-7659-2677
