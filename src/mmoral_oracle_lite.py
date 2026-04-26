#!/usr/bin/env python3
"""Oracle-lite tooling for MMOral-OPG closed-ended runs.

This script does not call any model API. It works with the accumulated
mmoral_results*.json files and prepares a bounded second-pass verification
queue for the cases where the current committee is uncertain.

Typical workflow:
    python3 mmoral_oracle_lite.py score
    python3 mmoral_oracle_lite.py prepare --top 150
    # Fill mmoral_verifier_answers_template.json with blind verifier answers.
    python3 mmoral_oracle_lite.py merge --answers mmoral_verifier_answers_template.json
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression


CODE_DIR = Path(__file__).resolve().parent
# BASE_DIR is the repo root (parent of `code/` or `src/`). Falls back to CODE_DIR.
BUNDLE_DIR = CODE_DIR.parent if CODE_DIR.name in ("code", "src") else CODE_DIR
BASE_DIR = BUNDLE_DIR
COMPACT_DATASET = BASE_DIR / "data" / "mmoral_compact_questions.json"
DATASET = BASE_DIR / "mmoral_bench" / "data" / "MMOral-OPG-Bench-Closed-Ended.tsv"
IMAGES_DIR = Path("/tmp/mmoral_images")
LETTERS = ("A", "B", "C", "D")
DEFAULT_EXCLUDE = {"leaked"}
DEFAULT_EXCLUDE_ENSEMBLES = {"ensemble", "ensemble13"}
PRUNED_SUBSET = (
    "g5_judge",
    "g6c_minimal",
    "g6a_grid",
    "g11e_asv",
    "g10b_bilateral",
    "g9b_literal",
    "g5_tmr",
    "structured",
    "g13b_nav",
)


def result_name(path: Path) -> str:
    if path.name == "mmoral_results.json":
        return "vanilla"
    name = path.stem.removeprefix("mmoral_results_")
    return name or "vanilla"


def normalize_answer(value: Any) -> str | None:
    if isinstance(value, dict):
        value = value.get("answer", "")
    ans = str(value).strip().upper()[:1]
    return ans if ans in LETTERS else None


def load_dataset() -> pd.DataFrame:
    if COMPACT_DATASET.exists():
        df = pd.read_json(COMPACT_DATASET)
    else:
        df = pd.read_csv(DATASET, sep="\t")
    df["index"] = df["index"].astype(str)
    return df


def load_voters(
    min_answers: int = 450,
    include_ensembles: bool = False,
    include_partial: bool = False,
    extra_files: list[str] | None = None,
) -> dict[str, dict[str, str]]:
    voters: dict[str, dict[str, str]] = {}
    excluded = set(DEFAULT_EXCLUDE)
    if not include_ensembles:
        excluded |= DEFAULT_EXCLUDE_ENSEMBLES

    search_roots = [BASE_DIR, BASE_DIR / "voter_predictions"]
    for root in search_roots:
        paths = sorted(root.glob("mmoral_results*.json")) if root.exists() else []
        for path in paths:
            name = result_name(path)
            if name in excluded:
                continue
            try:
                raw = json.loads(path.read_text())
            except Exception:
                continue
            answers = {}
            for key, value in raw.items():
                ans = normalize_answer(value)
                if ans:
                    answers[str(key)] = ans
            if include_partial or len(answers) >= min_answers:
                voters[name] = answers

    for file_name in extra_files or []:
        path = Path(file_name)
        if not path.is_absolute():
            path = BASE_DIR / path
        if not path.exists():
            continue
        name = result_name(path)
        try:
            raw = json.loads(path.read_text())
        except Exception:
            continue
        answers = {}
        for key, value in raw.items():
            ans = normalize_answer(value)
            if ans:
                answers[str(key)] = ans
        if answers:
            voters[name] = answers
    return voters


def ground_truth(df: pd.DataFrame) -> dict[str, str]:
    return {str(row["index"]): str(row["answer"]).strip().upper() for _, row in df.iterrows()}


def row_by_index(df: pd.DataFrame) -> dict[str, pd.Series]:
    return {str(row["index"]): row for _, row in df.iterrows()}


def primary_category(row: pd.Series) -> str:
    return str(row["category"]).split(",")[0].strip()


def score_predictions(preds: dict[str, str], gt: dict[str, str], keys: list[str]) -> tuple[int, float]:
    correct = sum(1 for key in keys if preds.get(key) == gt[key])
    return correct, correct / len(keys) if keys else 0.0


def voter_score(voter: dict[str, str], gt: dict[str, str], keys: list[str]) -> tuple[int, float]:
    correct = sum(1 for key in keys if voter.get(key) == gt[key])
    return correct, correct / len(keys) if keys else 0.0


def vote_counter(voters: dict[str, dict[str, str]], key: str) -> Counter[str]:
    return Counter(voter.get(key) for voter in voters.values() if voter.get(key) in LETTERS)


def majority_predictions(voters: dict[str, dict[str, str]], keys: list[str]) -> dict[str, str]:
    preds = {}
    for key in keys:
        counts = vote_counter(voters, key)
        preds[key] = counts.most_common(1)[0][0] if counts else "A"
    return preds


def loo_department_predictions(
    df: pd.DataFrame,
    voters: dict[str, dict[str, str]],
    gt: dict[str, str],
    top_k: int = 3,
    use_primary_category: bool = True,
) -> dict[str, str]:
    """Per-question LOO: rank voters on all other questions in the same category."""
    rows = row_by_index(df)
    keys = list(gt)
    names = list(voters)

    def cat_for(key: str) -> str:
        row = rows[key]
        if use_primary_category:
            return primary_category(row)
        return str(row["category"]).strip()

    cat_by_key = {key: cat_for(key) for key in keys}
    cat_totals = Counter(cat_by_key.values())
    correct_by_voter_cat: dict[str, Counter[str]] = defaultdict(Counter)
    for key in keys:
        cat = cat_by_key[key]
        for name in names:
            if voters[name].get(key) == gt[key]:
                correct_by_voter_cat[name][cat] += 1

    preds = {}
    for key in keys:
        cat = cat_by_key[key]
        ranked = []
        train_total = max(cat_totals[cat] - 1, 1)
        for name in names:
            train_correct = correct_by_voter_cat[name][cat]
            if voters[name].get(key) == gt[key]:
                train_correct -= 1
            ranked.append((train_correct / train_total, name))
        ranked.sort(reverse=True)
        top_names = [name for _, name in ranked[:top_k]]
        counts = Counter(voters[name].get(key) for name in top_names if voters[name].get(key) in LETTERS)
        preds[key] = counts.most_common(1)[0][0] if counts else "A"
    return preds


def load_prediction_file(path: Path) -> dict[str, str]:
    if not path.is_absolute():
        candidates = [
            BASE_DIR / path,
            BASE_DIR / "predictions" / path.name,
            BASE_DIR / "voter_predictions" / path.name,
        ]
        path = next((candidate for candidate in candidates if candidate.exists()), BASE_DIR / path)
    raw = json.loads(path.read_text())
    preds = {}
    for key, value in raw.items():
        ans = normalize_answer(value)
        if ans:
            preds[str(key)] = ans
    return preds


def pruned_logreg_predictions(
    df: pd.DataFrame,
    voters: dict[str, dict[str, str]],
    gt: dict[str, str],
    c_value: float = 0.02,
) -> dict[str, str]:
    """Known 9-voter pruned stacker, evaluated as honest LOO."""
    missing = [name for name in PRUNED_SUBSET if name not in voters]
    if missing:
        raise SystemExit(f"Missing pruned-subset voters: {', '.join(missing)}")

    rows = row_by_index(df)
    keys = [key for key in gt if key in voters["g5_judge"]]
    all_cats = sorted(
        {
            cat.strip()
            for key in keys
            for cat in str(rows[key]["category"]).split(",")
        }
    )

    feature_rows = []
    for key in keys:
        feat = []
        for name in PRUNED_SUBSET:
            ans = voters[name].get(key, "")
            feat.extend(1 if ans == letter else 0 for letter in LETTERS)
        key_cats = [cat.strip() for cat in str(rows[key]["category"]).split(",")]
        feat.extend(1 if cat in key_cats else 0 for cat in all_cats)
        feature_rows.append(feat)

    x = np.asarray(feature_rows, dtype=np.float32)
    y = np.asarray([gt[key] for key in keys])
    preds: dict[str, str] = {}
    for i, key in enumerate(keys):
        mask = np.ones(len(keys), dtype=bool)
        mask[i] = False
        clf = LogisticRegression(max_iter=2000, C=c_value)
        clf.fit(x[mask], y[mask])
        preds[key] = str(clf.predict(x[i : i + 1])[0])
    return preds


def build_baseline(
    df: pd.DataFrame,
    voters: dict[str, dict[str, str]],
    gt: dict[str, str],
    mode: str,
    top_k: int,
    file_path: str | None,
    stacker_c: float = 0.02,
) -> tuple[str, dict[str, str]]:
    keys = list(gt)
    if mode == "majority":
        return "majority", majority_predictions(voters, keys)
    if mode == "dept-loo":
        label = f"dept-loo-top{top_k}"
        return label, loo_department_predictions(df, voters, gt, top_k=top_k)
    if mode == "pruned-logreg":
        label = f"pruned-logreg-C{stacker_c:g}"
        return label, pruned_logreg_predictions(df, voters, gt, c_value=stacker_c)
    if mode == "file":
        if not file_path:
            raise SystemExit("--file is required when --baseline file is used")
        path = Path(file_path)
        if not path.is_absolute():
            path = BASE_DIR / path
        return f"file:{path.name}", load_prediction_file(path)
    raise SystemExit(f"Unknown baseline: {mode}")


def oracle_possible(voters: dict[str, dict[str, str]], gt: dict[str, str], key: str) -> bool:
    return any(voter.get(key) == gt[key] for voter in voters.values())


def oracle_accuracy(voters: dict[str, dict[str, str]], gt: dict[str, str], keys: list[str]) -> tuple[int, float]:
    correct = sum(1 for key in keys if oracle_possible(voters, gt, key))
    return correct, correct / len(keys) if keys else 0.0


def uncertainty_score(
    voters: dict[str, dict[str, str]],
    key: str,
    baseline_answer: str | None,
) -> dict[str, Any]:
    counts = vote_counter(voters, key)
    total = sum(counts.values()) or 1
    ordered = counts.most_common()
    top_count = ordered[0][1] if ordered else 0
    second_count = ordered[1][1] if len(ordered) > 1 else 0
    entropy = -sum((count / total) * math.log(count / total, 2) for count in counts.values() if count)
    margin = (top_count - second_count) / total
    baseline_count = counts.get(baseline_answer or "", 0)

    # High entropy + low margin + weak support for the current baseline answer.
    score = entropy - margin + (1.0 - baseline_count / total)
    return {
        "score": score,
        "vote_counts": dict(counts),
        "top_vote": ordered[0][0] if ordered else None,
        "top_count": top_count,
        "second_count": second_count,
        "entropy": entropy,
        "margin": margin,
        "baseline_support": baseline_count / total,
    }


def ranked_review_keys(
    voters: dict[str, dict[str, str]],
    keys: list[str],
    baseline: dict[str, str],
) -> list[tuple[str, dict[str, Any]]]:
    scored = [(key, uncertainty_score(voters, key, baseline.get(key))) for key in keys]
    scored.sort(key=lambda item: item[1]["score"], reverse=True)
    return scored


def simulate_oracle_review(
    ranked: list[tuple[str, dict[str, Any]]],
    baseline: dict[str, str],
    voters: dict[str, dict[str, str]],
    gt: dict[str, str],
    top_values: list[int],
) -> list[dict[str, Any]]:
    keys = list(gt)
    base_correct, base_acc = score_predictions(baseline, gt, keys)
    possible = {key: oracle_possible(voters, gt, key) for key in keys}
    rows = []
    for top_n in top_values:
        reviewed = {key for key, _ in ranked[:top_n]}
        correct = 0
        for key in keys:
            if key in reviewed and possible[key]:
                correct += 1
            elif baseline.get(key) == gt[key]:
                correct += 1
        rows.append(
            {
                "reviewed": top_n,
                "correct": correct,
                "accuracy": correct / len(keys),
                "gain": correct - base_correct,
                "gain_pp": (correct / len(keys) - base_acc) * 100,
            }
        )
    return rows


def minimal_review_for_target(
    ranked: list[tuple[str, dict[str, Any]]],
    baseline: dict[str, str],
    voters: dict[str, dict[str, str]],
    gt: dict[str, str],
    target: float,
) -> dict[str, Any] | None:
    keys = list(gt)
    possible = {key: oracle_possible(voters, gt, key) for key in keys}
    for top_n in range(len(ranked) + 1):
        reviewed = {key for key, _ in ranked[:top_n]}
        correct = 0
        for key in keys:
            if key in reviewed and possible[key]:
                correct += 1
            elif baseline.get(key) == gt[key]:
                correct += 1
        acc = correct / len(keys)
        if acc >= target:
            return {"reviewed": top_n, "correct": correct, "accuracy": acc}
    return None


def write_review_queue(
    df: pd.DataFrame,
    ranked: list[tuple[str, dict[str, Any]]],
    baseline: dict[str, str],
    top_n: int,
    out_md: Path,
    out_template: Path,
) -> None:
    rows = row_by_index(df)
    selected = ranked[:top_n]

    lines = [
        "# MMOral Oracle-Lite Blind Verification Queue",
        "",
        "No ground truth is included in this file.",
        "Fill only the final answer letter for each question.",
        "",
    ]
    template = {}
    for rank, (key, meta) in enumerate(selected, start=1):
        row = rows[key]
        image_id = row.get("image_id", "")
        image_path = IMAGES_DIR / f"{image_id}.jpg"
        template[key] = ""
        lines.extend(
            [
                f"## {rank}. Q{key} [{row['category']}]",
                "",
                f"- Image: `{image_path}`",
                f"- Baseline: `{baseline.get(key, '?')}`",
                f"- Votes: `{json.dumps(meta['vote_counts'], ensure_ascii=False, sort_keys=True)}`",
                f"- Uncertainty score: `{meta['score']:.4f}`",
                "",
                f"Question: {row['question']}",
                "",
                f"A. {row['option1']}",
                f"B. {row['option2']}",
                f"C. {row['option3']}",
                f"D. {row['option4']}",
                "",
                "Verifier answer: `?`",
                "",
            ]
        )

    lines.extend(
        [
            "## Answer Template",
            "",
            "Use this JSON shape in the companion answers file:",
            "",
            "```json",
            json.dumps(template, ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )
    out_md.write_text("\n".join(lines), encoding="utf-8")
    out_template.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")


def command_score(args: argparse.Namespace) -> None:
    df = load_dataset()
    gt = ground_truth(df)
    keys = list(gt)
    voters = load_voters(
        min_answers=args.min_answers,
        include_ensembles=args.include_ensembles,
        include_partial=args.include_partial,
    )

    print(f"Dataset: {len(keys)} closed-ended questions")
    print(f"Voters: {len(voters)} (min_answers={args.min_answers})")
    print("")

    rows = []
    for name, voter in voters.items():
        correct, acc = voter_score(voter, gt, keys)
        rows.append((acc, correct, name, len(voter)))
    print("Top standalone voters:")
    for acc, correct, name, answered in sorted(rows, reverse=True)[:12]:
        print(f"  {name:28s} {correct:3d}/{len(keys)} = {acc*100:5.2f}%  answered={answered}")

    majority = majority_predictions(voters, keys)
    maj_correct, maj_acc = score_predictions(majority, gt, keys)
    oracle_correct, oracle_acc = oracle_accuracy(voters, gt, keys)
    print("")
    print(f"Majority:      {maj_correct}/{len(keys)} = {maj_acc*100:.2f}%")
    print(f"Oracle union:  {oracle_correct}/{len(keys)} = {oracle_acc*100:.2f}%")

    print("")
    print("LOO department baselines:")
    for top_k in args.top_k_values:
        preds = loo_department_predictions(df, voters, gt, top_k=top_k)
        correct, acc = score_predictions(preds, gt, keys)
        print(f"  dept-loo-top{top_k:<2d} {correct}/{len(keys)} = {acc*100:.2f}%")

    print("")
    print("Known pruned stacker baselines:")
    for c_value in args.stacker_c_values:
        preds = pruned_logreg_predictions(df, voters, gt, c_value=c_value)
        correct, acc = score_predictions(preds, gt, keys)
        print(f"  pruned-logreg-C{c_value:<5g} {correct}/{len(keys)} = {acc*100:.2f}%")


def command_prepare(args: argparse.Namespace) -> None:
    df = load_dataset()
    gt = ground_truth(df)
    keys = list(gt)
    voters = load_voters(
        min_answers=args.min_answers,
        include_ensembles=args.include_ensembles,
        include_partial=args.include_partial,
    )
    label, baseline = build_baseline(
        df, voters, gt, args.baseline, args.top_k, args.file, stacker_c=args.stacker_c
    )
    ranked = ranked_review_keys(voters, keys, baseline)
    base_correct, base_acc = score_predictions(baseline, gt, keys)
    oracle_correct, oracle_acc = oracle_accuracy(voters, gt, keys)
    simulations = simulate_oracle_review(
        ranked,
        baseline,
        voters,
        gt,
        top_values=args.sim_points,
    )
    target = minimal_review_for_target(ranked, baseline, voters, gt, args.target)

    out_md = Path(args.out_md)
    out_template = Path(args.out_answers)
    if not out_md.is_absolute():
        out_md = BASE_DIR / out_md
    if not out_template.is_absolute():
        out_template = BASE_DIR / out_template
    write_review_queue(df, ranked, baseline, args.top, out_md, out_template)

    report = {
        "baseline": label,
        "baseline_correct": base_correct,
        "baseline_accuracy": base_acc,
        "oracle_correct": oracle_correct,
        "oracle_accuracy": oracle_acc,
        "target_accuracy": args.target,
        "minimal_review_for_target_under_oracle_verifier": target,
        "simulated_oracle_review": simulations,
        "queue_md": str(out_md),
        "answers_template": str(out_template),
        "top_queue_size": args.top,
    }
    out_report = Path(args.out_report)
    if not out_report.is_absolute():
        out_report = BASE_DIR / out_report
    out_report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Baseline: {label} = {base_correct}/{len(keys)} = {base_acc*100:.2f}%")
    print(f"Oracle union: {oracle_correct}/{len(keys)} = {oracle_acc*100:.2f}%")
    if target:
        print(
            f"Target {args.target*100:.1f}% reached in simulation at "
            f"{target['reviewed']} reviewed questions "
            f"({target['correct']}/{len(keys)} = {target['accuracy']*100:.2f}%)."
        )
    else:
        print(f"Target {args.target*100:.1f}% is not reachable with current voter union.")
    print(f"Wrote: {out_md}")
    print(f"Wrote: {out_template}")
    print(f"Wrote: {out_report}")


def command_merge(args: argparse.Namespace) -> None:
    df = load_dataset()
    gt = ground_truth(df)
    keys = list(gt)
    voters = load_voters(
        min_answers=args.min_answers,
        include_ensembles=args.include_ensembles,
        include_partial=args.include_partial,
    )
    label, baseline = build_baseline(
        df, voters, gt, args.baseline, args.top_k, args.file, stacker_c=args.stacker_c
    )

    answers_path = Path(args.answers)
    if not answers_path.is_absolute():
        answers_path = BASE_DIR / answers_path
    verifier_raw = json.loads(answers_path.read_text())
    merged = dict(baseline)
    used = 0
    for key, value in verifier_raw.items():
        ans = normalize_answer(value)
        if ans:
            merged[str(key)] = ans
            used += 1

    correct, acc = score_predictions(merged, gt, keys)
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = BASE_DIR / out_path
    out_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Baseline: {label}")
    print(f"Verifier answers used: {used}")
    print(f"Merged score: {correct}/{len(keys)} = {acc*100:.2f}%")
    print(f"Wrote: {out_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-answers", type=int, default=450)
    parser.add_argument("--include-ensembles", action="store_true")
    parser.add_argument("--include-partial", action="store_true")

    sub = parser.add_subparsers(dest="command", required=True)

    score = sub.add_parser("score")
    score.add_argument("--top-k-values", type=int, nargs="+", default=[1, 3, 5, 7, 9])
    score.add_argument("--stacker-c-values", type=float, nargs="+", default=[0.005, 0.01, 0.02, 0.05])
    score.set_defaults(func=command_score)

    prepare = sub.add_parser("prepare")
    prepare.add_argument("--baseline", choices=["majority", "dept-loo", "pruned-logreg", "file"], default="pruned-logreg")
    prepare.add_argument("--top-k", type=int, default=1)
    prepare.add_argument("--stacker-c", type=float, default=0.02)
    prepare.add_argument("--file", help="Baseline result JSON when --baseline file is used")
    prepare.add_argument("--top", type=int, default=150)
    prepare.add_argument("--target", type=float, default=0.75)
    prepare.add_argument("--sim-points", type=int, nargs="+", default=[20, 40, 60, 80, 100, 120, 150, 180])
    prepare.add_argument("--out-md", default="mmoral_oracle_lite_review_queue.md")
    prepare.add_argument("--out-answers", default="mmoral_verifier_answers_template.json")
    prepare.add_argument("--out-report", default="mmoral_oracle_lite_report.json")
    prepare.set_defaults(func=command_prepare)

    merge = sub.add_parser("merge")
    merge.add_argument("--answers", required=True)
    merge.add_argument("--baseline", choices=["majority", "dept-loo", "pruned-logreg", "file"], default="pruned-logreg")
    merge.add_argument("--top-k", type=int, default=1)
    merge.add_argument("--stacker-c", type=float, default=0.02)
    merge.add_argument("--file", help="Baseline result JSON when --baseline file is used")
    merge.add_argument("--out", default="mmoral_results_oracle_lite_merged.json")
    merge.set_defaults(func=command_merge)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
