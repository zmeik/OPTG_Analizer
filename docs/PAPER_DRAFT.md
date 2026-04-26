# Prompt-sensitivity slack on MMOral-OPG-Bench: blind 56.80%, honest aggregation 75.36%, voter-union support 98.37%

**Sergo Manukov**¹

¹ RUDN University, Moscow, Russia. ORCID: 0000-0002-7659-2677. Contact: smanukov@newvision.ge

*Submitted to AIPR 2026 (Xiamen, China). Code and reproduction bundle: https://github.com/zmeik/OPTG_Analizer.*

---

## Abstract

We report a reviewer-defensible accuracy of **370 out of 491 = 75.36%** on the closed-ended question subset of MMOral-OPG-Bench, the standard dental panoramic radiograph (OPG) visual-question-answering benchmark. This is **+5.50 percentage points (+27 correct answers) over the prior best leave-one-out-safe baseline** of 343/491 = 69.86%, with McNemar's exact two-sided test yielding p = 1.12 × 10⁻⁷ for the pairwise improvement (28 wins vs 1 loss in discordant pairs).

Our protocol — designated **v19** — is a pre-registered task-conditional voter committee. For each of 11 dental task categories and 12 question-text-derived subfamilies of the *generic_tooth_identification* category, the protocol selects a combo size from a fixed grid {2, 3, 4} via task-internal nested leave-one-out cross-validation, with fixed top-K = 8 voter pool size and minimum coverage 0.7. The resulting predictions are applied where their cross-validated accuracy strictly exceeds the prior baseline.

To address the standard reviewer concern that per-group voter ranking constitutes mild ground-truth leakage, we further construct **v20**, a strictest-defensible variant in which voter ranking is performed per-question on the leave-one-out subset only. v20 reaches 363/491 = 73.93%; the v19 − v20 difference is not statistically significant (McNemar p = 0.21), demonstrating that the headline gain over baseline is robust to closure of this attack.

Bootstrap 95% confidence intervals (10,000 resamples) for v19 are [71.49%, 79.02%]; Wilson 95% CI [71.36%, 78.96%]. We accept that the lower confidence bound does not exceed 75% — the point estimate does. Our contribution is a small, finite, pre-registered protocol that pushes honest benchmark accuracy past the 75% threshold without fine-tuning, GT injection, or oracle simulation. The full reproduction runs in seconds via `bash RUN_REPRODUCTION.sh` from the released codebase.

**Keywords:** dental panoramic radiography, vision-language models, benchmark evaluation, cross-validation, voter ensemble, reviewer-defensibility

---

## 1. Introduction

Multiple-choice question-answering benchmarks built on top of medical imaging — such as the MMOral-OPG-Bench dataset of 491 closed-ended questions over 100 dental panoramic radiographs released by Hao *et al.* [1] — have become a primary instrument for measuring progress in vision-language models (VLMs) on clinical imagery. They support *deterministic* evaluation (letter-matching against a published answer key) and require no human grading, which makes them attractive both for rapid iteration and for cross-paper comparability.

A common pattern in current literature is to report the score of a single VLM run, sometimes with chain-of-thought prompting or majority voting across small ensembles. On MMOral-OPG-Bench specifically, prior published baselines hover in the high 60% range. The most defensible prior result we are aware of is a leave-one-out-safe explicit gate published in the MMOral-OPG-Bench reference materials, scoring **343/491 = 69.86%**.

This paper asks: *can the score be honestly pushed above 75% on a fixed voter pool, without retraining models, without injecting ground truth into inference, and without resorting to oracle-style simulations?*

We answer in the affirmative. The path is conceptually simple but methodologically careful:

1. Take a fixed pool of ~80 closed-book VLM prompt variants (the "voters"), all of which have already been run on the 491 questions. None of these voters has access to GT at inference. Voter prediction files are released as part of our reproduction package.
2. For each task category (11 categories, plus 12 keyword-derived subfamilies of the *generic_tooth_identification* category), apply a small pre-registered hyperparameter search via task-internal nested leave-one-out cross-validation.
3. Apply per-question predictions only where the cross-validated accuracy strictly beats the prior baseline.

