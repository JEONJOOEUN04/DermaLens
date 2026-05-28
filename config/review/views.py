import json
import os

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.db.models import Avg
from django.conf import settings

from .models import Review, ReviewImage, Feedback, SearchLog, ProductView, ExternalSource, DataSyncHistory
from products.models import Product


# =====================
# 리뷰 CRUD
# =====================

@csrf_exempt
def create_review(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST 요청만 허용됩니다."}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "JSON 형식이 올바르지 않습니다."}, status=400)

    user_id = data.get("user_id")
    product_id = data.get("product_id")
    rating = data.get("rating")
    review_text = data.get("review_text", "")

    if not user_id or not product_id or rating is None:
        return JsonResponse({"success": False, "message": "user_id, product_id, rating이 필요합니다."}, status=400)

    if not isinstance(rating, int) or not (1 <= rating <= 5):
        return JsonResponse({"success": False, "message": "rating은 1~5 정수여야 합니다."}, status=400)

    if Review.objects.filter(user_id=user_id, product_id=product_id).exists():
        return JsonResponse({"success": False, "message": "이미 해당 제품에 리뷰를 작성했습니다."}, status=400,
                            json_dumps_params={"ensure_ascii": False})

    review = Review.objects.create(
        user_id=user_id,
        product_id=product_id,
        rating=rating,
        review_text=review_text,
    )

    return JsonResponse(
        {"success": True, "message": "리뷰가 등록되었습니다.", "review_id": review.review_id},
        status=201,
        json_dumps_params={"ensure_ascii": False},
    )


@csrf_exempt
def update_review(request, review_id):
    if request.method not in ("POST", "PATCH", "PUT"):
        return JsonResponse({"success": False, "message": "POST/PATCH 요청만 허용됩니다."}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "JSON 형식이 올바르지 않습니다."}, status=400)

    user_id = data.get("user_id")

    try:
        review = Review.objects.get(review_id=review_id, user_id=user_id)
    except Review.DoesNotExist:
        return JsonResponse({"success": False, "message": "리뷰를 찾을 수 없거나 권한이 없습니다."}, status=404,
                            json_dumps_params={"ensure_ascii": False})

    if "rating" in data:
        rating = data["rating"]
        if not isinstance(rating, int) or not (1 <= rating <= 5):
            return JsonResponse({"success": False, "message": "rating은 1~5 정수여야 합니다."}, status=400)
        review.rating = rating
    if "review_text" in data:
        review.review_text = data["review_text"]

    review.save()

    return JsonResponse(
        {"success": True, "message": "리뷰가 수정되었습니다.", "review_id": review.review_id},
        json_dumps_params={"ensure_ascii": False},
    )


