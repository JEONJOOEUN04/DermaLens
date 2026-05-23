from django.contrib import admin

from .models import (

    OCRImage,

    OCRRawText,

    AnalysisResult,

    OCR_AnalysisDetail,

    ChatSession,

    ChatMessage,

)

admin.site.register(OCRImage)

admin.site.register(OCRRawText)

admin.site.register(AnalysisResult)

admin.site.register(OCR_AnalysisDetail)

admin.site.register(ChatSession)

admin.site.register(ChatMessage)