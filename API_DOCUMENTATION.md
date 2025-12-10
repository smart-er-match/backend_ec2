# Smart ER-Match API Documentation

## Base URL
`https://www.smart-er-match.shop/`

## Authentication
*   **Type:** Bearer Token (JWT)
*   **Header:** `Authorization: Bearer <access_token>`

---

## 1. Accounts (회원 관리)

### 회원가입
*   **URL:** `/accounts/signup/`
*   **Method:** `POST`
*   **Permission:** AllowAny
*   **Body:**
    ```json
    {
        "username": "user@example.com",
        "email": "user@example.com",
        "password": "password123!",
        "name": "홍길동",
        "phone_number": "01012345678",
        "birth_date": "1990-01-01",
        "gender": "M"
    }
    ```

### 아이디(이메일) 중복 확인
*   **URL:** `/accounts/signup/uu/?username=user@example.com`
*   **Method:** `GET`
*   **Permission:** AllowAny
*   **Response:** `{ "bool_uu": true }` (사용 가능 시 true)

### 로그인
*   **URL:** `/accounts/login/`
*   **Method:** `POST`
*   **Permission:** AllowAny
*   **Body:** `{"email": "user@example.com", "password": "..."}`
*   **Response:** `{"access": "...", "refresh": "...", "user": {...}}`

### 프로필 수정
*   **URL:** `/accounts/profile/update/`
*   **Method:** `PATCH`
*   **Permission:** IsAuthenticated
*   **Body:** `{"name": "...", "phone_number": "...", "gender": "..."}`

### 비밀번호 변경 (로그인 상태)
*   **URL:** `/accounts/password/change/`
*   **Method:** `POST`
*   **Permission:** IsAuthenticated
*   **Body:** `{"old_password": "...", "new_password": "...", "new_password_confirm": "..."}`
*   **Note:** **소셜 로그인(카카오, 네이버) 사용자는 이용 불가.**

### 이메일 찾기
*   **URL:** `/accounts/find/email/`
*   **Method:** `POST`
*   **Permission:** AllowAny
*   **Body:** `{"name": "홍길동", "birth_date": "1990-01-01"}`
*   **Response:** `{"result": true, "email": "ho**@example.com"}`

### 비밀번호 찾기 - 인증번호 발송
*   **URL:** `/accounts/find/password/send/`
*   **Method:** `POST`
*   **Permission:** AllowAny
*   **Body:** `{"email": "user@example.com", "birth_date": "1990-01-01"}`
*   **Note:** 
    *   **소셜 로그인 사용자는 이용 불가.**
    *   하루 5회 제한, 15초 대기 시간 있음.
    *   이메일과 생년월일이 일치해야 발송됨.

### 비밀번호 찾기 - 인증번호 확인
*   **URL:** `/accounts/find/password/verify/`
*   **Method:** `POST`
*   **Permission:** AllowAny
*   **Body:** `{"email": "user@example.com", "code": "123456"}`
*   **Note:** 인증 성공 시 비밀번호 변경 권한(`can_password_edit`) 획득.

### 비밀번호 재설정
*   **URL:** `/accounts/find/password/reset/`
*   **Method:** `POST`
*   **Permission:** AllowAny
*   **Body:** `{"email": "user@example.com", "birth_date": "1990-01-01", "new_password": "...", "new_password_confirm": "..."}`
*   **Note:** **소셜 로그인 사용자 불가.** 생년월일 재확인 필수. 인증(`verify`) 선행 필수.

---

## 2. Hospitals (병원 및 구급대원)

### 구급대원 인증
*   **URL:** `/paramedic/apply/` (또는 `/accounts/paramedic/apply/`)
*   **Method:** `POST`
*   **Permission:** IsAuthenticated
*   **Body:** `{"LOGINOPTION": "0", "JUMIN": "...", "DSNM": "...", "PHONENUM": "...", "TELECOMGUBUN": "1"}`

### 사용자 위치 전송
*   **URL:** `/hospitals/user/location/`
*   **Method:** `POST`
*   **Permission:** IsAuthenticated
*   **Body:**
    ```json
    {
        "latitude": 37.5665,
        "longitude": 126.9780,
        "locationstext": "서울시청",
        "radius": 10
    }
    ```

### 증상 기반 병원 추천
*   **URL:** `/hospitals/general/symptom/`
*   **Method:** `POST`
*   **Permission:** IsAuthenticated
*   **Body:** `{"symptom": ["두통", "복통"], "latitude": 37.5..., "longitude": 126.9...}`
*   **Response:**
    ```json
    {
        "result": true,
        "sorted_by_distance": [...],
        "sorted_by_score": [...],
        "openai_recommendation": {"hvec": 30, ...}
    }
    ```

### 병원 후기
*   **목록/작성:** `/hospitals/reviews/<str:hpid>/` (GET, POST)
*   **상세/수정/삭제:** `/hospitals/reviews/detail/<int:review_id>/` (PUT, DELETE)
*   **Note:** 작성 후 3일 이내만 수정 가능.

### 댓글
*   **작성:** `/hospitals/comments/<int:review_id>/` (POST)
*   **상세/수정/삭제:** `/hospitals/comments/detail/<int:comment_id>/` (PUT, DELETE)
*   **Note:** 작성 후 3일 이내만 수정 가능.