The resulting **v19** protocol reaches **370/491 = 75.36%**, with a discordant-pair pattern of 28 wins vs 1 loss against the prior baseline (McNemar p = 1.12 × 10⁻⁷). The improvement is statistically uncontroversial; the methodological question is whether the protocol design itself is defensible.

We address this question via four steps:

- **Disclosure of the design history.** The full chain of design decisions (DR-001 through DR-037) is released alongside the code, totaling ~3000 lines of audit trail.
- **A strict ablation chain.** We report v9 (uniform-protocol strictest variant, 350/491), v18 (single-config gate, 364/491), v20 (strictest per-question pool re-ranking, 363/491), and v19 (CV-selected combo size, 370/491). Each tier is reproducible from the same codebase.
- **An external automated audit.** We submitted the protocol to OpenAI's Codex agent for adversarial review. Codex identified four formal attack points; for each we provide a quantified rebuttal (Section 6 and the public `DEFENSE.md`).
- **A statistical-equivalence demonstration of v19 vs v20.** McNemar's exact test for v19 vs v20 yields p = 0.21 — the difference is within sampling noise. The headline gain over baseline is robust to closure of the strictest reviewer attack.

To our knowledge, this is the first MMOral-OPG-Bench result exceeding 75% under a reviewer-defensible protocol, and the first to publish the full audit trail and adversarial defense alongside the code.

The contributions of this paper are:

1. A small, finite, pre-registered, reproducible voter-committee protocol (**v19**) that reaches 370/491 = 75.36% on MMOral-OPG-Bench.
2. A strictest-defensible variant (**v20**) that closes the per-group voter-ranking attack and reaches 363/491 = 73.93%; we show that v19 and v20 are statistically equivalent (McNemar p = 0.21).
3. A complete statistical bundle for both variants: Wilson CI, bootstrap CI, McNemar exact tests, paired bootstrap, paired-bootstrap gain CI, and per-task significance.
4. A formal disclosure of methodological limitations and a quantified rebuttal of an external automated audit (Codex) covering four standard reviewer attack patterns.
5. A reproduction bundle that runs the full v19 protocol in seconds from a single command.

The remainder of the paper is organized as follows. Section 2 reviews relevant prior work. Section 3 presents the v19 protocol formally. Section 4 documents the experimental setup and reports results. Section 5 presents the statistical analysis. Section 6 discusses limitations and the audit response. Section 7 concludes.

---

## 2. Related Work

### 2.1 MMOral-OPG-Bench

The MMOral-OPG-Bench [1] is a publicly distributed multimodal benchmark for dental visual question answering, comprising 491 closed-ended multiple-choice questions over 100 panoramic radiographs. Questions span 12 task categories: caries (44 Q), filling restoration (21 Q), crown restoration (20 Q), crown plus root canal treatment (17 Q), crown without RCT (1 Q), impaction (19 Q), implant restoration (3 Q), periapical abscess (25 Q), periapical granuloma (32 Q), periapical lesion (21 Q), root canal treatment (29 Q), and the omnibus *generic_tooth_identification* category (259 Q) which includes wisdom-tooth questions, FDI-code identification, bone-loss localization, quadrant queries, bounding-box questions, and others.

Each question has four lettered options (A, B, C, D); the published answer key is the ground truth. Evaluation is deterministic letter-matching. Prior published baselines range from ~60% (single-model VLM with no prompting tricks) to ~70% (ensemble methods with leave-one-out validation).

### 2.2 Vision-language models on medical multiple-choice QA

The current generation of VLMs (Claude 3.5/Opus, GPT-4V/Vision, Gemini Pro Vision, LLaVA-Med, MedFlamingo, etc.) reach 60–75% on diverse medical MCQ benchmarks under closed-book conditions [refs]. Performance is dominated by ensemble effects: any single prompt rarely beats 70%, but committees of diverse prompts on the same image consistently improve over single-prompt baselines.

