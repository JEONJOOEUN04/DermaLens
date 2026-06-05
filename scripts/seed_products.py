#!/usr/bin/env python
"""
네이버 쇼핑 API 화장품 초기 적재 스크립트

사용법:
    python scripts/seed_products.py
    python scripts/seed_products.py --keywords 토너 세럼 크림  (키워드 지정)
    python scripts/seed_products.py --sync  (주간 동기화 모드 — 신규만 추가)
"""

import argparse
import os
import sys
import time
import json
import re
import urllib.request
import urllib.parse
import logging

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "config"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.conf import settings
from products.models import Brand, Category, Product

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# 기초화장품 전용 키워드 (헤어/바디 제거)
COSMETICS_KEYWORDS = [
    # 기본 카테고리
    "토너", "스킨", "에센스", "세럼", "앰플",
    "로션", "에멀전", "크림", "젤크림", "오일",
    "미스트", "클렌징폼", "클렌징오일", "클렌징워터",
    "선크림", "선스틱", "마스크팩", "필링",
    "스팟케어", "아이크림",
    # 피부 고민별 (제품 다양성 확대)
    "수분크림", "진정크림", "시카크림", "재생크림", "영양크림",
    "보습토너", "각질토너", "모공토너",
    "비타민세럼", "레티놀세럼", "히알루론산세럼", "나이아신아마이드",
    "콜라겐크림", "펩타이드세럼", "PDRN", "어성초토너",
    "약산성클렌저", "딥클렌징", "립밤", "핸드크림",
    "수분마스크팩", "모델링팩", "패드", "토너패드",
]

DISPLAY_PER_KEYWORD = 100
REQUEST_DELAY = 1.0  # 네이버 API TPS 대응

# 네이버 category2 허용 목록 — 기초화장품만
ALLOWED_CATEGORY2 = {"스킨케어", "선케어/자외선차단", "클렌저"}

# 네이버 category3 → DB Category.category_name 매핑
NAVER_CATEGORY3_MAP = {
    "토너/스킨":              "토너",
    "에센스/세럼/앰플":       "에센스",
    "에센스":                 "에센스",
    "세럼":                   "세럼",
    "앰플":                   "앰플",
    "로션/에멀전":            "로션",
    "로션":                   "로션",
    "에멀전":                 "에멀전",
    "크림":                   "크림",
    "젤크림":                 "젤크림",
    "젤/젤크림":              "젤크림",
    "아이크림":               "아이크림",
    "미스트":                 "미스트",
    "오일":                   "오일",
    "스팟케어":               "스팟케어",
    "클렌징폼":               "클렌징폼",
    "클렌징오일/클렌징밤":    "클렌징오일",
    "클렌징오일":             "클렌징오일",
    "클렌징워터/클렌징밀크":  "클렌징워터",
    "클렌징워터":             "클렌징워터",
    "마스크팩":               "마스크팩",
    "필링/각질케어":          "필링/각질케어",
    "선크림":                 "선크림",
    "선스틱/선스프레이":      "선스틱",
    "선스틱":                 "선스틱",
}

# 검색 키워드 → DB 카테고리 (우선순위 순서대로 검사)
KEYWORD_CATEGORY_RULES = [
    ("젤크림", "젤크림"),
    ("토너패드", "토너"),
    ("토너", "토너"),
    ("스킨", "토너"),
    ("세럼", "세럼"),
    ("앰플", "앰플"),
    ("에센스", "에센스"),
    ("에멀전", "에멀전"),
    ("수분크림", "크림"),
    ("진정크림", "크림"),
    ("시카크림", "크림"),
    ("재생크림", "크림"),
    ("영양크림", "크림"),
    ("콜라겐크림", "크림"),
    ("아이크림", "아이크림"),
    ("핸드크림", "크림"),
    ("크림", "크림"),
    ("로션", "로션"),
    ("미스트", "미스트"),
    ("오일", "오일"),
    ("클렌징폼", "클렌징폼"),
    ("클렌징오일", "클렌징오일"),
    ("클렌징워터", "클렌징워터"),
    ("약산성클렌저", "클렌징폼"),
    ("딥클렌징", "클렌징폼"),
    ("선크림", "선크림"),
    ("선스틱", "선스틱"),
    ("마스크팩", "마스크팩"),
    ("모델링팩", "마스크팩"),
    ("패드", "필링/각질케어"),
    ("필링", "필링/각질케어"),
    ("스팟케어", "스팟케어"),
    # 성분 키워드 → 대표 카테고리
    ("비타민세럼", "세럼"),
    ("레티놀세럼", "세럼"),
    ("히알루론산세럼", "세럼"),
    ("펩타이드세럼", "세럼"),
    ("나이아신아마이드", "세럼"),
    ("보습토너", "토너"),
    ("각질토너", "토너"),
    ("모공토너", "토너"),
    ("어성초토너", "토너"),
]


