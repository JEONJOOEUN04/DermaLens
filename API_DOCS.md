# DermaLens API 문서

**Base URL:** `https://dermalens-production.up.railway.app`

## 인증 방식
JWT Bearer Token 사용
```
Authorization: Bearer {access_token}
```
- `access_token` 유효시간: 60분
- `refresh_token` 유효시간: 7일

---

## 공통 응답 형식
```json
{ "success": true }   // 성공
{ "success": false, "message": "에러 메시지" }  // 실패
```

---

## 1. Users (회원)

### POST /api/users/signup/ — 회원가입
**Request**
```json
{
  "email": "test@test.com",
  "password": "test1234",
  "nickname": "테스트유저"
}
```
**Response** `201`
```json
{
  "success": true,
  "message": "회원가입 성공",
  "user": {
    "user_id": 1,
    "email": "test@test.com",
    "nickname": "테스트유저",
    "created_at": "2026-05-25 00:00:00"
  },
  "tokens": {
    "access": "eyJ...",
    "refresh": "eyJ..."
  }
}
```

---

### GET /api/users/check-email/?email={email} — 이메일 중복 확인
**Response** `200`
```json
{
  "success": true,
  "available": true
}
```
> `available: true` → 사용 가능 / `false` → 이미 존재

---

### POST /api/users/login/ — 로그인
**Request**
```json
{
  "email": "test@test.com",
  "password": "test1234"
}
```
**Response** `200`
```json
{
  "success": true,
  "message": "로그인 성공",
  "user": {
    "user_id": 1,
    "email": "test@test.com",
    "nickname": "테스트유저",
    "created_at": "2026-05-25 00:00:00"
  },
  "tokens": {
    "access": "eyJ...",
    "refresh": "eyJ..."
  }
}
```

---

### POST /api/users/logout/ — 로그아웃
**Request**
```json
{ "refresh": "{refresh_token}" }
```
**Response** `200`
```json
{ "success": true, "message": "로그아웃 성공" }
```

---

### POST /api/users/token/refresh/ — 토큰 갱신
**Request**
```json
{ "refresh": "{refresh_token}" }
```
**Response** `200`
```json
{
  "access": "eyJ...",
  "refresh": "eyJ..."
}
```

---

### DELETE /api/users/delete/{user_id}/ — 회원 탈퇴
**Response** `200`
```json
{ "success": true, "message": "회원탈퇴 완료" }
```

---

### GET /api/users/profile/{user_id}/ — 유저 프로필 조회
**Response** `200`
```json
{
  "success": true,
  "user": {
    "user_id": 1,
    "email": "test@test.com",
    "nickname": "테스트유저",
    "created_at": "2026-05-25 00:00:00"
  }
}
```

---

### PATCH /api/users/profile/{user_id}/nickname/ — 닉네임 변경
**Request**
```json
{ "nickname": "새닉네임" }
```
**Response** `200`
```json
{
  "success": true,
  "message": "닉네임이 변경되었습니다.",
  "user": { "user_id": 1, "email": "...", "nickname": "새닉네임", "created_at": "..." }
}
```

---

### GET /api/users/skin-profile/{user_id}/ — 피부 프로필 조회
**Response** `200`
```json
{
  "success": true,
  "profile": {
    "profile_id": 1,
    "user_id": 1,
    "skin_type": {
      "id": 1,
      "code": "ON+",
      "name_kr": "지성-정상-수분충분"
    },
    "skin_concerns": ["트러블", "모공"],
    "allergies": ["향료"],
    "sensitivity_level": 3,
    "acne_prone_flag": false,
    "preferred_texture": {
      "id": 1,
      "name_kr": "젤"
    },
    "updated_at": "2026-05-25 00:00:00"
  }
}
```

---

### PATCH /api/users/skin-profile/{user_id}/update/ — 피부 프로필 수정
**Request** (모든 필드 선택)
```json
{
  "skin_type_id": 1,
  "sensitivity_level": 3,
  "acne_prone_flag": false,
  "preferred_texture_id": 1,
  "concern_ids": [1, 2],
  "allergy_ids": [1]
}
```
**Response** `200`
```json
{ "success": true, "message": "피부 프로필이 업데이트 되었습니다." }
```

---

### POST /api/users/survey/ — 설문 저장 및 피부 타입 분석
**Request**
```json
{
  "user_id": 1,
  "selected_option_ids": [1, 6, 12, 17, 24, 27, 30, 34, 36, 38]
}
```
**Response** `200`
```json
{
  "success": true,
  "message": "설문 저장 성공",
  "response_id": 1,
  "result": {
    "skin_type_code": "ON+",
    "skin_type_name": "지성-정상-수분충분",
    "sensitivity_level": 3,
    "acne_prone_flag": false,
    "preferred_texture_id": 1,
    "skin_concerns": [1, 2],
    "allergies": []
  }
}
```

