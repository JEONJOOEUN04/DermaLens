from django.contrib import admin
from .models import Recommendation


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ("recommendation_id", "user", "product", "score", "rank_order", "created_at")
    list_filter = ("rank_order",)
    search_fields = ("user__email", "product__product_name")
