from django.urls import path
from . import views

urlpatterns = [
    path("", views.create_review),
    path("<int:review_id>/update/", views.update_review),
    path("<int:review_id>/delete/", views.delete_review),
    path("<int:review_id>/images/", views.upload_review_images),
    path("<int:review_id>/images/<int:image_id>/", views.delete_review_image),
    path("product/<int:product_id>/", views.product_reviews),
    path("user/<int:user_id>/", views.user_reviews),
    path("feedback/", views.create_feedback),
    path("feedback/<int:user_id>/", views.feedback_list),
    path("search-log/", views.log_search),
    path("search-history/<int:user_id>/", views.search_history),
    path("trending/", views.trending_searches),
    path("product-view/", views.log_product_view),
    path("recently-viewed/<int:user_id>/", views.recently_viewed),
    path("sync-history/", views.sync_history),
]