---

### GET /api/users/mypage/{user_id}/ — 마이페이지
**Response** `200`
```json
{
  "success": true,
  "user": { "user_id": 1, "email": "...", "nickname": "...", "created_at": "..." },
  "skin_profile": {
    "skin_type": "지성-정상-수분충분",
    "skin_concerns": ["트러블"],
    "sensitivity_level": 3,
    "acne_prone_flag": false
  },
  "activity_summary": {
    "like_count": 5,
    "review_count": 3,
    "analysis_count": 10
  }
}
```

---

### GET /api/users/mypage/{user_id}/likes/ — 좋아요한 제품 목록
**Query Params:** `page=1`, `size=20`

**Response** `200`
```json
{
  "success": true,
  "page": 1,
  "count": 2,
  "liked_products": [
    {
      "product_id": 1,
      "product_name": "코스알엑스 토너",
      "image_url": "https://...",
      "price": 15000,
      "created_at": "2026-05-25 00:00:00"
    }
  ]
}
```

---

### GET /api/users/mypage/{user_id}/reviews/ — 내 리뷰 목록
**Query Params:** `page=1`, `size=20`

**Response** `200`
```json
{
  "success": true,
  "page": 1,
  "count": 1,
  "reviews": [
    {
      "review_id": 1,
      "product_id": 1,
      "product_name": "코스알엑스 토너",
      "rating": 4,
      "review_text": "좋아요",
      "created_at": "2026-05-25 00:00:00",
      "updated_at": null
    }
  ]
}
```

---

### GET /api/users/mypage/{user_id}/analysis/ — 내 분석 기록
**Query Params:** `page=1`, `size=20`

**Response** `200`
```json
{
  "success": true,
  "page": 1,
  "count": 1,
  "history": [
    {
      "analysis_id": 1,
      "product_id": 1,
      "analysis_type": "PRODUCT_SEARCH_ANALYSIS",
      "risk_score": 3.2,
      "summary": "전반적으로 안전한 성분 구성입니다.",
      "created_at": "2026-05-25 00:00:00"
    }
  ]
}
```

---

### GET /api/users/mypage/{user_id}/recommendations/ — 내 추천 목록
**Query Params:** `page=1`, `size=20`

**Response** `200`
```json
{
  "success": true,
  "page": 1,
  "count": 1,
  "recommendations": [
    {
      "recommendation_id": 1,
      "product_id": 1,
      "product_name": "코스알엑스 토너",
      "image_url": "https://...",
      "score": 82.5,
      "reason": "지성 피부에 적합한 보습 성분 포함",
      "rank_order": 1,
      "created_at": "2026-05-25 00:00:00"
    }
  ]
}
```

---

### GET /api/users/kakao/ — 카카오 로그인 URL 요청
**Response** `200`
```json
{
  "success": true,
  "auth_url": "https://kauth.kakao.com/oauth/authorize?..."
}
```

---

## 2. Products (상품)

### GET /api/products/ — 상품 목록
**Query Params:** `page=1`, `size=20`

**Response** `200`
```json
{
  "success": true,
  "page": 1,
  "count": 20,
  "products": [
    {
      "product_id": 1,
      "product_name": "코스알엑스 AHA/BHA 클래리파잉 토너",
      "brand_name": "COSRX",
      "category_name": "토너",
      "image_url": "https://...",
      "product_url": "https://...",
      "volume": null,
      "price": 15000,
      "description": null,
      "like_count": null
    }
  ]
}
```

---

### GET /api/products/search/?q={keyword} — 상품 검색
**Query Params:** `q=토너`, `page=1`, `size=20`, `user_id=1`(선택)

**Response** `200`
```json
{
  "success": true,
  "keyword": "토너",
  "page": 1,
  "count": 5,
  "products": [ /* 상품 목록 동일 */ ]
}
```

---

### GET /api/products/popular/ — 인기 상품
**Query Params:** `page=1`, `size=20`

**Response** `200` — 상품 목록과 동일 구조

---

### GET /api/products/{product_id}/ — 상품 상세
**Response** `200`
```json
{
  "success": true,
  "product": {
    "product_id": 1,
    "product_name": "코스알엑스 토너",
    "brand_name": "COSRX",
    "category_name": "토너",
    "image_url": "https://...",
    "product_url": "https://...",
    "volume": null,
    "price": 15000,
    "description": null,
    "like_count": 10,
    "avg_rating": 4.3,
    "review_count": 7,
    "official_ingredient_text": "정제수, 나이아신아마이드..."
  }
}
```

