from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve


def health_check(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("health/", health_check),
    path("admin/", admin.site.urls),

    path("api/users/", include("users.urls")),

    path("api/products/", include("products.urls")),

    path("api/analysis/", include("analysis.urls")),

    path("api/recommendation/", include("recommendation.urls")),

    path("api/review/", include("review.urls")),

    path("api/admin/", include("admin_stats.urls")),

    # media 파일 서빙 (DEBUG 무관 — OCR 서버가 업로드 이미지 다운로드해야 함)
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]