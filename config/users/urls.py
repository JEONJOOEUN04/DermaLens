from django.urls import path
from . import views

urlpatterns = [
    path("signup/", views.signup),
    path("login/", views.login),
    path("logout/", views.logout),
    path("delete/<int:user_id>/", views.delete_account),
    path("profile/<int:user_id>/", views.user_profile),
    path("profile/<int:user_id>/nickname/", views.update_nickname),
    path("skin-profile/<int:user_id>/", views.skin_profile),
    path("skin-profile/<int:user_id>/update/", views.update_skin_profile),
    path("survey/", views.save_survey),
    path("mypage/<int:user_id>/", views.mypage),
    path("mypage/<int:user_id>/likes/", views.my_liked_products),
    path("mypage/<int:user_id>/reviews/", views.my_reviews),
    path("mypage/<int:user_id>/analysis/", views.my_analysis_history),
    path("mypage/<int:user_id>/recommendations/", views.my_recommendations),
]
