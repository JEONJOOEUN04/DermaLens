import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.db.models import Count, Avg

from .models import Recommendation
from products.models import Product, ProductIngredient, ProductLike


# =====================
# 추천 알고리즘 핵심 로직
# =====================

def _compute_recommendation_score(product, user_profile, review_avg=None, like_count=0, allergy_names=None):
    """
    제품 추천 점수 계산 (0~100점).
    효능 적합도(40) + 위험 감점(-30) + 리뷰(20) + 인기도(10)
    """
    if user_profile is None:
        base = 50.0
        if review_avg:
            base += (review_avg - 3) * 4
        base += min(like_count * 0.5, 10)
        return round(min(max(base, 0), 100), 2), "인기 및 평점 기반 추천"

    score = 50.0
    reasons = []

    skin_type_code = user_profile.skin_type.skin_type_code if user_profile.skin_type else None
    acne_prone = user_profile.acne_prone_flag or False
    sensitivity = user_profile.sensitivity_level or 3
    avoidance_keywords = [n.lower() for n in (allergy_names or []) if n]

    mappings = ProductIngredient.objects.filter(product=product).select_related("ingredient")
    ingredients = [m.ingredient for m in mappings]

    moisturizing_count = 0
    soothing_count = 0
    risk_penalty = 0
    acne_penalty = 0
    avoidance_penalty = 0

    for ing in ingredients:
        risk = ing.risk_level or 0

        if skin_type_code and "S" in skin_type_code and ing.irritant_flag:
            risk_penalty += 3
        if acne_prone and ing.acne_caution_flag:
            acne_penalty += 2
        if risk >= 6:
            risk_penalty += 4
        elif risk >= 4:
            risk_penalty += 2
        if ing.moisturizing_flag:
            moisturizing_count += 1
        if ing.soothing_flag:
            soothing_count += 1

        kr = (ing.ingredient_name_kr or "").lower()
        en = (ing.ingredient_name_en or "").lower()
        for kw in avoidance_keywords:
            if kw and (kw in kr or kw in en):
                avoidance_penalty += 10
                break

    # 피부 타입별 효능 가산
    if skin_type_code and skin_type_code.startswith("D") and moisturizing_count > 0:
        efficacy_score = min(moisturizing_count * 5, 30)
        reasons.append(f"건성 피부에 적합한 보습 성분 {moisturizing_count}개 포함")
    elif skin_type_code and "S" in skin_type_code and soothing_count > 0:
        efficacy_score = min(soothing_count * 5, 30)
        reasons.append(f"민감성 피부에 적합한 진정 성분 {soothing_count}개 포함")
    elif skin_type_code and skin_type_code.startswith("O") and moisturizing_count > 0:
        efficacy_score = min(moisturizing_count * 3, 20)
        reasons.append("지성 피부용 가벼운 보습 성분 포함")
    else:
        efficacy_score = min((moisturizing_count + soothing_count) * 3, 20)

    score += efficacy_score
    score -= min(risk_penalty, 30)
    score -= min(acne_penalty, 15)
    score -= min(avoidance_penalty, 20)

    if review_avg:
        score += (review_avg - 3) * 3
    score += min(like_count * 0.5, 10)

    if sensitivity >= 4:
        score -= risk_penalty * 0.5

    score = round(min(max(score, 0), 100), 2)

    if not reasons:
        reasons.append("피부 타입 기반 추천")
    if avoidance_penalty > 0:
        reasons.append("⚠️ 기피 성분 포함")

    return score, " / ".join(reasons)


# =====================
# 개인화 추천 생성
# =====================

