from django.urls import path
from . import views

urlpatterns = [
    path("ingredients/", views.ingredient_list),
    path("ingredients/search/", views.ingredient_search),
    path("ingredients/<int:ingredient_id>/", views.ingredient_detail),
    path("categories/", views.category_list),
    path("categories/<int:category_id>/", views.product_by_category),
    path("", views.product_list),
    path("search/", views.product_search),
    path("popular/", views.product_popular),
    path("<int:product_id>/", views.product_detail),
    path("<int:product_id>/ingredients/", views.product_ingredients),
]
