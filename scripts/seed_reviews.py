#!/usr/bin/env python
"""
피부타입별 페르소나 더미 데이터 생성 스크립트
- 피부타입 8개 × 20명 = 160명 유저 생성
- 각 유저가 자기 피부타입에 맞는 카테고리 상품에 높은 평점 부여
- 각 유저가 3~7단계짜리 스킨케어 루틴 보유

사용법:
    python scripts/seed_reviews.py
    python scripts/seed_reviews.py --reset  (기존 더미 데이터 삭제 후 재생성)
"""

import argparse
import os
import sys
import random

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "config"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.contrib.auth.hashers import make_password
from users.models import User, UserSkinProfile, SkinTypeMaster
from products.models import Product, ProductLike, Category
from review.models import Review
from recommendation.models import UserRoutine, UserRoutineStep

# 피부타입별 선호 카테고리 (높은 평점) / 비선호 카테고리 (낮은 평점)
SKIN_TYPE_PREFERENCES = {
    "OS+": {
        "high": ["토너", "미스트", "시카크림", "에센스", "스팟케어", "마스크팩"],
        "low":  ["오일", "젤크림", "클렌징오일"],
    },
    "OS-": {
        "high": ["토너", "세럼", "앰플", "수분크림", "미스트", "마스크팩"],
        "low":  ["오일", "클렌징오일", "영양크림"],
    },
    "ON+": {
        "high": ["젤크림", "클렌징폼", "토너", "에센스", "선크림"],
        "low":  ["오일", "영양크림", "마스크팩"],
    },
    "ON-": {
        "high": ["세럼", "토너", "수분크림", "앰플", "클렌징폼"],
        "low":  ["오일", "젤크림"],
    },
    "DS+": {
        "high": ["크림", "에센스", "마스크팩", "클렌징오일", "앰플"],
        "low":  ["클렌징폼", "젤크림", "미스트"],
    },
    "DS-": {
        "high": ["수분크림", "오일", "앰플", "마스크팩", "에센스"],
        "low":  ["클렌징폼", "미스트", "젤크림"],
    },
    "DN+": {
        "high": ["로션", "에센스", "크림", "클렌징오일", "선크림"],
        "low":  ["스팟케어", "미스트"],
    },
    "DN-": {
        "high": ["수분크림", "오일", "마스크팩", "세럼", "앰플"],
        "low":  ["클렌징폼", "미스트", "젤크림"],
    },
}

REVIEW_TEXTS = {
    "high": [
        "제 피부 타입에 딱 맞아요! 재구매 의사 있습니다.",
        "사용 후 확실히 피부가 좋아진 느낌이에요.",
        "제 피부에 자극 없이 잘 맞네요. 추천해요!",
        "촉촉하고 편안한 사용감이에요. 만족합니다.",
        "꾸준히 사용하니 피부가 정말 좋아졌어요.",
        "성분이 좋고 피부 흡수도 빠른 것 같아요.",
        "제 피부 고민을 해결해줬어요. 강력 추천!",
        "사용감이 부드럽고 냄새도 좋아요.",
    ],
    "mid": [
        "무난하게 쓸 만해요.",
        "가격 대비 괜찮은 것 같아요.",
        "특별히 나쁘지는 않아요.",
        "보통 수준인 것 같습니다.",
        "아직 효과를 잘 모르겠어요.",
    ],
    "low": [
        "제 피부에는 잘 안 맞는 것 같아요.",
        "기대보다 효과가 없네요.",
        "제 피부 타입과 안 맞는 제품인 것 같아요.",
        "사용 후 약간 당기는 느낌이 있어요.",
    ],
}

DUMMY_USER_PREFIX = "derma_dummy_"

# 일반적인 스킨케어 루틴 적용 순서
ROUTINE_STEP_KEYWORDS = [
    "클렌징",
    "토너",
    "미스트",
    "에센스",
    "세럼",
    "앰플",
    "로션",
    "수분크림",
    "젤크림",
    "크림",
    "오일",
    "선크림",
    "마스크팩",
    "스팟케어",
]

ROUTINE_TITLES = [
    "나의 데일리 루틴",
    "아침 스킨케어",
    "저녁 집중 케어",
    "수분 충전 루틴",
    "간단 루틴",
    "민감 피부 루틴",
    "보습 집중 루틴",
    "피지 케어 루틴",
]


def get_category_name(product):
    if product.category:
        return product.category.category_name
    return ""


def get_rating_for_product(skin_type_code, product):
    cat_name = get_category_name(product)
    prefs = SKIN_TYPE_PREFERENCES.get(skin_type_code, {"high": [], "low": []})

    if any(h in cat_name for h in prefs["high"]):
        return random.choices([5, 4], weights=[60, 40])[0], "high"
    elif any(l in cat_name for l in prefs["low"]):
        return random.choices([2, 3, 1], weights=[50, 30, 20])[0], "low"
    else:
        return random.choices([3, 4, 2], weights=[40, 35, 25])[0], "mid"