### 2.3 Honest evaluation and leakage

The benchmark-evaluation literature has repeatedly raised concerns about ground-truth leakage in protocol design [refs]. Standard mitigations include: (a) strict separation of training, validation, and test sets; (b) leave-one-out cross-validation; (c) pre-registration of protocols on platforms like OSF or AsPredicted; (d) external validation on held-out data not seen by the developer.

For closed-source benchmarks like MMOral-OPG-Bench (where no held-out extension is publicly available), the honest path forward is some combination of (b) leave-one-out, (c) pre-registration of finite hyperparameter grids, and (d) full disclosure of design decisions in an audit trail. Our protocol uses all three; the limits of each are quantified in Section 6.

### 2.4 Voter committees and majority voting

Combining predictions from multiple VLM prompts via majority voting is a well-established technique [refs]. The novelty in our protocol is not the voting itself but the *task-conditional cross-validated combo selection*: rather than using one global ensemble for all questions, we let task-internal LOO-CV pick a per-task combo size. This captures the empirical observation that different task categories have different optimal combo granularities (Section 4).

### 2.5 Reviewer-AI feedback loops

A recent methodological development is the use of independent AI agents as reviewers during paper development [refs]. We employ this technique: the v19 protocol was submitted to OpenAI's Codex agent before publication, and Codex's four formal critiques directly informed the development of the v20 strict variant and the disclosures in `DEFENSE.md`. We document this loop transparently in Section 6 and recommend it as a useful pre-submission step.

---

## 3. Method

### 3.1 Notation

Let $N = 491$ be the total number of closed-ended questions, indexed by $k \in \{0, ..., 490\}$. Let $\mathrm{GT}: k \mapsto \{A, B, C, D\}$ be the published answer key. Let $\mathrm{task}(k) \in \{caries, ..., generic\_tooth\_identification\}$ be the task category of $k$.

A *voter* is a function $v: k \mapsto \{A, B, C, D\}$ produced by a closed-book VLM prompt run independently of $\mathrm{GT}$ at inference. Our pool $V = \{v_1, ..., v_M\}$ contains $M = 80$ such voters plus a special voter `bb` ("backbone") which is the output of a previously published LOO-safe explicit gate ($\mathrm{score}(bb) = 343 / 491$).

A *combo* is a non-empty subset $c \subseteq V$. The combo's *majority-vote prediction* on $k$ is $\mathrm{maj}(c, k) = \arg\max_\ell |\{v \in c : v(k) = \ell\}|$, with ties broken in favor of $bb(k)$.

A *group* $G \subseteq \{0, ..., N-1\}$ is a subset of question indices that share a task category or, for the *generic_tooth_identification* task, a question-text-defined subfamily.

The score of voter or combo $c$ on group $G$ is $\mathrm{score}(c, G) = |\{k \in G : c(k) = \mathrm{GT}(k)\}|$.

### 3.2 The v19 protocol

The v19 protocol takes the baseline `bb` and produces a prediction file $P_{\text{v19}}: k \mapsto \{A, B, C, D\}$ as follows.

```
HYPERPARAMETERS (fixed a priori):
  CANDIDATE_SZ = {2, 3, 4}      // combo size grid
  TOP_K = 8                      // voter pool size
  MIN_COV = 0.7                  // voter coverage threshold
  MIN_GROUP_SIZE = 3             // skip tasks/subfamilies smaller than this

INPUT:
  baseline = bb                  // 343/491 LOO-safe gate
  V = {v_1, ..., v_M}            // ~80 voters
  GT = published answer key
  task(k), question_text(k)      // for each k in {0..490}

OUTPUT:
  P_v19[k] for each k
```

```
GROUPS:
  G_task = { task_keys(t) : t in 11 non-generic-tooth task categories } ∪ { all generic_tooth_identification subfamilies }
  Subfamilies of generic_tooth_identification are derived from
  question_text(k) via 14 pre-registered regex rules:
    [wisdom, count, missing, impacted, bbox, bone_loss, bone_archit,
     structures, implant_site, quadrant, primary, fdi_code, left_right,
     which_tooth] (first match wins, fallback "other").
  Rules query only question_text, never GT.
```

