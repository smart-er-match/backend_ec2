# 🚑 Smart ER Match (백엔드 API 및 AI 시스템)

> **"응급실 뺑뺑이" 문제를 해결하기 위한 지능형 실시간 응급 의료 매칭 시스템**
> 사용자의 구어체 증상을 AI가 분석하고, 실시간 병상 데이터와 위치 정보를 결합해 최적의 병원을 추천합니다.

---

## 🛠 기술 스택 (Tech Stack)

### **Backend & Database**
- **Language:** Python 3.10+
- **Framework:** Django, Django REST Framework (DRF)
- **Database:** PostgreSQL (PostGIS 확장 포함) - 위치 기반 쿼리 최적화
- **Cache:** Redis - 챗봇 세션 및 실시간 데이터 캐싱

### **AI & Inference**
- **Model:** Qwen 2.5 0.5B (지식 증류 및 파인튜닝)
- **Server:** llama.cpp (GBNF Grammar 적용으로 출력 구조 강제)
- **Engine:** InferenceEngine (GPU/CPU 하이브리드 추론 지원)

### **Infrastructure & DevOps**
- **Cloud:** AWS (EC2 G4dn.xlarge, S3, IAM)
- **Container:** Docker, Docker-compose
- **Automation:** Boto3 기반 GPU 스팟 인스턴스 자동 스케일링 로직
- **Web Server:** Nginx (Gunicorn 연동)

---

## 📖 개요 (Overview)
최근 사회적으로 심각한 "응급실 뺑뺑이" 문제는 환자의 상태에 적합한 병원 정보를 실시간으로 파악하지 못해 발생합니다. 본 시스템은 백엔드에서 **전국 응급실 실시간 데이터를 5분 주기로 동기화**하고, **경량화된 LLM(Large Language Model)**을 통해 환자의 증상에 가장 적합한 진료 시설을 갖춘 병원을 우선적으로 매칭하여 골든타임을 확보하는 것을 목표로 합니다.

---

## ❓ 문제 정의 (Problem Definition)

### 1. 응급 의료 정보의 파편화
- 보건복지부, 국립중앙의료원 등에서 제공하는 데이터가 방대하지만, 일반 사용자가 즉각적으로 이해하고 본인의 증상과 매칭하기에는 진입장벽이 높습니다.

### 2. 증상과 진료과목의 미스매칭
- 환자는 "배가 아프다"고 말하지만, 실제 필요한 시설은 "조영제 CT"나 "소아 응급실"일 수 있습니다. 단순 거리순 검색은 이러한 전문 진료 가능 여부를 반영하지 못합니다.

### 3. 실시간 가용성 확보의 어려움
- 병상 정보는 분 단위로 변합니다. 백엔드에서 실시간으로 데이터를 수집하고 이를 가중치 알고리즘에 즉시 반영하는 고성능 처리 엔진이 필요합니다.

---

## 🌟 핵심 기능 (Core Backend Features)

### 1. 지능형 증상 분석 (AI Chatbot)
- **SFT(Supervised Fine-Tuning):** 응급 상황 구어체 데이터로 학습된 Qwen 0.5B 모델을 사용합니다.
- **GBNF Grammar:** AI가 딴소리를 하지 않고 반드시 지정된 JSON 구조(`age`, `gender`, `symptoms`)로만 답변하도록 문법을 강제하여 파싱 에러를 0%로 줄였습니다.
- **세션 관리:** Redis와 DB를 연동하여 사용자의 대화 맥락을 유지하고, 5분 미활동 시 자동 종료하는 타임아웃 로직을 구현했습니다.

### 2. 실시간 병상 데이터 동기화 (Data Sync)
- **Cron Job:** 국립중앙의료원(NMC) Open API를 연동하여 5분마다 전국 응급실의 가용 병상(`hvec`), 중환자실 상태, 주요 장비(CT, MRI 등) 가동 여부를 업데이트합니다.
- **PostGIS:** 사용자의 위경도 좌표를 기반으로 반경 50km 내의 병원을 공간 인덱싱을 통해 0.1초 내에 검색합니다.

### 3. 스마트 스코어링 추천 (Matching Algorithm)
- 단순히 가까운 순서가 아닌, **[거리 + 가용 병상 수 + AI 추천 시설 가중치]**를 합산한 점수로 순위를 산정합니다.
- 예: "심한 두통" 호소 시 AI가 `hvctayn`(CT 가용 여부)에 높은 가중치를 부여하여 해당 시설이 있는 병원을 상단에 배치합니다.

### 4. GPU 오토 스케일링 (AWS Infra Automation)
- 비용 절감을 위해 **AWS Spot Instance**를 활용합니다. 
- `scale_gpu.py` 스크립트를 통해 GPU 서버의 생존 여부를 감시하고, 회수 시 즉시 재생성하거나 로컬 CPU로 Failover하는 고가용성 아키텍처를 구축했습니다.

--- 

## 🌐 외부 API 연동 (External API Integration)

백엔드 시스템은 최신의 의료 데이터와 사용자 편의성을 위해 다양한 외부 서비스와 긴밀하게 연동되어 있습니다.

### 1. 국립중앙의료원 (NMC) 응급의료 API
- **기능:** 전국 응급실 실시간 가용 병상(`hvec`), 중환자실 상태, 특수 병상 정보를 5분 주기로 수집.
- **활용:** `hospitals/cron.py`를 통해 DB를 최신화하고 추천 알고리즘의 기초 데이터로 활용.

### 2. OpenAI API (GPT-4o)
- **기능:** `GeneralSymptomView`에서 사용자의 복합적인 증상을 분석.
- **활용:** 단순 키워드 매핑을 넘어, 증상에 필요한 TOP 10 의료 자원 필드를 선정하고 가중치(30~12점)를 부여하여 맞춤형 추천 점수 산출.

### 3. 소셜 로그인 OAuth 2.0 (Kakao, Naver, Google)
- **기능:** 긴급 상황에서 복잡한 회원가입 없이 즉시 서비스를 이용할 수 있도록 구현.
- **활용:** `accounts/views.py`에서 각 플랫폼의 액세스 토큰을 검증하고 자체 JWT(JSON Web Token)를 발행하여 보안 및 편의성 강화.

### 4. HuggingFace
- **기능:** Qwen 2.5 0.5B 모델 및 어댑터 설정 로드.
- **활용:** 로컬 및 GPU 추론 엔진의 기반 모델 관리.

---

## 🧮 4. 추천 알고리즘 (기술적 설명)백엔드와 AI 시스템의 긴밀한 연동을 통해, 사용자가 증상을 말하는 것만으로도 **"지금 즉시 진료 가능한 가장 최적의 응급실"**을 찾아줍니다. 이는 의료진에게는 불필요한 전원 요청을 줄여주고, 환자에게는 생명의 골든타임을 지켜주는 혁신적인 솔루션이 될 것입니다.

---

## 📂 산출물 문서
- **기획 및 설계:** `/CODEX` 폴더 참조
- **API 명세:** `API_DOCUMENTATION.md` 참조
- **데이터 모델(ERD):** `hospitals/models.py` 및 `accounts/models.py` 참조
