from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


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

]

if settings.DEBUG:

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)