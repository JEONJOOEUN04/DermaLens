#!/usr/bin/env python
"""
식약처 주간 증분 동기화 스크립트

사용법:
    python scripts/sync_weekly.py --api-key YOUR_KEY

크론 등록 예시 (매주 일요일 새벽 3시):
    0 3 * * 0 /Users/jeonjooeun/DermaLens/venv/bin/python \
        /Users/jeonjooeun/DermaLens/scripts/sync_weekly.py \
        --api-key $FOODSAFETY_API_KEY >> /var/log/dermalens_sync.log 2>&1

동작:
    - initial_seed.py와 동일한 로직이지만, 마지막 동기화 이후 변경분만 처리
    - API가 최종변경일(lastUpdtDt) 파라미터를 지원하면 활용, 아니면 전량 재처리
    - 새 성분은 INSERT, 기존 성분은 영문명·risk_level만 갱신
"""

import argparse
import os
import sys
import time
import urllib.parse
import urllib.request
import json
import logging
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "config"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dermalens.settings")

import django
django.setup()

from django.db import transaction
from django.db.models import Max
from products.models import Ingredient, IngredientAlias
from review.models import ExternalSource, DataSyncHistory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

BASE_URL = "https://apis.data.go.kr/1471000"
INGREDIENT_SERVICE = "CsmtcsIngdCpntInfoService01"
INGREDIENT_OPERATION = "getCsmtcsIngdCpntInfoService01"
REGULATION_SERVICE = "CsmtcsReglMaterialInfoService"
REGULATION_OPERATION = "getCsmtcsReglMaterialInfoService01"

PAGE_SIZE = 100
REQUEST_DELAY = 0.3

RISK_LEVEL_MAP = {
    "사용금지원료": 10,
    "사용제한원료": 6,
    "금지": 10,
    "제한": 6,
}


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
            log.warning("요청 실패 (%d/%d): %s", attempt, retries, exc)
            if attempt < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"API 호출 반복 실패: {full_url}")


def extract_items(data: dict) -> list[dict]:
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


def last_sync_date(source_name: str) -> str | None:
    """마지막 동기화 날짜를 YYYYMMDD 문자열로 반환. 없으면 None."""
    src = ExternalSource.objects.filter(source_name=source_name).first()
    if not src:
        return None
    latest = DataSyncHistory.objects.filter(source=src).aggregate(Max("sync_id"))["sync_id__max"]
    if not latest:
        return None
    # 7일 전을 기준으로 (안전 마진)
    cutoff = datetime.now() - timedelta(days=7)
    return cutoff.strftime("%Y%m%d")


def sync_ingredients(api_key: str) -> tuple[int, int]:
    url = f"{BASE_URL}/{INGREDIENT_SERVICE}/{INGREDIENT_OPERATION}"
    since = last_sync_date("식약처_원료성분정보")
    inserted = updated = 0
    page = 1

    log.info("=== 원료성분 증분 동기화 시작 (기준일: %s) ===", since or "전체")

    while True:
        params: dict = {
            "serviceKey": api_key,
            "pageNo": page,
            "numOfRows": PAGE_SIZE,
        }
        if since:
            params["lastUpdtDt"] = since

        try:
            data = fetch_json(url, params)
        except RuntimeError as e:
            log.error(str(e))
            break

        items = extract_items(data)
        if not items:
            break

        log.info("페이지 %d: %d개 처리", page, len(items))

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
                    if en_name and not ingredient.ingredient_name_en:
                        ingredient.ingredient_name_en = en_name
                        ingredient.save(update_fields=["ingredient_name_en"])
                    updated += 1

                if en_name:
                    IngredientAlias.objects.get_or_create(
                        ingredient=ingredient,
                        alias_name=en_name,
                        defaults={"alias_type": "INCI"},
                    )

                if synonym:
                    for syn in synonym.split(","):
                        syn = syn.strip()
                        if syn:
                            IngredientAlias.objects.get_or_create(
                                ingredient=ingredient,
                                alias_name=syn,
                                defaults={"alias_type": "SYNONYM"},
                            )

        if len(items) < PAGE_SIZE:
            break

        page += 1
        time.sleep(REQUEST_DELAY)

    log.info("원료성분 동기화 완료 — 신규: %d, 업데이트: %d", inserted, updated)
    return inserted, updated


def sync_regulations(api_key: str) -> tuple[int, int]:
    url = f"{BASE_URL}/{REGULATION_SERVICE}/{REGULATION_OPERATION}"
    updated = 0
    page = 1

    log.info("=== 규제정보 동기화 시작 ===")

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
            break

        with transaction.atomic():
            for item in items:
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

                risk = None
                for key, val in RISK_LEVEL_MAP.items():
                    if key in regl_type:
                        risk = val
                        break
                if risk is None:
                    continue

                qs = Ingredient.objects.filter(ingredient_name_kr=raw_name)
                if not qs.exists():
                    alias = IngredientAlias.objects.filter(alias_name=raw_name).select_related("ingredient").first()
                    if alias:
                        qs = Ingredient.objects.filter(pk=alias.ingredient_id)

                if qs.exists():
                    n = qs.filter(risk_level__lt=risk).update(risk_level=risk)
                    updated += n

        if len(items) < PAGE_SIZE:
            break

        page += 1
        time.sleep(REQUEST_DELAY)

    log.info("규제정보 동기화 완료 — 업데이트: %d", updated)
    return 0, updated


def main():
    parser = argparse.ArgumentParser(description="식약처 주간 증분 동기화")
    parser.add_argument("--api-key", default=os.environ.get("FOODSAFETY_API_KEY", ""))
    parser.add_argument("--skip-ingredients", action="store_true")
    parser.add_argument("--skip-regulations", action="store_true")
    args = parser.parse_args()

    if not args.api_key:
        log.error("API 키가 없습니다.")
        sys.exit(1)

    src_ingd, _ = ExternalSource.objects.get_or_create(
        source_name="식약처_원료성분정보",
        defaults={"api_url": f"{BASE_URL}/{INGREDIENT_SERVICE}/{INGREDIENT_OPERATION}"},
    )
    src_regl, _ = ExternalSource.objects.get_or_create(
        source_name="식약처_규제정보",
        defaults={"api_url": f"{BASE_URL}/{REGULATION_SERVICE}/{REGULATION_OPERATION}"},
    )

    if not args.skip_ingredients:
        i, u = sync_ingredients(args.api_key)
        DataSyncHistory.objects.create(source=src_ingd, inserted_count=i, updated_count=u)

    if not args.skip_regulations:
        _, u = sync_regulations(args.api_key)
        DataSyncHistory.objects.create(source=src_regl, inserted_count=0, updated_count=u)

    log.info("=== 동기화 완료 ===")


if __name__ == "__main__":
    main()
