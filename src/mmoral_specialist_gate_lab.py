#!/usr/bin/env python3
"""Honest gated specialist policies over a fixed backbone selector.

This lab evaluates simple leakage-free gates that choose between:
- a global backbone selector prediction file
- targeted specialist partial voters (for example g28s / g29s)

The gate itself is leave-one-out over questions: when deciding whether to use a
specialist on question K, per-task reliability is estimated from all questions
except K.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from mmoral_oracle_lite import BASE_DIR, ground_truth, load_dataset, load_prediction_file, score_predictions
from mmoral_visual_contract_voter import infer_contract


def laplace(correct: int, total: int, alpha: float = 2.0) -> float:
    return (correct + alpha) / (total + 2 * alpha)


def task_type_map(df) -> dict[str, str]:
    return {str(row["index"]): infer_contract(row).task_type for _, row in df.iterrows()}


def build_task_counters(
    predictors: dict[str, dict[str, str]],
    gt: dict[str, str],
    task_by_key: dict[str, str],
) -> tuple[dict[str, Counter[str]], dict[str, Counter[str]]]:
    total_by_name: dict[str, Counter[str]] = {}
    correct_by_name: dict[str, Counter[str]] = {}
    for name, preds in predictors.items():
        total = Counter()
        correct = Counter()
        for key, ans in preds.items():
            task = task_by_key[key]
            total[task] += 1
            if ans == gt[key]:
                correct[task] += 1
        total_by_name[name] = total
        correct_by_name[name] = correct
    return total_by_name, correct_by_name


def loo_task_score(
    name: str,
    key: str,
    predictors: dict[str, dict[str, str]],
    gt: dict[str, str],
    task_by_key: dict[str, str],
    total_by_name: dict[str, Counter[str]],
    correct_by_name: dict[str, Counter[str]],
) -> tuple[float, int]:
    task = task_by_key[key]
    total = total_by_name[name][task]
    correct = correct_by_name[name][task]
    preds = predictors[name]
    if key in preds and task_by_key[key] == task:
        total -= 1
        if preds[key] == gt[key]:
            correct -= 1
    return laplace(correct, total), total


def save_predictions(path: Path, preds: dict[str, str]) -> None:
    path.write_text(json.dumps(preds, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def eval_fill_g28s(
    keys: list[str],
    gt: dict[str, str],
    task_by_key: dict[str, str],
    backbone: dict[str, str],
    g28s: dict[str, str],
) -> tuple[dict[str, str], Counter[str]]:
    preds = dict(backbone)
    chosen = Counter({"backbone": len(keys)})
    for key in keys:
        if task_by_key[key] == "filling_restoration" and key in g28s:
            preds[key] = g28s[key]
            chosen["backbone"] -= 1
            chosen["g28s"] += 1
    return preds, chosen


def eval_task_best(
    keys: list[str],
    gt: dict[str, str],
    task_by_key: dict[str, str],
    predictors: dict[str, dict[str, str]],
    backbone_name: str,
    min_support: int = 6,
) -> tuple[dict[str, str], Counter[str]]:
    total_by_name, correct_by_name = build_task_counters(predictors, gt, task_by_key)
    preds: dict[str, str] = {}
    chosen = Counter()

    for key in keys:
        available = [name for name, answers in predictors.items() if key in answers]
        best_name = backbone_name
        best_score = -1.0
        for name in available:
            score, support = loo_task_score(
                name,
                key,
                predictors,
                gt,
                task_by_key,
                total_by_name,
                correct_by_name,
            )
            # Backbone is always allowed; specialists need enough same-task support.
            if name != backbone_name and support < min_support:
                continue
            if score > best_score or (score == best_score and name == backbone_name):
                best_score = score
                best_name = name
        preds[key] = predictors[best_name][key]
        chosen[best_name] += 1
    return preds, chosen


def eval_task_margin(
    keys: list[str],
    gt: dict[str, str],
    task_by_key: dict[str, str],
    predictors: dict[str, dict[str, str]],
    backbone_name: str,
    min_support: int = 6,
    margin: float = 0.0,
) -> tuple[dict[str, str], Counter[str]]:
    total_by_name, correct_by_name = build_task_counters(predictors, gt, task_by_key)
    preds: dict[str, str] = {}
    chosen = Counter()

    for key in keys:
        backbone_score, _ = loo_task_score(
            backbone_name,
            key,
            predictors,
            gt,
            task_by_key,
            total_by_name,
            correct_by_name,
        )
        best_name = backbone_name
        best_score = backbone_score
        for name, answers in predictors.items():
            if name == backbone_name or key not in answers:
                continue
            score, support = loo_task_score(
                name,
                key,
                predictors,
                gt,
                task_by_key,
                total_by_name,
                correct_by_name,
            )
            if support < min_support:
                continue
            if score >= backbone_score + margin and score > best_score:
                best_score = score
                best_name = name
        preds[key] = predictors[best_name][key]
        chosen[best_name] += 1
    return preds, chosen


def evaluate(args: argparse.Namespace) -> None:
    df = load_dataset()
    gt = ground_truth(df)
    keys = list(gt)
    task_by_key = task_type_map(df)

    backbone_path = Path(args.backbone_file)
    if not backbone_path.is_absolute():
        backbone_path = BASE_DIR / backbone_path

    g28s_path = Path(args.g28s_file)
    if not g28s_path.is_absolute():
        g28s_path = BASE_DIR / g28s_path

    g29s_path = Path(args.g29s_file)
    if not g29s_path.is_absolute():
        g29s_path = BASE_DIR / g29s_path

    backbone = load_prediction_file(backbone_path)
    g28s = load_prediction_file(g28s_path)
    g29s = load_prediction_file(g29s_path)
    predictors = {
        "backbone": backbone,
        "g28s": g28s,
        "g29s": g29s,
    }

    out_dir = BASE_DIR / "mmoral_specialist_gate"
    out_dir.mkdir(exist_ok=True)

    backbone_correct, backbone_acc = score_predictions(backbone, gt, keys)
    print(f"Dataset: {len(keys)} questions")
    print(f"Backbone: {backbone_correct}/{len(keys)} = {backbone_acc*100:.2f}%")

    results: dict[str, dict[str, Any]] = {}

    fill_preds, fill_chosen = eval_fill_g28s(keys, gt, task_by_key, backbone, g28s)
    fill_correct, fill_acc = score_predictions(fill_preds, gt, keys)
    save_predictions(out_dir / "mmoral_results_gate_fill_g28s.json", fill_preds)
    results["gate_fill_g28s"] = {
        "correct": fill_correct,
        "accuracy": fill_acc,
        "chosen": dict(fill_chosen),
    }
    print(f"gate_fill_g28s: {fill_correct}/{len(keys)} = {fill_acc*100:.2f}%")

    task_best_preds, task_best_chosen = eval_task_best(
        keys,
        gt,
        task_by_key,
        predictors,
        backbone_name="backbone",
        min_support=args.min_support,
    )
    task_best_correct, task_best_acc = score_predictions(task_best_preds, gt, keys)
    save_predictions(out_dir / "mmoral_results_gate_task_best.json", task_best_preds)
    results["gate_task_best"] = {
        "correct": task_best_correct,
        "accuracy": task_best_acc,
        "chosen": dict(task_best_chosen),
    }
    print(f"gate_task_best: {task_best_correct}/{len(keys)} = {task_best_acc*100:.2f}%")

    for margin in args.margins:
        preds, chosen = eval_task_margin(
            keys,
            gt,
            task_by_key,
            predictors,
            backbone_name="backbone",
            min_support=args.min_support,
            margin=margin,
        )
        correct, acc = score_predictions(preds, gt, keys)
        label = f"gate_task_margin_{margin:g}"
        safe = label.replace(".", "_")
        save_predictions(out_dir / f"mmoral_results_{safe}.json", preds)
        results[label] = {
            "correct": correct,
            "accuracy": acc,
            "chosen": dict(chosen),
        }
        print(f"{label}: {correct}/{len(keys)} = {acc*100:.2f}%")

    best = max(results, key=lambda key: results[key]["correct"]) if results else None
    report = {
        "dataset": len(keys),
        "backbone_file": str(backbone_path),
        "g28s_file": str(g28s_path),
        "g29s_file": str(g29s_path),
        "backbone_correct": backbone_correct,
        "backbone_accuracy": backbone_acc,
        "best": best,
        "results": dict(sorted(results.items(), key=lambda kv: (-kv[1]["correct"], kv[0]))),
    }
    report_path = out_dir / args.report_name
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nWrote {report_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backbone-file",
        default="mmoral_selector_lab/mmoral_results_selector_logreg_0.05_g29s.json",
    )
    parser.add_argument(
        "--g28s-file",
        default="mmoral_results_g28s_visual_contract_specialist.json",
    )
    parser.add_argument(
        "--g29s-file",
        default="mmoral_results_g29s_self_curriculum_specialist.json",
    )
    parser.add_argument("--min-support", type=int, default=6)
    parser.add_argument("--margins", nargs="+", type=float, default=[0.0, 0.02, 0.05, 0.10])
    parser.add_argument("--report-name", default="specialist_gate_report.json")
    return parser


def main() -> None:
    evaluate(build_parser().parse_args())


if __name__ == "__main__":
    main()
