from django.db import models
from users.models import User
from products.models import Product


class Review(models.Model):
    review_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, db_column='product_id')
    rating = models.IntegerField()
    review_text = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        db_table = 'Review'


class ReviewImage(models.Model):
    image_id = models.AutoField(primary_key=True)
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='images', db_column='review_id')
    image_url = models.TextField()
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ReviewImage'
        ordering = ['order', 'image_id']


class Feedback(models.Model):
    feedback_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL,
        null=True, blank=True, db_column='product_id'
    )
    feedback_type = models.CharField(max_length=50)
    satisfaction_score = models.IntegerField(null=True, blank=True)
    side_effect_text = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'Feedback'


class SearchLog(models.Model):
    search_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    keyword = models.CharField(max_length=255)
    clicked_product = models.ForeignKey(
        Product, on_delete=models.SET_NULL,
        null=True, blank=True, db_column='clicked_product_id'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'SearchLog'


class ProductView(models.Model):
    view_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, db_column='product_id')
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ProductView'
        ordering = ['-viewed_at']


class ExternalSource(models.Model):
    source_id = models.AutoField(primary_key=True)
    source_name = models.CharField(max_length=255)
    api_url = models.TextField()

    class Meta:
        db_table = 'ExternalSource'


class DataSyncHistory(models.Model):
    sync_id = models.AutoField(primary_key=True)
    source = models.ForeignKey(ExternalSource, on_delete=models.CASCADE, db_column='source_id')
    inserted_count = models.IntegerField(null=True, blank=True)
    updated_count = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'DataSyncHistory'
