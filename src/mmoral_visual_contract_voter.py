#!/usr/bin/env python3
"""CLI-only MMOral voter using question-derived visual contracts.

This runner keeps the honest evaluation regime:
- no GT in prompts
- no API
- Codex CLI only

The question and options are converted into a "visual contract":
- what finding must be verified
- which radiographic signs count as support
- which confounders should be rejected
- what crop geometry best fits the task

Each option is then checked against task-adapted ROIs plus the original OPG.
"""

from __future__ import annotations

import argparse
import base64
import json
import random
import re
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageOps


CODE_DIR = Path(__file__).resolve().parent
BUNDLE_DIR = CODE_DIR.parent if CODE_DIR.name == "code" else CODE_DIR
BASE_DIR = BUNDLE_DIR
COMPACT_DATASET = BASE_DIR / "data" / "mmoral_compact_questions.json"
DATASET = BASE_DIR / "mmoral_bench" / "data" / "MMOral-OPG-Bench-Closed-Ended.tsv"
IMAGES_DIR = Path("/tmp/mmoral_images")
RAW_BASE = BASE_DIR / "mmoral_visual_contract_raw"
LETTERS = "ABCD"

UPPER_SEQUENCE = [*(f"1{i}" for i in range(8, 0, -1)), *(f"2{i}" for i in range(1, 9))]
LOWER_SEQUENCE = [*(f"4{i}" for i in range(8, 0, -1)), *(f"3{i}" for i in range(1, 9))]
VALID_PERMANENT_FDI = {f"{q}{p}" for q in range(1, 5) for p in range(1, 9)}
VALID_PRIMARY_FDI = {f"{q}{p}" for q in range(5, 9) for p in range(1, 6)}
OPTION_COLORS = {
    "A": (214, 39, 40),
    "B": (31, 119, 180),
    "C": (255, 127, 14),
    "D": (148, 103, 189),
}


@dataclass
class ContractSpec:
    task_type: str
    focus_tag: str
    crop_mode: str
    target_finding: str
    positive_signs: list[str]
    confounders: list[str]
    comparison_rule: str
    option_rule: str
    adult_assumption: bool


def result_path(variant: str) -> Path:
    return BASE_DIR / f"mmoral_results_{variant}.json"


def load_json(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def load_dataset() -> pd.DataFrame:
    if COMPACT_DATASET.exists():
        return pd.read_json(COMPACT_DATASET)
    return pd.read_csv(DATASET, sep="\t")


def image_stem(value: Any) -> str:
    text = str(value).strip()
    if re.fullmatch(r"\d+\.0", text):
        return text[:-2]
    return text


def resolve_image_path(row: pd.Series) -> Path:
    raw_id = str(row["image_id"]).strip()
    candidates = [IMAGES_DIR / f"{raw_id}.jpg", IMAGES_DIR / f"{image_stem(raw_id)}.jpg"]
    for path in candidates:
        if path.exists():
            return path

    cache_dir = RAW_BASE / "_image_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{image_stem(raw_id)}.jpg"
    if not cache_path.exists():
        img_b64 = str(row.get("image", "") or "")
        if not img_b64:
            raise FileNotFoundError(f"No extracted image and no base64 image payload for image_id={raw_id}")
        cache_path.write_bytes(base64.b64decode(img_b64))
    return cache_path


def parse_answer(raw: str) -> str | None:
    match = re.search(r"ANSWER:\s*([ABCD])\b", raw, flags=re.IGNORECASE)
    if match:
        return match.group(1).upper()
    text = raw.strip().upper()
    if text in LETTERS:
        return text
    matches = re.findall(r"\b([ABCD])\b", text)
    return matches[-1] if matches else None


def option_text(row: pd.Series, letter: str) -> str:
    return str(row[f"option{LETTERS.index(letter) + 1}"])


def all_numeric_codes(text: str) -> list[str]:
    raw = re.findall(r"#\s*(\d{2})\b|\b(\d{2})\b", text)
    out: list[str] = []
    for a, b in raw:
        code = a or b
        if code and code not in out:
            out.append(code)
    return out


def option_fdi_codes(row: pd.Series, letter: str) -> list[str]:
    text = option_text(row, letter)
    codes = [code for code in all_numeric_codes(text) if code in VALID_PERMANENT_FDI]
    if not codes:
        question = str(row["question"]).lower()
        if "milk" in question or "primary" in question or "deciduous" in question:
            codes = [code for code in all_numeric_codes(text) if code in VALID_PRIMARY_FDI]
    return codes


def try_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    names = ["Arial Bold.ttf", "Helvetica.ttc"] if bold else ["Arial.ttf", "Helvetica.ttc"]
    for name in names:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_text_box(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int] = (0, 0, 0),
    box_fill: tuple[int, int, int] = (255, 255, 255),
    outline: tuple[int, int, int] = (0, 0, 0),
) -> None:
    x, y = xy
    bbox = draw.textbbox((x, y), text, font=font)
    pad = 3
    draw.rectangle(
        [bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad],
        fill=box_fill,
        outline=outline,
    )
    draw.text((x, y), text, fill=fill, font=font)