def create_routine_for_user(user, skin_type_code, all_products):
    prefs = SKIN_TYPE_PREFERENCES.get(skin_type_code, {"high": [], "low": []})
    preferred_cats = prefs["high"]

    # 루틴 키워드별 후보 상품: 선호 카테고리 우선, 없으면 키워드만 매칭
    step_candidates = {}
    for keyword in ROUTINE_STEP_KEYWORDS:
        # 선호 카테고리이면서 해당 키워드 포함
        matched = [
            p for p in all_products
            if keyword in get_category_name(p)
            and any(h in get_category_name(p) for h in preferred_cats)
        ]
        if not matched:
            matched = [p for p in all_products if keyword in get_category_name(p)]
        if matched:
            step_candidates[keyword] = matched

    available_keywords = [k for k in ROUTINE_STEP_KEYWORDS if k in step_candidates]
    if not available_keywords:
        return None

    # 3~7단계 랜덤, 클렌징/토너는 있으면 우선 포함
    num_steps = random.randint(3, 7)
    essential = [k for k in ["클렌징", "토너"] if k in available_keywords]
    optional = [k for k in available_keywords if k not in essential]

    selected = essential[:]
    remaining = num_steps - len(selected)
    if remaining > 0 and optional:
        selected += random.sample(optional, min(remaining, len(optional)))

    # 루틴 순서대로 정렬
    selected.sort(key=lambda k: ROUTINE_STEP_KEYWORDS.index(k))

    routine = UserRoutine.objects.create(
        user=user,
        title=random.choice(ROUTINE_TITLES),
        is_public=random.random() < 0.8,
    )
    for order, keyword in enumerate(selected):
        product = random.choice(step_candidates[keyword])
        UserRoutineStep.objects.create(
            routine=routine,
            product=product,
            step_order=order,
        )
    return routine


def reset_dummy_data():
    dummy_users = User.objects.filter(email__startswith=DUMMY_USER_PREFIX)
    user_ids = list(dummy_users.values_list("user_id", flat=True))
    Review.objects.filter(user_id__in=user_ids).delete()
    ProductLike.objects.filter(user_id__in=user_ids).delete()
    dummy_users.delete()
    print(f"더미 데이터 {len(user_ids)}명 삭제 완료")


def run(users_per_type=20, reviews_per_user=15):
    skin_types = list(SkinTypeMaster.objects.filter(is_active=True))
    if not skin_types:
        print("SkinTypeMaster 데이터가 없습니다. 마스터 데이터를 먼저 넣어주세요.")
        return

    products = list(Product.objects.select_related("category").all()[:300])
    if not products:
        print("Product 데이터가 없습니다. seed_products.py를 먼저 실행해주세요.")
        return

    print(f"피부타입 {len(skin_types)}개 × {users_per_type}명 = {len(skin_types) * users_per_type}명 생성")
    print(f"유저당 최대 {reviews_per_user}개 리뷰")

    total_users = 0
    total_reviews = 0
    total_likes = 0
    total_routines = 0

    for skin_type in skin_types:
        code = skin_type.skin_type_code
        prefs = SKIN_TYPE_PREFERENCES.get(code, {"high": [], "low": []})

        for i in range(1, users_per_type + 1):
            email = f"{DUMMY_USER_PREFIX}{code.lower()}_{i:02d}@dermalens.test"

            if User.objects.filter(email=email).exists():
                continue

            user = User.objects.create(
                email=email,
                password=make_password("dummy1234"),
                nickname=f"{skin_type.skin_type_name_kr}_{i:02d}",
            )
            UserSkinProfile.objects.create(
                user=user,
                skin_type=skin_type,
                sensitivity_level=random.randint(1, 5),
                acne_prone_flag=random.choice([True, False]),
            )
            total_users += 1

            # 리뷰할 상품 선택 (선호 카테고리 위주)
            preferred = [p for p in products if any(h in get_category_name(p) for h in prefs["high"])]
            others = [p for p in products if p not in preferred]

            sample_preferred = random.sample(preferred, min(len(preferred), int(reviews_per_user * 0.7)))
            sample_others = random.sample(others, min(len(others), reviews_per_user - len(sample_preferred)))
            sample_products = sample_preferred + sample_others
            random.shuffle(sample_products)

            reviewed_ids = set()
            for product in sample_products:
                if product.product_id in reviewed_ids:
                    continue
                reviewed_ids.add(product.product_id)

                rating, tier = get_rating_for_product(code, product)
                review_text = random.choice(REVIEW_TEXTS[tier])

                Review.objects.create(
                    user=user,
                    product=product,
                    rating=rating,
                    review_text=review_text,
                )
                total_reviews += 1

                # 4~5점 상품은 좋아요도
                if rating >= 4 and random.random() < 0.6:
                    ProductLike.objects.get_or_create(user=user, product=product)
                    total_likes += 1

            # 루틴 생성 (70% 확률로 1개)
            if random.random() < 0.7:
                routine = create_routine_for_user(user, code, products)
                if routine:
                    total_routines += 1

        print(f"[{code}] {users_per_type}명 완료")

    print(f"\n=== 완료 ===")
    print(f"생성된 유저: {total_users}명")
    print(f"생성된 리뷰: {total_reviews}개")
    print(f"생성된 좋아요: {total_likes}개")
    print(f"생성된 루틴: {total_routines}개")


def main():
    parser = argparse.ArgumentParser(description="피부타입별 더미 데이터 생성")
    parser.add_argument("--reset", action="store_true", help="기존 더미 데이터 삭제 후 재생성")
    parser.add_argument("--users", type=int, default=100, help="피부타입당 유저 수 (기본: 100)")
    parser.add_argument("--reviews", type=int, default=15, help="유저당 리뷰 수 (기본: 15)")
    args = parser.parse_args()

    if args.reset:
        reset_dummy_data()

    run(users_per_type=args.users, reviews_per_user=args.reviews)


if __name__ == "__main__":
    main()