@csrf_exempt
def delete_review(request, review_id):
    if request.method != "DELETE":
        return JsonResponse({"success": False, "message": "DELETE 요청만 허용됩니다."}, status=405)

    user_id = request.GET.get("user_id")
    if not user_id:
        try:
            data = json.loads(request.body.decode("utf-8"))
            user_id = data.get("user_id")
        except Exception:
            pass

    try:
        review = Review.objects.get(review_id=review_id, user_id=user_id)
    except Review.DoesNotExist:
        return JsonResponse({"success": False, "message": "리뷰를 찾을 수 없거나 권한이 없습니다."}, status=404,
                            json_dumps_params={"ensure_ascii": False})

    review.delete()
    return JsonResponse({"success": True, "message": "리뷰가 삭제되었습니다."}, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
def upload_review_images(request, review_id):
    """리뷰 이미지 업로드 (multipart, 최대 5장)."""
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST 요청만 허용됩니다."}, status=405)

    user_id = request.POST.get("user_id")
    try:
        review = Review.objects.get(review_id=review_id, user_id=user_id)
    except Review.DoesNotExist:
        return JsonResponse({"success": False, "message": "리뷰를 찾을 수 없거나 권한이 없습니다."}, status=404,
                            json_dumps_params={"ensure_ascii": False})

    files = request.FILES.getlist("images")
    if not files:
        return JsonResponse({"success": False, "message": "images 파일이 필요합니다."}, status=400)

    current_count = ReviewImage.objects.filter(review=review).count()
    if current_count + len(files) > 5:
        return JsonResponse({"success": False, "message": f"이미지는 최대 5장까지 등록 가능합니다. (현재 {current_count}장)"}, status=400,
                            json_dumps_params={"ensure_ascii": False})

    upload_dir = os.path.join(settings.MEDIA_ROOT, "review_images")
    os.makedirs(upload_dir, exist_ok=True)

    saved = []
    for idx, f in enumerate(files):
        file_name = f"review{review_id}_user{user_id}_{current_count + idx}_{f.name}"
        file_path = os.path.join(upload_dir, file_name)
        with open(file_path, "wb") as fp:
            for chunk in f.chunks():
                fp.write(chunk)
        image_url = f"{settings.MEDIA_URL}review_images/{file_name}"
        img = ReviewImage.objects.create(review=review, image_url=image_url, order=current_count + idx)
        saved.append({"image_id": img.image_id, "image_url": image_url})

    return JsonResponse({"success": True, "uploaded": saved}, status=201, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
def delete_review_image(request, review_id, image_id):
    """리뷰 이미지 단건 삭제."""
    if request.method != "DELETE":
        return JsonResponse({"success": False, "message": "DELETE 요청만 허용됩니다."}, status=405)

    user_id = request.GET.get("user_id")
    try:
        review = Review.objects.get(review_id=review_id, user_id=user_id)
        img = ReviewImage.objects.get(image_id=image_id, review=review)
    except (Review.DoesNotExist, ReviewImage.DoesNotExist):
        return JsonResponse({"success": False, "message": "이미지를 찾을 수 없거나 권한이 없습니다."}, status=404,
                            json_dumps_params={"ensure_ascii": False})

    img.delete()
    return JsonResponse({"success": True, "message": "이미지가 삭제되었습니다."}, json_dumps_params={"ensure_ascii": False})


@require_GET
def product_reviews(request, product_id):
    """제품 리뷰 목록 (최신순 / 인기순)."""
    sort = request.GET.get("sort", "latest")  # latest | rating
    page = int(request.GET.get("page", 1))
    size = int(request.GET.get("size", 20))
    offset = (page - 1) * size

    qs = Review.objects.filter(product_id=product_id).select_related("user")
    if sort == "rating":
        qs = qs.order_by("-rating", "-created_at")
    else:
        qs = qs.order_by("-created_at")

    reviews = qs[offset:offset + size]
    avg_rating = Review.objects.filter(product_id=product_id).aggregate(avg=Avg("rating"))["avg"]

    data = [
        {
            "review_id": r.review_id,
            "user_id": r.user_id,
            "nickname": r.user.nickname,
            "rating": r.rating,
            "review_text": r.review_text,
            "images": [{"image_id": img.image_id, "image_url": img.image_url} for img in r.images.all()],
            "created_at": str(r.created_at),
            "updated_at": str(r.updated_at),
        }
        for r in reviews
    ]

    return JsonResponse(
        {
            "success": True,
            "product_id": product_id,
            "avg_rating": round(avg_rating, 2) if avg_rating else None,
            "page": page,
            "count": len(data),
            "reviews": data,
        },
        json_dumps_params={"ensure_ascii": False},
    )


@require_GET
def user_reviews(request, user_id):
    """사용자가 작성한 리뷰 목록."""
    page = int(request.GET.get("page", 1))
    size = int(request.GET.get("size", 20))
    offset = (page - 1) * size

    reviews = Review.objects.filter(user_id=user_id).select_related("product").order_by("-created_at")[offset:offset + size]

    data = [
        {
            "review_id": r.review_id,
            "product_id": r.product_id,
            "product_name": r.product.product_name,
            "rating": r.rating,
            "review_text": r.review_text,
            "images": [{"image_id": img.image_id, "image_url": img.image_url} for img in r.images.all()],
            "created_at": str(r.created_at),
            "updated_at": str(r.updated_at),
        }
        for r in reviews
    ]

    return JsonResponse(
        {"success": True, "user_id": user_id, "page": page, "count": len(data), "reviews": data},
        json_dumps_params={"ensure_ascii": False},
    )


# =====================
# 피드백
# =====================

@csrf_exempt
def create_feedback(request):
    """만족도 평가 / 부작용 신고 / 문의 등록."""
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST 요청만 허용됩니다."}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "JSON 형식이 올바르지 않습니다."}, status=400)

    user_id = data.get("user_id")
    feedback_type = data.get("feedback_type", "")  # SATISFACTION / SIDE_EFFECT / INQUIRY

    if not user_id or not feedback_type:
        return JsonResponse({"success": False, "message": "user_id와 feedback_type이 필요합니다."}, status=400)

    valid_types = {"SATISFACTION", "SIDE_EFFECT", "INQUIRY"}
    if feedback_type not in valid_types:
        return JsonResponse(
            {"success": False, "message": f"feedback_type은 {valid_types} 중 하나여야 합니다."},
            status=400,
            json_dumps_params={"ensure_ascii": False},
        )

    feedback = Feedback.objects.create(
        user_id=user_id,
        product_id=data.get("product_id"),
        feedback_type=feedback_type,
        satisfaction_score=data.get("satisfaction_score"),
        side_effect_text=data.get("side_effect_text", ""),
    )

    return JsonResponse(
        {"success": True, "message": "피드백이 등록되었습니다.", "feedback_id": feedback.feedback_id},
        status=201,
        json_dumps_params={"ensure_ascii": False},
    )


@require_GET
def feedback_list(request, user_id):
    feedbacks = Feedback.objects.filter(user_id=user_id).order_by("-created_at")[:50]
    data = [
        {
            "feedback_id": f.feedback_id,
            "product_id": f.product_id,
            "feedback_type": f.feedback_type,
            "satisfaction_score": f.satisfaction_score,
            "side_effect_text": f.side_effect_text,
            "created_at": str(f.created_at),
        }
        for f in feedbacks
    ]
    return JsonResponse(
        {"success": True, "count": len(data), "feedbacks": data},
        json_dumps_params={"ensure_ascii": False},
    )


# =====================
# 검색 로그
# =====================

@csrf_exempt
def log_search(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST 요청만 허용됩니다."}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "JSON 형식이 올바르지 않습니다."}, status=400)

    user_id = data.get("user_id")
    keyword = data.get("keyword", "").strip()

    if not user_id or not keyword:
        return JsonResponse({"success": False, "message": "user_id와 keyword가 필요합니다."}, status=400)

    log = SearchLog.objects.create(
        user_id=user_id,
        keyword=keyword,
        clicked_product_id=data.get("clicked_product_id"),
    )
    return JsonResponse({"success": True, "log_id": log.search_id}, json_dumps_params={"ensure_ascii": False})


@require_GET
def search_history(request, user_id):
    """최근 검색어 (중복 제거, 최신 기준 20개)."""
    seen = set()
    data = []
    logs = SearchLog.objects.filter(user_id=user_id).order_by("-created_at")[:200]
    for l in logs:
        if l.keyword not in seen:
            seen.add(l.keyword)
            data.append({
                "keyword": l.keyword,
                "created_at": str(l.created_at),
            })
        if len(data) >= 20:
            break
    return JsonResponse(
        {"success": True, "count": len(data), "search_history": data},
        json_dumps_params={"ensure_ascii": False},
    )


@csrf_exempt
def log_product_view(request):
    """최근 본 제품 로그 저장."""
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

    ProductView.objects.create(user_id=user_id, product_id=product_id)
    return JsonResponse({"success": True}, json_dumps_params={"ensure_ascii": False})


@require_GET
def recently_viewed(request, user_id):
    """최근 본 제품 목록 (중복 제거, 최대 20개)."""
    seen = set()
    results = []
    logs = ProductView.objects.filter(user_id=user_id).select_related("product__brand").order_by("-viewed_at")[:100]
    for log in logs:
        if log.product_id not in seen:
            seen.add(log.product_id)
            p = log.product
            results.append({
                "product_id": p.product_id,
                "product_name": p.product_name,
                "image_url": p.image_url,
                "price": p.price,
                "brand_name": p.brand.brand_name_kr if p.brand else "",
                "viewed_at": str(log.viewed_at),
            })
        if len(results) >= 20:
            break
    return JsonResponse(
        {"success": True, "count": len(results), "products": results},
        json_dumps_params={"ensure_ascii": False},
    )


@require_GET
def trending_searches(request):
    """급상승 검색어 (최근 7일 기준 검색 횟수 상위 10개)."""
    import datetime
    from django.utils import timezone
    from django.db.models import Count

    week_ago = timezone.now() - datetime.timedelta(days=7)
    keywords = (
        SearchLog.objects
        .filter(created_at__gte=week_ago)
        .values("keyword")
        .annotate(count=Count("search_id"))
        .order_by("-count")[:10]
    )
    data = [{"keyword": k["keyword"], "count": k["count"]} for k in keywords]
    return JsonResponse(
        {"success": True, "trending": data},
        json_dumps_params={"ensure_ascii": False},
    )


# =====================
# 외부 데이터 동기화 이력
# =====================

@require_GET
def sync_history(request):
    histories = DataSyncHistory.objects.select_related("source").order_by("-sync_id")[:50]
    data = [
        {
            "sync_id": h.sync_id,
            "source_name": h.source.source_name,
            "inserted_count": h.inserted_count,
            "updated_count": h.updated_count,
        }
        for h in histories
    ]
    return JsonResponse({"success": True, "count": len(data), "sync_history": data},
                        json_dumps_params={"ensure_ascii": False})
