#!/usr/bin/env python
"""
성분 플래그(위험도/자극/알레르기 등) 업데이트 스크립트

모드 1 — 내장 데이터 (즉시 실행):
    python scripts/seed_flags.py

모드 2 — EWG CSV 파일 사용:
    python scripts/seed_flags.py --ewg-csv path/to/ewg_ingredients.csv
    (EWG 다운로드: https://www.ewg.org/skindeep/ → Full Ingredient List)

업데이트 컬럼:
    Ingredient.risk_level, allergy_flag, irritant_flag,
    acne_caution_flag, moisturizing_flag, soothing_flag
"""

import argparse
import csv
import os
import sys
import logging

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "config"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.db import transaction
from products.models import Ingredient, IngredientAlias

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ── 내장 성분 플래그 데이터 ────────────────────────────────────────────────────
# INCI명 기준. 매칭은 IngredientAlias(alias_type=INCI) 또는 ingredient_name_en으로 시도.

ALLERGY_INGREDIENTS = [
    "Fragrance", "Parfum",
    "Linalool", "Limonene", "Citronellol", "Geraniol", "Eugenol",
    "Cinnamal", "Cinnamyl Alcohol", "Isoeugenol", "Amyl Cinnamal",
    "Benzyl Alcohol", "Benzyl Salicylate", "Benzyl Benzoate",
    "Hydroxycitronellal", "Coumarin", "Farnesol", "Butylphenyl Methylpropional",
    "Methylisothiazolinone", "Methylchloroisothiazolinone",
    "Formaldehyde", "Quaternium-15", "DMDM Hydantoin", "Imidazolidinyl Urea",
    "Diazolidinyl Urea", "Bronopol",
    "Propolis Extract", "Bee Venom",
    "Lanolin", "Lanolin Alcohol",
]

IRRITANT_INGREDIENTS = [
    "Alcohol Denat.", "SD Alcohol", "Alcohol",
    "Sodium Lauryl Sulfate", "Sodium Laureth Sulfate", "Ammonium Lauryl Sulfate",
    "Fragrance", "Parfum",
    "Menthol", "Peppermint Oil", "Camphor", "Eucalyptus Oil",
    "Witch Hazel", "Hamamelis Virginiana Extract",
    "Retinol", "Retinyl Palmitate", "Retinoic Acid",
    "Glycolic Acid", "Salicylic Acid", "Lactic Acid", "Citric Acid",
    "Methylisothiazolinone", "Methylchloroisothiazolinone",
    "Hydrogen Peroxide",
    "Sodium Hydroxide", "Potassium Hydroxide",
    "Benzoyl Peroxide",
]

ACNE_CAUTION_INGREDIENTS = [
    "Isopropyl Myristate", "Isopropyl Palmitate", "Isopropyl Isostearate",
    "Butyl Stearate", "Isostearyl Neopentanoate",
    "Sodium Lauryl Sulfate",
    "Coconut Oil", "Cocos Nucifera Oil",
    "Cocoa Butter", "Theobroma Cacao Seed Butter",
    "Wheat Germ Oil", "Triticum Vulgare Germ Oil",
    "Acetylated Lanolin", "Acetylated Lanolin Alcohol",
    "D&C Red", "D&C Red 9", "D&C Red 17", "D&C Red 21", "D&C Red 36",
    "Algae Extract",
]

MOISTURIZING_INGREDIENTS = [
    "Hyaluronic Acid", "Sodium Hyaluronate",
    "Glycerin", "Glycerol",
    "Niacinamide",
    "Panthenol", "Dexpanthenol",
    "Allantoin",
    "Squalane", "Squalene",
    "Ceramide NP", "Ceramide AP", "Ceramide EOP", "Ceramide NS", "Ceramide AS",
    "Betaine",
    "Sorbitol",
    "Urea",
    "Trehalose",
    "Sodium PCA",
    "Propylene Glycol",
    "Butylene Glycol",
    "Pentylene Glycol",
    "Polyglutamic Acid",
    "Beta-Glucan",
    "Collagen", "Hydrolyzed Collagen",
    "Elastin", "Hydrolyzed Elastin",
]

SOOTHING_INGREDIENTS = [
    "Centella Asiatica Extract", "Centella Asiatica",
    "Madecassoside", "Asiaticoside", "Madecassic Acid", "Asiatic Acid",
    "Aloe Barbadensis Leaf Extract", "Aloe Vera",
    "Bisabolol", "Alpha-Bisabolol",
    "Allantoin",
    "Chamomilla Recutita Flower Extract", "Chamomile Extract",
    "Camellia Sinensis Leaf Extract", "Green Tea Extract",
    "Panthenol",
    "Licorice Root Extract", "Glycyrrhiza Glabra Root Extract",
    "Dipotassium Glycyrrhizate",
    "Portulaca Oleracea Extract",
    "Artemisia Extract", "Artemisia Princeps Leaf Extract",
    "Houttuynia Cordata Extract",
    "Calendula Officinalis Flower Extract",
    "Lavandula Angustifolia Extract",
    "Niacinamide",
    "Saccharide Isomerate",
]


