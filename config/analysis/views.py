import json
import os
import urllib.request
import urllib.error

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.db.models import Q, Avg
from django.conf import settings

from products.models import Ingredient, IngredientAlias, ProductIngredient
from .models import (
    OCRImage, OCRRawText, AnalysisResult, OCR_AnalysisDetail,
    ChatSession, ChatMessage,
)


# =====================
# 성분 매칭 유틸
# =====================

def _match_ingredient(name):
    """성분명으로 DB 매칭: 정확 일치 → alias → 부분 일치 순."""
    name = name.strip()
    if not name:
        return None

    ing = Ingredient.objects.filter(
        Q(ingredient_name_kr__iexact=name) | Q(ingredient_name_en__iexact=name)
    ).first()
    if ing:
        return ing

    alias = IngredientAlias.objects.filter(alias_name__iexact=name, is_active=True).first()
    if alias:
        return alias.ingredient

    return Ingredient.objects.filter(
        Q(ingredient_name_kr__icontains=name) | Q(ingredient_name_en__icontains=name)
    ).first()


def _build_risk_summary(matched, user_profile=None, user_allergy_names=None):
    """
    매칭된 성분 리스트로 위험도·효능 분석.
    신호등: avg ≤ 2 GREEN / ≤ 5 YELLOW / 6+ RED
    """
    total_risk = 0
    high_risk = []
    allergy_warnings = []
    irritant_warnings = []
    acne_warnings = []
    moisturizing = []
    soothing = []
    personalized_warnings = []

    skin_type_code = None
    if user_profile and user_profile.skin_type:
        skin_type_code = user_profile.skin_type.skin_type_code

    avoidance_keywords = [n.lower() for n in (user_allergy_names or []) if n]

    for item in matched:
        ing = item["ingredient"]
        risk = ing.risk_level or 0

        if skin_type_code and "S" in skin_type_code and ing.irritant_flag:
            risk += 2
        if user_profile and user_profile.acne_prone_flag and ing.acne_caution_flag:
            risk += 1

        total_risk += risk

        if risk >= 5:
            high_risk.append(ing.ingredient_name_kr)
        if ing.allergy_flag:
            allergy_warnings.append(ing.ingredient_name_kr)
        if ing.irritant_flag:
            irritant_warnings.append(ing.ingredient_name_kr)
        if ing.acne_caution_flag:
            acne_warnings.append(ing.ingredient_name_kr)
        if ing.moisturizing_flag:
            moisturizing.append(ing.ingredient_name_kr)
        if ing.soothing_flag:
            soothing.append(ing.ingredient_name_kr)

        kr = (ing.ingredient_name_kr or "").lower()
        en = (ing.ingredient_name_en or "").lower()
        for kw in avoidance_keywords:
            if kw and (kw in kr or kw in en):
                personalized_warnings.append(ing.ingredient_name_kr)
                break

    avg_risk = round(total_risk / len(matched), 2) if matched else 0

    if avg_risk <= 2:
        traffic_light = "GREEN"
    elif avg_risk <= 5:
        traffic_light = "YELLOW"
    else:
        traffic_light = "RED"

    summary_parts = []
    if high_risk:
        summary_parts.append(f"고위험 성분 포함: {', '.join(high_risk[:3])}")
    if allergy_warnings:
        summary_parts.append(f"알레르기 유발 가능 성분: {', '.join(allergy_warnings[:3])}")
    if moisturizing:
        summary_parts.append(f"보습 성분 포함: {', '.join(moisturizing[:3])}")
    if soothing:
        summary_parts.append(f"진정 성분 포함: {', '.join(soothing[:3])}")

    return {
        "avg_risk_score": avg_risk,
        "traffic_light": traffic_light,
        "summary": " / ".join(summary_parts) if summary_parts else "분석이 완료되었습니다.",
        "high_risk_ingredients": high_risk,
        "allergy_warnings": allergy_warnings,
        "irritant_warnings": irritant_warnings,
        "acne_warnings": acne_warnings,
        "efficacy": {"moisturizing": moisturizing, "soothing": soothing},
        "personalized_warnings": personalized_warnings,
    }


def _get_user_context(user_id):
    """사용자 프로필 + 알레르기 목록 반환."""
    from users.models import UserSkinProfile, UserAllergy
    profile = UserSkinProfile.objects.filter(user_id=user_id).select_related("skin_type").first()
    allergy_names = list(
        UserAllergy.objects.filter(user_id=user_id)
        .select_related("allergy")
        .values_list("allergy__allergy_name_kr", flat=True)
    )
    return profile, allergy_names


# =====================
# OCR 성분 분석
# =====================