def target_codes(row: pd.Series) -> dict[str, list[str]]:
    return {letter: option_fdi_codes(row, letter) for letter in LETTERS}


def question_mentions_primary(row: pd.Series) -> bool:
    text = " ".join(
        [str(row.get("question", "") or "")]
        + [option_text(row, letter) for letter in LETTERS]
    ).lower()
    return bool(re.search(r"milk|primary|deciduous|mixed dentition|mixed-dentition|child|pediatric", text))


def infer_contract(row: pd.Series) -> ContractSpec:
    q = str(row.get("question", "") or "").lower()
    all_text = " ".join([q] + [option_text(row, letter).lower() for letter in LETTERS])
    adult_assumption = not question_mentions_primary(row)

    if "implant restoration" in q or ("implant" in q and "restoration" in q):
        return ContractSpec(
            task_type="implant_restoration",
            focus_tag="IMPLANT",
            crop_mode="implant_full",
            target_finding="an implant fixture with a restorative suprastructure",
            positive_signs=[
                "threaded or screw-like radiopaque implant body in bone",
                "coronal crown or abutment attached above the fixture",
                "appearance clearly different from a natural root",
            ],
            confounders=[
                "natural crowned tooth without implant fixture",
                "bridge pontic over an empty site",
                "metal artifact not centered in an alveolar ridge",
            ],
            comparison_rule="Confirm both the fixture in bone and the restoration above it.",
            option_rule="If an option lists multiple teeth, all listed teeth must satisfy the implant-restoration claim.",
            adult_assumption=adult_assumption,
        )

    if "without any signs of root canal treatment" in q:
        return ContractSpec(
            task_type="crown_without_rct",
            focus_tag="CROWN+NO_RCT",
            crop_mode="full_tooth",
            target_finding="a crown restoration with no visible root canal filling",
            positive_signs=[
                "full-coverage coronal restoration or cap",
                "root canals not filled with dense radiopaque endodontic material",
                "root retains a natural canal appearance or no canal filling is visible",
            ],
            confounders=[
                "root canal filling inside the root",
                "post-and-core masquerading as crown-only",
                "large filling that is not a full crown",
            ],
            comparison_rule="Verify crown first, then actively reject any option that shows gutta-percha or post-like canal filling.",
            option_rule="For multi-tooth options, every listed tooth must have crown present and root-canal evidence absent.",
            adult_assumption=adult_assumption,
        )

    if ("crown" in q or "crown restoration" in q) and ("root canal" in q or "endodont" in q or "rct" in q):
        return ContractSpec(
            task_type="crown_plus_rct",
            focus_tag="CROWN+RCT",
            crop_mode="full_tooth",
            target_finding="a crowned tooth that also has root canal treatment",
            positive_signs=[
                "full-coverage crown or coronal cap",
                "radiopaque endodontic filling inside the root canal",
                "both coronal and radicular treatment features are visible together",
            ],
            confounders=[
                "crown only with untreated canal",
                "root canal treatment without crown",
                "post/core alone without a true crown",
            ],
            comparison_rule="Choose only options where both crown and endodontic evidence coexist on the same tooth.",
            option_rule="For multi-tooth options, every listed tooth must show both crown and root-canal evidence.",
            adult_assumption=adult_assumption,
        )

    if "root canal" in q or "endodont" in q or "rct" in q:
        return ContractSpec(
            task_type="root_canal_treatment",
            focus_tag="RCT",
            crop_mode="full_tooth",
            target_finding="root canal treatment",
            positive_signs=[
                "dense radiopaque material within the root canal space",
                "canal filling extending along most of the root length",
                "possible associated post or crown but canal filling is the key sign",
            ],
            confounders=[
                "natural empty canal mistaken for filling",
                "only coronal restoration with no filled canal",
                "overlapping dense anatomy outside the canal",
            ],
            comparison_rule="Trace the canal from chamber toward the apex and confirm that the density lies inside the canal path.",
            option_rule="For multi-tooth options, each listed tooth must show canal filling.",
            adult_assumption=adult_assumption,
        )

    if "crown" in q:
        return ContractSpec(
            task_type="crown_restoration",
            focus_tag="CROWN",
            crop_mode="coronal",
            target_finding="a crown restoration",
            positive_signs=[
                "full-coverage coronal cap replacing the natural crown contour",
                "uniform radiopaque shell over the crown",
                "outline unlike a small intracoronal filling",
            ],
            confounders=[
                "simple filling or inlay instead of a full crown",
                "implant crown when the question asks for a natural tooth",
                "overlapping structures creating pseudo-cap appearance",
            ],
            comparison_rule="Compare coronal outline against neighboring teeth to distinguish full coverage from a localized filling.",
            option_rule="For multi-tooth options, all listed teeth must show crown restoration.",
            adult_assumption=adult_assumption,
        )

    if "filling" in q or "restoration" in q:
        return ContractSpec(
            task_type="filling_restoration",
            focus_tag="FILLING",
            crop_mode="coronal",
            target_finding="an intracoronal filling/restoration",
            positive_signs=[
                "localized radiopaque material within part of the crown",
                "shape confined to an occlusal, proximal, or coronal defect",
                "not full coverage of the entire crown",
            ],
            confounders=[
                "natural enamel brightness",
                "full crown restoration",
                "metal overlap from adjacent structures",
            ],
            comparison_rule="Look for a bounded radiopaque patch inside the crown, not a full-shell cap.",
            option_rule="For multi-tooth options, all listed teeth must have visible fillings unless the wording says otherwise.",
            adult_assumption=adult_assumption,
        )

    if "impacted" in q or "unerupted" in q:
        return ContractSpec(
            task_type="impaction",
            focus_tag="IMPACTION",
            crop_mode="posterior_context",
            target_finding="an impacted or unerupted tooth",
            positive_signs=[
                "tooth not erupted into normal occlusal position",
                "abnormal angulation, often mesio-angular or horizontal for third molars",
                "posterior tooth partly or fully within bone or ramus/tuberosity region",
            ],
            confounders=[
                "erupted but tilted tooth",
                "missing tooth space with no impacted tooth visible",
                "ghost or overlap in the posterior corner",
            ],
            comparison_rule="Use posterior context: compare the candidate tooth to the second molar, ramus, and occlusal plane.",
            option_rule="If one option is 'none detected', choose it only when no candidate tooth shows convincing impaction.",
            adult_assumption=adult_assumption,
        )

    if "caries" in q or "carious" in q or "deep caries" in q:
        return ContractSpec(
            task_type="caries",
            focus_tag="CARIES",
            crop_mode="coronal",
            target_finding="caries",
            positive_signs=[
                "localized radiolucent defect in enamel or dentin",
                "loss of normal crown contour or dark undermined area",
                "darker than surrounding tooth substance in a plausible caries location",
            ],
            confounders=[
                "cervical burnout",
                "open contact or overlap artifact",
                "restoration margins mistaken for decay",
            ],
            comparison_rule="Compare brightness and contour against adjacent teeth; true caries should look focal and pathologic, not symmetric artifact.",
            option_rule="For multi-tooth options, every listed tooth must show convincing caries.",
            adult_assumption=adult_assumption,
        )

    if "granuloma" in q:
        return ContractSpec(
            task_type="periapical_granuloma",
            focus_tag="APEX",
            crop_mode="apical",
            target_finding="a periapical granuloma or small chronic apical lesion",
            positive_signs=[
                "small radiolucency centered at the root apex",
                "loss or interruption of apical lamina dura",
                "chronic apical darkening with a relatively localized contour",
            ],
            confounders=[
                "mental foramen near premolar apices",
                "maxillary sinus recess above upper posterior roots",
                "normal anatomic radiolucency not centered on the apex",
            ],
            comparison_rule="Anchor on the apex itself. The lesion should be apical, not just nearby.",
            option_rule="For multi-tooth options, every listed tooth must show apical pathology.",
            adult_assumption=adult_assumption,
        )

    if "abscess" in q:
        return ContractSpec(
            task_type="periapical_abscess",
            focus_tag="APEX",
            crop_mode="apical",
            target_finding="a periapical abscess or strong apical inflammatory lesion",
            positive_signs=[
                "radiolucency centered around a root apex",
                "apical lamina dura loss or PDL widening",
                "dark apical focus with inflammatory appearance",
            ],
            confounders=[
                "mental foramen",
                "sinus floor or sinus recess superimposition",
                "mandibular canal or other normal radiolucent anatomy near the root",
            ],
            comparison_rule="Prioritize true apical disease: the dark area must be rooted at the apex, not merely adjacent anatomy.",
            option_rule="For multi-tooth options, every listed tooth must show apical pathology.",
            adult_assumption=adult_assumption,
        )

    if "periapical lesion" in q or "periapical" in q or "lesion" in q:
        return ContractSpec(
            task_type="periapical_lesion",
            focus_tag="APEX",
            crop_mode="apical",
            target_finding="a periapical lesion",
            positive_signs=[
                "radiolucency at the root apex",
                "apical lamina dura disruption or widened PDL",
                "dark periapical change stronger than surrounding bone pattern",
            ],
            confounders=[
                "mental foramen",
                "sinus-related radiolucency",
                "normal marrow space not centered at the apex",
            ],
            comparison_rule="Distinguish a lesion from nearby anatomy by centering the judgment on the exact apex.",
            option_rule="For multi-tooth options, every listed tooth must show apical pathology.",
            adult_assumption=adult_assumption,
        )

    return ContractSpec(
        task_type="generic_tooth_identification",
        focus_tag="FULL_TOOTH",
        crop_mode="full_tooth",
        target_finding="the tooth or teeth most compatible with the question stem",
        positive_signs=[
            "visible evidence matching the asked finding",
            "correct tooth position and laterality",
            "better match than neighboring options",
        ],
        confounders=[
            "mirror-rule mistakes",
            "relying on option wording without image support",
            "nearby anatomy mistaken for target finding",
        ],
        comparison_rule="Compare every option directly against its neighbors and choose the strongest image-supported match.",
        option_rule="For multi-tooth options, the listed teeth should all fit the claim unless the wording allows partial match.",
        adult_assumption=adult_assumption,
    )


