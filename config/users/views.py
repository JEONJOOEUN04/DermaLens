import json
import urllib.request
import urllib.parse

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.contrib.auth.hashers import make_password, check_password
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    User, UserSkinProfile, SurveyResponse,
    SkinTypeMaster, TextureMaster, AllergyMaster, SkinConcernMaster,
    UserSkinConcern, UserAllergy,
)


def _user_to_dict(user):
    return {
        "user_id": user.user_id,
        "email": user.email,
        "nickname": user.nickname,
        "created_at": str(user.created_at),
    }


def _get_tokens(user):
    """커스텀 User 모델용 JWT 토큰 발급."""
    refresh = RefreshToken()
    refresh["user_id"] = user.user_id
    refresh["email"] = user.email
    refresh["nickname"] = user.nickname
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


@require_GET
def check_email(request):
    email = request.GET.get("email", "").strip()
    if not email:
        return JsonResponse({"success": False, "message": "email이 필요합니다."}, status=400)
    exists = User.objects.filter(email=email).exists()
    return JsonResponse({"success": True, "available": not exists})


@csrf_exempt
def signup(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST 요청만 허용됩니다."}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "JSON 형식이 올바르지 않습니다."}, status=400)

    email = data.get("email", "").strip()
    password = data.get("password", "")
    nickname = data.get("nickname", "").strip()

    if not email or not password or not nickname:
        return JsonResponse({"success": False, "message": "email, password, nickname이 필요합니다."}, status=400)

    if len(password) < 8:
        return JsonResponse({"success": False, "message": "비밀번호는 8자 이상이어야 합니다."}, status=400)

    if User.objects.filter(email=email).exists():
        return JsonResponse({"success": False, "message": "이미 가입된 이메일입니다."}, status=400)

    user = User.objects.create(
        email=email,
        password=make_password(password),
        nickname=nickname,
    )

    profile_kwargs = {"user": user}
    skin_type_id = data.get("skin_type_id")
    if skin_type_id:
        try:
            profile_kwargs["skin_type"] = SkinTypeMaster.objects.get(pk=skin_type_id)
        except SkinTypeMaster.DoesNotExist:
            pass
    if data.get("sensitivity_level") is not None:
        profile_kwargs["sensitivity_level"] = data["sensitivity_level"]
    if data.get("acne_prone_flag") is not None:
        profile_kwargs["acne_prone_flag"] = data["acne_prone_flag"]

    UserSkinProfile.objects.create(**profile_kwargs)

    tokens = _get_tokens(user)
    return JsonResponse(
        {"success": True, "message": "회원가입 성공", "user": _user_to_dict(user), "tokens": tokens},
        status=201,
        json_dumps_params={"ensure_ascii": False},
    )


@csrf_exempt
def login(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST 요청만 허용됩니다."}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "JSON 형식이 올바르지 않습니다."}, status=400)

    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not email or not password:
        return JsonResponse({"success": False, "message": "email과 password가 필요합니다."}, status=400)

    try:
        user = User.objects.get(email=email, is_active=True)
    except User.DoesNotExist:
        return JsonResponse({"success": False, "message": "존재하지 않는 이메일이거나 탈퇴한 계정입니다."}, status=404)

    if not check_password(password, user.password):
        return JsonResponse({"success": False, "message": "비밀번호가 일치하지 않습니다."}, status=401)

    tokens = _get_tokens(user)
    return JsonResponse(
        {"success": True, "message": "로그인 성공", "user": _user_to_dict(user), "tokens": tokens},
        json_dumps_params={"ensure_ascii": False},
    )


@csrf_exempt
def logout(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST 요청만 허용됩니다."}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        refresh_token = data.get("refresh")
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
    except Exception:
        pass

    return JsonResponse({"success": True, "message": "로그아웃 성공"}, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
def delete_account(request, user_id):
    if request.method != "DELETE":
        return JsonResponse({"success": False, "message": "DELETE 요청만 허용됩니다."}, status=405)

    try:
        user = User.objects.get(user_id=user_id, is_active=True)
    except User.DoesNotExist:
        return JsonResponse({"success": False, "message": "사용자를 찾을 수 없습니다."}, status=404)

    user.is_active = False
    user.save()
    return JsonResponse({"success": True, "message": "회원탈퇴 완료"}, json_dumps_params={"ensure_ascii": False})


@require_GET
def user_profile(request, user_id):
    try:
        user = User.objects.get(user_id=user_id, is_active=True)
        return JsonResponse(
            {"success": True, "user": _user_to_dict(user)},
            json_dumps_params={"ensure_ascii": False},
        )
    except User.DoesNotExist:
        return JsonResponse({"success": False, "message": "사용자를 찾을 수 없습니다."}, status=404)


@require_GET
def skin_profile(request, user_id):
    profile = UserSkinProfile.objects.filter(user_id=user_id).select_related(
        "skin_type", "preferred_texture"
    ).first()
    if not profile:
        return JsonResponse({"success": False, "message": "피부 프로필이 없습니다."}, status=404)

    concerns = list(
        UserSkinConcern.objects.filter(user_id=user_id)
        .select_related("concern")
        .values_list("concern__concern_name_kr", flat=True)
    )
    allergies = list(
        UserAllergy.objects.filter(user_id=user_id)
        .select_related("allergy")
        .values_list("allergy__allergy_name_kr", flat=True)
    )

    return JsonResponse(
        {
            "success": True,
            "profile": {
                "profile_id": profile.profile_id,
                "user_id": profile.user_id,
                "skin_type": {
                    "id": profile.skin_type_id,
                    "code": profile.skin_type.skin_type_code if profile.skin_type else None,
                    "name_kr": profile.skin_type.skin_type_name_kr if profile.skin_type else None,
                } if profile.skin_type else None,
                "skin_concerns": concerns,
                "allergies": allergies,
                "sensitivity_level": profile.sensitivity_level,
                "acne_prone_flag": profile.acne_prone_flag,
                "preferred_texture": {
                    "id": profile.preferred_texture_id,
                    "name_kr": profile.preferred_texture.texture_name_kr if profile.preferred_texture else None,
                } if profile.preferred_texture else None,
                "updated_at": str(profile.updated_at) if profile.updated_at else None,
            },
        },
        json_dumps_params={"ensure_ascii": False},
    )


@csrf_exempt
def update_skin_profile(request, user_id):
    if request.method not in ("POST", "PATCH", "PUT"):
        return JsonResponse({"success": False, "message": "POST/PATCH 요청만 허용됩니다."}, status=405)

    try:
        user = User.objects.get(user_id=user_id, is_active=True)
    except User.DoesNotExist:
        return JsonResponse({"success": False, "message": "사용자를 찾을 수 없습니다."}, status=404)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "JSON 형식이 올바르지 않습니다."}, status=400)

    profile, _ = UserSkinProfile.objects.get_or_create(user=user)

    if "skin_type_id" in data:
        try:
            profile.skin_type = SkinTypeMaster.objects.get(pk=data["skin_type_id"])
        except SkinTypeMaster.DoesNotExist:
            return JsonResponse({"success": False, "message": "존재하지 않는 skin_type_id입니다."}, status=400)
    if "sensitivity_level" in data:
        profile.sensitivity_level = data["sensitivity_level"]
    if "acne_prone_flag" in data:
        profile.acne_prone_flag = data["acne_prone_flag"]
    if "preferred_texture_id" in data:
        try:
            profile.preferred_texture = TextureMaster.objects.get(pk=data["preferred_texture_id"])
        except TextureMaster.DoesNotExist:
            return JsonResponse({"success": False, "message": "존재하지 않는 preferred_texture_id입니다."}, status=400)
    profile.save()

    # 피부 고민 갱신 (concern_ids 배열로 전달)
    if "concern_ids" in data:
        UserSkinConcern.objects.filter(user=user).delete()
        for cid in data["concern_ids"]:
            try:
                concern = SkinConcernMaster.objects.get(pk=cid)
                UserSkinConcern.objects.get_or_create(user=user, concern=concern)
            except SkinConcernMaster.DoesNotExist:
                pass

    # 알레르기 갱신 (allergy_ids 배열로 전달)
    if "allergy_ids" in data:
        UserAllergy.objects.filter(user=user).delete()
        for aid in data["allergy_ids"]:
            try:
                allergy = AllergyMaster.objects.get(pk=aid)
                UserAllergy.objects.get_or_create(user=user, allergy=allergy)
            except AllergyMaster.DoesNotExist:
                pass

    return JsonResponse(
        {"success": True, "message": "피부 프로필이 업데이트 되었습니다."},
        json_dumps_params={"ensure_ascii": False},
    )


@csrf_exempt
def update_nickname(request, user_id):
    if request.method not in ("POST", "PATCH", "PUT"):
        return JsonResponse({"success": False, "message": "POST/PATCH 요청만 허용됩니다."}, status=405)

    try:
        user = User.objects.get(user_id=user_id, is_active=True)
    except User.DoesNotExist:
        return JsonResponse({"success": False, "message": "사용자를 찾을 수 없습니다."}, status=404)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "JSON 형식이 올바르지 않습니다."}, status=400)

    nickname = data.get("nickname", "").strip()
    if not nickname:
        return JsonResponse({"success": False, "message": "nickname이 필요합니다."}, status=400)

    user.nickname = nickname
    user.save()
    return JsonResponse(
        {"success": True, "message": "닉네임이 변경되었습니다.", "user": _user_to_dict(user)},
        json_dumps_params={"ensure_ascii": False},
    )


