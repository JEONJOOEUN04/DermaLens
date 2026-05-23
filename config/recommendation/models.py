from django.db import models
from users.models import User
from products.models import Product


class Recommendation(models.Model):
    recommendation_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, db_column='product_id')
    score = models.FloatField()
    reason = models.TextField(null=True, blank=True)
    rank_order = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'Recommendation'
