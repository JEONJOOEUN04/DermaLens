from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Avg, Count
from django.conf import settings
import json
import re
import urllib.request
import urllib.parse

from .models import Ingredient, IngredientAlias, Product, ProductIngredient, Brand, Category, ProductLike


# =====================
# 네이버 쇼핑 API 연동
# =====================

def _strip_html(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _fetch_naver_products(keyword, display=20):
    client_id = getattr(settings, "NAVER_CLIENT_ID", "") or ""
    client_secret = getattr(settings, "NAVER_CLIENT_SECRET", "") or ""
    if not client_id or not client_secret:
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
            return json.loads(resp.read().decode("utf-8")).get("items", [])
    except Exception:
        return []


def _get_or_create_brand(brand_name):
    if not brand_name:
        brand_name = "기타"
    brand, _ = Brand.objects.get_or_create(
        brand_name_kr=brand_name,
        defaults={"brand_name_en": brand_name},
    )
    return brand


def _get_default_category():
    cat = Category.objects.filter(category_name="기타").first()
    if not cat:
        cat = Category.objects.order_by("category_id").first()
    return cat


def _save_naver_item(item):
    """네이버 쇼핑 결과 한 건을 Product DB에 저장하고 반환."""
    product_name = _strip_html(item.get("title", ""))
    if not product_name:
        return None

    brand = _get_or_create_brand(_strip_html(item.get("brand", "")))
    category = _get_default_category()
    if not category:
        return None

    price_str = item.get("lprice", "") or ""
    price = int(price_str) if price_str.isdigit() else None

    product, _ = Product.objects.get_or_create(
        product_name=product_name,
        brand=brand,
        defaults={
            "category": category,
            "image_url": item.get("image", ""),
            "product_url": item.get("link", ""),
            "price": price,
        },
    )
    return product


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

    # DB에 결과 없으면 네이버 API에서 가져와 저장
    if not data and page == 1:
        naver_items = _fetch_naver_products(keyword, display=size)
        for item in naver_items:
            product = _save_naver_item(item)
            if product:
                data.append(_product_to_dict(product))

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


# =====================
# 성분 스캔 기여 (사용자 OCR → 제품 성분 누적 + 리워드)
# =====================

MAX_CONTRIBUTORS = 10          # 제품당 최대 기여자 수
CONFIRM_THRESHOLD = 2          # 성분 확정 기준 (검출 횟수)
REWARD_FIRST = 5               # 최초 등록 리워드 (원)
REWARD_VERIFY = 1             # 추가 검증 리워드 (원)


def _match_ingredient(name):
    """성분명 → DB 매칭: 정확 → alias → 부분일치."""
    name = (name or "").strip()
    if not name:
        return None
    ing = Ingredient.objects.filter(
        Q(ingredient_name_kr__iexact=name) | Q(ingredient_name_en__iexact=name)
    ).first()
    if ing:
        return ing
    alias = IngredientAlias.objects.filter(alias_name__iexact=name, is_active=True).first()
    if alias:
        return alias.ingredient
    return Ingredient.objects.filter(
        Q(ingredient_name_kr__icontains=name) | Q(ingredient_name_en__icontains=name)
    ).first()


def _call_ocr_for_ingredients(image_url):
    """OCR 서버 호출 → 성분 리스트 반환. 실패 시 빈 리스트."""
    ocr_server_url = getattr(settings, "OCR_SERVER_URL", "https://web-production-38634.up.railway.app")
    payload = json.dumps({"user_id": "scan", "image_url": image_url}).encode("utf-8")
    req = urllib.request.Request(
        f"{ocr_server_url}/ocr", data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        # OCR 서버 응답에서 ingredients 추출 (sent_payload 또는 result 안)
        sp = data.get("sent_payload") or data.get("result", {}).get("sent_payload") or {}
        return sp.get("ingredients", []) or data.get("ingredients", [])
    except Exception:
        return []


@csrf_exempt
def ingredient_scan(request, product_id):
    """
    제품 성분표 사진 업로드 → OCR 추출 → 성분 누적 + 리워드 적립.
    - 1인 1제품 1회 / 제품당 최대 10명
    - 최초 기여 5원, 이후 1원 / OCR 실패 시 0원(시도 미차감)
    """
    from products.models import ProductIngredientCandidate, ProductScanContribution
    from users.models import User, PointHistory

    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST 요청만 허용됩니다."}, status=405)

    try:
        product = Product.objects.get(product_id=product_id)
    except Product.DoesNotExist:
        return JsonResponse({"success": False, "message": "제품을 찾을 수 없습니다."}, status=404,
                            json_dumps_params={"ensure_ascii": False})

    user_id = request.POST.get("user_id")
    is_admin = request.POST.get("is_admin") in ("true", "1", "True")
    image_url = request.POST.get("image_url", "")
    image_file = request.FILES.get("image")

    # 이미지 파일 업로드 시 저장
    if image_file and not image_url:
        import os
        import uuid
        upload_dir = os.path.join(settings.MEDIA_ROOT, "scan_images")
        os.makedirs(upload_dir, exist_ok=True)
        # 확장자만 원본에서 추출, 파일명은 URL 안전하게 생성 (공백/한글 방지)
        ext = os.path.splitext(image_file.name)[1].lower() or ".jpg"
        if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic"):
            ext = ".jpg"
        file_name = f"scan_p{product_id}_u{user_id or 'admin'}_{uuid.uuid4().hex[:12]}{ext}"
        file_path = os.path.join(upload_dir, file_name)
        with open(file_path, "wb") as f:
            for chunk in image_file.chunks():
                f.write(chunk)
        base_url = getattr(settings, "BASE_URL", "https://dermalens-production.up.railway.app")
        image_url = f"{base_url}{settings.MEDIA_URL}scan_images/{file_name}"

    if not image_url:
        return JsonResponse({"success": False, "message": "image 또는 image_url이 필요합니다."}, status=400)

    # 사용자 기여인 경우 제한 검사
    if not is_admin:
        if not user_id:
            return JsonResponse({"success": False, "message": "user_id가 필요합니다."}, status=400)
        if ProductScanContribution.objects.filter(user_id=user_id, product=product).exists():
            return JsonResponse({"success": False, "message": "이미 이 제품에 사진을 등록했습니다."}, status=400,
                                json_dumps_params={"ensure_ascii": False})
        contributor_count = ProductScanContribution.objects.filter(product=product).count()
        if contributor_count >= MAX_CONTRIBUTORS:
            return JsonResponse({"success": False, "message": f"이 제품은 이미 {MAX_CONTRIBUTORS}명이 등록을 완료했습니다."}, status=400,
                                json_dumps_params={"ensure_ascii": False})

    # OCR 호출
    raw_ingredients = _call_ocr_for_ingredients(image_url)

    # 성분 정규화 + 후보 누적
    matched_ids = set()
    for name in raw_ingredients:
        ing = _match_ingredient(str(name))
        if ing:
            matched_ids.add(ing.ingredient_id)

    # OCR 실패 (추출 성분 0) → 리워드 0, 시도 미차감
    if not matched_ids:
        return JsonResponse({
            "success": False,
            "message": "성분을 인식하지 못했습니다. 더 선명한 사진으로 다시 시도해주세요.",
            "reward_points": 0,
            "detected_count": 0,
        }, json_dumps_params={"ensure_ascii": False})

    newly_confirmed = []
    for ing_id in matched_ids:
        cand, created = ProductIngredientCandidate.objects.get_or_create(
            product=product, ingredient_id=ing_id,
        )
        if not created:
            cand.detection_count += 1
        # 확정 처리
        if not cand.confirmed and cand.detection_count >= CONFIRM_THRESHOLD:
            cand.confirmed = True
            ProductIngredient.objects.get_or_create(product=product, ingredient_id=ing_id)
            newly_confirmed.append(ing_id)
        cand.save()

    # 관리자는 기록/리워드 없음 (검수용)
    if is_admin:
        return JsonResponse({
            "success": True,
            "message": "관리자 성분 등록 완료",
            "detected_count": len(matched_ids),
            "newly_confirmed": len(newly_confirmed),
            "reward_points": 0,
        }, json_dumps_params={"ensure_ascii": False})

    # 사용자 리워드 계산
    is_first = not ProductScanContribution.objects.filter(product=product).exists()
    reward = REWARD_FIRST if is_first else REWARD_VERIFY

    ProductScanContribution.objects.create(
        user_id=user_id, product=product, image_url=image_url,
        detected_count=len(matched_ids), reward_points=reward, is_first=is_first,
    )

    # 포인트 적립
    user = User.objects.get(user_id=user_id)
    user.points = (user.points or 0) + reward
    user.save(update_fields=["points"])
    PointHistory.objects.create(
        user=user, points=reward,
        reason="성분 등록 최초" if is_first else "성분 등록 검증",
        related_product_id=product_id,
    )

    return JsonResponse({
        "success": True,
        "message": f"성분 등록 완료! {reward}원 적립되었습니다.",
        "detected_count": len(matched_ids),
        "newly_confirmed": len(newly_confirmed),
        "reward_points": reward,
        "total_points": user.points,
        "is_first": is_first,
    }, json_dumps_params={"ensure_ascii": False})
