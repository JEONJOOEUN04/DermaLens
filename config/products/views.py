from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Avg, Count
import json

from .models import Ingredient, IngredientAlias, Product, ProductIngredient, Brand, Category, ProductLike


def _product_to_dict(item, like_count=None):
    return {
        "product_id": item.product_id,
        "product_name": item.product_name,
        "brand_name": item.brand.brand_name_kr if item.brand else None,
        "category_name": item.category.category_name if item.category else None,
        "image_url": item.image_url,
        "product_url": item.product_url,
        "volume": item.volume,
        "price": item.price,
        "description": item.description,
        "like_count": like_count,
    }


def _ingredient_to_dict(item):
    return {
        "ingredient_id": item.ingredient_id,
        "ingredient_name_kr": item.ingredient_name_kr,
        "ingredient_name_en": item.ingredient_name_en,
        "risk_level": item.risk_level,
        "allergy_flag": item.allergy_flag,
        "irritant_flag": item.irritant_flag,
        "acne_caution_flag": item.acne_caution_flag,
        "moisturizing_flag": item.moisturizing_flag,
        "soothing_flag": item.soothing_flag,
        "description": item.description,
    }


# =====================
# 성분 API
# =====================

@require_GET
def ingredient_list(request):
    page = int(request.GET.get("page", 1))
    size = int(request.GET.get("size", 50))
    offset = (page - 1) * size

    ingredients = Ingredient.objects.all().order_by("ingredient_id")[offset:offset + size]
    data = [_ingredient_to_dict(i) for i in ingredients]

    return JsonResponse(
        {"success": True, "page": page, "count": len(data), "ingredients": data},
        json_dumps_params={"ensure_ascii": False},
    )


@require_GET
def ingredient_search(request):
    name = request.GET.get("name", "").strip()
    if not name:
        return JsonResponse({"success": False, "message": "name 파라미터가 필요합니다."}, status=400,
                            json_dumps_params={"ensure_ascii": False})

    # 정확 일치 → alias 매칭 → 부분 일치 순으로 조회
    exact = Ingredient.objects.filter(
        Q(ingredient_name_kr__iexact=name) | Q(ingredient_name_en__iexact=name)
    )
    alias_ids = IngredientAlias.objects.filter(alias_name__iexact=name).values_list("ingredient_id", flat=True)
    partial = Ingredient.objects.filter(
        Q(ingredient_name_kr__icontains=name) | Q(ingredient_name_en__icontains=name)
    ).exclude(ingredient_id__in=exact.values_list("ingredient_id", flat=True))

    alias_qs = Ingredient.objects.filter(ingredient_id__in=alias_ids).exclude(
        ingredient_id__in=exact.values_list("ingredient_id", flat=True)
    )

    combined = list(exact) + list(alias_qs) + list(partial)
    seen = set()
    results = []
    for i in combined:
        if i.ingredient_id not in seen:
            seen.add(i.ingredient_id)
            results.append(i)
        if len(results) >= 30:
            break

    data = [_ingredient_to_dict(i) for i in results]

    return JsonResponse(
        {"success": True, "keyword": name, "count": len(data), "results": data},
        json_dumps_params={"ensure_ascii": False},
    )


@require_GET
def ingredient_detail(request, ingredient_id):
    try:
        item = Ingredient.objects.get(ingredient_id=ingredient_id)
        aliases = list(IngredientAlias.objects.filter(ingredient=item).values_list("alias_name", flat=True))
        d = _ingredient_to_dict(item)
        d["aliases"] = aliases
        return JsonResponse({"success": True, "ingredient": d}, json_dumps_params={"ensure_ascii": False})
    except Ingredient.DoesNotExist:
        return JsonResponse({"success": False, "message": "해당 성분을 찾을 수 없습니다."}, status=404,
                            json_dumps_params={"ensure_ascii": False})


# =====================
# 제품 API
# =====================

@require_GET
def product_list(request):
    page = int(request.GET.get("page", 1))
    size = int(request.GET.get("size", 20))
    offset = (page - 1) * size

    products = Product.objects.select_related("brand", "category").order_by("product_id")[offset:offset + size]
    data = [_product_to_dict(p) for p in products]

    return JsonResponse(
        {"success": True, "page": page, "count": len(data), "products": data},
        json_dumps_params={"ensure_ascii": False},
    )