---

### GET /api/products/{product_id}/ingredients/ — 상품 성분 목록
**Response** `200`
```json
{
  "success": true,
  "product_id": 1,
  "count": 15,
  "ingredients": [
    {
      "ingredient_id": 1,
      "ingredient_name_kr": "나이아신아마이드",
      "ingredient_name_en": "Niacinamide",
      "risk_level": 1,
      "allergy_flag": false,
      "irritant_flag": false,
      "acne_caution_flag": false,
      "moisturizing_flag": true,
      "soothing_flag": false,
      "description": null
    }
  ]
}
```

---

### GET /api/products/categories/ — 카테고리 목록
**Response** `200`
```json
{
  "success": true,
  "categories": [
    {
      "category_id": 1,
      "category_name": "스킨케어",
      "subcategories": [
        { "category_id": 5, "category_name": "토너" },
        { "category_id": 6, "category_name": "에센스" }
      ]
    }
  ]
}
```

---

### GET /api/products/categories/{category_id}/ — 카테고리별 상품
**Query Params:** `page=1`, `size=20`

**Response** `200` — 상품 목록과 동일 구조

---

### GET /api/products/ingredients/ — 성분 목록
**Query Params:** `page=1`, `size=50`

**Response** `200`
```json
{
  "success": true,
  "page": 1,
  "count": 50,
  "ingredients": [ /* 성분 목록 */ ]
}
```

---

### GET /api/products/ingredients/search/?name={name} — 성분 검색
**Query Params:** `name=나이아신아마이드`

**Response** `200`
```json
{
  "success": true,
  "keyword": "나이아신아마이드",
  "count": 1,
  "results": [ /* 성분 목록 */ ]
}
```

---

### GET /api/products/ingredients/{ingredient_id}/ — 성분 상세
**Response** `200`
```json
{
  "success": true,
  "ingredient": {
    "ingredient_id": 1,
    "ingredient_name_kr": "나이아신아마이드",
    "ingredient_name_en": "Niacinamide",
    "risk_level": 1,
    "allergy_flag": false,
    "irritant_flag": false,
    "acne_caution_flag": false,
    "moisturizing_flag": true,
    "soothing_flag": false,
    "description": null,
    "aliases": ["Vitamin B3", "비타민B3"]
  }
}
```

---

## 3. Analysis (분석)

### POST /api/analysis/upload-image/ — OCR 이미지 업로드
**Request** `multipart/form-data`
```
user_id: 1
product_id: 1 (선택)
image_type: ingredient_label
image: [파일]
```
**Response** `200`
```json
{
  "success": true,
  "ocr_image_id": 1,
  "image_url": "/media/ocr_images/user1_example.jpg"
}
```

---

### POST /api/analysis/ocr-result/ — OCR 결과 저장 및 성분 분석
**Request**
```json
{
  "user_id": 1,
  "product_id": 1,
  "raw_text": "정제수, 나이아신아마이드, 글리세린",
  "ingredients": ["정제수", "나이아신아마이드", "글리세린"],
  "ocr_confidence": 0.95,
  "ocr_image_id": 1
}
```
**Response** `200`
```json
{
  "success": true,
  "analysis_id": 1,
  "matched_count": 3,
  "unmatched": [],
  "risk_summary": {
    "traffic_light": "GREEN",
    "avg_risk_score": 1.2,
    "summary": "전반적으로 안전한 성분 구성입니다.",
    "high_risk_ingredients": [],
    "allergy_warnings": [],
    "irritant_warnings": [],
    "acne_warnings": [],
    "moisturizing_ingredients": ["글리세린"],
    "soothing_ingredients": [],
    "personalized_warnings": []
  },
  "matched_ingredients": [
    {
      "detected_text": "나이아신아마이드",
      "ingredient_id": 1,
      "ingredient_name_kr": "나이아신아마이드",
      "risk_level": 1,
      "allergy_flag": false,
      "irritant_flag": false,
      "acne_caution_flag": false,
      "moisturizing_flag": true,
      "soothing_flag": false
    }
  ]
}
```

---

### POST /api/analysis/analyze-product/ — 기존 제품 성분 분석
**Request**
```json
{
  "user_id": 1,
  "product_id": 1
}
```
**Response** `200` — OCR 결과와 동일 구조

---

