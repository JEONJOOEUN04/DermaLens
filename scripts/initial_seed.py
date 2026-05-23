#!/usr/bin/env python
"""
식약처 공공데이터 포털 초기 시드 스크립트

사용법:
    python scripts/initial_seed.py --api-key YOUR_KEY
    FOODSAFETY_API_KEY=YOUR_KEY python scripts/initial_seed.py

수행 작업:
    1. 원료성분정보 API → Ingredient + IngredientAlias (INCI, SYNONYM) 적재
    2. 규제정보 API → Ingredient.risk_level 업데이트 (금지=10, 제한=6)
    3. DataSyncHistory 기록
"""

import argparse
import os
import sys
import time
import urllib.parse
import urllib.request
import json
import logging

# ── Django 설정 ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "config"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dermalens.settings")

import django
django.setup()

from django.db import transaction
from products.models import Ingredient, IngredientAlias
from review.models import ExternalSource, DataSyncHistory

# ── 로깅 ─────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── API 상수 ──────────────────────────────────────────────────────────────────
BASE_URL = "https://apis.data.go.kr/1471000"
INGREDIENT_SERVICE = "CsmtcsIngdCpntInfoService01"
INGREDIENT_OPERATION = "getCsmtcsIngdCpntInfoService01"
REGULATION_SERVICE = "CsmtcsReglMaterialInfoService"
REGULATION_OPERATION = "getCsmtcsReglMaterialInfoService01"

PAGE_SIZE = 100
REQUEST_DELAY = 0.3  # 공공데이터 TPS 제한 대응


def fetch_json(url: str, params: dict, retries: int = 3) -> dict:
    params["_type"] = "json"
    query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    full_url = f"{url}?{query}"

    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(full_url, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
            return json.loads(raw)
        except Exception as exc:
            log.warning("요청 실패 (시도 %d/%d): %s — %s", attempt, retries, full_url, exc)
            if attempt < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"API 호출 반복 실패: {full_url}")


def extract_items(data: dict) -> list[dict]:
    """공공데이터 포털 공통 응답 구조에서 item 목록 추출."""
    try:
        body = data["response"]["body"]
        items = body.get("items", {})
        if not items:
            return []
        item = items.get("item", [])
        if isinstance(item, dict):
            return [item]
        return item
    except (KeyError, TypeError):
        return []


def total_count(data: dict) -> int:
    try:
        return int(data["response"]["body"]["totalCount"])
    except (KeyError, TypeError, ValueError):
        return 0


# ── 1단계: 원료성분정보 적재 ──────────────────────────────────────────────────

def seed_ingredients(api_key: str) -> tuple[int, int]:
    """
    원료성분정보 API를 전량 조회해 Ingredient + IngredientAlias 적재.
    반환값: (inserted, updated)
    """
    url = f"{BASE_URL}/{INGREDIENT_SERVICE}/{INGREDIENT_OPERATION}"
    inserted = updated = 0
    page = 1

    log.info("=== 원료성분정보 적재 시작 ===")

    while True:
        params = {
            "serviceKey": api_key,
            "pageNo": page,
            "numOfRows": PAGE_SIZE,
        }

        try:
            data = fetch_json(url, params)
        except RuntimeError as e:
            log.error(str(e))
            break

        items = extract_items(data)
        if not items:
            log.info("페이지 %d: 항목 없음 — 종료", page)
            break

        log.info("페이지 %d: %d개 항목 처리 중...", page, len(items))

        with transaction.atomic():
            for item in items:
                kr_name = (item.get("ingdCpntKrlNm") or "").strip()
                en_name = (item.get("ingdCpntEngNm") or "").strip()
                synonym = (item.get("ingdCpntSynonymNm") or "").strip()

                if not kr_name:
                    continue

                ingredient, created = Ingredient.objects.get_or_create(
                    ingredient_name_kr=kr_name,
                    defaults={"ingredient_name_en": en_name or None},
                )

                if created:
                    inserted += 1
                else:
                    # 영문명이 없으면 채워줌
                    if en_name and not ingredient.ingredient_name_en:
                        ingredient.ingredient_name_en = en_name
                        ingredient.save(update_fields=["ingredient_name_en"])
                    updated += 1

                # INCI alias (영문명)
                if en_name:
                    IngredientAlias.objects.get_or_create(
                        ingredient=ingredient,
                        alias_name=en_name,
                        defaults={"alias_type": "INCI"},
                    )

                # SYNONYM alias
                if synonym:
                    for syn in synonym.split(","):
                        syn = syn.strip()
                        if syn:
                            IngredientAlias.objects.get_or_create(
                                ingredient=ingredient,
                                alias_name=syn,
                                defaults={"alias_type": "SYNONYM"},
                            )

        # 공공데이터 totalCount는 신뢰하기 어려우므로 항목 수로 판단
        if len(items) < PAGE_SIZE:
            log.info("마지막 페이지 도달 (페이지 %d)", page)
            break

        page += 1
        time.sleep(REQUEST_DELAY)

    log.info("원료성분정보 완료 — 신규: %d, 업데이트: %d", inserted, updated)
    return inserted, updated


# ── 2단계: 규제정보로 risk_level 업데이트 ─────────────────────────────────────

RISK_LEVEL_MAP = {
    "사용금지원료": 10,
    "사용제한원료": 6,
    "금지": 10,
    "제한": 6,
}


