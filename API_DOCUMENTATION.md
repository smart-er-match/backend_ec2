# Smart ER-Match API Documentation

## Base URL
`https://www.smart-er-match.shop/` (또는 로컬 `http://localhost:8000/`)

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
*   **Method:** `PUT`
*   **Permission:** IsAuthenticated
*   **Body:** `{"name": "...", "phone_number": "...", "gender": "..."}` (일부만 보내도 됨)

### 비밀번호 변경 (로그인 상태)
*   **URL:** `/accounts/password/change/`
*   **Method:** `POST`
*   **Permission:** IsAuthenticated
*   **Body:** `{"old_password": "...", "new_password": "...", "new_password_confirm": "..."}`

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
*   **Body:** `{"email": "user@example.com"}`
*   **Note:** 하루 5회 제한, 15초 대기 시간 있음.

### 비밀번호 찾기 - 인증번호 확인
*   **URL:** `/accounts/find/password/verify/`
*   **Method:** `POST`
*   **Permission:** AllowAny
*   **Body:** `{"email": "user@example.com", "code": "123456"}`
*   **Note:** 인증 성공 시 비밀번호 변경 권한 획득.

### 비밀번호 재설정 (인증 후)
*   **URL:** `/accounts/find/password/reset/`
*   **Method:** `POST`
*   **Permission:** AllowAny
*   **Body:** `{"email": "user@example.com", "new_password": "...", "new_password_confirm": "..."}`

---

## 2. Hospitals (병원 및 구급대원)

### 구급대원 인증 (면허 인증)
*   **URL:** `/paramedic/apply/` (또는 `/accounts/paramedic/apply/`)
*   **Method:** `POST`
*   **Permission:** IsAuthenticated
*   **Body:**
    ```json
    {
        "LOGINOPTION": "0", 
        "JUMIN": "9001011", 
        "DSNM": "홍길동", 
        "PHONENUM": "01012345678",
        "TELECOMGUBUN": "1" (통신사 인증 시 필수)
    }
    ```

### 사용자 위치 전송
*   **URL:** `/hospitals/user/location/` (또는 `/hospitals/general/list/` - *urls.py 확인 필요*)
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
*   **Body:**
    ```json
    {
        "symptom": ["두통", "고열"],
        "latitude": 37.5665,
        "longitude": 126.9780
    }
    ```
*   **Response:** 거리순/점수순 병원 목록 반환.

### 병원 후기 작성/조회
*   **URL:** `/hospitals/reviews/<str:hpid>/`
*   **Method:**
    *   `GET`: 해당 병원의 후기 목록 조회
    *   `POST`: 후기 작성 (`{"content": "...", "rating": 5}`)
*   **Permission:** IsAuthenticatedOrReadOnly

### 후기 상세 (수정/삭제)
*   **URL:** `/hospitals/reviews/detail/<int:review_id>/`
*   **Method:** `PUT` (수정), `DELETE` (삭제)
*   **Permission:** IsAuthenticated (본인만 가능, 수정은 3일 이내)

### 후기 댓글 작성
*   **URL:** `/hospitals/comments/<int:review_id>/`
*   **Method:** `POST` (`{"content": "..."}`)
*   **Permission:** IsAuthenticated

### 댓글 상세 (수정/삭제)
*   **URL:** `/hospitals/comments/detail/<int:comment_id>/`
*   **Method:** `PUT`, `DELETE`
*   **Permission:** IsAuthenticated (본인만 가능, 수정은 3일 이내)