def rough_tooth_center(code: str, width: int, height: int) -> tuple[float, float]:
    quadrant = int(code[0])
    pos = int(code[1])
    image_left_side = quadrant in {1, 4}
    upper = quadrant in {1, 2}
    sign = -1 if image_left_side else 1

    offsets = {
        1: 0.030,
        2: 0.060,
        3: 0.100,
        4: 0.150,
        5: 0.200,
        6: 0.255,
        7: 0.315,
        8: 0.370,
    }
    x = width * (0.5 + sign * offsets[pos])
    if upper:
        y = height * (0.420 if pos <= 3 else 0.455 if pos <= 5 else 0.485)
    else:
        y = height * (0.575 if pos <= 3 else 0.600 if pos <= 5 else 0.620)
    return x, y


def contract_bbox(code: str, contract: ContractSpec, width: int, height: int) -> tuple[int, int, int, int]:
    quadrant = int(code[0])
    pos = int(code[1])
    upper = quadrant in {1, 2}
    image_left_side = quadrant in {1, 4}
    sign = -1 if image_left_side else 1
    crown_dir = 1 if upper else -1
    root_dir = -1 if upper else 1

    x, y = rough_tooth_center(code, width, height)
    if pos <= 3:
        box_w, box_h = width * 0.110, height * 0.300
    elif pos <= 5:
        box_w, box_h = width * 0.135, height * 0.315
    elif pos <= 7:
        box_w, box_h = width * 0.185, height * 0.345
    else:
        box_w, box_h = width * 0.225, height * 0.380

    mode = contract.crop_mode
    if mode == "coronal":
        box_w *= 1.08
        box_h *= 0.80
        y += crown_dir * box_h * 0.18
    elif mode == "apical":
        box_w *= 1.10
        box_h *= 1.15
        y += root_dir * box_h * 0.18
    elif mode == "posterior_context":
        box_w *= 1.35
        box_h *= 1.25
        x += sign * box_w * 0.10
        if pos == 8:
            x += sign * box_w * 0.06
    elif mode == "implant_full":
        box_w *= 1.15
        box_h *= 1.10
    else:
        box_w *= 1.05
        box_h *= 1.06

    x1 = max(0, int(x - box_w / 2))
    y1 = max(0, int(y - box_h / 2))
    x2 = min(width, int(x + box_w / 2))
    y2 = min(height, int(y + box_h / 2))
    return x1, y1, x2, y2