def keyword_to_category_name(keyword):
    """검색 키워드에서 DB 카테고리명 추론."""
    for needle, cat_name in KEYWORD_CATEGORY_RULES:
        if needle in keyword:
            return cat_name
    return None


_category_cache = {}  # 반복 DB 조회 방지


def strip_html(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()


def parse_volume(product_name):
    """상품명에서 용량 파싱. 예: '토너 500ml, 1개' → '500ml'"""
    match = re.search(r"(\d+(?:\.\d+)?)\s*(ml|ML|mL|g|G|kg|KG|oz|fl\.?\s*oz)", product_name)
    if match:
        return match.group(1) + match.group(2).lower().replace(" ", "")
    return None


def fetch_naver_items(keyword, display=20):
    client_id = getattr(settings, "NAVER_CLIENT_ID", "")
    client_secret = getattr(settings, "NAVER_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        log.error("NAVER_CLIENT_ID 또는 NAVER_CLIENT_SECRET 환경변수가 없습니다.")
        return []

    url = "https://openapi.naver.com/v1/search/shop.json?" + urllib.parse.urlencode({
        "query": keyword, "display": display, "sort": "sim"
    })
    req = urllib.request.Request(url, headers={
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("items", [])
    except Exception as e:
        log.warning("네이버 API 호출 실패 (%s): %s", keyword, e)
        return []


def get_or_create_brand(brand_name):
    if not brand_name:
        brand_name = "기타"
    brand, _ = Brand.objects.get_or_create(
        brand_name_kr=brand_name,
        defaults={"brand_name_en": brand_name},
    )
    return brand


def get_default_category():
    if "__default__" not in _category_cache:
        cat = Category.objects.filter(category_name="기타").first()
        if not cat:
            cat = Category.objects.order_by("category_id").first()
        _category_cache["__default__"] = cat
    return _category_cache["__default__"]


def get_category_by_name(name):
    if name not in _category_cache:
        cat = Category.objects.filter(category_name=name).first()
        _category_cache[name] = cat or get_default_category()
    return _category_cache[name]


def is_skincare_item(item):
    """네이버 category2 기준으로 기초화장품 여부 판별."""
    cat2 = item.get("category2", "")
    return any(allowed in cat2 for allowed in ALLOWED_CATEGORY2)


def resolve_category(item, keyword=None):
    """카테고리 결정: 검색 키워드 우선 → 네이버 category3 → 기타."""
    # 1) 검색 키워드 기반 (가장 정확 — 우리가 그 키워드로 검색했으므로)
    if keyword:
        kw_name = keyword_to_category_name(keyword)
        if kw_name:
            return get_category_by_name(kw_name)
    # 2) 네이버 category3 매핑
    cat3 = item.get("category3", "")
    db_name = NAVER_CATEGORY3_MAP.get(cat3)
    if db_name:
        return get_category_by_name(db_name)
    # 3) 기타
    return get_default_category()


def save_item(item, sync_mode=False, keyword=None):
    """
    네이버 쇼핑 결과 한 건 저장.
    기초화장품이 아니면 저장하지 않음.
    sync_mode=True면 이미 있는 제품은 가격/이미지만 업데이트.
    """
    if not is_skincare_item(item):
        return None, False

    product_name = strip_html(item.get("title", ""))
    if not product_name:
        return None, False

    brand = get_or_create_brand(strip_html(item.get("brand", "")))
    category = resolve_category(item, keyword=keyword)
    if not category:
        return None, False

    price_str = item.get("lprice", "") or ""
    price = int(price_str) if price_str.isdigit() else None
    image_url = item.get("image", "")
    product_url = item.get("link", "")
    volume = parse_volume(product_name)

    existing = Product.objects.filter(product_name=product_name, brand=brand).first()

    if existing:
        if sync_mode:
            # 주간 동기화 — 가격/이미지/용량 업데이트
            updated = False
            if price and existing.price != price:
                existing.price = price
                updated = True
            if image_url and existing.image_url != image_url:
                existing.image_url = image_url
                updated = True
            if volume and not existing.volume:
                existing.volume = volume
                updated = True
            if updated:
                existing.save()
        return existing, False  # (product, is_new)

    product = Product.objects.create(
        product_name=product_name,
        brand=brand,
        category=category,
        image_url=image_url,
        product_url=product_url,
        price=price,
        volume=volume,
    )
    return product, True  # (product, is_new)


def run(keywords, sync_mode=False):
    mode_label = "주간 동기화" if sync_mode else "초기 적재"
    log.info("=== 제품 %s 시작 (키워드 %d개 × %d건) ===", mode_label, len(keywords), DISPLAY_PER_KEYWORD)

    total_new = 0
    total_skip = 0

    for keyword in keywords:
        items = fetch_naver_items(keyword, display=DISPLAY_PER_KEYWORD)
        new_count = 0
        skip_count = 0

        for item in items:
            # brand 없으면 maker(제조사) 사용
            if not item.get("brand"):
                item["brand"] = item.get("maker", "")
            _, is_new = save_item(item, sync_mode=sync_mode, keyword=keyword)
            if is_new:
                new_count += 1
            else:
                skip_count += 1

        log.info("[%s] 신규: %d, 기존: %d", keyword, new_count, skip_count)
        total_new += new_count
        total_skip += skip_count
        time.sleep(REQUEST_DELAY)

    log.info("=== 완료 — 총 신규: %d, 총 기존: %d ===", total_new, total_skip)


def recategorize_existing():
    """기존 제품을 제품명 키워드로 재분류 (잘못 들어간 기타/에센스 교정)."""
    # 제품명 → 카테고리 추론 규칙 (KEYWORD_CATEGORY_RULES 재사용)
    products = list(Product.objects.select_related("category").all())
    log.info("재분류 대상 제품: %d개", len(products))

    updates = []
    for p in products:
        new_name = keyword_to_category_name(p.product_name)
        if not new_name:
            continue
        target = get_category_by_name(new_name)
        if target and p.category_id != target.category_id:
            p.category = target
            updates.append(p)

    # 일괄 업데이트 (연결 안정성)
    for i in range(0, len(updates), 300):
        Product.objects.bulk_update(updates[i:i + 300], ["category"])

    log.info("=== 재분류 완료 — 변경된 제품: %d개 ===", len(updates))


def main():
    parser = argparse.ArgumentParser(description="네이버 쇼핑 화장품 제품 적재")
    parser.add_argument("--keywords", nargs="+", help="키워드 직접 지정 (기본: 내장 키워드 목록)")
    parser.add_argument("--sync", action="store_true", help="주간 동기화 모드 (신규 추가 + 가격/이미지 업데이트)")
    parser.add_argument("--recategorize", action="store_true", help="기존 제품을 제품명 기준으로 재분류")
    args = parser.parse_args()

    if args.recategorize:
        recategorize_existing()
        return

    keywords = args.keywords if args.keywords else COSMETICS_KEYWORDS
    run(keywords, sync_mode=args.sync)


if __name__ == "__main__":
    main()