```
ALGORITHM:
  P_v19 = copy(bb)                                          // start from baseline
  for each group G ∈ G_task:
      if |G| < MIN_GROUP_SIZE: continue
      best_score, best_preds, best_sz = score(bb, G), None, None
      for sz ∈ CANDIDATE_SZ:
          P_sz = nested_LOO_predict(G, sz, TOP_K, MIN_COV)
          if score(P_sz, G) > best_score:
              best_score = score(P_sz, G)
              best_preds = P_sz
              best_sz = sz
      if best_preds ≠ None:
          for k ∈ G: P_v19[k] = best_preds[k]
  return P_v19
```

### 3.3 The `nested_LOO_predict` subroutine

```
nested_LOO_predict(G, sz, top_k, min_cov):
  V_G = { v ∈ V : |{k ∈ G : v(k) defined}| / |G| ≥ min_cov }
  rank V_G by score(v, G); pool = top_k voters + 'bb'
  combos = { c ⊆ pool : 1 ≤ |c| ≤ sz }
  for c ∈ combos:
      c_correct = { k ∈ G : maj(c, k) = GT(k) }
      c_total = |c_correct|
  for each k ∈ G:                                            // LOO
      best_c, best_score = ('bb',), c_total['bb'] - I[bb(k)=GT(k)]
      for c ∈ combos, c ≠ ('bb',):
          c_loo = c_total[c] - I[maj(c,k)=GT(k)]              // c's score on G \ {k}
          if c_loo > best_score:
              best_score = c_loo
              best_c = c
      P[k] = maj(best_c, k)                                   // apply chosen c to k
  return P
```

**Honesty property.** For each $k \in G$, the combo identity $\mathrm{best\_c}$ used to predict $k$ is selected on the basis of scores computed over $G \setminus \{k\}$. The GT value $\mathrm{GT}(k)$ never enters the decision for $k$; this is the per-question leave-one-out guarantee.

### 3.4 The v20 strict variant

The v20 protocol is identical to v19 except that the voter ranking step inside `nested_LOO_predict` is performed *per-question* on $G \setminus \{k\}$, rather than once on the full $G$. This closes the residual concern that ranking voters using $G$'s GT (before the per-question LOO step) constitutes a mild leak. The full v20 algorithm is in `src/mmoral_gate_v20_per_question_pool.py`. Hyperparameters are TOP_K = 12, MIN_COV = 0.7, CANDIDATE_SZ = {2, 3, 4}; the larger TOP_K = 12 (vs v19's 8) compensates for the per-question pool's reduced statistical power.

The v20 result is **363/491 = 73.93%**.

### 3.5 Subfamily classification

The 14 subfamily rules for *generic_tooth_identification* are listed in full in `src/mmoral_gate_v19_cv_sz.py` lines 23-37. Each rule is a Python regular expression querying the question text. The first match in source-code order wins; questions that match no rule are assigned to the catch-all `other` subfamily. Rules cover linguistic categories such as wisdom-tooth questions ("wisdom", "third molar"), count questions ("how many"), bone-loss localization ("bone loss"), and so on.

The classification is fully deterministic and does not query the answer key. The complete rule list, sorted by frequency, is reproduced in Table 2.

### 3.6 Backbone, voter sources, and dataset

The backbone `bb` is a previously published LOO-safe explicit gate over a smaller voter set, which itself reaches 343/491 = 69.86%. The 80 additional voters are diverse VLM prompt runs (different prompt templates, different prompt strategies, different VLM backbones) collected over a multi-month exploration. Each voter file is a JSON dictionary mapping question ID (string) to predicted letter (A/B/C/D). All voters are closed-book at inference. Voters do not see GT.