def union_bbox(
    boxes: list[tuple[int, int, int, int]],
    width: int,
    height: int,
    contract: ContractSpec,
) -> tuple[int, int, int, int]:
    x1 = min(b[0] for b in boxes)
    y1 = min(b[1] for b in boxes)
    x2 = max(b[2] for b in boxes)
    y2 = max(b[3] for b in boxes)
    pad_x = int((x2 - x1) * 0.10)
    pad_y = int((y2 - y1) * 0.10)
    if contract.crop_mode == "posterior_context":
        pad_x = int((x2 - x1) * 0.16)
        pad_y = int((y2 - y1) * 0.14)
    elif contract.crop_mode == "apical":
        pad_y = int((y2 - y1) * 0.14)
    return max(0, x1 - pad_x), max(0, y1 - pad_y), min(width, x2 + pad_x), min(height, y2 + pad_y)


def make_sidecar_map(
    out_dir: Path,
    option_codes: dict[str, list[str]],
    size: tuple[int, int] = (1200, 520),
) -> tuple[Path, dict[str, str]]:
    highlighted = {code: letter for letter, codes in option_codes.items() for code in codes}
    width, height = size
    canvas = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(canvas)
    font = try_font(18)
    bold = try_font(22, bold=True)
    small = try_font(15)

    upper_y = int(height * 0.35)
    lower_y = int(height * 0.68)
    left_x = int(width * 0.08)
    right_x = int(width * 0.92)
    step = (right_x - left_x) / 15
    fdi_order: dict[str, str] = {}

    draw_text_box(draw, (18, 18), "FDI sidecar map (locator only)", bold)
    draw_text_box(draw, (18, 58), "Image left = patient right. Diagnose from the real OPG, not this map.", small)
    draw.line([(left_x, upper_y), (right_x, upper_y)], fill=(0, 140, 190), width=5)
    draw.line([(left_x, lower_y), (right_x, lower_y)], fill=(215, 165, 0), width=5)
    draw.text((left_x - 62, upper_y - 13), "UPPER", fill=(0, 90, 130), font=font)
    draw.text((left_x - 62, lower_y - 13), "LOWER", fill=(150, 110, 0), font=font)

    for arch_name, seq, y in [("U", UPPER_SEQUENCE, upper_y), ("L", LOWER_SEQUENCE, lower_y)]:
        for i, code in enumerate(seq):
            x = int(left_x + step * i)
            fdi_order[code] = f"{arch_name}{i + 1:02d}"
            letter = highlighted.get(code)
            if letter:
                color = OPTION_COLORS[letter]
                r = 25
                draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255), outline=color, width=6)
                draw.text((x - 18, y - 12), letter, fill=color, font=bold)
                draw_text_box(draw, (x - 26, y + 34), code, font, fill=color, outline=color)
            else:
                r = 14
                draw.ellipse([x - r, y - r, x + r, y + r], fill=(245, 245, 245), outline=(90, 90, 90), width=2)
                draw.text((x - 13, y + 20), code, fill=(0, 0, 0), font=small)

    sidecar_path = out_dir / "sidecar_fdi_map.jpg"
    canvas.save(sidecar_path, quality=92)
    return sidecar_path, fdi_order