def _find_ingredient(inci_name: str):
    """INCI명으로 Ingredient 조회 — alias 우선, 없으면 ingredient_name_en."""
    alias = IngredientAlias.objects.filter(
        alias_name__iexact=inci_name,
    ).select_related("ingredient").first()
    if alias:
        return alias.ingredient
    return Ingredient.objects.filter(ingredient_name_en__iexact=inci_name).first()


def _update_flag(ing, field, value=True):
    if getattr(ing, field) != value:
        setattr(ing, field, value)
        return True
    return False


# ── 모드 1: 내장 데이터 적용 ──────────────────────────────────────────────────

def seed_builtin():
    log.info("=== 내장 성분 플래그 적재 시작 ===")
    updated = 0
    not_found = 0

    flag_map = [
        (ALLERGY_INGREDIENTS,    "allergy_flag"),
        (IRRITANT_INGREDIENTS,   "irritant_flag"),
        (ACNE_CAUTION_INGREDIENTS, "acne_caution_flag"),
        (MOISTURIZING_INGREDIENTS, "moisturizing_flag"),
        (SOOTHING_INGREDIENTS,   "soothing_flag"),
    ]

    seen = {}  # ingredient_id → Ingredient (변경 누적)

    for name_list, flag_field in flag_map:
        for inci_name in name_list:
            ing = _find_ingredient(inci_name)
            if not ing:
                not_found += 1
                continue
            if ing.ingredient_id not in seen:
                seen[ing.ingredient_id] = ing
            changed = _update_flag(seen[ing.ingredient_id], flag_field)

    with transaction.atomic():
        for ing in seen.values():
            ing.save()
            updated += 1

    log.info("내장 데이터 완료 — 업데이트: %d, 미매칭(누적): %d", updated, not_found)
    return updated


# ── 모드 2: EWG CSV 적용 ──────────────────────────────────────────────────────

EWG_SCORE_THRESHOLD = {
    "high":     (7, 10),
    "moderate": (4, 6),
    "low":      (1, 3),
}


def _ewg_score_to_risk(score: float) -> int | None:
    if score >= 7:
        return 8
    if score >= 4:
        return 5
    if score >= 1:
        return 2
    return None


def _parse_score(raw: str) -> float:
    raw = raw.strip()
    if "-" in raw:
        parts = raw.split("-")
        try:
            return max(float(p.strip()) for p in parts)
        except ValueError:
            return 0.0
    try:
        return float(raw)
    except ValueError:
        return 0.0


def seed_ewg_csv(csv_path: str):
    log.info("=== EWG CSV 적재 시작: %s ===", csv_path)
    updated = 0
    not_found = 0

    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        log.info("CSV 컬럼: %s", reader.fieldnames)

        batch = {}

        for row in reader:
            inci_name = (
                row.get("ingredient") or row.get("ingredient_name") or
                row.get("INCI_NAME") or row.get("name") or ""
            ).strip()

            score_raw = (
                row.get("score") or row.get("ewg_score") or
                row.get("EWG_SCORE") or row.get("hazard_score") or "0"
            ).strip()

            concern_str = (
                row.get("concerns") or row.get("concern_list") or
                row.get("data_concerns") or ""
            ).lower()

            if not inci_name:
                continue

            score = _parse_score(score_raw)

            ing = _find_ingredient(inci_name)
            if not ing:
                not_found += 1
                continue

            if ing.ingredient_id not in batch:
                batch[ing.ingredient_id] = ing

            target = batch[ing.ingredient_id]

            risk = _ewg_score_to_risk(score)
            if risk and (target.risk_level is None or target.risk_level < risk):
                target.risk_level = risk

            if score >= 3:
                _update_flag(target, "irritant_flag")
            if "allerg" in concern_str:
                _update_flag(target, "allergy_flag")
            if "acne" in concern_str or "comedogen" in concern_str:
                _update_flag(target, "acne_caution_flag")
            if "moistur" in concern_str or "hydrat" in concern_str:
                _update_flag(target, "moisturizing_flag")
            if "sooth" in concern_str or "calm" in concern_str:
                _update_flag(target, "soothing_flag")

        with transaction.atomic():
            for ing in batch.values():
                ing.save()
                updated += 1

    log.info("EWG CSV 완료 — 업데이트: %d, 미매칭: %d", updated, not_found)
    return updated


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="성분 플래그 업데이트")
    parser.add_argument(
        "--ewg-csv",
        default=None,
        help="EWG CSV 파일 경로 (없으면 내장 데이터로 실행)",
    )
    args = parser.parse_args()

    if args.ewg_csv:
        if not os.path.exists(args.ewg_csv):
            log.error("파일을 찾을 수 없습니다: %s", args.ewg_csv)
            sys.exit(1)
        seed_ewg_csv(args.ewg_csv)
    else:
        log.info("EWG CSV 미지정 — 내장 성분 데이터로 실행합니다.")
        seed_builtin()

    log.info("=== 플래그 업데이트 완료 ===")


if __name__ == "__main__":
    main()