### GET /api/analysis/detail/{analysis_id}/ — 분석 결과 상세 조회
**Response** `200`
```json
{
  "success": true,
  "analysis": {
    "analysis_id": 1,
    "user_id": 1,
    "product_id": 1,
    "analysis_type": "PRODUCT_SEARCH_ANALYSIS",
    "risk_score": 1.2,
    "summary": "전반적으로 안전한 성분 구성입니다.",
    "created_at": "2026-05-25 00:00:00",
    "details": [ /* 성분별 분석 상세 */ ]
  }
}
```

---

### GET /api/analysis/history/{user_id}/ — 분석 기록 목록
**Query Params:** `page=1`, `size=20`

**Response** `200`
```json
{
  "success": true,
  "page": 1,
  "count": 3,
  "history": [
    {
      "analysis_id": 1,
      "product_id": 1,
      "product_name": "코스알엑스 토너",
      "analysis_type": "OCR_ANALYSIS",
      "risk_score": 1.2,
      "traffic_light": "GREEN",
      "summary": "안전한 성분 구성",
      "created_at": "2026-05-25 00:00:00"
    }
  ]
}
```

---

### POST /api/analysis/chat/ — 챗봇 (통합 엔드포인트)
**Request**
```json
{
  "user_id": 1,
  "message": "지성 피부에 좋은 토너 추천해줘"
}
```
**Response** `200`
```json
{
  "success": true,
  "reply": "지성 피부에 적합한 토너를 추천드립니다.",
  "intent": "PRODUCT_RECOMMEND",
  "components": {
    "recommended_products": [
      {
        "product_id": 1,
        "product_name": "코스알엑스 토너",
        "brand_name": "COSRX",
        "image_url": "https://...",
        "price": 15000,
        "score": 82.5
      }
    ]
  }
}
```

---

### POST /api/analysis/chat/start/ — 채팅 세션 시작
**Request**
```json
{ "user_id": 1 }
```
**Response** `200`
```json
{ "success": true, "session_id": 1 }
```

---

### POST /api/analysis/chat/message/ — 채팅 메시지 전송
**Request**
```json
{
  "user_id": 1,
  "session_id": 1,
  "message": "지성 피부에 좋은 토너 추천해줘"
}
```
**Response** `200`
```json
{
  "success": true,
  "session_id": 1,
  "reply": "추천 결과입니다.",
  "intent": "PRODUCT_RECOMMEND",
  "components": { /* 챗봇 응답 컴포넌트 */ }
}
```

---

### GET /api/analysis/chat/history/{session_id}/ — 채팅 기록 조회
**Response** `200`
```json
{
  "success": true,
  "session_id": 1,
  "messages": [
    {
      "message_id": 1,
      "message_type": "USER",
      "content": "토너 추천해줘",
      "created_at": "2026-05-25 00:00:00"
    },
    {
      "message_id": 2,
      "message_type": "BOT",
      "content": "추천 결과입니다.",
      "created_at": "2026-05-25 00:00:00"
    }
  ]
}
```

---

### GET /api/analysis/chat/sessions/{user_id}/ — 유저 채팅 세션 목록
**Response** `200`
```json
{
  "success": true,
  "count": 2,
  "sessions": [
    {
      "session_id": 1,
      "created_at": "2026-05-25 00:00:00"
    }
  ]
}
```

---

## 4. Recommendation (추천)

### POST /api/recommendation/generate/ — 개인화 추천 생성
**Request**
```json
{
  "user_id": 1,
  "category_id": 5,
  "top_n": 10
}
```
> `category_id`, `top_n` 선택사항

**Response** `200`
```json
{
  "success": true,
  "message": "추천 생성 완료 (10개)",
  "recommendations": [
    {
      "recommendation_id": 1,
      "rank_order": 1,
      "product_id": 1,
      "product_name": "코스알엑스 토너",
      "image_url": "https://...",
      "price": 15000,
      "score": 82.5,
      "reason": "지성 피부에 적합한 보습 성분 포함"
    }
  ]
}
```

---

### GET /api/recommendation/user/{user_id}/ — 저장된 추천 목록 조회
**Query Params:** `page=1`, `size=20`

**Response** `200`
```json
{
  "success": true,
  "page": 1,
  "count": 10,
  "recommendations": [
    {
      "recommendation_id": 1,
      "rank_order": 1,
      "product_id": 1,
      "product_name": "코스알엑스 토너",
      "brand_name": "COSRX",
      "image_url": "https://...",
      "price": 15000,
      "score": 82.5,
      "reason": "지성 피부에 적합",
      "created_at": "2026-05-25 00:00:00"
    }
  ]
}
```

---