def labelled_contract_crop(
    image: Image.Image,
    bbox: tuple[int, int, int, int],
    header: str,
    color: tuple[int, int, int],
    size: tuple[int, int] = (640, 410),
) -> Image.Image:
    header_h = 50
    canvas = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(canvas)
    font = try_font(18, bold=True)
    draw.rectangle([0, 0, size[0] - 1, size[1] - 1], outline=color, width=4)
    draw.rectangle([0, 0, size[0], header_h], fill="white")
    draw.text((12, 13), header, fill=color, font=font)

    crop = image.crop(bbox).convert("RGB")
    fitted = ImageOps.contain(crop, (size[0] - 16, size[1] - header_h - 16))
    x = (size[0] - fitted.width) // 2
    y = header_h + (size[1] - header_h - fitted.height) // 2
    canvas.paste(fitted, (x, y))
    return canvas


def make_contract_roi_sheet(
    row: pd.Series,
    out_dir: Path,
    contract: ContractSpec,
    option_codes: dict[str, list[str]],
    fdi_order: dict[str, str],
) -> Path:
    image_path = resolve_image_path(row)
    image = Image.open(image_path).convert("RGB")
    width, height = image.size

    cells = []
    for letter in LETTERS:
        text = option_text(row, letter)
        codes = option_codes[letter]
        color = OPTION_COLORS[letter]
        if codes:
            boxes = [contract_bbox(code, contract, width, height) for code in codes]
            bbox = union_bbox(boxes, width, height, contract)
            target = ", ".join(f"{code}@{fdi_order.get(code, '?')}" for code in codes)
            header = f"{letter}) [{contract.focus_tag}] {target}"
            cells.append(labelled_contract_crop(image, bbox, header, color))
        else:
            blank = Image.new("RGB", (640, 410), "white")
            draw = ImageDraw.Draw(blank)
            font = try_font(18, bold=True)
            draw.rectangle([0, 0, 639, 409], outline=color, width=4)
            draw.text((12, 13), f"{letter}) [{contract.focus_tag}] no ROI", fill=color, font=font)
            draw.text((24, 172), text[:60], fill=(0, 0, 0), font=try_font(18))
            draw.text((24, 214), "Use full OPG and option text context.", fill=(0, 0, 0), font=try_font(16))
            cells.append(blank)

    sheet = Image.new("RGB", (1280, 820), "white")
    positions = [(0, 0), (640, 0), (0, 410), (640, 410)]
    for cell, pos in zip(cells, positions):
        sheet.paste(cell, pos)
    sheet_path = out_dir / "contract_option_rois.jpg"
    sheet.save(sheet_path, quality=92)
    return sheet_path


