# 프로젝트 진행 상황 요약 (2025-12-01)

## 1. 프로젝트 개요
- **이름:** Smart ER-Match (Finalproject)
- **환경:** Django REST Framework, Docker, Nginx, Gunicorn, PostgreSQL
- **배포:** AWS EC2 (Ubuntu Linux)

## 2. 주요 변경 사항 (Accounts 앱)
### 인증 로직 변경
- **파라메트릭 인증:** 기존 로컬 로직에서 **AWS Lambda API 연동**으로 변경.
- **엔드포인트:** `POST /paramedic/apply/` (프로젝트 루트 URL에서 직접 연결)
- **로직:**
    1. 프론트엔드에서 `Authorization` 헤더(Bearer Token)와 함께 신원정보(`JUMIN` 등) 전송.
    2. 백엔드(`ParamedicAuthView`)에서 AWS Lambda 호출.
    3. 인증 성공 시 `User` 모델의 `role`=True 및 면허 정보(`license_kind`, `license_number` 등) 업데이트.
    4. `ParamedicAuthHistory`에 이력 저장.

## 3. 주요 변경 사항 (Hospitals 앱) - 전면 리팩토링
### 모델 구조 (`models.py`)
1. **`Category`**: 시/도 정보.
2. **`Hospital`**: 병원 기본 정보 (불변). `fetch_hospitals`로 갱신.
3. **`HospitalRealtimeStatus`**: 실시간 응급실 가용 병상 정보.
    - `fetch_all_data`로 5분마다 갱신.
    - `Hospital`과 1:1 관계 (`hpid`).
    - XML 필드 `hv*`, `hvs*` 전체 반영.
4. **`HospitalSevereInfo`**: **삭제됨** (데이터 Null 문제로 제거).
5. **`UserLocationLog`**: 사용자 위치 전송 기록.
    - 필드: `user`, `user_email`, `sign_kind`, `latitude`, `longitude`, `location_text`.

### API 엔드포인트
- **사용자 위치 전송:** `POST /hospitals/general/list/`
    - Body: `{ useremail, sign_kind, latitude, longitude, locationstext }`
    - Header: `Authorization: Bearer <token>`

### 관리 커맨드 (`management/commands/`)
1. **`fetch_hospitals`**: 국립중앙의료원 API에서 병원 목록 전체 갱신.
2. **`fetch_all_data`**: 실시간 병상 정보(`getEmrrmRltmUsefulSckbdInfoInqire`) 갱신.
    - `HospitalSevereInfo` 관련 로직은 제거됨.

### 스케줄링 (`cron.py`)
- `django-cron` 사용.
- `FetchHospitalsCronJob`: 5분마다 `fetch_all_data` 실행.

## 4. 현재 서버 상태
- **Docker:** `django_app`, `backend_nginx`, `postgres_emergency` 컨테이너 정상 구동 중.
- **DB:** 초기화 후 최신 데이터 적재 완료 (병원 500+개, 실시간 정보 400+개).
- **이슈 해결:**
    - `views.py` Import Error 해결.
    - `HospitalSevereInfo` Null 데이터 문제로 모델 삭제 처리.
    - 프론트엔드 401 Unauthorized 문제 (DB 초기화로 인한 토큰 불일치) -> 재가입 안내.

## 5. 다음 작업 가이드
새로운 세션 시작 시, 이 파일을 읽고 다음 작업을 이어서 진행하면 됩니다.
- 프론트엔드 연동 테스트 (`/paramedic/apply/`, `/hospitals/general/list/`).
- 추가 API 개발 필요 시 `hospitals/views.py` 확장.