### POST /api/recommendation/like/ — 좋아요 토글
**Request**
```json
{
  "user_id": 1,
  "product_id": 1
}
```
**Response** `200`
```json
{
  "success": true,
  "message": "좋아요 추가",
  "liked": true,
  "like_count": 11
}
```
> 이미 좋아요한 경우 `"message": "좋아요 취소"`, `"liked": false`

---

### GET /api/recommendation/like/{user_id}/{product_id}/ — 좋아요 상태 확인
**Response** `200`
```json
{
  "success": true,
  "liked": true,
  "like_count": 11
}
```

---

## 5. Review (리뷰)

### POST /api/review/ — 리뷰 작성
**Request**
```json
{
  "user_id": 1,
  "product_id": 1,
  "rating": 4,
  "review_text": "수분감이 좋고 자극이 없어요."
}
```
> `rating`: 1~5 정수, 필수

**Response** `201`
```json
{
  "success": true,
  "message": "리뷰가 등록되었습니다.",
  "review_id": 1
}
```

---

### PATCH /api/review/{review_id}/update/ — 리뷰 수정
**Request**
```json
{
  "user_id": 1,
  "rating": 5,
  "review_text": "재구매 의사 있어요!"
}
```
**Response** `200`
```json
{ "success": true, "message": "리뷰가 수정되었습니다.", "review_id": 1 }
```

---

### DELETE /api/review/{review_id}/delete/ — 리뷰 삭제
**Request**
```json
{ "user_id": 1 }
```
**Response** `200`
```json
{ "success": true, "message": "리뷰가 삭제되었습니다." }
```

---

### GET /api/review/product/{product_id}/ — 상품별 리뷰 목록
**Query Params:** `page=1`, `size=20`, `sort=latest`(`latest` | `rating`)

**Response** `200`
```json
{
  "success": true,
  "product_id": 1,
  "avg_rating": 4.3,
  "page": 1,
  "count": 5,
  "reviews": [
    {
      "review_id": 1,
      "user_id": 1,
      "nickname": "테스트유저",
      "rating": 4,
      "review_text": "수분감이 좋아요.",
      "created_at": "2026-05-25 00:00:00",
      "updated_at": "2026-05-25 00:00:00"
    }
  ]
}
```

---

### GET /api/review/user/{user_id}/ — 유저별 리뷰 목록
**Query Params:** `page=1`, `size=20`

**Response** `200`
```json
{
  "success": true,
  "user_id": 1,
  "page": 1,
  "count": 2,
  "reviews": [ /* 리뷰 목록 */ ]
}
```

---

### POST /api/review/feedback/ — 앱 피드백 작성
**Request**
```json
{
  "user_id": 1,
  "product_id": 1,
  "feedback_type": "SATISFACTION",
  "satisfaction_score": 5,
  "side_effect_text": ""
}
```
> `feedback_type`: `SATISFACTION` | `SIDE_EFFECT` | `INQUIRY`

**Response** `201`
```json
{ "success": true, "message": "피드백이 등록되었습니다.", "feedback_id": 1 }
```

---

### GET /api/review/feedback/{user_id}/ — 피드백 목록
**Response** `200`
```json
{
  "success": true,
  "count": 1,
  "feedbacks": [
    {
      "feedback_id": 1,
      "product_id": 1,
      "feedback_type": "SATISFACTION",
      "satisfaction_score": 5,
      "side_effect_text": "",
      "created_at": "2026-05-25 00:00:00"
    }
  ]
}
```

---

### POST /api/review/search-log/ — 검색 기록 저장
**Request**
```json
{
  "user_id": 1,
  "keyword": "나이아신아마이드",
  "clicked_product_id": 1
}
```
> `clicked_product_id` 선택사항

**Response** `200`
```json
{ "success": true, "log_id": 1 }
```

---

### GET /api/review/search-history/{user_id}/ — 검색 기록 조회
**Response** `200`
```json
{
  "success": true,
  "count": 2,
  "search_history": [
    {
      "log_id": 1,
      "keyword": "나이아신아마이드",
      "clicked_product_id": 1,
      "created_at": "2026-05-25 00:00:00"
    }
  ]
}
```

---

## HTTP 상태 코드 요약

| 코드 | 의미 |
|------|------|
| 200 | 성공 |
| 201 | 생성 성공 |
| 400 | 잘못된 요청 (필수 파라미터 누락 등) |
| 401 | 인증 실패 (비밀번호 불일치) |
| 404 | 리소스 없음 |
| 405 | 잘못된 HTTP 메서드 |
| 502 | 외부 서버 오류 (카카오 등) |