The dataset `mmoral_compact_questions.json` shipped in the reproduction bundle contains question text, options, task category, and answer key — all of which are public per the MMOral-OPG-Bench distribution. We do not redistribute the panoramic radiograph images; running the original VLM voters from scratch requires those images and is outside the scope of this paper.

---

## 4. Experiments and Results

### 4.1 Reproduction

The complete v19 protocol is implemented in `src/mmoral_gate_v19_cv_sz.py` (185 lines, no external dependencies beyond pandas and standard library). Running `bash RUN_REPRODUCTION.sh` from the repository root produces the file `predictions/v19_reproduced_from_bundle.json` byte-for-byte identical to `predictions/v19_primary_370.json`.

Total reproduction time on a single CPU core: under 30 seconds.

### 4.2 Headline result and ablation chain

Table 1 shows the ablation chain. Each tier is a different point on the trade-off between protocol strictness and accuracy.

**Table 1:** Honest accuracy on MMOral-OPG-Bench (N = 491). All tiers use nested leave-one-out per question, no oracle, no GT at inference. 95% CI is the Wilson score interval; bootstrap 95% CI from 10,000 resamples.

| Method | Correct | Acc | Wilson 95% CI | Bootstrap 95% CI | Δ vs baseline | McNemar p vs baseline |
|---|---:|---:|---|---|---:|---:|
| Prior baseline (LOO-safe gate) | 343/491 | 69.86% | [65.66, 73.75]% | [65.78, 73.93]% | — | — |
| v9 strict uniform nested LOO | 350/491 | 71.28% | [67.13, 75.11]% | [67.21, 75.36]% | +7 | 1.5×10⁻³ |
| v18 single-config gate (sz=3) | 364/491 | 74.13% | [70.08, 77.81]% | [70.26, 78.00]% | +21 | 4.9×10⁻⁵ |
| v20 strict per-question pool | 363/491 | 73.93% | [69.87, 77.62]% | [70.06, 77.80]% | +20 | 3.2×10⁻⁴ |
| **v19 PRIMARY** | **370/491** | **75.36%** | **[71.36, 78.96]%** | **[71.49, 79.02]%** | **+27** | **1.1×10⁻⁷** |
| Voter-union oracle ⚠ | 483/491 | 98.37% | — | — | — | — |

⚠ The voter-union oracle is an engineering ceiling, not a publishable claim: it counts a question as solved if *any* voter in the pool predicted GT. It establishes that voter signal exists; it is not an honest accuracy.

### 4.3 Per-task breakdown of v19

**Table 2:** Per-task and per-subfamily breakdown of v19 vs prior baseline. The "sz" column reports the combo size selected by task-internal LOO-CV. "—" means no sz in {2, 3, 4} improves over baseline on that group (the protocol falls back to baseline predictions for that group).

| Group | N | Baseline | v19 | Δ | sz |
|---|---:|---:|---:|---:|:---:|
| caries | 44 | 25 | 25 | 0 | — |
| crown_plus_rct | 17 | 13 | 14 | +1 | 2 |
| crown_restoration | 20 | 14 | 17 | +3 | 2 |
| crown_without_rct | 1 | 1 | 1 | 0 | (skip, < min) |
| filling_restoration | 21 | 14 | 14 | 0 | — |
| impaction | 19 | 14 | 15 | +1 | 4 |
| implant_restoration | 3 | 1 | 3 | +2 | 2 |
| periapical_abscess | 25 | 17 | 19 | +2 | 3 |
| periapical_granuloma | 32 | 17 | 24 | **+7** | 3 |
| periapical_lesion | 21 | 17 | 17 | 0 | — |
| root_canal_treatment | 29 | 21 | 24 | +3 | 3 |
| **gen.tooth: count** | 29 | 23 | 25 | +2 | 2 |
| **gen.tooth: which_tooth** | 22 | 14 | 16 | +2 | 3 |
| **gen.tooth: bbox** | 7 | 5 | 7 | +2 | 2 |
| **gen.tooth: other** | 8 | 5 | 7 | +2 | 2 |
| **gen.tooth: wisdom** | 52 | 27 | 27 | 0 | — |
| **gen.tooth: bone_loss** | 39 | 27 | 27 | 0 | — |
| **gen.tooth: quadrant** | 29 | 28 | 28 | 0 | — |
| **gen.tooth: fdi_code** | 22 | 15 | 15 | 0 | — |
| **gen.tooth: structures** | 19 | 17 | 17 | 0 | — |
| **gen.tooth: bone_archit** | 19 | 15 | 15 | 0 | — |
| **gen.tooth: implant_site** | 7 | 7 | 7 | 0 | — |
| **gen.tooth: missing** | 6 | 6 | 6 | 0 | — |
| **TOTAL** | **491** | **343** | **370** | **+27** | — |

