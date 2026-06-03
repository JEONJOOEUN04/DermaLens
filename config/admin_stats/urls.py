from django.urls import path
from . import views

urlpatterns = [
    # 유저 현황
    path("stats/users/count", views.users_count),
    path("stats/users/signups", views.users_signups),
    path("stats/users/by-skin-type", views.users_by_skin_type),
    path("stats/users/by-provider", views.users_by_provider),
    path("stats/survey/completion", views.survey_completion),

    # 분석 활동
    path("stats/analysis/daily", views.analysis_daily),
    path("stats/analysis/traffic", views.analysis_traffic),
    path("stats/analysis/top-products", views.analysis_top_products),
    path("stats/ingredients/top-risk", views.ingredients_top_risk),

    # 제품/리뷰
    path("products/top-rated", views.products_top_rated),
    path("products/by-category", views.products_by_category),
    path("reviews", views.reviews_list),
    path("reviews/<int:review_id>/moderate", views.review_moderate),

    # 챗봇
    path("stats/chat/usage", views.chat_usage),
    path("stats/chat/intents", views.chat_intents),
]