@csrf_exempt
def save_survey(request):
    """
    설문 응답 처리 엔드포인트.
    요청 형식:
    {
        "user_id": 1,
        "selected_option_ids": [1, 6, 12, 17, 24, 27, 30, 34, 36, 38, 46, 51, 53, 63, 73, 76]
    }
    selected_option_ids: 사용자가 선택한 SurveyOption의 option_id 목록
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST 요청만 허용됩니다."}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "JSON 형식이 올바르지 않습니다."}, status=400)

    user_id = data.get("user_id")
    selected_option_ids = data.get("selected_option_ids", [])

    if not user_id:
        return JsonResponse({"success": False, "message": "user_id가 필요합니다."}, status=400)
    if not selected_option_ids:
        return JsonResponse({"success": False, "message": "selected_option_ids가 필요합니다."}, status=400)

    # SurveyOption에서 선택된 항목 조회
    from .models import SurveyOption
    options = SurveyOption.objects.filter(option_id__in=selected_option_ids).select_related("question")

    # 점수 집계
    scores = {}
    concern_ids = []
    allergy_ids = []
    texture_id = None
    acne_flag = None
    sensitivity_score = 0

    for opt in options:
        field = opt.score_field
        val = opt.score_value

        if field == "concern_id":
            concern_ids.append(val)
        elif field == "allergy_id":
            allergy_ids.append(val)
        elif field == "texture_id":
            texture_id = val
        elif field == "acne_flag":
            acne_flag = bool(val)
        else:
            scores[field] = scores.get(field, 0) + val

    oil_score = scores.get("oil_score", 0)
    sensitive_score = scores.get("sensitive_score", 0)
    dehydrated_score = scores.get("dehydrated_score", 0)
    sensitivity_level = scores.get("sensitive_score", 0)  # Q10 선택 점수를 민감도로 사용

    # answers_json 저장 (원본 선택 기록 보존)
    answers_json = {
        "selected_option_ids": selected_option_ids,
        "oil_score": oil_score,
        "sensitive_score": sensitive_score,
        "dehydrated_score": dehydrated_score,
    }
    survey = SurveyResponse.objects.create(user_id=user_id, answers_json=answers_json)

    # 피부 타입 분류
    skin_type_code = _classify_skin_type(oil_score, sensitive_score, dehydrated_score)

    # UserSkinProfile 저장
    profile, _ = UserSkinProfile.objects.get_or_create(user_id=user_id)
    try:
        profile.skin_type = SkinTypeMaster.objects.get(skin_type_code=skin_type_code)
    except SkinTypeMaster.DoesNotExist:
        pass

    # 민감도 레벨 (1~5 스케일로 정규화)
    profile.sensitivity_level = min(max(round(sensitivity_level / 3 * 5), 1), 5) if sensitive_score else None
    if acne_flag is not None:
        profile.acne_prone_flag = acne_flag
    if texture_id:
        try:
            profile.preferred_texture = TextureMaster.objects.get(pk=texture_id)
        except TextureMaster.DoesNotExist:
            pass
    profile.save()

    # 피부 고민 저장 (기존 데이터 교체)
    UserSkinConcern.objects.filter(user_id=user_id).delete()
    for cid in concern_ids:
        try:
            UserSkinConcern.objects.create(
                user_id=user_id,
                concern=SkinConcernMaster.objects.get(pk=cid),
            )
        except SkinConcernMaster.DoesNotExist:
            pass

    # 알레르기/기피 성분 저장 (기존 데이터 교체)
    UserAllergy.objects.filter(user_id=user_id).delete()
    for aid in allergy_ids:
        try:
            UserAllergy.objects.create(
                user_id=user_id,
                allergy=AllergyMaster.objects.get(pk=aid),
            )
        except AllergyMaster.DoesNotExist:
            pass

    skin_type_name = profile.skin_type.skin_type_name_kr if profile.skin_type else None

    return JsonResponse(
        {
            "success": True,
            "message": "설문 저장 성공",
            "response_id": survey.response_id,
            "result": {
                "skin_type_code": skin_type_code,
                "skin_type_name": skin_type_name,
                "sensitivity_level": profile.sensitivity_level,
                "acne_prone_flag": profile.acne_prone_flag,
                "preferred_texture_id": texture_id,
                "skin_concerns": concern_ids,
                "allergies": allergy_ids,
            },
        },
        json_dumps_params={"ensure_ascii": False},
    )


def _classify_skin_type(oil_score, sensitive_score, dehydrated_score):
    """
    점수 기반 피부 타입 분류 → SkinTypeMaster 코드 반환.

    점수 기준 (합산):
      oil_score max ≈ 8 (Q1+Q2+Q5), 임계값 4
      sensitive_score max ≈ 8 (Q3+Q4+Q7), 임계값 4
      dehydrated_score max ≈ 8 (Q1+Q2+Q6+Q8), 임계값 4
    """
    is_oily = oil_score >= 4
    is_sensitive = sensitive_score >= 4
    is_dehydrated = dehydrated_score >= 4

    # OS+/OS-/ON+/ON-/DS+/DS-/DN+/DN-
    if is_oily and is_sensitive:
        return "OS-" if is_dehydrated else "OS+"
    if is_oily:
        return "ON-" if is_dehydrated else "ON+"
    if is_sensitive:
        return "DS-" if is_dehydrated else "DS+"
    return "DN-" if is_dehydrated else "DN+"


# =====================
# 마이페이지
# =====================

@require_GET
def mypage(request, user_id):
    try:
        user = User.objects.get(user_id=user_id, is_active=True)
    except User.DoesNotExist:
        return JsonResponse({"success": False, "message": "사용자를 찾을 수 없습니다."}, status=404)

    profile = UserSkinProfile.objects.filter(user=user).select_related("skin_type").first()
    concerns = list(
        UserSkinConcern.objects.filter(user=user)
        .select_related("concern")
        .values_list("concern__concern_name_kr", flat=True)
    )

    from products.models import ProductLike
    from review.models import Review
    from analysis.models import AnalysisResult

    like_count = ProductLike.objects.filter(user=user).count()
    review_count = Review.objects.filter(user=user).count()
    analysis_count = AnalysisResult.objects.filter(user=user).count()

    return JsonResponse(
        {
            "success": True,
            "user": _user_to_dict(user),
            "skin_profile": {
                "skin_type": profile.skin_type.skin_type_name_kr if profile and profile.skin_type else None,
                "skin_concerns": concerns,
                "sensitivity_level": profile.sensitivity_level if profile else None,
                "acne_prone_flag": profile.acne_prone_flag if profile else None,
            } if profile else None,
            "activity_summary": {
                "like_count": like_count,
                "review_count": review_count,
                "analysis_count": analysis_count,
            },
        },
        json_dumps_params={"ensure_ascii": False},
    )


@require_GET
def my_liked_products(request, user_id):
    from products.models import ProductLike
    page = int(request.GET.get("page", 1))
    size = int(request.GET.get("size", 20))
    offset = (page - 1) * size

    likes = ProductLike.objects.filter(user_id=user_id).select_related("product").order_by("-created_at")[offset:offset + size]
    data = [
        {
            "product_id": like.product_id,
            "product_name": like.product.product_name,
            "image_url": like.product.image_url,
            "price": like.product.price,
            "created_at": str(like.created_at),
        }
        for like in likes
    ]
    return JsonResponse(
        {"success": True, "page": page, "count": len(data), "liked_products": data},
        json_dumps_params={"ensure_ascii": False},
    )


@require_GET
def my_reviews(request, user_id):
    from review.models import Review
    page = int(request.GET.get("page", 1))
    size = int(request.GET.get("size", 20))
    offset = (page - 1) * size

    reviews = Review.objects.filter(user_id=user_id).select_related("product").order_by("-created_at")[offset:offset + size]
    data = [
        {
            "review_id": r.review_id,
            "product_id": r.product_id,
            "product_name": r.product.product_name,
            "rating": r.rating,
            "review_text": r.review_text,
            "created_at": str(r.created_at),
            "updated_at": str(r.updated_at) if r.updated_at else None,
        }
        for r in reviews
    ]
    return JsonResponse(
        {"success": True, "page": page, "count": len(data), "reviews": data},
        json_dumps_params={"ensure_ascii": False},
    )


@require_GET
def my_analysis_history(request, user_id):
    from analysis.models import AnalysisResult
    page = int(request.GET.get("page", 1))
    size = int(request.GET.get("size", 20))
    offset = (page - 1) * size

    results = AnalysisResult.objects.filter(user_id=user_id).order_by("-created_at")[offset:offset + size]
    data = [
        {
            "analysis_id": r.analysis_id,
            "product_id": r.product_id,
            "analysis_type": r.analysis_type,
            "risk_score": r.risk_score,
            "summary": r.summary,
            "created_at": str(r.created_at),
        }
        for r in results
    ]
    return JsonResponse(
        {"success": True, "page": page, "count": len(data), "history": data},
        json_dumps_params={"ensure_ascii": False},
    )


# =====================
# 카카오 로그인
# =====================

@require_GET
def kakao_login(request):
    """카카오 인증 페이지 URL 반환."""
    kakao_auth_url = "https://kauth.kakao.com/oauth/authorize?" + urllib.parse.urlencode({
        "client_id": settings.KAKAO_REST_API_KEY,
        "redirect_uri": settings.KAKAO_REDIRECT_URI,
        "response_type": "code",
    })
    return JsonResponse({"success": True, "auth_url": kakao_auth_url})


@require_GET
def kakao_callback(request):
    """카카오 인증 코드 → 토큰 → 유저 정보 → JWT 발급."""
    code = request.GET.get("code")
    if not code:
        return JsonResponse({"success": False, "message": "인증 코드가 없습니다."}, status=400)

    # 1. 카카오 액세스 토큰 발급
    token_data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "client_id": settings.KAKAO_REST_API_KEY,
        "redirect_uri": settings.KAKAO_REDIRECT_URI,
        "code": code,
    }).encode("utf-8")

    token_req = urllib.request.Request(
        "https://kauth.kakao.com/oauth/token",
        data=token_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(token_req, timeout=10) as resp:
            token_resp = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return JsonResponse({"success": False, "message": f"카카오 토큰 요청 실패: {e}"}, status=502)

    kakao_access_token = token_resp.get("access_token")
    if not kakao_access_token:
        return JsonResponse({"success": False, "message": "액세스 토큰 발급 실패"}, status=502)

    # 2. 카카오 유저 정보 조회
    user_info_req = urllib.request.Request(
        "https://kapi.kakao.com/v2/user/me",
        headers={"Authorization": f"Bearer {kakao_access_token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(user_info_req, timeout=10) as resp:
            user_info = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return JsonResponse({"success": False, "message": f"카카오 유저 정보 요청 실패: {e}"}, status=502)

    kakao_id = str(user_info.get("id", ""))
    kakao_account = user_info.get("kakao_account", {})
    email = kakao_account.get("email") or f"kakao_{kakao_id}@kakao.placeholder"
    nickname = (
        kakao_account.get("profile", {}).get("nickname")
        or f"kakao_{kakao_id[:6]}"
    )

    # 3. 유저 조회 또는 생성
    user = User.objects.filter(kakao_id=kakao_id).first()
    is_new = False

    if not user:
        user = User.objects.filter(email=email).first()
        if user:
            # 기존 일반 가입 유저 → kakao_id 연결
            user.kakao_id = kakao_id
            user.save()
        else:
            # 신규 가입
            user = User.objects.create(
                email=email,
                password=make_password(None),  # 카카오 유저는 비밀번호 없음
                nickname=nickname,
                kakao_id=kakao_id,
            )
            UserSkinProfile.objects.create(user=user)
            is_new = True

    tokens = _get_tokens(user)
    return JsonResponse(
        {
            "success": True,
            "is_new_user": is_new,
            "user": _user_to_dict(user),
            "tokens": tokens,
        },
        json_dumps_params={"ensure_ascii": False},
    )


@require_GET
def my_recommendations(request, user_id):
    from recommendation.models import Recommendation
    page = int(request.GET.get("page", 1))
    size = int(request.GET.get("size", 20))
    offset = (page - 1) * size

    recs = Recommendation.objects.filter(user_id=user_id).select_related("product").order_by("rank_order", "-score")[offset:offset + size]
    data = [
        {
            "recommendation_id": r.recommendation_id,
            "product_id": r.product_id,
            "product_name": r.product.product_name,
            "image_url": r.product.image_url,
            "score": r.score,
            "reason": r.reason,
            "rank_order": r.rank_order,
            "created_at": str(r.created_at),
        }
        for r in recs
    ]
    return JsonResponse(
        {"success": True, "page": page, "count": len(data), "recommendations": data},
        json_dumps_params={"ensure_ascii": False},
    )