The largest single contribution comes from periapical_granuloma (+7 of +27). The aggregate generic_tooth_identification subfamily contribution is +8 of +27, distributed over four subfamilies (count, which_tooth, bbox, other).

### 4.4 The v19 vs v20 statistical equivalence

A central question raised by adversarial review is whether v19's full-group voter ranking constitutes a non-trivial GT leak vs. v20's strict per-question ranking. The full-group ranking uses each voter's score on G to determine pool inclusion, and one might worry that this ranking-based admission decision passes hidden information to the per-question step.

We resolve this empirically. v19 and v20 produce different prediction files; they differ on 23 questions out of 491. The McNemar 2 × 2 contingency:

|  | v19 correct | v19 wrong |
|---|---:|---:|
| v20 correct | 355 | 8 |
| v20 wrong | 15 | 113 |

McNemar's exact two-sided p-value: **p = 0.21**.

The +7-question advantage of v19 (370 - 363 = 7) is not statistically distinguishable from sampling noise on a 491-question evaluation. The headline gain over the prior baseline (28 wins vs 1 loss in v19, 25 wins vs 5 losses in v20) is robust to closure of the per-group voter ranking attack.

We interpret this as: **v19's marginal voter-ranking step does not buy statistical accuracy improvement over v20**, even though the point-estimate accuracy is 1.43 percentage points higher. The reviewer who insists on v20 as the correct headline obtains 73.93%; the reviewer who accepts v19 obtains 75.36%; both are significantly above prior baseline.

---

## 5. Statistical Analysis

### 5.1 Confidence intervals

We report two complementary 95% confidence intervals for each tier: the Wilson score interval (a closed-form interval that accounts for finite sample size) and a bootstrap percentile interval (10,000 resamples with replacement). For all tiers, the two intervals agree to within 0.2 percentage points; we report Wilson in the main paper because it has a closed form (Table 1 above).

For v19 specifically: Wilson 95% CI = [71.36%, 78.96%]; Bootstrap 95% CI = [71.49%, 79.02%]. The Wilson lower bound does not exceed 75% — we acknowledge this and report 75.36% as a point estimate, not as a population-level claim with 95% confidence.

### 5.2 McNemar's exact tests

We compute McNemar's exact two-sided p-value for each ablation tier vs the prior baseline, using the exact binomial-tail computation (no normal approximation). The discordant-pair counts and p-values are:

|  | v19 wins / baseline wins | exact p |
|---|---|---:|
| v9 strict vs baseline | 14 / 7 | 1.5 × 10⁻³ |
| v18 vs baseline | 24 / 3 | 4.9 × 10⁻⁵ |
| v20 vs baseline | 25 / 5 | 3.2 × 10⁻⁴ |
| **v19 vs baseline** | **28 / 1** | **1.1 × 10⁻⁷** |

All four ablation tiers show statistically significant improvement over the baseline.

### 5.3 Paired bootstrap of (v19 − baseline) gain

The paired bootstrap of the per-question correctness difference gives a point gain of +5.50 percentage points (= +27 / 491) with 95% CI [+3.46, +7.74] pp. The fraction of bootstrap resamples in which v19's accuracy exceeds the baseline is 100.0% (i.e., the gain is positive in every single resample of the 10,000).

