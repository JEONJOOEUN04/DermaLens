from django.contrib import admin
from .models import (
    User, SkinTypeMaster, TextureMaster, SkinConcernMaster, AllergyMaster,
    UserSkinProfile, UserSkinConcern, UserAllergy,
    SurveyResponse, SurveyQuestion, SurveyOption,
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("user_id", "email", "nickname", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("email", "nickname")


@admin.register(UserSkinProfile)
class UserSkinProfileAdmin(admin.ModelAdmin):
    list_display = ("profile_id", "user", "skin_type", "sensitivity_level", "acne_prone_flag", "updated_at")
    search_fields = ("user__email", "user__nickname")


@admin.register(SkinTypeMaster)
class SkinTypeMasterAdmin(admin.ModelAdmin):
    list_display = ("skin_type_id", "skin_type_code", "skin_type_name_kr", "is_active")


@admin.register(SkinConcernMaster)
class SkinConcernMasterAdmin(admin.ModelAdmin):
    list_display = ("concern_id", "concern_name_kr", "is_active")


@admin.register(AllergyMaster)
class AllergyMasterAdmin(admin.ModelAdmin):
    list_display = ("allergy_id", "allergy_name_kr", "is_active")


@admin.register(TextureMaster)
class TextureMasterAdmin(admin.ModelAdmin):
    list_display = ("texture_id", "texture_name_kr", "is_active")


@admin.register(SurveyQuestion)
class SurveyQuestionAdmin(admin.ModelAdmin):
    list_display = ("question_id", "survey_type", "question_text")


admin.site.register(UserSkinConcern)
admin.site.register(UserAllergy)
admin.site.register(SurveyResponse)
admin.site.register(SurveyOption)
