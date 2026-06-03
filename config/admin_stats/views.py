import datetime
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, Avg, Q
from django.utils import timezone
import json


def _require_staff(request):
    """is_staff 체크. 비관리자면 403 반환, 관리자면 None."""
    from users.models import User
    user_id = request.GET.get("user_id") or request.headers.get("X-User-Id")
    if not user_id:
        return JsonResponse({"success": False, "message": "user_id가 필요합니다."}, status=403)
    try:
        user = User.objects.get(user_id=user_id, is_staff=True)
    except User.DoesNotExist:
        return JsonResponse({"success": False, "message": "관리자 권한이 필요합니다."}, status=403)
    return None


def _parse_date(s, default):
    try:
        return datetime.date.fromisoformat(s)
    except Exception:
        return default


# =====================
# 유저 현황
# =====================

@require_GET
def users_count(request):
    err = _require_staff(request)
    if err:
        return err
    from users.models import User
    now = timezone.now()
    total = User.objects.count()
    active = User.objects.filter(created_at__gte=now - datetime.timedelta(days=30)).count()
    dormant = total - active
    banned = User.objects.filter(is_active=False).count()
    return JsonResponse({
        "success": True,
        "stats": {
            "total": total,
            "active_last_30d": active,
            "dormant": dormant,
            "banned": banned,
        }
    })


