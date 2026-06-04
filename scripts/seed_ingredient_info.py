#!/usr/bin/env python
"""
핵심 성분 효능 설명(description) + 기능 매핑(IngredientFunction) 채우기.

화장품 업계에서 효능이 명확히 정립된 핵심 성분 위주로 작성.
성분명은 부분 일치(icontains)로 DB와 매칭.

FunctionMaster ID:
  1 보습  2 진정  3 미백  4 주름개선  5 피지조절
  6 각질케어  7 장벽강화  8 항산화  9 트러블케어  10 자외선차단

사용법:
    python scripts/seed_ingredient_info.py
    python scripts/seed_ingredient_info.py --reset  (효능/매핑 초기화 후 재설정)
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
from products.models import Ingredient, FunctionMaster, IngredientFunction


# (성분명 매칭 키워드, 기능ID 리스트, 한글 효능 설명)
INGREDIENT_INFO = [
    # ===== 보습 =====
    ("하이알루로닉애씨드", [1, 7], "강력한 수분 보유 성분. 피부 속건조를 개선하고 수분막을 형성합니다."),
    ("하이알루로네이트", [1, 7], "히알루론산 유도체로 수분을 끌어당겨 보습막을 형성합니다."),
    ("글리세린", [1], "대표적인 보습 성분. 수분을 끌어와 피부를 촉촉하게 유지합니다."),
    ("판테놀", [1, 2, 7], "비타민B5 유도체. 보습·진정과 함께 피부 장벽 회복을 돕습니다."),
    ("베타인", [1], "수분 보유력을 높여 건조함을 완화하는 보습 성분입니다."),
    ("뷰틸렌글라이콜", [1], "보습과 함께 다른 성분의 용해를 돕는 습윤제입니다."),
    ("프로판다이올", [1], "식물 유래 보습 성분으로 자극이 적고 촉촉함을 줍니다."),
    ("소듐피씨에이", [1, 7], "피부 천연보습인자(NMF) 성분으로 수분 유지에 핵심적입니다."),
    ("트레할로스", [1], "수분 손실을 막아 건조 환경에서도 촉촉함을 유지시킵니다."),
    ("스쿠알란", [1, 7], "피부 친화적 오일 성분. 유분막을 형성해 수분 증발을 막습니다."),

    # ===== 진정 =====
    ("센텔라아시아티카", [2, 7], "병풀 추출물. 자극받은 피부를 진정시키고 재생을 돕습니다."),
    ("아시아티코사이드", [2], "병풀 유래 성분으로 피부 진정과 회복에 도움을 줍니다."),
    ("마데카소사이드", [2, 7], "병풀 유래 진정 성분. 민감해진 피부를 가라앉힙니다."),
    ("병풀", [2, 7], "대표적인 진정 성분. 자극 완화와 장벽 강화에 도움을 줍니다."),
    ("알로에", [2, 1], "수분 공급과 진정에 탁월한 식물 성분입니다."),
    ("알란토인", [2, 7], "피부 진정과 보호막 형성을 돕는 순한 성분입니다."),
    ("어성초", [2, 9], "진정과 트러블 케어에 도움을 주는 식물 추출물입니다."),
    ("녹차", [2, 8], "항산화와 진정 효과가 있는 폴리페놀 풍부 성분입니다."),
    ("마치현", [2], "쇠비름 추출물로 민감한 피부를 진정시킵니다."),
    ("비사보롤", [2], "캐모마일 유래 진정 성분으로 자극을 완화합니다."),
    ("징크옥사이드", [2, 10], "진정과 함께 물리적 자외선 차단 역할을 합니다."),
    ("판테놀", [1, 2, 7], "비타민B5. 진정·보습·장벽 회복을 함께 돕습니다."),

    # ===== 미백 =====
    ("나이아신아마이드", [3, 7, 5], "비타민B3. 톤 개선, 피부 장벽 강화, 피지 조절에 도움을 줍니다."),
    ("알부틴", [3], "멜라닌 생성을 억제해 톤을 밝게 개선하는 미백 성분입니다."),
    ("아스코빅애씨드", [3, 8], "비타민C. 미백과 항산화에 효과적인 대표 성분입니다."),
    ("아스코빌글루코사이드", [3, 8], "안정화된 비타민C 유도체로 톤 개선을 돕습니다."),
    ("에틸아스코빅애씨드", [3, 8], "비타민C 유도체. 미백과 항산화 작용을 합니다."),
    ("트라넥사믹애씨드", [3], "색소 침착을 완화해 균일한 톤을 만드는 미백 성분입니다."),
    ("알파-비사보롤", [3, 2], "미백과 진정을 함께 돕는 식물 유래 성분입니다."),
    ("글루타치온", [3, 8], "항산화와 미백에 도움을 주는 성분입니다."),

    # ===== 주름개선 / 안티에이징 =====
    ("레티놀", [4, 8], "콜라겐 생성을 촉진하는 대표 안티에이징 성분입니다."),
    ("레티날", [4], "레티놀보다 빠르게 작용하는 주름개선 성분입니다."),
    ("레티닐팔미테이트", [4], "순한 레티놀 유도체로 주름 개선을 돕습니다."),
    ("아데노신", [4], "식약처 주름개선 고시 성분. 탄력 개선에 도움을 줍니다."),
    ("바쿠치올", [4, 2], "식물 유래 레티놀 대체 성분으로 순한 안티에이징을 제공합니다."),
    ("펩타이드", [4, 7], "피부 탄력과 장벽 강화에 도움을 주는 아미노산 결합 성분입니다."),
    ("콜라겐", [4, 1], "피부 탄력과 보습에 관여하는 단백질 성분입니다."),
    ("코엔자임", [4, 8], "코엔자임Q10. 항산화와 탄력 개선에 도움을 줍니다."),
    ("이데베논", [4, 8], "강력한 항산화로 노화 징후 완화를 돕습니다."),

    # ===== 피지조절 / 모공 =====
    ("살리실릭애씨드", [5, 6, 9], "BHA. 모공 속 피지와 각질을 녹여 트러블을 관리합니다."),
    ("징크피씨에이", [5], "피지 분비를 조절해 번들거림을 완화합니다."),
    ("위치하젤", [5, 2], "모공 수렴과 피지 조절에 도움을 주는 식물 성분입니다."),

    # ===== 각질케어 =====
    ("글라이콜릭애씨드", [6, 3], "AHA. 묵은 각질을 제거해 톤과 결을 개선합니다."),
    ("락틱애씨드", [6, 1], "AHA. 각질 제거와 함께 보습을 더하는 순한 산입니다."),
    ("만델릭애씨드", [6], "입자가 큰 AHA로 자극이 적은 각질 케어 성분입니다."),
    ("폴리하이드록시", [6, 1], "PHA. 가장 순한 각질 케어 성분으로 민감 피부에 적합합니다."),
    ("엘에이치에이", [6, 5], "LHA. 모공과 각질을 부드럽게 정돈합니다."),

    # ===== 장벽강화 =====
    ("세라마이드", [7, 1], "피부 장벽의 핵심 지질. 수분 손실을 막고 장벽을 강화합니다."),
    ("콜레스테롤", [7], "피부 장벽 구성 지질로 보호막 강화에 도움을 줍니다."),
    ("피토스핑고신", [7, 9], "장벽 강화와 항균 작용으로 트러블 완화를 돕습니다."),
    ("마데카식애씨드", [7, 2], "병풀 유래 성분으로 장벽 회복과 진정을 돕습니다."),

    # ===== 항산화 =====
    ("토코페롤", [8, 1], "비타민E. 항산화로 피부를 보호하고 유연하게 합니다."),
    ("페룰릭애씨드", [8], "비타민C의 항산화력을 안정화·강화하는 성분입니다."),
    ("레스베라트롤", [8], "포도 유래 강력한 항산화 성분입니다."),
    ("아스타잔틴", [8], "강력한 항산화로 피부 노화 방지를 돕습니다."),
    ("폴리페놀", [8, 2], "항산화와 진정에 도움을 주는 식물 성분입니다."),

    # ===== 트러블케어 =====
    ("티트리", [9, 2], "항균·진정으로 트러블 피부 관리에 도움을 줍니다."),
    ("아줄렌", [9, 2], "캐모마일 유래 진정 성분으로 염증성 트러블을 완화합니다."),
    ("설퍼", [9, 5], "유황. 피지와 트러블 관리에 사용되는 성분입니다."),
    ("센텔라", [2, 7], "병풀. 진정과 장벽 회복으로 트러블 피부를 돕습니다."),

    # ===== 자외선차단 =====
    ("타이타늄디옥사이드", [10, 2], "물리적 자외선 차단제. 자극이 적어 민감 피부에 적합합니다."),
    ("옥토크릴렌", [10], "화학적 자외선 차단 성분으로 UVB를 흡수합니다."),
    ("아보벤존", [10], "UVA를 차단하는 화학적 자외선 차단 성분입니다."),
    ("유비뉼", [10], "넓은 파장의 자외선을 차단하는 성분입니다."),
]


def reset_info():
    Ingredient.objects.exclude(description__isnull=True).update(description=None)
    IngredientFunction.objects.all().delete()
    print("기존 description / IngredientFunction 초기화 완료")


MAX_MATCH_PER_KEYWORD = 15  # 광범위 키워드 폭주 방지


def run():
    if not FunctionMaster.objects.exists():
        print("FunctionMaster 데이터가 없습니다.")
        return

    # 기존 매핑 (ingredient_id, function_id) 셋 — 중복 방지
    existing_pairs = set(
        IngredientFunction.objects.values_list("ingredient_id", "function_id")
    )

    ing_updates = {}          # ingredient_id -> Ingredient (description/flag 변경분)
    new_mappings = []         # IngredientFunction 버퍼
    matched_ing = 0

    for keyword, func_ids, description in INGREDIENT_INFO:
        ings = list(
            Ingredient.objects.filter(
                Q(ingredient_name_kr__icontains=keyword) | Q(ingredient_name_en__icontains=keyword)
            )[:MAX_MATCH_PER_KEYWORD]
        )
        if not ings:
            print(f"  [없음] {keyword}")
            continue

        for ing in ings:
            changed = False
            if not ing.description:
                ing.description = description
                changed = True
            if 1 in func_ids and not ing.moisturizing_flag:
                ing.moisturizing_flag = True
                changed = True
            if 2 in func_ids and not ing.soothing_flag:
                ing.soothing_flag = True
                changed = True
            if 9 in func_ids and not ing.acne_caution_flag:
                ing.acne_caution_flag = True
                changed = True
            if changed:
                ing_updates[ing.ingredient_id] = ing

            for fid in func_ids:
                if (ing.ingredient_id, fid) not in existing_pairs:
                    existing_pairs.add((ing.ingredient_id, fid))
                    new_mappings.append(
                        IngredientFunction(ingredient_id=ing.ingredient_id, function_id=fid)
                    )

        matched_ing += len(ings)
        print(f"  [OK] {keyword} → {len(ings)}개")

    # 일괄 반영
    updates = list(ing_updates.values())
    for i in range(0, len(updates), 200):
        Ingredient.objects.bulk_update(
            updates[i:i + 200],
            ["description", "moisturizing_flag", "soothing_flag", "acne_caution_flag"],
        )
    for i in range(0, len(new_mappings), 300):
        IngredientFunction.objects.bulk_create(
            new_mappings[i:i + 300], ignore_conflicts=True
        )

    print(f"\n=== 완료 ===")
    print(f"성분 업데이트(효능/flag): {len(updates)}개")
    print(f"기능 매핑 추가: {len(new_mappings)}개")
    print(f"매칭된 성분(중복 포함): {matched_ing}개")


def main():
    parser = argparse.ArgumentParser(description="핵심 성분 효능/기능 채우기")
    parser.add_argument("--reset", action="store_true", help="기존 데이터 초기화 후 재설정")
    args = parser.parse_args()

    if args.reset:
        reset_info()
    run()


if __name__ == "__main__":
    main()