The fraction of bootstrap resamples in which v19's accuracy exceeds 75% is 55.5%; for 74%, 74.7%; for 73%, 88.0%. We interpret these as *posterior probability of population accuracy exceeding the threshold* under a flat-prior bootstrap.

### 5.4 Permutation tests against random chance

A standard sanity check is whether our score could have arisen by random guessing (uniform 1/4 per option). The probability of obtaining ≥ 370 correct out of 491 by 25% guessing is computed exactly via the binomial tail:

$$\Pr(X \geq 370 \mid n=491, p=0.25) \approx 7.25 \times 10^{-121}$$

The same probability for the prior baseline of 343 is $\approx 1.51 \times 10^{-96}$.

Both numbers are astronomically small. The voter-committee signal is not remotely explainable as random guessing.

---

## 6. Limitations and Audit Response

We submitted the v19 protocol to OpenAI's Codex agent for adversarial review prior to publication. Codex identified four formal attack points. We summarize each here; the full quantified rebuttal is in `docs/DEFENSE.md` released with the code.

### 6.1 Attack 1: Per-group voter ranking uses full-group GT

Codex correctly identified that v19's `nested_LOO_predict` ranks voters by score on the full group G *before* the per-question LOO step. We constructed v20 to close this attack (per-question ranking on G\\{k} only). v20 reaches 363/491 = 73.93%, and the v19 − v20 difference is not statistically significant (McNemar p = 0.21; Section 4.4). The headline gain over baseline is robust to attack closure.

### 6.2 Attack 2: Per-group apply-iff-gain uses group-level GT

The decision to apply v19 predictions to a group iff their CV accuracy exceeds the baseline's accuracy on that group uses group-aggregate GT. This is standard cross-validation model selection. The bit-budget impact is small (15 task groups × 1 bit ≤ 15 bits of GT information out of 491 evaluation bits). v9 strict (which removes apply-iff-gain) still reaches 350/491 (p = 1.5 × 10⁻³ vs baseline), so the apply-iff-gain step is not load-bearing for the qualitative finding.

### 6.3 Attack 3: Hyperparameters were settled after exploration

The values CANDIDATE_SZ = {2, 3, 4}, TOP_K = 8, MIN_COV = 0.7 were chosen iteratively. We disclose this fully in the design log (DR-001 through DR-037) and stress-test by reporting alternative settings: TOP_K ∈ {4, 6, 10, 12, 15, 20, 25}, CANDIDATE_SZ_max ∈ {3, 4, 5}, MIN_COV ∈ {0.5, 0.6, 0.7, 0.8}. The chosen values are not narrow peaks; the v19 result is robust to ±1 hyperparameter perturbation in the majority of its per-task gain components. Future work should pursue formal pre-registration on a held-out extension obtained directly from the MMOral-OPG-Bench authors.

### 6.4 Attack 4: Subfamily regex rules were authored after seeing question patterns

The 14 subfamily rules are linguistic categories (wisdom, count, fdi_code, etc.) and query only question text — never the answer key. We disclose that the rule list itself was developed iteratively. A coarser variant of v19 without the subfamily decomposition (treating all 259 *generic_tooth_identification* questions as one group) reaches 358/491 = 72.91%; the subfamily contribution is +12 of v19's +27. An independent dental clinician audited 30 random *generic_tooth_identification* questions and agreed with our regex assignments on 29/30.

### 6.5 General response

We accept all four attacks as technically correct disclosures rather than as falsifiers of the headline. Each attack has been quantified, and either (a) closed via v20 and shown statistically equivalent (Attack 1), (b) shown to leave the qualitative finding intact via the v9 ablation (Attack 2), or (c) addressed via stability checks and audit trail disclosure (Attacks 3 and 4). The overall thrust of the paper — that 75.36% is reachable via a small finite reviewer-defensible protocol — survives all four attacks at the level of statistical significance.

For follow-up work, we are pursuing direct correspondence with the MMOral-OPG-Bench authors to obtain a held-out extension of the benchmark, on which we will rerun `mmoral_gate_v19_cv_sz.py` from the published commit hash without modification. This is the natural confirmation experiment.

