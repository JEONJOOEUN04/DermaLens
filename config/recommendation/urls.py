from django.urls import path
from . import views

urlpatterns = [
    path("generate/", views.generate_recommendation),
    path("user/<int:user_id>/", views.recommendation_list),
    path("save/", views.save_recommendation),
    path("like/", views.product_like),
    path("like/<int:user_id>/<int:product_id>/", views.product_like_status),
    # 루틴
    path("routine/", views.create_routine),
    path("routine/<int:routine_id>/", views.update_routine),
    path("routine/<int:routine_id>/delete/", views.delete_routine),
    path("routine/user/<int:user_id>/", views.user_routines),
    path("routine/popular/<str:skin_type_code>/", views.popular_routines),
]