def option_notes(row: pd.Series, option_codes: dict[str, list[str]], contract: ContractSpec) -> dict[str, str]:
    notes: dict[str, str] = {}
    for letter in LETTERS:
        text = option_text(row, letter)
        nums = all_numeric_codes(text)
        invalid = [code for code in nums if code not in VALID_PERMANENT_FDI and code not in VALID_PRIMARY_FDI]
        codes = option_codes[letter]
        lower = text.lower()
        parts: list[str] = []
        if codes:
            parts.append("mapped ROI")
        elif invalid:
            parts.append(f"unmappable code(s): {', '.join(invalid)}")
        elif "none" in lower:
            parts.append("none-detected option")
        elif lower.strip() == "nan":
            parts.append("option text missing")
        else:
            parts.append("no explicit permanent FDI code")
        if len(codes) > 1:
            parts.append("multi-tooth option")
        if contract.adult_assumption and any(code in VALID_PRIMARY_FDI for code in nums):
            parts.append("primary-code in adult context")
        notes[letter] = "; ".join(parts)
    return notes


def save_contract_artifact(
    out_dir: Path,
    row: pd.Series,
    contract: ContractSpec,
    option_codes: dict[str, list[str]],
    notes: dict[str, str],
) -> None:
    payload = {
        "index": int(row["index"]),
        "question": str(row["question"]),
        "category": str(row["category"]),
        "contract": asdict(contract),
        "options": {
            letter: {
                "text": option_text(row, letter),
                "valid_fdi_codes": option_codes[letter],
                "note": notes[letter],
            }
            for letter in LETTERS
        },
    }
    write_json(out_dir / "visual_contract.json", payload)


def make_images(
    row: pd.Series,
    out_dir: Path,
    contract: ContractSpec,
) -> tuple[list[Path], dict[str, list[str]], dict[str, str], dict[str, str]]:
    image_path = resolve_image_path(row)
    image = Image.open(image_path).convert("RGB")
    out_dir.mkdir(parents=True, exist_ok=True)

    overview_path = out_dir / "overview.jpg"
    ImageOps.contain(image, (1400, 760)).save(overview_path, quality=92)

    option_codes = target_codes(row)
    sidecar_path, fdi_order = make_sidecar_map(out_dir, option_codes)
    roi_sheet_path = make_contract_roi_sheet(row, out_dir, contract, option_codes, fdi_order)
    notes = option_notes(row, option_codes, contract)
    save_contract_artifact(out_dir, row, contract, option_codes, notes)
    return [overview_path, sidecar_path, roi_sheet_path], option_codes, fdi_order, notes


