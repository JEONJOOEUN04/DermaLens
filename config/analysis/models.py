from django.db import models
from users.models import User
from products.models import Product, Ingredient


class OCRImage(models.Model):
    ocr_image_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL,
        null=True, blank=True, db_column='product_id'
    )
    image_url = models.TextField()
    image_type = models.CharField(max_length=50, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'OCRImage'


class OCRRawText(models.Model):
    raw_text_id = models.AutoField(primary_key=True)
    ocr_image = models.ForeignKey(OCRImage, on_delete=models.CASCADE, db_column='ocr_image_id')
    raw_text = models.TextField()
    ocr_engine = models.CharField(max_length=100, null=True, blank=True)
    ocr_confidence = models.FloatField(null=True, blank=True)
    extracted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'OCRRawText'


class AnalysisResult(models.Model):
    analysis_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL,
        null=True, blank=True, db_column='product_id'
    )
    ocr_image = models.ForeignKey(
        OCRImage, on_delete=models.SET_NULL,
        null=True, blank=True, db_column='ocr_image_id'
    )
    analysis_type = models.CharField(max_length=100, null=True, blank=True)
    risk_score = models.FloatField(null=True, blank=True)
    summary = models.TextField(null=True, blank=True)
    product_name = models.CharField(max_length=300, null=True, blank=True)
    capacity = models.CharField(max_length=100, null=True, blank=True)
    usage = models.JSONField(null=True, blank=True)
    cautions = models.JSONField(null=True, blank=True)
    effects = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'AnalysisResult'


class OCR_AnalysisDetail(models.Model):
    analysis_detail_id = models.AutoField(primary_key=True)
    analysis = models.ForeignKey(AnalysisResult, on_delete=models.CASCADE, db_column='analysis_id')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, db_column='ingredient_id')
    detected_text = models.TextField(null=True, blank=True)
    risk_contribution = models.FloatField(null=True, blank=True)
    caution_reason = models.TextField(null=True, blank=True)
    match_status = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = 'OCR_AnalysisDetail'


class ChatSession(models.Model):
    session_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    created_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'ChatSession'

    def __str__(self):
        return f"ChatSession {self.session_id}"


class ChatMessage(models.Model):
    message_id = models.AutoField(primary_key=True)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, db_column='session_id')
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    message_type = models.CharField(max_length=20)  # USER / BOT
    content = models.TextField()
    intent = models.CharField(max_length=50, null=True, blank=True)
    related_product = models.ForeignKey(
        Product, on_delete=models.SET_NULL,
        null=True, blank=True, db_column='related_product_id'
    )
    related_ingredient = models.ForeignKey(
        Ingredient, on_delete=models.SET_NULL,
        null=True, blank=True, db_column='related_ingredient_id'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ChatMessage'

    def __str__(self):
        return f"{self.message_type} - {self.message_id}"