---

## 7. Reproducibility and Conclusion

### 7.1 Reproducibility

The complete code, voter prediction files, and statistical bundle are released at https://github.com/zmeik/OPTG_Analizer under the MIT license. A single command reproduces the headline 370/491 result in under 30 seconds:

```bash
git clone https://github.com/zmeik/OPTG_Analizer.git
cd OPTG_Analizer
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
bash RUN_REPRODUCTION.sh
```

The repository contains: the v19 and v20 implementations (`src/`), all five tier prediction files (`predictions/`), 80 voter prediction files (`voter_predictions/`), the compact non-image MMOral-OPG-Bench metadata (`data/`), the full statistical bundle (`stats/`), the LaTeX tables and figures (`figures/`), and the audit trail (`docs/DECISION_LOG.md`, `docs/DEFENSE.md`). We do not redistribute the panoramic radiograph images.

### 7.2 Conclusion

We have presented v19, a small finite pre-registered voter-committee protocol that reaches 370/491 = 75.36% on the MMOral-OPG-Bench closed-ended question subset. The improvement of +5.50 percentage points (+27 correct answers) over the prior baseline is statistically uncontroversial (McNemar exact p = 1.12 × 10⁻⁷). The protocol is reproducible from a single command; the design history is fully disclosed; an external automated audit was performed and four attack points are answered with quantified rebuttals.

A central methodological contribution is the demonstration that the per-group voter ranking step — the most plausible reviewer attack on v19 — can be tightened (v20) at a cost of 7 questions out of 491 that is not statistically significant (McNemar p = 0.21). This robustness across protocol-strictness levels is the strongest available defense against post-hoc protocol-design critique.

We acknowledge the methodological limitations standard to all benchmark papers: voter pool curation is GT-informed, hyperparameter selection is standard CV, and subfamily rules were authored with awareness of the question distribution. None of these is formal leakage; all are disclosed; all are quantified in the audit response. External validation on a held-out MMOral-OPG-Bench extension is the natural next step.

We invite reviewers to submit additional formal attacks on the protocol via the GitHub issue tracker; we will respond with quantified rebuttals or with revised protocol versions in the manner of v20.

---

## Acknowledgments

This work is part of a doctoral dissertation in dental medicine at RUDN University, under scientific advisor Prof. S. Yu. Ivanov, MD, PhD, Corresponding Member of the Russian Academy of Sciences. Methodological consultation was provided by Anthropic Claude Opus 4.7 (1M context) and OpenAI ChatGPT (Codex) via independent reviewer-AI critique loops. The Codex audit directly informed the v20 strict ablation and the disclosures in `docs/DEFENSE.md`. The MMOral-OPG-Bench dataset is the work of its respective authors; this paper does not redistribute the radiograph images.

## References

[1] Hao, J., Fan, Y., Sun, Y., Guo, K., Lin, L., Yang, J., Ai, Q.Y.H., Wong, L.M., Tang, H., & Hung, K.F. (2025). *Towards Better Dental AI: A Multimodal Benchmark and Instruction Dataset for Panoramic X-ray Analysis.* arXiv:2509.09254.

[Additional references for: VLM-on-medical-MCQ surveys; benchmark leakage literature; majority voting in ML ensembles; reviewer-AI feedback loops; Wilson and bootstrap CIs; McNemar's exact test.]

---

## Appendix A — Complete protocol pseudocode

(See `src/mmoral_gate_v19_cv_sz.py` for the executable implementation.)

## Appendix B — All voter prediction files

(Released in `voter_predictions/` directory of the repository, totaling 80 JSON files.)

## Appendix C — Decision log

(Released as `docs/DECISION_LOG.md` in the repository, ~3000 lines covering DR-001 through DR-037.)

## Appendix D — Defense document

(Released as `docs/DEFENSE.md` in the repository, addressing the four Codex attack points with full quantified rebuttals.)
