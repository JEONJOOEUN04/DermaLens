from django.urls import path
from . import views

urlpatterns = [
    path("upload-image/", views.upload_ocr_image),
    path("request-ocr/", views.request_ocr),
    path("ocr-result/", views.save_ocr_result),
    path("analyze-product/", views.analyze_product),
    path("detail/<int:analysis_id>/", views.analysis_detail),
    path("history/<int:user_id>/", views.analysis_history),
    path("chat/start/", views.chat_start),
    path("chat/message/", views.chat_message),
    path("chat/history/<int:session_id>/", views.chat_history),
    path("chat/sessions/<int:user_id>/", views.user_sessions),
    path("chat/", views.chat),
]
