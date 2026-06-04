#!/usr/bin/env python
"""
성분 별칭(IngredientAlias) 채우기.

화장품 마케팅에서 흔히 쓰는 줄임말·통칭을 실제 DB 성분명과 연결.
예: "PDRN" → 소듐디엔에이, "비타민C" → 아스코빅애씨드

검색(_match_ingredient)이 alias도 조회하므로, 사용자가 통칭으로 입력해도 매칭됨.

사용법:
    python scripts/seed_ingredient_aliases.py
    python scripts/seed_ingredient_aliases.py --reset
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
from products.models import Ingredient, IngredientAlias


# (별칭, 실제 성분명 매칭 키워드) — 키워드로 대표 성분 1개 찾아 연결
ALIASES = [
    # 마케팅 줄임말
    ("PDRN", "소듐디엔에이"),
    ("피디알엔", "소듐디엔에이"),
    ("연어주사", "소듐디엔에이"),
    # 비타민 통칭
    ("비타민C", "아스코빅애씨드"),
    ("비타민씨", "아스코빅애씨드"),
    ("바이타민C", "아스코빅애씨드"),
    ("비타민B3", "나이아신아마이드"),
    ("비타민B5", "판테놀"),
    ("프로비타민B5", "판테놀"),
    ("비타민E", "토코페롤"),
    ("비타민A", "레티놀"),
    ("비타민H", "바이오틴"),
    # 산 통칭
    ("AHA", "글라이콜릭애씨드"),
    ("BHA", "살리실릭애씨드"),
    ("PHA", "글루코노락톤"),
    ("LHA", "카프릴로일살리실릭애씨드"),
    ("히알루론산", "하이알루로닉애씨드"),
    ("히아루론산", "하이알루로닉애씨드"),
    ("글리콜산", "글라이콜릭애씨드"),
    ("살리실산", "살리실릭애씨드"),
    ("아젤라산", "아젤라익애씨드"),
    ("코직산", "코직애씨드"),
    ("만델산", "만델릭애씨드"),
    # 식물/진정 통칭
    ("병풀", "센텔라아시아티카"),
    ("시카", "센텔라아시아티카"),
    ("어성초", "어성초추출물"),
    ("녹차", "녹차추출물"),
    ("알로에", "알로에베라잎추출물"),
    ("티트리", "티트리잎오일"),
    ("쑥", "병쑥추출물"),
    ("감초", "감초추출물"),
    # 안티에이징/펩타이드 통칭
    ("레티놀", "레티놀"),
    ("바쿠치올", "바쿠치올"),
    ("아데노신", "아데노신"),
    ("콜라겐", "콜라겐"),
    ("펩타이드", "올리고펩타이드"),
    ("구리펩타이드", "카퍼트라이펩타이드"),
    ("코엔자임Q10", "유비퀴논"),
    ("코큐텐", "유비퀴논"),
    # 보습 통칭
    ("세라마이드", "세라마이드엔피"),
    ("판테놀", "판테놀"),
    ("스쿠알란", "스쿠알란"),
    ("마데카소사이드", "마데카소사이드"),
    # 미백
    ("나이아신아마이드", "나이아신아마이드"),
    ("알부틴", "알부틴"),
    ("트라넥사믹애씨드", "트라넥사믹애씨드"),
    ("글루타치온", "글루타치온"),
]


def reset_aliases():
    # 이 스크립트가 넣는 alias_type만 삭제
    deleted, _ = IngredientAlias.objects.filter(alias_type="common").delete()
    print(f"기존 통칭 별칭 {deleted}개 삭제 완료")


def run():
    added = 0
    skipped = 0

    for alias_name, keyword in ALIASES:
        ing = Ingredient.objects.filter(
            Q(ingredient_name_kr__icontains=keyword) | Q(ingredient_name_en__icontains=keyword)
        ).first()

        if not ing:
            print(f"  [없음] {alias_name} → '{keyword}' 매칭 성분 없음")
            continue

        obj, created = IngredientAlias.objects.get_or_create(
            ingredient=ing,
            alias_name=alias_name,
            defaults={"alias_type": "common", "is_active": True},
        )
        if created:
            added += 1
            print(f"  [OK] {alias_name} → {ing.ingredient_name_kr}")
        else:
            skipped += 1

    print(f"\n=== 완료 ===")
    print(f"추가된 별칭: {added}개")
    print(f"이미 존재(건너뜀): {skipped}개")


def main():
    parser = argparse.ArgumentParser(description="성분 별칭 채우기")
    parser.add_argument("--reset", action="store_true", help="기존 통칭 별칭 삭제 후 재설정")
    args = parser.parse_args()

    if args.reset:
        reset_aliases()
    run()


if __name__ == "__main__":
    main()
