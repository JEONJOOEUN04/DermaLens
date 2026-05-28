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


class UserRoutine(models.Model):
    routine_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    title = models.CharField(max_length=100, default='나의 루틴')
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'UserRoutine'


class UserRoutineStep(models.Model):
    step_id = models.AutoField(primary_key=True)
    routine = models.ForeignKey(UserRoutine, on_delete=models.CASCADE, related_name='steps', db_column='routine_id')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, db_column='product_id')
    product_name_custom = models.CharField(max_length=200, null=True, blank=True)
    step_order = models.IntegerField(default=0)
    memo = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'UserRoutineStep'
        ordering = ['step_order']