def build_prompt(
    row: pd.Series,
    contract: ContractSpec,
    option_codes: dict[str, list[str]],
    fdi_order: dict[str, str],
    notes: dict[str, str],
) -> str:
    option_lines = "\n".join(f"{letter}) {option_text(row, letter)}" for letter in LETTERS)
    target_rows = []
    for letter, codes in option_codes.items():
        if codes:
            targets = ", ".join(f"{code} at {fdi_order.get(code, '?')}" for code in codes)
        else:
            targets = notes[letter]
        target_rows.append(f"- {letter}: {targets}")
    target_lines = "\n".join(target_rows)
    positive = "\n".join(f"- {item}" for item in contract.positive_signs)
    confounders = "\n".join(f"- {item}" for item in contract.confounders)

    assumption = ""
    if contract.adult_assumption:
        assumption = (
            "\nAdult permanent dentition assumption: unless the image clearly shows pediatric or mixed dentition, "
            "prefer permanent FDI interpretation and treat unmappable codes cautiously."
        )

    return f"""You are a blind dental panoramic radiograph MCQ voter.

Your job is not to answer from language alone. Convert the question into a visual contract, then verify that contract against the image.

Attached images:
1. The original full OPG overview with no diagnostic overlay.
2. A separate FDI sidecar map. It is only a locator.
3. A 2x2 contact sheet of task-adapted option ROIs. Headers are outside the diagnostic pixels.

Orientation rule: image left = patient's right; image right = patient's left.{assumption}

Question category: {row['category']}
Question: {row['question']}

Options:
{option_lines}

Visual contract:
- Task type: {contract.task_type}
- Focus: {contract.focus_tag}
- Target finding: {contract.target_finding}
- Comparison rule: {contract.comparison_rule}
- Option rule: {contract.option_rule}

Positive signs to seek:
{positive}

Confounders to reject:
{confounders}

Option ROI targets / notes:
{target_lines}

Decision discipline:
1. Inspect every option ROI and also cross-check on the full OPG.
2. Write one judgment per option: yes / no / uncertain.
3. For multi-tooth options, require all listed teeth to satisfy the claim unless the wording clearly says otherwise.
4. If an option is "none detected", choose it only if no explicit candidate tooth convincingly matches.
5. Prefer direct image evidence over the sidecar map or option wording.

Return exactly in this format:
A: yes/no/uncertain - short reason
B: yes/no/uncertain - short reason
C: yes/no/uncertain - short reason
D: yes/no/uncertain - short reason
ANSWER: <one capital letter>
"""