@require_GET
def users_signups(request):
    err = _require_staff(request)
    if err:
        return err
    from users.models import User
    period = request.GET.get("period", "daily")
    today = timezone.now().date()

    if period == "weekly":
        default_from = today - datetime.timedelta(weeks=12)
    elif period == "monthly":
        default_from = today - datetime.timedelta(days=365)
    else:
        default_from = today - datetime.timedelta(days=30)

    date_from = _parse_date(request.GET.get("from"), default_from)
    date_to = _parse_date(request.GET.get("to"), today)

    series = []
    total = 0

    if period == "daily":
        d = date_from
        while d <= date_to:
            count = User.objects.filter(created_at__date=d).count()
            series.append({"date": str(d), "count": count})
            total += count
            d += datetime.timedelta(days=1)
    elif period == "weekly":
        d = date_from
        while d <= date_to:
            week_end = min(d + datetime.timedelta(days=6), date_to)
            count = User.objects.filter(created_at__date__gte=d, created_at__date__lte=week_end).count()
            series.append({"date": str(d), "count": count})
            total += count
            d += datetime.timedelta(weeks=1)
    elif period == "monthly":
        d = date_from.replace(day=1)
        while d <= date_to:
            next_month = (d.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
            count = User.objects.filter(created_at__date__gte=d, created_at__date__lt=next_month).count()
            series.append({"date": str(d)[:7], "count": count})
            total += count
            d = next_month

    return JsonResponse({"success": True, "period": period, "series": series, "total": total})


@require_GET
def users_by_skin_type(request):
    err = _require_staff(request)
    if err:
        return err
    from users.models import UserSkinProfile
    dist = list(
        UserSkinProfile.objects
        .select_related("skin_type")
        .values("skin_type__skin_type_code", "skin_type__skin_type_name_kr")
        .annotate(count=Count("profile_id"))
        .order_by("-count")
    )
    distribution = [
        {
            "skin_type_code": d["skin_type__skin_type_code"] or "UNKNOWN",
            "skin_type_name": d["skin_type__skin_type_name_kr"] or "미설정",
            "count": d["count"],
        }
        for d in dist
    ]
    total = sum(d["count"] for d in distribution)
    return JsonResponse({"success": True, "distribution": distribution, "total": total})


@require_GET
def users_by_provider(request):
    err = _require_staff(request)
    if err:
        return err
    from users.models import User
    total = User.objects.count()
    kakao = User.objects.filter(kakao_id__isnull=False).count()
    email = total - kakao
    return JsonResponse({
        "success": True,
        "providers": [
            {"provider": "email", "count": email, "ratio": round(email / total, 3) if total else 0},
            {"provider": "kakao", "count": kakao, "ratio": round(kakao / total, 3) if total else 0},
        ],
        "total": total,
    })


@require_GET
def survey_completion(request):
    err = _require_staff(request)
    if err:
        return err
    from users.models import User, SurveyResponse
    total = User.objects.count()
    completed = SurveyResponse.objects.values("user_id").distinct().count()
    not_completed = total - completed
    return JsonResponse({
        "success": True,
        "completed": completed,
        "not_completed": not_completed,
        "completion_rate": round(completed / total, 3) if total else 0,
    })


# =====================
# 분석 활동
# =====================

@require_GET
def analysis_daily(request):
    err = _require_staff(request)
    if err:
        return err
    from analysis.models import AnalysisResult
    today = timezone.now().date()
    date_from = _parse_date(request.GET.get("from"), today - datetime.timedelta(days=30))
    date_to = _parse_date(request.GET.get("to"), today)

    series = []
    d = date_from
    while d <= date_to:
        ocr = AnalysisResult.objects.filter(created_at__date=d, analysis_type="OCR_INGREDIENT_ANALYSIS").count()
        product_search = AnalysisResult.objects.filter(created_at__date=d, analysis_type="PRODUCT_SEARCH_ANALYSIS").count()
        series.append({"date": str(d), "ocr": ocr, "product_search": product_search, "total": ocr + product_search})
        d += datetime.timedelta(days=1)

    return JsonResponse({"success": True, "series": series})


@require_GET
def analysis_traffic(request):
    err = _require_staff(request)
    if err:
        return err
    from analysis.models import AnalysisResult
    qs = AnalysisResult.objects.exclude(risk_score__isnull=True)
    today = timezone.now().date()
    date_from = _parse_date(request.GET.get("from"), None)
    date_to = _parse_date(request.GET.get("to"), None)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    green = qs.filter(risk_score__lte=2).count()
    yellow = qs.filter(risk_score__gt=2, risk_score__lte=5).count()
    red = qs.filter(risk_score__gt=5).count()
    total = green + yellow + red

    return JsonResponse({
        "success": True,
        "distribution": [
            {"level": "GREEN", "count": green, "ratio": round(green / total, 3) if total else 0},
            {"level": "YELLOW", "count": yellow, "ratio": round(yellow / total, 3) if total else 0},
            {"level": "RED", "count": red, "ratio": round(red / total, 3) if total else 0},
        ],
        "total": total,
    })


@require_GET
def analysis_top_products(request):
    err = _require_staff(request)
    if err:
        return err
    from analysis.models import AnalysisResult
    limit = min(int(request.GET.get("limit", 10)), 50)
    products = list(
        AnalysisResult.objects
        .filter(product_id__isnull=False)
        .select_related("product__brand")
        .values("product_id", "product__product_name", "product__brand__brand_name_kr", "product__image_url")
        .annotate(analysis_count=Count("analysis_id"))
        .order_by("-analysis_count")[:limit]
    )
    return JsonResponse({
        "success": True,
        "products": [
            {
                "product_id": p["product_id"],
                "product_name": p["product__product_name"],
                "brand_name": p["product__brand__brand_name_kr"] or "",
                "image_url": p["product__image_url"] or "",
                "analysis_count": p["analysis_count"],
            }
            for p in products
        ]
    })


@require_GET
def ingredients_top_risk(request):
    err = _require_staff(request)
    if err:
        return err
    from analysis.models import OCR_AnalysisDetail
    limit = min(int(request.GET.get("limit", 10)), 50)
    min_risk = int(request.GET.get("min_risk_level", 1))

    ings = list(
        OCR_AnalysisDetail.objects
        .filter(match_status="MATCHED", ingredient__risk_level__gte=min_risk)
        .select_related("ingredient")
        .values(
            "ingredient_id",
            "ingredient__ingredient_name_kr",
            "ingredient__ingredient_name_en",
            "ingredient__risk_level",
            "ingredient__allergy_flag",
            "ingredient__irritant_flag",
        )
        .annotate(detection_count=Count("analysis_detail_id"))
        .order_by("-detection_count")[:limit]
    )
    return JsonResponse({
        "success": True,
        "ingredients": [
            {
                "ingredient_id": i["ingredient_id"],
                "ingredient_name_kr": i["ingredient__ingredient_name_kr"],
                "ingredient_name_en": i["ingredient__ingredient_name_en"],
                "risk_level": i["ingredient__risk_level"],
                "detection_count": i["detection_count"],
                "allergy_flag": i["ingredient__allergy_flag"],
                "irritant_flag": i["ingredient__irritant_flag"],
            }
            for i in ings
        ]
    })


# =====================
# 제품/리뷰
# =====================

@require_GET
def products_top_rated(request):
    err = _require_staff(request)
    if err:
        return err
    from review.models import Review
    limit = min(int(request.GET.get("limit", 10)), 50)
    min_reviews = int(request.GET.get("min_reviews", 5))

    products = list(
        Review.objects
        .select_related("product__brand")
        .values("product_id", "product__product_name", "product__brand__brand_name_kr", "product__image_url")
        .annotate(avg_rating=Avg("rating"), review_count=Count("review_id"))
        .filter(review_count__gte=min_reviews)
        .order_by("-avg_rating")[:limit]
    )
    return JsonResponse({
        "success": True,
        "products": [
            {
                "product_id": p["product_id"],
                "product_name": p["product__product_name"],
                "brand_name": p["product__brand__brand_name_kr"] or "",
                "image_url": p["product__image_url"] or "",
                "avg_rating": round(p["avg_rating"], 1),
                "review_count": p["review_count"],
            }
            for p in products
        ]
    })


@require_GET
def products_by_category(request):
    err = _require_staff(request)
    if err:
        return err
    from products.models import Product
    limit = int(request.GET.get("limit", 0))  # 0 = 전체
    dist = list(
        Product.objects
        .filter(category__isnull=False)
        .select_related("category")
        .values("category_id", "category__category_name")
        .annotate(count=Count("product_id"))
        .order_by("-count")
    )
    if limit:
        dist = dist[:limit]
    return JsonResponse({
        "success": True,
        "distribution": [
            {
                "category_id": d["category_id"],
                "category_name": d["category__category_name"],
                "count": d["count"],
            }
            for d in dist
        ],
        "total": sum(d["count"] for d in dist),
    }, json_dumps_params={"ensure_ascii": False})


@require_GET
def reviews_list(request):
    err = _require_staff(request)
    if err:
        return err
    from review.models import Review, ReviewImage
    page = int(request.GET.get("page", 1))
    size = int(request.GET.get("size", 20))
    sort = request.GET.get("sort", "recent")
    offset = (page - 1) * size

    qs = Review.objects.select_related("product", "user")
    if sort == "rating_asc":
        qs = qs.order_by("rating", "-created_at")
    elif sort == "rating_desc":
        qs = qs.order_by("-rating", "-created_at")
    else:
        qs = qs.order_by("-created_at")

    total_count = qs.count()
    reviews = qs[offset:offset + size]

    data = [
        {
            "review_id": r.review_id,
            "user_id": r.user_id,
            "nickname": r.user.nickname,
            "product_id": r.product_id,
            "product_name": r.product.product_name,
            "rating": r.rating,
            "review_text": r.review_text,
            "image_count": r.images.count(),
            "created_at": str(r.created_at),
        }
        for r in reviews
    ]
    return JsonResponse({
        "success": True,
        "page": page,
        "size": size,
        "count": len(data),
        "total_count": total_count,
        "total_pages": (total_count + size - 1) // size,
        "reviews": data,
    }, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
def review_moderate(request, review_id):
    from users.models import User
    user_id = request.GET.get("user_id") or request.headers.get("X-User-Id")
    if not user_id or not User.objects.filter(user_id=user_id, is_staff=True).exists():
        return JsonResponse({"success": False, "message": "관리자 권한이 필요합니다."}, status=403)

    if request.method != "PATCH":
        return JsonResponse({"success": False, "message": "PATCH 요청만 허용됩니다."}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"success": False, "message": "JSON 형식이 올바르지 않습니다."}, status=400)

    from review.models import Review
    action = data.get("action")
    try:
        review = Review.objects.get(review_id=review_id)
    except Review.DoesNotExist:
        return JsonResponse({"success": False, "message": "리뷰를 찾을 수 없습니다."}, status=404,
                            json_dumps_params={"ensure_ascii": False})

    if action == "delete":
        review.delete()
        return JsonResponse({"success": True, "review_id": review_id, "status": "deleted"},
                            json_dumps_params={"ensure_ascii": False})

    return JsonResponse({"success": True, "review_id": review_id, "action": action},
                        json_dumps_params={"ensure_ascii": False})


# =====================
# 챗봇
# =====================

@require_GET
def chat_usage(request):
    err = _require_staff(request)
    if err:
        return err
    from analysis.models import ChatMessage, ChatSession
    today = timezone.now().date()
    date_from = _parse_date(request.GET.get("from"), today - datetime.timedelta(days=30))
    date_to = _parse_date(request.GET.get("to"), today)

    series = []
    d = date_from
    while d <= date_to:
        sessions = ChatSession.objects.filter(created_at__date=d).count()
        messages = ChatMessage.objects.filter(message_type="USER", created_at__date=d).count()
        series.append({"date": str(d), "sessions": sessions, "messages": messages})
        d += datetime.timedelta(days=1)

    total_sessions = ChatSession.objects.count()
    total_messages = ChatMessage.objects.filter(message_type="USER").count()
    avg = round(total_messages / total_sessions, 1) if total_sessions else 0

    return JsonResponse({
        "success": True,
        "series": series,
        "total_sessions": total_sessions,
        "total_messages": total_messages,
        "avg_messages_per_session": avg,
    })


@require_GET
def chat_intents(request):
    err = _require_staff(request)
    if err:
        return err
    from analysis.models import ChatMessage
    dist = list(
        ChatMessage.objects
        .filter(message_type="BOT")
        .exclude(intent__isnull=True)
        .values("intent")
        .annotate(count=Count("message_id"))
        .order_by("-count")
    )
    total = sum(d["count"] for d in dist)
    return JsonResponse({
        "success": True,
        "distribution": [
            {"intent": d["intent"], "count": d["count"], "ratio": round(d["count"] / total, 3) if total else 0}
            for d in dist
        ],
        "total": total,
    })