@require_GET
def product_detail(request, product_id):
    try:
        item = Product.objects.select_related("brand", "category").get(product_id=product_id)

        # 평균 평점
        from review.models import Review
        avg_rating = Review.objects.filter(product=item).aggregate(avg=Avg("rating"))["avg"]
        review_count = Review.objects.filter(product=item).count()

        like_count = ProductLike.objects.filter(product=item).count()

        d = _product_to_dict(item, like_count=like_count)
        d["avg_rating"] = round(avg_rating, 2) if avg_rating else None
        d["review_count"] = review_count
        d["official_ingredient_text"] = item.official_ingredient_text

        return JsonResponse({"success": True, "product": d}, json_dumps_params={"ensure_ascii": False})
    except Product.DoesNotExist:
        return JsonResponse({"success": False, "message": "해당 제품을 찾을 수 없습니다."}, status=404,
                            json_dumps_params={"ensure_ascii": False})


@require_GET
def product_search(request):
    """키워드로 제품명·브랜드명 검색 + 검색 로그 저장."""
    keyword = request.GET.get("q", "").strip()
    page = int(request.GET.get("page", 1))
    size = int(request.GET.get("size", 20))
    offset = (page - 1) * size

    if not keyword:
        return JsonResponse({"success": False, "message": "q 파라미터가 필요합니다."}, status=400,
                            json_dumps_params={"ensure_ascii": False})

    products = Product.objects.select_related("brand", "category").filter(
        Q(product_name__icontains=keyword)
        | Q(brand__brand_name_kr__icontains=keyword)
        | Q(brand__brand_name_en__icontains=keyword)
        | Q(description__icontains=keyword)
    ).order_by("product_id")[offset:offset + size]

    data = [_product_to_dict(p) for p in products]

    # 검색 로그 저장 (user_id 선택적)
    user_id = request.GET.get("user_id")
    if user_id:
        try:
            from review.models import SearchLog
            SearchLog.objects.create(user_id=int(user_id), keyword=keyword)
        except Exception:
            pass

    return JsonResponse(
        {"success": True, "keyword": keyword, "page": page, "count": len(data), "products": data},
        json_dumps_params={"ensure_ascii": False},
    )


@require_GET
def product_by_category(request, category_id):
    """카테고리 기반 제품 목록."""
    page = int(request.GET.get("page", 1))
    size = int(request.GET.get("size", 20))
    offset = (page - 1) * size

    products = Product.objects.select_related("brand", "category").filter(
        category_id=category_id
    ).order_by("product_id")[offset:offset + size]

    data = [_product_to_dict(p) for p in products]

    return JsonResponse(
        {"success": True, "category_id": category_id, "page": page, "count": len(data), "products": data},
        json_dumps_params={"ensure_ascii": False},
    )


@require_GET
def product_popular(request):
    """좋아요 수 기준 인기 상품."""
    page = int(request.GET.get("page", 1))
    size = int(request.GET.get("size", 20))
    offset = (page - 1) * size

    like_counts = (
        ProductLike.objects.values("product_id")
        .annotate(like_count=Count("pk"))
        .order_by("-like_count")
    )

    product_ids_ordered = [row["product_id"] for row in like_counts[offset:offset + size]]

    if not product_ids_ordered:
        # 좋아요 데이터 없으면 등록 순으로 반환
        products = Product.objects.select_related("brand", "category").order_by("product_id")[offset:offset + size]
        data = [_product_to_dict(p) for p in products]
    else:
        product_map = {
            p.product_id: p
            for p in Product.objects.select_related("brand", "category").filter(product_id__in=product_ids_ordered)
        }
        like_map = {row["product_id"]: row["like_count"] for row in like_counts}
        data = [
            _product_to_dict(product_map[pid], like_count=like_map.get(pid, 0))
            for pid in product_ids_ordered
            if pid in product_map
        ]

    return JsonResponse(
        {"success": True, "page": page, "count": len(data), "products": data},
        json_dumps_params={"ensure_ascii": False},
    )


@require_GET
def product_ingredients(request, product_id):
    """제품의 성분 목록 조회."""
    if not Product.objects.filter(product_id=product_id).exists():
        return JsonResponse({"success": False, "message": "해당 제품을 찾을 수 없습니다."}, status=404,
                            json_dumps_params={"ensure_ascii": False})

    mappings = ProductIngredient.objects.filter(product_id=product_id).select_related("ingredient")
    data = [_ingredient_to_dict(m.ingredient) for m in mappings]

    return JsonResponse(
        {"success": True, "product_id": product_id, "count": len(data), "ingredients": data},
        json_dumps_params={"ensure_ascii": False},
    )


@require_GET
def category_list(request):
    categories = Category.objects.filter(parent__isnull=True).order_by("category_id")
    data = []
    for cat in categories:
        children = list(Category.objects.filter(parent=cat).values("category_id", "category_name"))
        data.append({
            "category_id": cat.category_id,
            "category_name": cat.category_name,
            "subcategories": children,
        })
    return JsonResponse({"success": True, "categories": data}, json_dumps_params={"ensure_ascii": False})