@csrf_exempt
def generate_recommendation(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST 요청만 허용됩니다."}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "JSON 형식이 올바르지 않습니다."}, status=400)

    user_id = data.get("user_id")
    category_id = data.get("category_id")
    top_n = int(data.get("top_n", 10))

    if not user_id:
        return JsonResponse({"success": False, "message": "user_id가 필요합니다."}, status=400)

    from users.models import UserSkinProfile, UserAllergy
    from review.models import Review

    user_profile = UserSkinProfile.objects.filter(user_id=user_id).select_related("skin_type").first()
    allergy_names = list(
        UserAllergy.objects.filter(user_id=user_id)
        .select_related("allergy")
        .values_list("allergy__allergy_name_kr", flat=True)
    )

    products_qs = Product.objects.select_related("brand", "category")
    if category_id:
        products_qs = products_qs.filter(category_id=category_id)

    liked_ids = ProductLike.objects.filter(user_id=user_id).values_list("product_id", flat=True)
    products_qs = products_qs.exclude(product_id__in=liked_ids)

    review_avgs = {
        row["product_id"]: row["avg"]
        for row in Review.objects.values("product_id").annotate(avg=Avg("rating"))
    }
    like_counts = {
        row["product_id"]: row["cnt"]
        for row in ProductLike.objects.values("product_id").annotate(cnt=Count("pk"))
    }

    scored = []
    for product in products_qs[:200]:
        review_avg = review_avgs.get(product.product_id)
        like_count = like_counts.get(product.product_id, 0)
        score, reason = _compute_recommendation_score(
            product, user_profile, review_avg, like_count, allergy_names
        )
        scored.append((score, reason, product))

    scored.sort(key=lambda x: x[0], reverse=True)

    Recommendation.objects.filter(user_id=user_id).delete()

    results = []
    for rank, (score, reason, product) in enumerate(scored[:top_n], 1):
        rec = Recommendation.objects.create(
            user_id=user_id, product=product,
            score=score, reason=reason, rank_order=rank,
        )
        results.append({
            "recommendation_id": rec.recommendation_id,
            "rank_order": rank,
            "product_id": product.product_id,
            "product_name": product.product_name,
            "image_url": product.image_url,
            "price": product.price,
            "score": score,
            "reason": reason,
        })

    return JsonResponse(
        {"success": True, "message": f"추천 생성 완료 ({len(results)}개)", "recommendations": results},
        json_dumps_params={"ensure_ascii": False},
    )


@require_GET
def recommendation_list(request, user_id):
    page = int(request.GET.get("page", 1))
    size = int(request.GET.get("size", 20))
    offset = (page - 1) * size

    recs = (
        Recommendation.objects.filter(user_id=user_id)
        .select_related("product", "product__brand")
        .order_by("rank_order", "-score")[offset:offset + size]
    )
    data = [
        {
            "recommendation_id": r.recommendation_id,
            "rank_order": r.rank_order,
            "product_id": r.product_id,
            "product_name": r.product.product_name,
            "brand_name": r.product.brand.brand_name_kr if r.product.brand else None,
            "image_url": r.product.image_url,
            "price": r.product.price,
            "score": r.score,
            "reason": r.reason,
            "created_at": str(r.created_at),
        }
        for r in recs
    ]
    return JsonResponse(
        {"success": True, "page": page, "count": len(data), "recommendations": data},
        json_dumps_params={"ensure_ascii": False},
    )


@csrf_exempt
def save_recommendation(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST 요청만 허용됩니다."}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "JSON 형식이 올바르지 않습니다."}, status=400)

    rec = Recommendation.objects.create(
        user_id=data.get("user_id"),
        product_id=data.get("product_id"),
        score=data.get("score", 0),
        reason=data.get("reason", ""),
        rank_order=data.get("rank_order"),
    )
    return JsonResponse(
        {"success": True, "recommendation_id": rec.recommendation_id},
        json_dumps_params={"ensure_ascii": False},
    )


# =====================
# 좋아요
# =====================

@csrf_exempt
def product_like(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST 요청만 허용됩니다."}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "JSON 형식이 올바르지 않습니다."}, status=400)

    user_id = data.get("user_id")
    product_id = data.get("product_id")

    if not user_id or not product_id:
        return JsonResponse({"success": False, "message": "user_id와 product_id가 필요합니다."}, status=400)

    if not Product.objects.filter(product_id=product_id).exists():
        return JsonResponse({"success": False, "message": "존재하지 않는 제품입니다."}, status=404,
                            json_dumps_params={"ensure_ascii": False})

    existing = ProductLike.objects.filter(user_id=user_id, product_id=product_id).first()
    if existing:
        existing.delete()
        liked = False
        message = "좋아요 취소"
    else:
        ProductLike.objects.create(user_id=user_id, product_id=product_id)
        liked = True
        message = "좋아요 추가"

    like_count = ProductLike.objects.filter(product_id=product_id).count()
    return JsonResponse(
        {"success": True, "message": message, "liked": liked, "like_count": like_count},
        json_dumps_params={"ensure_ascii": False},
    )


@require_GET
def product_like_status(request, user_id, product_id):
    liked = ProductLike.objects.filter(user_id=user_id, product_id=product_id).exists()
    like_count = ProductLike.objects.filter(product_id=product_id).count()
    return JsonResponse(
        {"success": True, "liked": liked, "like_count": like_count},
        json_dumps_params={"ensure_ascii": False},
    )