def _resolve_risk(regl_type: str) -> int | None:
    if not regl_type:
        return None
    regl_type = regl_type.strip()
    for key, val in RISK_LEVEL_MAP.items():
        if key in regl_type:
            return val
    return None


def seed_regulations(api_key: str) -> tuple[int, int]:
    """
    규제정보 API를 전량 조회해 매칭되는 Ingredient.risk_level 업데이트.
    반환값: (inserted=0, updated)
    """
    url = f"{BASE_URL}/{REGULATION_SERVICE}/{REGULATION_OPERATION}"
    updated = 0
    not_found = 0
    page = 1

    log.info("=== 규제정보 적재 시작 ===")

    while True:
        params = {
            "serviceKey": api_key,
            "pageNo": page,
            "numOfRows": PAGE_SIZE,
        }

        try:
            data = fetch_json(url, params)
        except RuntimeError as e:
            log.error(str(e))
            break

        items = extract_items(data)
        if not items:
            log.info("페이지 %d: 항목 없음 — 종료", page)
            break

        log.info("페이지 %d: %d개 항목 처리 중...", page, len(items))

        with transaction.atomic():
            for item in items:
                # 필드명은 API 버전에 따라 다를 수 있어 여러 후보 시도
                raw_name = (
                    item.get("reglMaterialNm")
                    or item.get("ingdNm")
                    or item.get("materialNm")
                    or ""
                ).strip()

                regl_type = (
                    item.get("reglTypNm")
                    or item.get("reglType")
                    or item.get("useLimitTypNm")
                    or ""
                )

                if not raw_name:
                    continue

                risk = _resolve_risk(regl_type)
                if risk is None:
                    continue

                # 한글명으로 직접 매칭 먼저 시도
                qs = Ingredient.objects.filter(ingredient_name_kr=raw_name)

                # 없으면 alias에서 찾기
                if not qs.exists():
                    alias = IngredientAlias.objects.filter(alias_name=raw_name).select_related("ingredient").first()
                    if alias:
                        qs = Ingredient.objects.filter(pk=alias.ingredient_id)

                if qs.exists():
                    n = qs.filter(risk_level__lt=risk).update(risk_level=risk)
                    updated += n
                else:
                    not_found += 1
                    log.debug("규제 원료 미매칭: %s", raw_name)

        if len(items) < PAGE_SIZE:
            log.info("마지막 페이지 도달 (페이지 %d)", page)
            break

        page += 1
        time.sleep(REQUEST_DELAY)

    log.info("규제정보 완료 — risk_level 업데이트: %d, 미매칭: %d", updated, not_found)
    return 0, updated


# ── ExternalSource 초기화 ─────────────────────────────────────────────────────

SOURCE_DEFS = [
    {
        "source_name": "식약처_원료성분정보",
        "api_url": f"{BASE_URL}/{INGREDIENT_SERVICE}/{INGREDIENT_OPERATION}",
    },
    {
        "source_name": "식약처_규제정보",
        "api_url": f"{BASE_URL}/{REGULATION_SERVICE}/{REGULATION_OPERATION}",
    },
]


def get_or_create_sources() -> tuple[ExternalSource, ExternalSource]:
    src_ingd, _ = ExternalSource.objects.get_or_create(
        source_name=SOURCE_DEFS[0]["source_name"],
        defaults={"api_url": SOURCE_DEFS[0]["api_url"]},
    )
    src_regl, _ = ExternalSource.objects.get_or_create(
        source_name=SOURCE_DEFS[1]["source_name"],
        defaults={"api_url": SOURCE_DEFS[1]["api_url"]},
    )
    return src_ingd, src_regl


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="식약처 원료성분 초기 시드")
    parser.add_argument(
        "--api-key",
        default=os.environ.get("FOODSAFETY_API_KEY", ""),
        help="공공데이터 포털 서비스키 (또는 FOODSAFETY_API_KEY 환경변수)",
    )
    parser.add_argument(
        "--skip-ingredients",
        action="store_true",
        help="원료성분정보 단계 건너뜀 (규제정보만 재실행 시)",
    )
    parser.add_argument(
        "--skip-regulations",
        action="store_true",
        help="규제정보 단계 건너뜀",
    )
    args = parser.parse_args()

    if not args.api_key:
        log.error("API 키가 없습니다. --api-key 또는 FOODSAFETY_API_KEY 환경변수를 설정하세요.")
        sys.exit(1)

    src_ingd, src_regl = get_or_create_sources()

    # 원료성분정보 단계
    if not args.skip_ingredients:
        i_inserted, i_updated = seed_ingredients(args.api_key)
        DataSyncHistory.objects.create(
            source=src_ingd,
            inserted_count=i_inserted,
            updated_count=i_updated,
        )
        log.info("DataSyncHistory 기록 완료 (원료성분정보)")
    else:
        log.info("원료성분정보 단계 건너뜀")

    # 규제정보 단계
    if not args.skip_regulations:
        _, r_updated = seed_regulations(args.api_key)
        DataSyncHistory.objects.create(
            source=src_regl,
            inserted_count=0,
            updated_count=r_updated,
        )
        log.info("DataSyncHistory 기록 완료 (규제정보)")
    else:
        log.info("규제정보 단계 건너뜀")

    log.info("=== 초기 시드 완료 ===")


if __name__ == "__main__":
    main()
