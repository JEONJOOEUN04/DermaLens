#!/usr/bin/env python
"""
성분 안전 플래그 채우기 스크립트 (공식 고시 기반)

출처:
- EU 화장품 규정 (EC) No 1223/2009 부속서 III — 알레르기 유발 착향제 26종
- 대한민국 식약처 「화장품 안전기준 등에 관한 규정」 사용제한 원료

각 성분의 한글/영문명을 DB와 매칭해 allergy_flag / irritant_flag 설정.

사용법:
    python scripts/seed_ingredient_flags.py
    python scripts/seed_ingredient_flags.py --reset  (플래그 전체 초기화 후 재설정)
"""

import argparse
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "config"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.db.models import Q
from products.models import Ingredient


# EU 알레르기 유발 착향제 26종 (allergy_flag)
# (한글명 후보, 영문명 후보) — 부분 일치로 매칭
EU_ALLERGENS = [
    (["아밀신남알"], ["Amyl Cinnamal"]),
    (["아밀신나밀알코올"], ["Amylcinnamyl Alcohol"]),
    (["벤질알코올"], ["Benzyl Alcohol"]),
    (["벤질신남에이트", "벤질신나메이트"], ["Benzyl Cinnamate"]),
    (["벤질벤조에이트"], ["Benzyl Benzoate"]),
    (["벤질살리실레이트", "벤질살리시레이트"], ["Benzyl Salicylate"]),
    (["신남알", "신나밀알데하이드"], ["Cinnamal"]),
    (["신나밀알코올"], ["Cinnamyl Alcohol"]),
    (["시트랄"], ["Citral"]),
    (["시트로넬올"], ["Citronellol"]),
    (["쿠마린"], ["Coumarin"]),
    (["유제놀"], ["Eugenol"]),
    (["파네솔"], ["Farnesol"]),
    (["제라니올"], ["Geraniol"]),
    (["헥실신남알"], ["Hexyl Cinnamal"]),
    (["하이드록시시트로넬알"], ["Hydroxycitronellal"]),
    (["하이드록시이소헥실", "리랄"], ["Hydroxyisohexyl 3-Cyclohexene Carboxaldehyde", "Lyral"]),
    (["이소유제놀"], ["Isoeugenol"]),
    (["아이소메틸이오논", "이소메틸이오논"], ["Isomethyl Ionone", "Methyl 2-Octynoate"]),
    (["리모넨"], ["Limonene"]),
    (["리날룰"], ["Linalool"]),
    (["메틸2옥티노에이트", "메칠2옥티노에이트"], ["Methyl 2-Octynoate"]),
    (["참나무이끼추출물", "오크모스"], ["Evernia Prunastri", "Oakmoss"]),
    (["나무이끼추출물", "트리모스"], ["Evernia Furfuracea", "Treemoss"]),
    (["부틸페닐메틸프로피오날", "릴리알"], ["Butylphenyl Methylpropional", "Lilial"]),
    (["아니스알코올", "아니스에이트알코올"], ["Anise Alcohol", "Anisyl Alcohol"]),
]

# 식약처 사용제한/주의 원료 중 화장품에 등장 가능한 것 (irritant_flag)
KFDA_RESTRICTED = [
    (["메칠이소치아졸리논", "메틸이소치아졸리논"], ["Methylisothiazolinone"]),
    (["메칠클로로이소치아졸리논", "메틸클로로이소치아졸리논"], ["Methylchloroisothiazolinone"]),
    (["페녹시에탄올", "페녹시에칠알코올"], ["Phenoxyethanol"]),
    (["메칠파라벤", "메틸파라벤"], ["Methylparaben"]),
    (["에칠파라벤", "에틸파라벤"], ["Ethylparaben"]),
    (["프로필파라벤"], ["Propylparaben"]),
    (["부틸파라벤"], ["Butylparaben"]),
    (["이미다졸리디닐우레아"], ["Imidazolidinyl Urea"]),
    (["디아졸리디닐우레아", "다이아졸리디닐우레아"], ["Diazolidinyl Urea"]),
    (["디엠디엠하이단토인", "디엠디엠하이단토인"], ["DMDM Hydantoin"]),
    (["트리클로산", "트라이클로산"], ["Triclosan"]),
    (["벤조페논-3", "벤조페논3", "옥시벤존"], ["Benzophenone-3", "Oxybenzone"]),
    (["소듐라우릴설페이트"], ["Sodium Lauryl Sulfate"]),
    (["알부틴"], ["Arbutin"]),
    (["살리실릭애씨드", "살리실릭산"], ["Salicylic Acid"]),
]


def match_and_flag(name_kr_list, name_en_list, flag_field):
    """이름 후보로 성분 찾아 플래그 설정. 매칭된 성분명 리스트 반환."""
    q = Q()
    for kr in name_kr_list:
        q |= Q(ingredient_name_kr__icontains=kr)
    for en in name_en_list:
        q |= Q(ingredient_name_en__icontains=en)

    matched = Ingredient.objects.filter(q)
    names = []
    for ing in matched:
        setattr(ing, flag_field, True)
        ing.save(update_fields=[flag_field])
        names.append(ing.ingredient_name_kr)
    return names


def reset_flags():
    Ingredient.objects.update(allergy_flag=False, irritant_flag=False)
    print("기존 allergy_flag / irritant_flag 전체 초기화 완료")


def run():
    print("=== EU 알레르기 유발 착향제 26종 (allergy_flag) ===")
    allergy_total = 0
    for kr_list, en_list in EU_ALLERGENS:
        names = match_and_flag(kr_list, en_list, "allergy_flag")
        allergy_total += len(names)
        status = ", ".join(names) if names else "(DB에 없음)"
        print(f"  {kr_list[0]:20s} → {status}")

    print(f"\n=== 식약처 사용제한 원료 (irritant_flag) ===")
    irritant_total = 0
    for kr_list, en_list in KFDA_RESTRICTED:
        names = match_and_flag(kr_list, en_list, "irritant_flag")
        irritant_total += len(names)
        status = ", ".join(names) if names else "(DB에 없음)"
        print(f"  {kr_list[0]:20s} → {status}")

    print(f"\n=== 완료 ===")
    print(f"allergy_flag 설정: {allergy_total}개")
    print(f"irritant_flag 설정: {irritant_total}개")


def main():
    parser = argparse.ArgumentParser(description="성분 안전 플래그 채우기")
    parser.add_argument("--reset", action="store_true", help="기존 플래그 초기화 후 재설정")
    args = parser.parse_args()

    if args.reset:
        reset_flags()
    run()


if __name__ == "__main__":
    main()
