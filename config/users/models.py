from django.db import models


class User(models.Model):
    user_id = models.AutoField(primary_key=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    nickname = models.CharField(max_length=100)
    kakao_id = models.CharField(max_length=100, null=True, blank=True, unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'User'

    def __str__(self):
        return self.nickname


class SkinTypeMaster(models.Model):
    skin_type_id = models.IntegerField(primary_key=True)
    skin_type_code = models.CharField(max_length=10, unique=True)
    skin_type_name_kr = models.CharField(max_length=100)
    skin_type_name_en = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'SkinTypeMaster'

    def __str__(self):
        return self.skin_type_name_kr


class TextureMaster(models.Model):
    texture_id = models.IntegerField(primary_key=True)
    texture_name_kr = models.CharField(max_length=100)
    texture_name_en = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'TextureMaster'

    def __str__(self):
        return self.texture_name_kr


class SkinConcernMaster(models.Model):
    concern_id = models.IntegerField(primary_key=True)
    concern_name_kr = models.CharField(max_length=100)
    concern_name_en = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'SkinConcernMaster'

    def __str__(self):
        return self.concern_name_kr


class AllergyMaster(models.Model):
    allergy_id = models.IntegerField(primary_key=True)
    allergy_name_kr = models.CharField(max_length=100)
    allergy_name_en = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'AllergyMaster'

    def __str__(self):
        return self.allergy_name_kr


class UserSkinProfile(models.Model):
    profile_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, db_column='user_id')
    skin_type = models.ForeignKey(
        SkinTypeMaster, on_delete=models.PROTECT,
        null=True, blank=True, db_column='skin_type_id'
    )
    sensitivity_level = models.IntegerField(null=True, blank=True)
    acne_prone_flag = models.BooleanField(null=True, blank=True)
    preferred_texture = models.ForeignKey(
        TextureMaster, on_delete=models.SET_NULL,
        null=True, blank=True, db_column='preferred_texture_id'
    )
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        db_table = 'UserSkinProfile'

    def __str__(self):
        return f"{self.user.nickname} 피부프로필"


class UserSkinConcern(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    concern = models.ForeignKey(SkinConcernMaster, on_delete=models.CASCADE, db_column='concern_id')

    class Meta:
        db_table = 'UserSkinConcern'
        unique_together = ('user', 'concern')


class UserAllergy(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    allergy = models.ForeignKey(AllergyMaster, on_delete=models.CASCADE, db_column='allergy_id')

    class Meta:
        db_table = 'UserAllergy'
        unique_together = ('user', 'allergy')


class SurveyResponse(models.Model):
    response_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    answers_json = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'SurveyResponse'

    def __str__(self):
        return f"설문응답-{self.user.nickname}"


class SurveyQuestion(models.Model):
    question_id = models.IntegerField(primary_key=True)
    survey_type = models.CharField(max_length=50)
    question_text = models.CharField(max_length=255)
    save_table = models.CharField(max_length=100, null=True, blank=True)
    linked_master = models.CharField(max_length=100, null=True, blank=True)
    score_field = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = 'SurveyQuestion'

    def __str__(self):
        return self.question_text


class SurveyOption(models.Model):
    option_id = models.IntegerField(primary_key=True)
    question = models.ForeignKey(SurveyQuestion, on_delete=models.CASCADE, db_column='question_id')
    option_text = models.CharField(max_length=100)
    score_value = models.IntegerField()
    score_field = models.CharField(max_length=50)

    class Meta:
        db_table = 'SurveyOption'

    def __str__(self):
        return self.option_text


class UserNotification(models.Model):
    notification_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    type = models.CharField(max_length=50, default='OCR_COMPLETE')
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    related_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'UserNotification'
        ordering = ['-created_at']
