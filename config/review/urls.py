from django.urls import path
from . import views

urlpatterns = [
    path("", views.create_review),
    path("<int:review_id>/update/", views.update_review),
    path("<int:review_id>/delete/", views.delete_review),
    path("product/<int:product_id>/", views.product_reviews),
    path("user/<int:user_id>/", views.user_reviews),
    path("feedback/", views.create_feedback),
    path("feedback/<int:user_id>/", views.feedback_list),
    path("search-log/", views.log_search),
    path("search-history/<int:user_id>/", views.search_history),
    path("sync-history/", views.sync_history),
]