def call_codex(
    prompt: str,
    image_paths: list[Path],
    model: str,
    effort: str,
    timeout: int,
    raw_path: Path,
) -> tuple[str | None, str]:
    last_message_path = raw_path.with_suffix(".last.txt")
    cmd = [
        "codex",
        "exec",
        "-m",
        model,
        "-c",
        f'model_reasoning_effort="{effort}"',
        "--ephemeral",
        "-C",
        "/tmp",
        "--skip-git-repo-check",
        "--ignore-rules",
        "--sandbox",
        "read-only",
        "--color",
        "never",
        "-o",
        str(last_message_path),
    ]
    for path in image_paths:
        cmd.extend(["--image", str(path)])
    cmd.append("-")

    proc = subprocess.run(
        cmd,
        input=prompt,
        cwd="/tmp",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    raw = last_message_path.read_text(encoding="utf-8").strip() if last_message_path.exists() else proc.stdout.strip()
    raw_path.write_text("\n".join(part for part in [raw, proc.stderr.strip()] if part), encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"codex exec failed: {(raw + proc.stderr)[:500]}")
    return parse_answer(raw), raw


def choose_indices(df: pd.DataFrame, args: argparse.Namespace, existing: dict[str, str]) -> list[int]:
    if args.indices:
        candidates = [int(x.strip()) for x in args.indices.split(",") if x.strip()]
    elif args.indices_file:
        raw = Path(args.indices_file).read_text(encoding="utf-8")
        raw_stripped = raw.strip()
        if raw_stripped.startswith("{") or raw_stripped.startswith("["):
            parsed = json.loads(raw_stripped)
            if isinstance(parsed, dict):
                items = parsed.get("indices", [])
            else:
                items = parsed
            candidates = [int(x) for x in items]
        else:
            candidates = [int(x.strip()) for x in re.split(r"[\s,]+", raw) if x.strip()]
    elif args.sample_overlap:
        overlap = load_json(Path(args.sample_overlap), {})
        candidates = sorted(int(k) for k in overlap)
    else:
        candidates = sorted(int(x) for x in df["index"])

    if args.shuffle:
        rng = random.Random(args.seed)
        rng.shuffle(candidates)

    if args.eligible_only:
        eligible = set()
        for _, row in df.iterrows():
            per_option = [option_fdi_codes(row, letter) for letter in LETTERS]
            if sum(1 for codes in per_option if codes) >= 2:
                eligible.add(int(row["index"]))
        candidates = [idx for idx in candidates if idx in eligible]

    if args.limit:
        candidates = candidates[: args.limit]

    if args.resume:
        candidates = [idx for idx in candidates if str(idx) not in existing]
    return candidates


def cmd_run(args: argparse.Namespace) -> None:
    df = load_dataset()
    out_path = result_path(args.variant)
    results = load_json(out_path, {})
    indices = choose_indices(df, args, results)
    raw_root = RAW_BASE / args.variant
    raw_root.mkdir(parents=True, exist_ok=True)

    print(f"Variant: {args.variant}", flush=True)
    print(f"Questions selected: {len(indices)}", flush=True)
    print(f"Output: {out_path}", flush=True)

    failures = 0
    for n, idx in enumerate(indices, start=1):
        row = df[df["index"] == idx].iloc[0]
        contract = infer_contract(row)
        q_dir = raw_root / f"Q{idx}"
        image_paths, option_codes, fdi_order, notes = make_images(row, q_dir, contract)
        prompt = build_prompt(row, contract, option_codes, fdi_order, notes)
        started = time.time()
        ans = None
        last_exc: Exception | None = None
        for attempt in range(1, args.retries + 2):
            try:
                ans, _raw = call_codex(
                    prompt,
                    image_paths,
                    args.model,
                    args.effort,
                    args.timeout,
                    q_dir / "response.txt",
                )
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                if attempt <= args.retries:
                    print(
                        f"[{n}/{len(indices)}] Q{idx}: retry {attempt}/{args.retries} after failure ({exc})",
                        flush=True,
                    )
                    time.sleep(args.retry_delay)
        if last_exc is not None:
            failures += 1
            print(f"[{n}/{len(indices)}] Q{idx}: failed ({last_exc})", flush=True)
            if failures >= args.max_failures:
                raise SystemExit(f"Stopping after {failures} failures.") from last_exc
            continue

        elapsed = time.time() - started
        if ans:
            results[str(idx)] = ans
            write_json(out_path, results)
            print(f"[{n}/{len(indices)}] Q{idx}: {ans} ({elapsed:.1f}s) [{contract.task_type}]", flush=True)
        else:
            failures += 1
            print(f"[{n}/{len(indices)}] Q{idx}: parse-failed ({elapsed:.1f}s)", flush=True)
            if failures >= args.max_failures:
                raise SystemExit(f"Stopping after {failures} parse failures.")


def cmd_compare(args: argparse.Namespace) -> None:
    df = load_dataset()
    target = load_json(result_path(args.variant), {})
    baseline = load_json(Path(args.compare_to), {}) if args.compare_to else {}
    keys = sorted(int(k) for k in target)
    if baseline:
        keys = [k for k in keys if str(k) in baseline]
    if args.limit:
        keys = keys[: args.limit]

    target_correct = 0
    baseline_correct = 0
    both = 0
    target_only = 0
    baseline_only = 0
    for idx in keys:
        row = df[df["index"] == idx].iloc[0]
        gt = str(row["answer"]).strip().upper()
        t_ok = target.get(str(idx), "").strip().upper() == gt
        b_ok = baseline.get(str(idx), "").strip().upper() == gt if baseline else False
        target_correct += int(t_ok)
        baseline_correct += int(b_ok)
        both += int(t_ok and b_ok)
        target_only += int(t_ok and not b_ok)
        baseline_only += int(b_ok and not t_ok)

    total = len(keys)
    print(f"Compared questions: {total}")
    if total:
        print(f"{args.variant}: {target_correct}/{total} = {target_correct / total * 100:.2f}%")
        if baseline:
            print(f"{Path(args.compare_to).stem}: {baseline_correct}/{total} = {baseline_correct / total * 100:.2f}%")
            print(f"Both correct: {both}")
            print(f"{args.variant} only correct: {target_only}")
            print(f"Baseline only correct: {baseline_only}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run")
    run.add_argument("--variant", default="g28_visual_contract_codex")
    run.add_argument("--indices")
    run.add_argument("--indices-file")
    run.add_argument("--sample-overlap")
    run.add_argument("--limit", type=int, default=0)
    run.add_argument("--resume", action="store_true")
    run.add_argument("--shuffle", action="store_true")
    run.add_argument("--seed", type=int, default=42)
    run.add_argument("--eligible-only", action="store_true")
    run.add_argument("--model", default="gpt-5.4")
    run.add_argument("--effort", default="low", choices=["low", "medium", "high", "xhigh"])
    run.add_argument("--timeout", type=int, default=180)
    run.add_argument("--max-failures", type=int, default=3)
    run.add_argument("--retries", type=int, default=2)
    run.add_argument("--retry-delay", type=float, default=8.0)
    run.set_defaults(func=cmd_run)

    compare = sub.add_parser("compare")
    compare.add_argument("--variant", default="g28_visual_contract_codex")
    compare.add_argument("--compare-to")
    compare.add_argument("--limit", type=int, default=0)
    compare.set_defaults(func=cmd_compare)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
