from django.contrib import admin
from .models import (
    Brand, Category, FunctionMaster, Ingredient,
    IngredientAlias, IngredientFunction,
    Product, ProductIngredient, ProductLike,
)


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ("ingredient_id", "ingredient_name_kr", "ingredient_name_en", "risk_level",
                    "allergy_flag", "irritant_flag", "moisturizing_flag", "soothing_flag")
    search_fields = ("ingredient_name_kr", "ingredient_name_en")
    list_filter = ("allergy_flag", "irritant_flag", "acne_caution_flag", "moisturizing_flag", "soothing_flag")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("product_id", "product_name", "brand", "category", "price")
    search_fields = ("product_name",)
    list_filter = ("category", "brand")


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("brand_id", "brand_name_kr", "brand_name_en", "is_active")
    search_fields = ("brand_name_kr", "brand_name_en")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("category_id", "category_name", "parent", "depth")


@admin.register(ProductLike)
class ProductLikeAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "product", "created_at")
    search_fields = ("user__email", "product__product_name")


admin.site.register(FunctionMaster)
admin.site.register(IngredientAlias)
admin.site.register(IngredientFunction)
admin.site.register(ProductIngredient)
