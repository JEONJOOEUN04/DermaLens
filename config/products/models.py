from django.db import models
from users.models import User, TextureMaster


class Brand(models.Model):
    brand_id = models.AutoField(primary_key=True)
    brand_name_kr = models.CharField(max_length=255)
    brand_name_en = models.CharField(max_length=255, null=True, blank=True)
    brand_description = models.TextField(null=True, blank=True)
    official_site_url = models.TextField(null=True, blank=True)
    logo_url = models.TextField(null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        db_table = 'Brand'

    def __str__(self):
        return self.brand_name_kr


class Category(models.Model):
    category_id = models.AutoField(primary_key=True)
    category_name = models.CharField(max_length=100)
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True, db_column='parent_id'
    )
    depth = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'Category'

    def __str__(self):
        return self.category_name


class FunctionMaster(models.Model):
    function_id = models.IntegerField(primary_key=True)
    function_name_kr = models.CharField(max_length=100)
    function_name_en = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'FunctionMaster'

    def __str__(self):
        return self.function_name_kr


class Ingredient(models.Model):
    ingredient_id = models.AutoField(primary_key=True)
    ingredient_name_kr = models.CharField(max_length=255)
    ingredient_name_en = models.CharField(max_length=255, null=True, blank=True)
    risk_level = models.IntegerField(null=True, blank=True)
    allergy_flag = models.BooleanField(default=False, null=True)
    irritant_flag = models.BooleanField(default=False, null=True)
    acne_caution_flag = models.BooleanField(default=False, null=True)
    moisturizing_flag = models.BooleanField(default=False, null=True)
    soothing_flag = models.BooleanField(default=False, null=True)
    description = models.TextField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        db_table = 'Ingredient'

    def __str__(self):
        return self.ingredient_name_kr


class IngredientAlias(models.Model):
    alias_id = models.AutoField(primary_key=True)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, db_column='ingredient_id')
    alias_name = models.CharField(max_length=255)
    alias_type = models.CharField(max_length=50, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        db_table = 'IngredientAlias'


class IngredientFunction(models.Model):
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, db_column='ingredient_id')
    function = models.ForeignKey(FunctionMaster, on_delete=models.CASCADE, db_column='function_id')

    class Meta:
        db_table = 'IngredientFunction'
        unique_together = ('ingredient', 'function')


class Product(models.Model):
    product_id = models.AutoField(primary_key=True)
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, db_column='brand_id')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, db_column='category_id')
    texture = models.ForeignKey(
        TextureMaster, on_delete=models.SET_NULL,
        null=True, blank=True, db_column='texture_id'
    )
    product_name = models.CharField(max_length=255)
    image_url = models.TextField(null=True, blank=True)
    product_url = models.TextField(null=True, blank=True)
    volume = models.CharField(max_length=50, null=True, blank=True)
    price = models.IntegerField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    official_ingredient_text = models.TextField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        db_table = 'Product'

    def __str__(self):
        return self.product_name


class ProductIngredient(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, db_column='product_id')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, db_column='ingredient_id')

    class Meta:
        db_table = 'ProductIngredient'
        unique_together = ('product', 'ingredient')


class ProductLike(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, db_column='product_id')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ProductLike'
        unique_together = ('user', 'product')


class ProductIngredientCandidate(models.Model):
    """제품 성분 후보 (OCR 교차검증용). 2회 이상 검출 시 ProductIngredient로 확정."""
    candidate_id = models.AutoField(primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, db_column='product_id')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, db_column='ingredient_id')
    detection_count = models.IntegerField(default=1)
    confirmed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ProductIngredientCandidate'
        unique_together = ('product', 'ingredient')


class ProductScanContribution(models.Model):
    """제품 성분 스캔 기여 기록 (1인 1제품 1회, 제품당 10명 제한)."""
    contribution_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, db_column='product_id')
    image_url = models.TextField(null=True, blank=True)
    detected_count = models.IntegerField(default=0)  # 추출된 성분 수
    reward_points = models.IntegerField(default=0)
    is_first = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ProductScanContribution'
        unique_together = ('user', 'product')