@csrf_exempt
def upload_ocr_image(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST 요청만 허용됩니다."}, status=405)

    user_id = request.POST.get("user_id")
    product_id = request.POST.get("product_id")
    image_type = request.POST.get("image_type", "ingredient_label")
    image_file = request.FILES.get("image")

    if not user_id:
        return JsonResponse({"success": False, "message": "user_id가 필요합니다."}, status=400)

    if image_file:
        upload_dir = os.path.join(settings.MEDIA_ROOT, "ocr_images")
        os.makedirs(upload_dir, exist_ok=True)
        file_name = f"user{user_id}_{image_file.name}"
        file_path = os.path.join(upload_dir, file_name)
        with open(file_path, "wb") as f:
            for chunk in image_file.chunks():
                f.write(chunk)
        image_url = f"{settings.MEDIA_URL}ocr_images/{file_name}"
    else:
        image_url = request.POST.get("image_url", "")

    ocr_image = OCRImage.objects.create(
        user_id=user_id,
        product_id=product_id if product_id else None,
        image_url=image_url,
        image_type=image_type,
    )
    return JsonResponse(
        {"success": True, "ocr_image_id": ocr_image.ocr_image_id, "image_url": image_url},
        json_dumps_params={"ensure_ascii": False},
    )


@csrf_exempt
def save_ocr_result(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST 요청만 허용됩니다."}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "JSON 형식이 올바르지 않습니다."}, status=400)

    user_id = data.get("user_id")
    product_id = data.get("product_id")
    image_url = data.get("image_url", "")
    raw_text = data.get("raw_text", "")
    ingredients = data.get("ingredients", [])
    ocr_confidence = data.get("ocr_confidence")
    ocr_image_id = data.get("ocr_image_id")
    product_name = data.get("product_name")
    capacity = data.get("capacity")
    usage = data.get("usage")
    cautions = data.get("cautions")
    effects = data.get("effects")

    if not user_id:
        return JsonResponse({"success": False, "message": "user_id가 필요합니다."}, status=400)
    if not ingredients:
        return JsonResponse({"success": False, "message": "ingredients 배열이 필요합니다."}, status=400)

    if ocr_image_id:
        try:
            ocr_image = OCRImage.objects.get(ocr_image_id=ocr_image_id)
        except OCRImage.DoesNotExist:
            ocr_image = OCRImage.objects.create(
                user_id=user_id, product_id=product_id,
                image_url=image_url, image_type="ingredient_label",
            )
    else:
        ocr_image = OCRImage.objects.create(
            user_id=user_id, product_id=product_id,
            image_url=image_url or "ocr_uploaded", image_type="ingredient_label",
        )

    OCRRawText.objects.create(
        ocr_image=ocr_image, raw_text=raw_text,
        ocr_engine="PaddleOCR", ocr_confidence=ocr_confidence,
    )

    analysis = AnalysisResult.objects.create(
        user_id=user_id, product_id=product_id,
        ocr_image=ocr_image, analysis_type="OCR_INGREDIENT_ANALYSIS",
        risk_score=0, summary="분석 중",
        product_name=product_name,
        capacity=capacity,
        usage=usage,
        cautions=cautions,
        effects=effects,
    )

    user_profile, allergy_names = _get_user_context(user_id)
    matched_list, unmatched = [], []

    for name in ingredients:
        name = str(name).strip()
        if not name:
            continue
        ing = _match_ingredient(name)
        if ing:
            matched_list.append({"detected_text": name, "ingredient": ing})
            OCR_AnalysisDetail.objects.create(
                analysis=analysis, ingredient=ing, detected_text=name,
                risk_contribution=ing.risk_level or 0,
                caution_reason="DB 매칭 완료", match_status="MATCHED",
            )
        else:
            unmatched.append(name)

    risk_summary = _build_risk_summary(matched_list, user_profile, allergy_names)
    analysis.risk_score = risk_summary["avg_risk_score"]
    analysis.summary = risk_summary["summary"]
    analysis.save()

    # OCR 완료 알림 생성
    try:
        from users.models import UserNotification
        product_label = analysis.product_name or "성분"
        traffic = risk_summary["traffic_light"]
        label_map = {"GREEN": "안전", "YELLOW": "주의", "RED": "위험"}
        UserNotification.objects.create(
            user_id=user_id,
            type="OCR_COMPLETE",
            message=f"{product_label} 분석 완료 · {label_map.get(traffic, traffic)}",
            related_id=analysis.analysis_id,
        )
    except Exception:
        pass

    matched_output = [
        {
            "detected_text": item["detected_text"],
            "ingredient_id": item["ingredient"].ingredient_id,
            "ingredient_name_kr": item["ingredient"].ingredient_name_kr,
            "ingredient_name_en": item["ingredient"].ingredient_name_en,
            "risk_level": item["ingredient"].risk_level,
            "allergy_flag": item["ingredient"].allergy_flag,
            "irritant_flag": item["ingredient"].irritant_flag,
            "acne_caution_flag": item["ingredient"].acne_caution_flag,
            "moisturizing_flag": item["ingredient"].moisturizing_flag,
            "soothing_flag": item["ingredient"].soothing_flag,
        }
        for item in matched_list
    ]

    return JsonResponse(
        {
            "success": True,
            "message": "OCR 분석이 완료되었습니다.",
            "analysis_id": analysis.analysis_id,
            "product_name": analysis.product_name,
            "capacity": analysis.capacity,
            "usage": analysis.usage,
            "cautions": analysis.cautions,
            "effects": analysis.effects,
            "risk_score": risk_summary["avg_risk_score"],
            "traffic_light": risk_summary["traffic_light"],
            "summary": risk_summary["summary"],
            "matched_count": len(matched_list),
            "unmatched_count": len(unmatched),
            "matched_ingredients": matched_output,
            "unmatched_ingredients": unmatched,
            "high_risk_ingredients": risk_summary["high_risk_ingredients"],
            "allergy_warnings": risk_summary["allergy_warnings"],
            "acne_warnings": risk_summary["acne_warnings"],
            "efficacy": risk_summary["efficacy"],
            "personalized_warnings": risk_summary["personalized_warnings"],
        },
        json_dumps_params={"ensure_ascii": False},
    )


@require_GET
def analysis_detail(request, analysis_id):
    try:
        analysis = AnalysisResult.objects.get(analysis_id=analysis_id)
    except AnalysisResult.DoesNotExist:
        return JsonResponse({"success": False, "message": "분석 결과를 찾을 수 없습니다."}, status=404,
                            json_dumps_params={"ensure_ascii": False})

    details = OCR_AnalysisDetail.objects.filter(analysis=analysis).select_related("ingredient")
    ingredient_details = [
        {
            "ingredient_id": d.ingredient_id,
            "ingredient_name_kr": d.ingredient.ingredient_name_kr,
            "detected_text": d.detected_text,
            "risk_contribution": d.risk_contribution,
            "caution_reason": d.caution_reason,
            "match_status": d.match_status,
        }
        for d in details
    ]

    return JsonResponse(
        {
            "success": True,
            "analysis": {
                "analysis_id": analysis.analysis_id,
                "user_id": analysis.user_id,
                "product_id": analysis.product_id,
                "analysis_type": analysis.analysis_type,
                "risk_score": analysis.risk_score,
                "summary": analysis.summary,
                "product_name": analysis.product_name,
                "capacity": analysis.capacity,
                "usage": analysis.usage,
                "cautions": analysis.cautions,
                "effects": analysis.effects,
                "created_at": str(analysis.created_at),
            },
            "ingredient_details": ingredient_details,
        },
        json_dumps_params={"ensure_ascii": False},
    )


@csrf_exempt
def delete_analysis(request, analysis_id):
    """성분 분석 결과 삭제."""
    if request.method != "DELETE":
        return JsonResponse({"success": False, "message": "DELETE 요청만 허용됩니다."}, status=405)

    user_id = request.GET.get("user_id")
    try:
        analysis = AnalysisResult.objects.get(analysis_id=analysis_id, user_id=user_id)
    except AnalysisResult.DoesNotExist:
        return JsonResponse({"success": False, "message": "분석 결과를 찾을 수 없거나 권한이 없습니다."}, status=404,
                            json_dumps_params={"ensure_ascii": False})

    analysis.delete()
    return JsonResponse({"success": True, "message": "분석 결과가 삭제되었습니다."}, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
def analyze_product(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST 요청만 허용됩니다."}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "JSON 형식이 올바르지 않습니다."}, status=400)

    user_id = data.get("user_id")
    product_id = data.get("product_id")

    if not user_id or not product_id:
        return JsonResponse({"success": False, "message": "user_id와 product_id가 필요합니다."}, status=400)

    mappings = ProductIngredient.objects.filter(product_id=product_id).select_related("ingredient")
    if not mappings.exists():
        return JsonResponse({"success": False, "message": "해당 제품의 성분 정보가 없습니다."}, status=404,
                            json_dumps_params={"ensure_ascii": False})

    user_profile, allergy_names = _get_user_context(user_id)
    matched_list = [{"detected_text": m.ingredient.ingredient_name_kr, "ingredient": m.ingredient} for m in mappings]
    risk_summary = _build_risk_summary(matched_list, user_profile, allergy_names)

    analysis = AnalysisResult.objects.create(
        user_id=user_id, product_id=product_id,
        analysis_type="PRODUCT_SEARCH_ANALYSIS",
        risk_score=risk_summary["avg_risk_score"],
        summary=risk_summary["summary"],
    )
    for item in matched_list:
        OCR_AnalysisDetail.objects.create(
            analysis=analysis, ingredient=item["ingredient"],
            detected_text=item["detected_text"],
            risk_contribution=item["ingredient"].risk_level or 0,
            caution_reason="제품 DB 기반 분석", match_status="MATCHED",
        )

    return JsonResponse(
        {
            "success": True,
            "analysis_id": analysis.analysis_id,
            "risk_score": risk_summary["avg_risk_score"],
            "traffic_light": risk_summary["traffic_light"],
            "summary": risk_summary["summary"],
            "total_ingredients": len(matched_list),
            "high_risk_ingredients": risk_summary["high_risk_ingredients"],
            "allergy_warnings": risk_summary["allergy_warnings"],
            "acne_warnings": risk_summary["acne_warnings"],
            "efficacy": risk_summary["efficacy"],
            "personalized_warnings": risk_summary["personalized_warnings"],
        },
        json_dumps_params={"ensure_ascii": False},
    )


@require_GET
def analysis_history(request, user_id):
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
# 챗봇
# =====================

@csrf_exempt
def chat_start(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST 요청만 허용됩니다."}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "JSON 형식이 올바르지 않습니다."}, status=400)

    user_id = data.get("user_id")
    if not user_id:
        return JsonResponse({"success": False, "message": "user_id가 필요합니다."}, status=400)

    session = ChatSession.objects.create(user_id=user_id)
    return JsonResponse(
        {"success": True, "session_id": session.session_id},
        json_dumps_params={"ensure_ascii": False},
    )


@csrf_exempt
def chat_message(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST 요청만 허용됩니다."}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "JSON 형식이 올바르지 않습니다."}, status=400)

    user_id = data.get("user_id")
    session_id = data.get("session_id")
    message_text = data.get("message", "").strip()

    if not user_id or not message_text:
        return JsonResponse({"success": False, "message": "user_id와 message가 필요합니다."}, status=400)

    if session_id:
        session = ChatSession.objects.filter(session_id=session_id, user_id=user_id).first()
        if not session:
            session = ChatSession.objects.create(user_id=user_id)
    else:
        session = ChatSession.objects.create(user_id=user_id)

    ChatMessage.objects.create(
        session=session, user_id=user_id,
        message_type="USER", content=message_text,
    )

    prev_messages = ChatMessage.objects.filter(session=session).order_by("created_at")[:-1]
    context_history = [
        {
            "role": "user" if m.message_type == "USER" else "assistant",
            "content": m.content,
        }
        for m in prev_messages
    ]

    intent, db_context = _analyze_intent_and_fetch(message_text, user_id)
    bot_reply = _generate_response(message_text, intent, db_context, context_history, user_id)

    ChatMessage.objects.create(
        session=session, user_id=user_id,
        message_type="BOT", content=bot_reply, intent=intent,
    )

    return JsonResponse(
        {"success": True, "session_id": session.session_id, "intent": intent, "reply": bot_reply},
        json_dumps_params={"ensure_ascii": False},
    )


def _analyze_intent_and_fetch(message, user_id):
    msg_lower = message.lower()

    if any(k in msg_lower for k in ["성분", "ingredient", "함유", "들어있", "위험", "알레르기", "자극"]):
        intent = "ingredient"
    elif any(k in msg_lower for k in ["제품", "추천", "화장품", "크림", "세럼", "토너", "로션", "어떤 제품"]):
        intent = "product_recommendation"
    elif any(k in msg_lower for k in ["리뷰", "후기", "평점", "사용자 평가"]):
        intent = "review"
    elif any(k in msg_lower for k in ["피부", "타입", "건성", "지성", "민감", "여드름", "복합"]):
        intent = "skin_type"
    elif any(k in msg_lower for k in ["분석", "결과", "이전 분석", "OCR"]):
        intent = "analysis"
    else:
        intent = "general"

    db_context = {}

    if intent == "ingredient":
        ings = Ingredient.objects.filter(
            Q(ingredient_name_kr__icontains=message) | Q(ingredient_name_en__icontains=message)
        )[:5]
        if ings:
            db_context["ingredients"] = [
                {
                    "name_kr": i.ingredient_name_kr,
                    "risk_level": i.risk_level,
                    "allergy_flag": i.allergy_flag,
                    "irritant_flag": i.irritant_flag,
                    "description": i.description,
                }
                for i in ings
            ]

    elif intent == "product_recommendation":
        from recommendation.models import Recommendation
        recs = Recommendation.objects.filter(user_id=user_id).select_related("product").order_by("rank_order")[:5]
        if recs:
            db_context["recommendations"] = [
                {"product_name": r.product.product_name, "reason": r.reason, "score": r.score}
                for r in recs
            ]

    elif intent == "analysis":
        recent = AnalysisResult.objects.filter(user_id=user_id).order_by("-created_at").first()
        if recent:
            db_context["last_analysis"] = {
                "analysis_id": recent.analysis_id,
                "risk_score": recent.risk_score,
                "summary": recent.summary,
                "created_at": str(recent.created_at),
            }

    elif intent == "skin_type":
        from users.models import UserSkinProfile, UserSkinConcern
        profile = UserSkinProfile.objects.filter(user_id=user_id).select_related("skin_type").first()
        if profile:
            concerns = list(
                UserSkinConcern.objects.filter(user_id=user_id)
                .values_list("concern__concern_name_kr", flat=True)
            )
            db_context["skin_profile"] = {
                "skin_type": profile.skin_type.skin_type_name_kr if profile.skin_type else "미설정",
                "skin_concerns": concerns,
                "sensitivity_level": profile.sensitivity_level,
                "acne_prone_flag": profile.acne_prone_flag,
            }

    return intent, db_context


def _generate_response(message, intent, db_context, history, user_id):
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")

    if api_key and api_key.startswith("sk-ant"):
        return _call_claude(message, intent, db_context, history, api_key)
    elif api_key and api_key.startswith("sk-"):
        return _call_openai(message, intent, db_context, history, api_key)
    else:
        return _rule_based_response(message, intent, db_context)


def _call_claude(message, intent, db_context, history, api_key):
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        system_prompt = _build_system_prompt(db_context, intent)
        messages = history + [{"role": "user", "content": message}]
        response = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=1024,
            system=system_prompt, messages=messages,
        )
        return response.content[0].text
    except Exception:
        return _rule_based_response(message, intent, db_context)


def _call_openai(message, intent, db_context, history, api_key):
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        system_prompt = _build_system_prompt(db_context, intent)
        messages = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": message}]
        response = client.chat.completions.create(
            model="gpt-4o-mini", messages=messages, max_tokens=1024,
        )
        return response.choices[0].message.content
    except Exception:
        return _rule_based_response(message, intent, db_context)


def _build_system_prompt(db_context, intent):
    base = (
        "당신은 DermaLens의 AI 뷰티 어시스턴트입니다. "
        "화장품 성분, 피부 타입, 제품 추천에 대해 전문적이고 친절하게 답변하세요. "
        "의학적 진단은 하지 마세요.\n\n"
    )
    if db_context.get("ingredients"):
        ings_text = "\n".join(
            f"- {i['name_kr']}: 위험도 {i['risk_level']}, 알레르기={i['allergy_flag']}, 설명={i['description']}"
            for i in db_context["ingredients"]
        )
        base += f"[관련 성분 정보]\n{ings_text}\n\n"
    if db_context.get("recommendations"):
        recs_text = "\n".join(
            f"- {r['product_name']}: {r['reason']} (점수: {r['score']})"
            for r in db_context["recommendations"]
        )
        base += f"[사용자 맞춤 추천 제품]\n{recs_text}\n\n"
    if db_context.get("last_analysis"):
        a = db_context["last_analysis"]
        base += f"[최근 분석 결과] 위험도: {a['risk_score']}, 요약: {a['summary']}\n\n"
    if db_context.get("skin_profile"):
        p = db_context["skin_profile"]
        base += (
            f"[사용자 피부 프로필] 피부타입: {p['skin_type']}, "
            f"피부고민: {', '.join(p.get('skin_concerns', []))}, "
            f"민감도: {p['sensitivity_level']}\n\n"
        )
    return base


def _rule_based_response(message, intent, db_context):
    if intent == "ingredient" and db_context.get("ingredients"):
        ing = db_context["ingredients"][0]
        risk_text = "낮음" if (ing["risk_level"] or 0) <= 2 else ("중간" if (ing["risk_level"] or 0) <= 5 else "높음")
        return (
            f"'{ing['name_kr']}'에 대한 정보입니다.\n"
            f"• 위험도: {risk_text} ({ing['risk_level']})\n"
            f"• 알레르기 유발 가능: {'예' if ing['allergy_flag'] else '아니오'}\n"
            f"• 피부 자극 가능: {'예' if ing['irritant_flag'] else '아니오'}\n"
            + (f"• 설명: {ing['description']}" if ing.get("description") else "")
        )
    if intent == "product_recommendation" and db_context.get("recommendations"):
        lines = ["맞춤 제품 추천 목록입니다:"]
        for i, r in enumerate(db_context["recommendations"], 1):
            lines.append(f"{i}. {r['product_name']} - {r['reason']}")
        return "\n".join(lines)
    if intent == "skin_type" and db_context.get("skin_profile"):
        p = db_context["skin_profile"]
        return (
            f"피부 프로필 정보입니다.\n"
            f"• 피부 타입: {p['skin_type']}\n"
            f"• 피부 고민: {', '.join(p.get('skin_concerns', [])) or '없음'}\n"
            f"• 민감도: {p['sensitivity_level'] or '미설정'}\n"
            f"• 여드름성 피부: {'예' if p['acne_prone_flag'] else '아니오'}"
        )
    if intent == "analysis" and db_context.get("last_analysis"):
        a = db_context["last_analysis"]
        return (
            f"가장 최근 분석 결과입니다.\n"
            f"• 위험도 점수: {a['risk_score']}\n"
            f"• 요약: {a['summary']}\n"
            f"• 분석 일시: {a['created_at']}"
        )
    return (
        "안녕하세요! DermaLens AI 어시스턴트입니다. "
        "화장품 성분, 피부 타입, 제품 추천에 관한 질문을 해주세요. "
        "예: '히알루론산은 어떤 성분인가요?', '건성 피부에 맞는 제품 추천해주세요'"
    )


@require_GET
def chat_history(request, session_id):
    messages = ChatMessage.objects.filter(session_id=session_id).order_by("created_at")
    data = [
        {
            "message_id": m.message_id,
            "message_type": m.message_type,
            "content": m.content,
            "intent": m.intent,
            "created_at": str(m.created_at),
        }
        for m in messages
    ]
    return JsonResponse(
        {"success": True, "session_id": session_id, "count": len(data), "messages": data},
        json_dumps_params={"ensure_ascii": False},
    )


@require_GET
def user_sessions(request, user_id):
    sessions = ChatSession.objects.filter(user_id=user_id).order_by("-created_at")[:20]
    data = [
        {
            "session_id": s.session_id,
            "created_at": str(s.created_at),
            "ended_at": str(s.ended_at) if s.ended_at else None,
        }
        for s in sessions
    ]
    return JsonResponse(
        {"success": True, "count": len(data), "sessions": data},
        json_dumps_params={"ensure_ascii": False},
    )


# =====================
# OCR 서버 연동
# =====================

@csrf_exempt
def request_ocr(request):
    """프론트 → 백엔드: 이미지 받아 OCR 서버로 전달 후 결과 반환."""
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST 요청만 허용됩니다."}, status=405)

    user_id = request.POST.get("user_id")
    image_url = request.POST.get("image_url", "")
    image_file = request.FILES.get("image")

    if not user_id:
        return JsonResponse({"success": False, "message": "user_id가 필요합니다."}, status=400)

    # 이미지 파일 업로드된 경우 저장 후 URL 생성
    if image_file and not image_url:
        upload_dir = os.path.join(settings.MEDIA_ROOT, "ocr_images")
        os.makedirs(upload_dir, exist_ok=True)
        file_name = f"user{user_id}_{image_file.name}"
        file_path = os.path.join(upload_dir, file_name)
        with open(file_path, "wb") as f:
            for chunk in image_file.chunks():
                f.write(chunk)
        base_url = getattr(settings, "BASE_URL", "https://dermalens-production.up.railway.app")
        image_url = f"{base_url}{settings.MEDIA_URL}ocr_images/{file_name}"

    if not image_url:
        return JsonResponse({"success": False, "message": "image_url 또는 image 파일이 필요합니다."}, status=400)

    ocr_server_url = getattr(settings, "OCR_SERVER_URL", "https://web-production-38634.up.railway.app")
    payload = json.dumps({"user_id": str(user_id), "image_url": image_url}).encode("utf-8")
    req = urllib.request.Request(
        f"{ocr_server_url}/ocr",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            ocr_resp = json.loads(resp.read().decode("utf-8"))
        return JsonResponse(
            {"success": True, "message": "OCR 분석이 완료되었습니다.", "result": ocr_resp},
            json_dumps_params={"ensure_ascii": False},
        )
    except Exception:
        return JsonResponse(
            {"success": False, "message": "OCR 서버 연결에 실패했습니다."},
            status=502,
            json_dumps_params={"ensure_ascii": False},
        )


# =====================
# 챗봇 서버 연동 (POST /api/chat/)
# =====================

def _call_chatbot_server(message: str) -> dict | None:
    """챗봇 서버(CHATBOT_URL/chat)에 메시지 전달 후 intent/keywords 반환."""
    chatbot_url = getattr(settings, "CHATBOT_URL", "http://localhost:5000")
    url = f"{chatbot_url}/chat"
    payload = json.dumps({"message": message}).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _build_chat_response(chatbot_resp: dict, user_id: int | None) -> dict:
    """챗봇 서버 응답 + DB 조회 결과를 합쳐 최종 응답 구성."""
    intent = chatbot_resp.get("intent", "UNKNOWN")
    keywords = chatbot_resp.get("keywords", {})
    message = chatbot_resp.get("message", "")
    components = list(chatbot_resp.get("components", []))
    quick_replies = list(chatbot_resp.get("quickReplies", []))

    from products.models import Product
    from review.models import Review

    if intent == "PRODUCT_RECOMMEND":
        category_name = keywords.get("category", "")
        skin_type = keywords.get("skin_type", "")

        # 카테고리 필터
        base_qs = Product.objects.select_related("brand", "category")
        if category_name:
            base_qs = base_qs.filter(category__category_name__icontains=category_name)

        # 피부타입 키워드 → SkinTypeMaster 코드 조건 매핑
        #   코드 형식: [O지성/D건성][S민감/N비민감][+수분충분/-수분부족]
        from users.models import UserSkinProfile
        from review.models import Review
        from django.db.models import Avg, Count

        code_filter = None
        if "지성" in skin_type or "오일" in skin_type:
            code_filter = Q(skin_type__skin_type_code__startswith="O")
        elif "건성" in skin_type or "건조" in skin_type:
            code_filter = Q(skin_type__skin_type_code__startswith="D")
        if "민감" in skin_type:
            sens = Q(skin_type__skin_type_code__contains="S")
            code_filter = sens if code_filter is None else (code_filter & sens)

        products = []
        if code_filter is not None:
            # 해당 피부타입 유저들이 높게 평가한 제품 순
            user_ids = list(
                UserSkinProfile.objects.filter(code_filter).values_list("user_id", flat=True)
            )
            if user_ids:
                ranked = (
                    Review.objects
                    .filter(user_id__in=user_ids, product__in=base_qs)
                    .values("product_id")
                    .annotate(avg=Avg("rating"), cnt=Count("review_id"))
                    .filter(cnt__gte=1)
                    .order_by("-avg", "-cnt")[:5]
                )
                ranked_ids = [r["product_id"] for r in ranked]
                if ranked_ids:
                    pmap = {p.product_id: p for p in base_qs.filter(product_id__in=ranked_ids)}
                    products = [pmap[pid] for pid in ranked_ids if pid in pmap]

        # 피부타입 매칭 결과가 부족하면 카테고리 기본 제품으로 보강
        if len(products) < 5:
            have = {p.product_id for p in products}
            for p in base_qs.order_by("product_id"):
                if p.product_id not in have:
                    products.append(p)
                if len(products) >= 5:
                    break

        for p in products[:5]:
            components.append({
                "type": "card",
                "product_id": p.product_id,
                "title": p.product_name,
                "description": p.brand.brand_name_kr if p.brand else "",
                "image_url": p.image_url,
                "price": p.price,
                "riskLevel": "LOW",
                "buttonText": "제품 상세보기",
            })
        if not quick_replies:
            quick_replies = ["성분 분석", "피부 진단"]

    elif intent in ("INGREDIENT_RISK", "INGREDIENT_ANALYSIS"):
        ing_name = keywords.get("ingredient", "")
        ing = _match_ingredient(ing_name) if ing_name else None
        if ing:
            risk = ing.risk_level or 0
            risk_label = "HIGH" if risk >= 7 else ("MEDIUM" if risk >= 4 else "LOW")
            from products.models import IngredientFunction
            functions = list(
                IngredientFunction.objects
                .filter(ingredient=ing)
                .select_related("function")
                .values_list("function__function_name_kr", flat=True)
            )
            components.append({
                "type": "card",
                "title": ing.ingredient_name_kr,
                "name_en": ing.ingredient_name_en or "",
                "description": ing.description or "",
                "functions": functions,
                "riskLevel": risk_label,
                "allergy_flag": ing.allergy_flag,
                "irritant_flag": ing.irritant_flag,
                "acne_caution_flag": ing.acne_caution_flag,
                "moisturizing_flag": ing.moisturizing_flag,
                "soothing_flag": ing.soothing_flag,
                "buttonText": "성분 상세보기",
            })
        else:
            # 성분 못 찾음 → 챗봇이 안내 메시지 띄울 수 있도록 신호
            label = ing_name or "해당"
            message = f"'{label}' 성분 정보를 찾을 수 없어요. 성분명을 다시 확인해 주세요."
            if not quick_replies:
                quick_replies = ["제품 추천", "피부 진단"]
            return {
                "intent": intent,
                "score": chatbot_resp.get("score", 0),
                "keywords": keywords,
                "message": message,
                "components": components,
                "quickReplies": quick_replies,
                "not_found": True,
            }
        if not quick_replies:
            quick_replies = ["제품 추천", "피부 진단"]

    elif intent == "SKIN_TYPE_TEST":
        components.append({
            "type": "link",
            "label": "피부 진단 시작하기",
            "url": "/survey",
        })
        if not quick_replies:
            quick_replies = ["제품 추천", "성분 분석"]

    elif intent == "REVIEW_SUMMARY":
        product_name = keywords.get("product", "") or keywords.get("category", "")
        if product_name:
            product = Product.objects.filter(product_name__icontains=product_name).first()
            if product:
                avg = Review.objects.filter(product=product).aggregate(avg=Avg("rating"))["avg"]
                count = Review.objects.filter(product=product).count()
                components.append({
                    "type": "card",
                    "title": product.product_name,
                    "description": f"평균 평점: {round(avg, 1) if avg else '없음'} / 리뷰 {count}개",
                    "riskLevel": "LOW",
                    "buttonText": "리뷰 전체보기",
                })
        if not quick_replies:
            quick_replies = ["제품 추천", "성분 분석"]

    elif intent == "ANALYSIS_HISTORY" and user_id:
        recent = AnalysisResult.objects.filter(user_id=user_id).order_by("-created_at").first()
        if recent:
            risk = recent.risk_score or 0
            risk_label = "HIGH" if risk >= 7 else ("MEDIUM" if risk >= 4 else "LOW")
            components.append({
                "type": "card",
                "title": "최근 분석 결과",
                "description": recent.summary or "",
                "riskLevel": risk_label,
                "buttonText": "분석 상세보기",
            })
        if not quick_replies:
            quick_replies = ["제품 추천", "성분 분석"]

    else:  # UNKNOWN
        if not quick_replies:
            quick_replies = ["제품 추천", "성분 분석", "피부 진단"]

    return {
        "intent": intent,
        "score": chatbot_resp.get("score", 0),
        "keywords": keywords,
        "message": message,
        "components": components,
        "quickReplies": quick_replies,
    }


@csrf_exempt
def chat(request):
    """
    챗봇 중계 엔드포인트.
    - intent/keywords를 직접 보내면 챗봇 서버 호출 생략 (챗봇 담당자 직접 연동 방식)
    - intent 없으면 챗봇 서버에 분석 요청 후 처리
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST 요청만 허용됩니다."}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "JSON 형식이 올바르지 않습니다."}, status=400)

    message = data.get("message", "").strip()
    user_id = data.get("user_id")
    intent = data.get("intent")
    keywords = data.get("keywords", {})

    if not message:
        return JsonResponse({"success": False, "message": "message가 필요합니다."}, status=400)

    # 세션 처리
    session_id = data.get("session_id")
    session = None
    if user_id:
        if session_id:
            session = ChatSession.objects.filter(session_id=session_id, user_id=user_id).first()
        if not session:
            session = ChatSession.objects.create(user_id=user_id)

    # 유저 메시지 저장
    if session:
        ChatMessage.objects.create(
            session=session, user_id=user_id,
            message_type="USER", content=message,
        )

    # 챗봇이 intent+keywords 직접 전달한 경우 → 챗봇 서버 호출 생략
    if intent:
        chatbot_resp = {
            "intent": intent,
            "keywords": keywords,
            "message": message,
            "score": data.get("score", 1.0),
            "components": [],
            "quickReplies": [],
        }
    else:
        chatbot_resp = _call_chatbot_server(message)

    if chatbot_resp is None:
        return JsonResponse({
            "intent": "UNKNOWN",
            "score": 0,
            "keywords": {},
            "message": "현재 챗봇 서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.",
            "components": [],
            "quickReplies": ["제품 추천", "성분 분석", "피부 진단"],
        }, json_dumps_params={"ensure_ascii": False})

    response = _build_chat_response(chatbot_resp, user_id)

    # 봇 응답 저장
    if session:
        ChatMessage.objects.create(
            session=session, user_id=user_id,
            message_type="BOT", content=response.get("message", ""),
            intent=response.get("intent"),
        )
        response["session_id"] = session.session_id

    return JsonResponse(response, json_dumps_params={"ensure_ascii": False})


# =====================
# 성분 자동완성 (챗봇 타이핑용)
# =====================

@require_GET
def ingredient_autocomplete(request):
    """성분명 부분일치 자동완성. 이름 배열만 반환."""
    q = (request.GET.get("q") or "").strip()
    try:
        limit = min(int(request.GET.get("limit", 8)), 20)
    except ValueError:
        limit = 8

    if not q:
        return JsonResponse({"ingredients": []}, json_dumps_params={"ensure_ascii": False})

    names = list(
        Ingredient.objects
        .filter(Q(ingredient_name_kr__icontains=q) | Q(ingredient_name_en__icontains=q))
        .order_by("ingredient_name_kr")
        .values_list("ingredient_name_kr", flat=True)[:limit]
    )
    return JsonResponse({"ingredients": names}, json_dumps_params={"ensure_ascii": False})
