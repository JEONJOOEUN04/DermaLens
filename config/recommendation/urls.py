from django.urls import path
from . import views

urlpatterns = [
    path("generate/", views.generate_recommendation),
    path("user/<int:user_id>/", views.recommendation_list),
    path("save/", views.save_recommendation),
    path("like/", views.product_like),
    path("like/<int:user_id>/<int:product_id>/", views.product_like_status),
]
