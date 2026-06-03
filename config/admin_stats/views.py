import datetime
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Count, Avg
from django.utils import timezone


@require_GET
def stats(request):
    from users.models import User, UserSkinProfile, SurveyResponse
    from products.models import Product, ProductLike
    from review.models import Review, SearchLog
    from analysis.models import AnalysisResult, OCR_AnalysisDetail
    from analysis.models import ChatMessage

    now = timezone.now()
    today = now.date()
    week_ago = now - datetime.timedelta(days=7)
    month_ago = now - datetime.timedelta(days=30)

    # =====================
    # 유저 현황
    # =====================
    total_users = User.objects.count()
    new_today = User.objects.filter(created_at__date=today).count()
    new_this_week = User.objects.filter(created_at__gte=week_ago).count()

    survey_users = SurveyResponse.objects.values("user_id").distinct().count()
    kakao_users = User.objects.filter(kakao_id__isnull=False).count()

    skin_dist = list(
        UserSkinProfile.objects
        .select_related("skin_type")
        .values("skin_type__skin_type_code")
        .annotate(count=Count("profile_id"))
        .order_by("-count")
    )
    skin_distribution = [
        {"skin_type": d["skin_type__skin_type_code"] or "미설정", "count": d["count"]}
        for d in skin_dist
    ]

    # 일별 신규 가입자 (최근 7일)
    daily_signup = []
    for i in range(6, -1, -1):
        d = today - datetime.timedelta(days=i)
        count = User.objects.filter(created_at__date=d).count()
        daily_signup.append({"date": str(d), "count": count})

    # =====================
    # 분석 활동
    # =====================
    total_analysis = AnalysisResult.objects.count()
    analysis_today = AnalysisResult.objects.filter(created_at__date=today).count()

    traffic_counts = dict(
        AnalysisResult.objects
        .exclude(risk_score__isnull=True)
        .values_list("risk_score")
        .annotate(c=Count("analysis_id"))
        [:0]  # just init
    )
    green = AnalysisResult.objects.filter(risk_score__lte=2).count()
    yellow = AnalysisResult.objects.filter(risk_score__gt=2, risk_score__lte=5).count()
    red = AnalysisResult.objects.filter(risk_score__gt=5).count()

    top_risk_ingredients = list(
        OCR_AnalysisDetail.objects
        .filter(match_status="MATCHED")
        .select_related("ingredient")
        .values("ingredient__ingredient_name_kr")
        .annotate(count=Count("analysis_detail_id"))
        .order_by("-count")[:10]
    )
    top_risk = [
        {"ingredient": d["ingredient__ingredient_name_kr"], "count": d["count"]}
        for d in top_risk_ingredients
    ]

    top_analyzed_products = list(
        AnalysisResult.objects
        .filter(product_id__isnull=False)
        .select_related("product")
        .values("product__product_name")
        .annotate(count=Count("analysis_id"))
        .order_by("-count")[:10]
    )
    top_products_analyzed = [
        {"product_name": d["product__product_name"], "count": d["count"]}
        for d in top_analyzed_products
    ]

    # =====================
    # 제품/리뷰
    # =====================
    top_liked = list(
        ProductLike.objects
        .values("product__product_name", "product_id")
        .annotate(count=Count("product_id"))
        .order_by("-count")[:10]
    )
    top_liked_products = [
        {"product_name": d["product__product_name"], "like_count": d["count"]}
        for d in top_liked
    ]

    top_rated = list(
        Review.objects
        .values("product__product_name", "product_id")
        .annotate(avg=Avg("rating"), count=Count("review_id"))
        .filter(count__gte=3)
        .order_by("-avg")[:10]
    )
    top_rated_products = [
        {"product_name": d["product__product_name"], "avg_rating": round(d["avg"], 1), "review_count": d["count"]}
        for d in top_rated
    ]

    recent_reviews = list(
        Review.objects
        .select_related("product", "user")
        .order_by("-created_at")[:10]
        .values("review_id", "user__nickname", "product__product_name", "rating", "review_text", "created_at")
    )
    recent_reviews_list = [
        {
            "review_id": r["review_id"],
            "nickname": r["user__nickname"],
            "product_name": r["product__product_name"],
            "rating": r["rating"],
            "review_text": r["review_text"],
            "created_at": str(r["created_at"]),
        }
        for r in recent_reviews
    ]

    trending = list(
        SearchLog.objects
        .filter(created_at__gte=week_ago)
        .values("keyword")
        .annotate(count=Count("search_id"))
        .order_by("-count")[:10]
    )
    trending_keywords = [{"keyword": t["keyword"], "count": t["count"]} for t in trending]

    # =====================
    # 챗봇
    # =====================
    total_chat = ChatMessage.objects.filter(message_type="USER").count()
    chat_today = ChatMessage.objects.filter(message_type="USER", created_at__date=today).count()

    intent_dist = list(
        ChatMessage.objects
        .filter(message_type="BOT")
        .exclude(intent__isnull=True)
        .values("intent")
        .annotate(count=Count("message_id"))
        .order_by("-count")
    )
    intent_distribution = [{"intent": d["intent"], "count": d["count"]} for d in intent_dist]

    return JsonResponse({
        "users": {
            "total": total_users,
            "new_today": new_today,
            "new_this_week": new_this_week,
            "survey_responded": survey_users,
            "survey_rate": round(survey_users / total_users * 100, 1) if total_users else 0,
            "kakao_login": kakao_users,
            "normal_login": total_users - kakao_users,
            "skin_distribution": skin_distribution,
            "daily_signup": daily_signup,
        },
        "analysis": {
            "total": total_analysis,
            "today": analysis_today,
            "traffic_light": {"GREEN": green, "YELLOW": yellow, "RED": red},
            "top_risk_ingredients": top_risk,
            "top_analyzed_products": top_products_analyzed,
        },
        "products": {
            "top_liked": top_liked_products,
            "top_rated": top_rated_products,
            "recent_reviews": recent_reviews_list,
            "trending_keywords": trending_keywords,
        },
        "chatbot": {
            "total_messages": total_chat,
            "today_messages": chat_today,
            "intent_distribution": intent_distribution,
        },
    }, json_dumps_params={"ensure_ascii": False})
